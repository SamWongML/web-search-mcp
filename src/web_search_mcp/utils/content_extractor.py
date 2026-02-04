"""
Content extraction utilities for producing clean, LLM-optimized markdown.

This module provides Firecrawl-quality content extraction by combining:
1. HTML preprocessing - Remove unwanted elements before extraction (Firecrawl approach)
2. Trafilatura - Best-in-class main content extraction and boilerplate removal
3. Readability - Mozilla's algorithm for extracting readable content
4. Post-processing - Fix formatting issues and normalize output

The extraction pipeline:
1. Preprocess HTML to remove nav, ads, modals, etc. (like Firecrawl)
2. Try trafilatura first (best for articles, docs, blogs)
3. Fall back to readability + markdownify (better for some SPAs)
4. Apply post-processing to fix common issues
"""

import contextlib
import re
from typing import Iterable, Literal
from urllib.parse import urljoin, urlparse

import structlog

logger = structlog.get_logger(__name__)

# Firecrawl's excludeNonMainTags - elements to remove when onlyMainContent=true
# Source: https://github.com/mendableai/firecrawl/blob/main/apps/api/src/scraper/scrapeURL/lib/removeUnwantedElements.ts
EXCLUDE_NON_MAIN_TAGS = [
    # Semantic elements
    "header",
    "footer",
    "nav",
    "aside",
    # Header/footer classes
    ".header",
    ".top",
    ".navbar",
    "#header",
    ".footer",
    ".bottom",
    "#footer",
    # Sidebar
    ".sidebar",
    ".side",
    ".aside",
    "#sidebar",
    # Modals/popups
    ".modal",
    ".popup",
    "#modal",
    ".overlay",
    # Ads
    ".ad",
    ".ads",
    ".advert",
    "#ad",
    ".advertisement",
    ".sponsored",
    # Language selector
    ".lang-selector",
    ".language",
    "#language-selector",
    # Social
    ".social",
    ".social-media",
    ".social-links",
    "#social",
    ".social-share",
    ".share-buttons",
    # Navigation
    ".menu",
    ".navigation",
    "#nav",
    ".breadcrumbs",
    "#breadcrumbs",
    ".breadcrumb",
    ".pagination",
    # Share/widgets
    ".share",
    "#share",
    ".widget",
    "#widget",
    # Cookie notices
    ".cookie",
    "#cookie",
    ".cookie-banner",
    ".cookie-consent",
    ".gdpr",
    # Comments
    ".comments",
    "#comments",
    ".comment-section",
    # Related content
    ".related",
    ".related-posts",
    ".recommended",
    ".suggestions",
    # Newsletter/signup
    ".newsletter",
    ".signup",
    ".subscribe",
    # Search
    ".search",
    ".search-form",
    "#search",
]

# Elements to force include even if inside excluded areas
FORCE_INCLUDE_TAGS = [
    "#main",
    "main",
    "article",
    "[role='main']",
    ".main-content",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".content",
]

# UI text patterns that should be removed
UI_TEXT_PATTERNS = [
    r"^Skip to (?:main )?content\.?$",
    r"^(?:Close|Clear|Cancel|Submit)$",
    r"^Search\.{0,3}$",
    r"^Menu$",
    r"^Toggle (?:navigation|menu|sidebar)$",
    r"^(?:Copy|Share|Print|Save)(?:\s+(?:link|page|article))?$",
    r"^(?:Previous|Next)(?:\s+(?:page|article|post))?$",
    r"^Back to top$",
    r"^Loading\.{0,3}$",
    r"^Show (?:more|less)$",
    r"^Read more$",
    r"^See (?:more|all)$",
    r"^Cookie (?:policy|consent|settings)$",
    r"^Accept (?:all )?cookies?$",
    r"^⌘\s*K$",  # Keyboard shortcut hints
    r"^Ctrl\s*\+\s*\w$",
    r"^Sign (?:in|up|out)$",
    r"^Log (?:in|out)$",
    r"^Subscribe$",
    r"^Follow us$",
]


def extract_main_content(
    html: str,
    url: str | None = None,
    include_links: bool = True,
    include_images: bool = False,
    include_tables: bool = True,
    output_format: Literal["markdown", "text", "html"] = "markdown",
    favor_precision: bool = True,
    only_main_content: bool = True,
    include_selectors: Iterable[str] | None = None,
    exclude_selectors: Iterable[str] | None = None,
) -> str:
    """
    Extract main content from HTML and convert to clean markdown.

    This function produces Firecrawl-quality output by:
    - Preprocessing HTML to remove nav, ads, modals (like Firecrawl)
    - Removing navigation, headers, footers, sidebars
    - Extracting only the main article/content area
    - Converting to clean, well-formatted markdown
    - Preserving semantic structure (headings, lists, code blocks)
    - Optionally including links and images

    Args:
        html: Raw HTML content
        url: Base URL for resolving relative links
        include_links: Whether to preserve hyperlinks
        include_images: Whether to include image references
        include_tables: Whether to include tables
        output_format: Output format ("markdown", "text", or "html")
        favor_precision: If True, be more aggressive about removing noise
        only_main_content: If True, remove non-main content elements (Firecrawl-style)
        include_selectors: CSS selectors to force-include
        exclude_selectors: CSS selectors to remove

    Returns:
        Clean markdown content optimized for LLM consumption
    """
    if not html:
        return ""

    # Step 1: Preprocess HTML to remove unwanted elements (like Firecrawl)
    if only_main_content or include_selectors or exclude_selectors:
        html = _preprocess_html(
            html,
            url,
            include_selectors=include_selectors,
            exclude_selectors=exclude_selectors,
        )

    # Step 2: Try trafilatura first (best quality for most sites)
    if output_format == "html":
        markdown = _extract_html_with_readability(html)
    else:
        markdown = _extract_with_trafilatura(
            html,
            url=url,
            include_links=include_links,
            include_images=include_images,
            include_tables=include_tables,
            output_format=output_format,
            favor_precision=favor_precision,
        )

    # Step 3: Fall back to readability if trafilatura returns empty or very short content
    if output_format != "html" and (not markdown or len(markdown.strip()) < 100):
        logger.debug("trafilatura_fallback", reason="short_content", length=len(markdown or ""))
        markdown = _extract_with_readability(
            html,
            url=url,
            include_links=include_links,
        )

    # Step 4: Apply post-processing
    if output_format != "html":
        markdown = _postprocess_markdown(markdown, base_url=url)

    return markdown


def _preprocess_html(
    html: str,
    url: str | None = None,
    include_selectors: Iterable[str] | None = None,
    exclude_selectors: Iterable[str] | None = None,
) -> str:
    """
    Preprocess HTML by removing unwanted elements before content extraction.

    This mimics Firecrawl's approach of using CSS selectors to remove
    navigation, ads, modals, etc. before the main extraction.

    Args:
        html: Raw HTML content
        url: Base URL for resolving relative links

    Returns:
        Cleaned HTML with unwanted elements removed
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4_not_installed", msg="pip install beautifulsoup4")
        return html

    try:
        soup = BeautifulSoup(html, "html.parser")

        include_selectors_list = _normalize_selectors(include_selectors)
        exclude_selectors_list = _normalize_selectors(exclude_selectors)
        include_ids = _collect_selector_ids(soup, include_selectors_list)

        # Remove script, style, noscript, meta, head (like Firecrawl)
        for tag in soup.find_all(["script", "style", "noscript", "meta"]):
            tag.decompose()

        # Remove non-main content elements
        for selector in EXCLUDE_NON_MAIN_TAGS:
            try:
                # Handle different selector types
                if selector.startswith("."):
                    # Class selector
                    for el in soup.find_all(class_=selector[1:]):
                        # Check if element contains force-include content
                        if not _contains_main_content(el, include_ids):
                            el.decompose()
                elif selector.startswith("#"):
                    # ID selector
                    el = soup.find(id=selector[1:])
                    if el and not _contains_main_content(el, include_ids):
                        el.decompose()
                elif selector.startswith("["):
                    # Attribute selector - skip for now
                    pass
                else:
                    # Tag selector
                    for el in soup.find_all(selector):
                        if not _contains_main_content(el, include_ids):
                            el.decompose()
            except Exception as e:
                logger.debug("selector_error", selector=selector, error=str(e))

        # Apply custom exclude selectors
        for selector in exclude_selectors_list:
            try:
                for el in soup.select(selector):
                    if not _contains_main_content(el, include_ids):
                        el.decompose()
            except Exception as e:
                logger.debug("custom_selector_error", selector=selector, error=str(e))

        # Make image URLs absolute (like Firecrawl)
        if url:
            for img in soup.find_all("img", src=True):
                with contextlib.suppress(Exception):
                    img["src"] = urljoin(url, img["src"])

            for a in soup.find_all("a", href=True):
                with contextlib.suppress(Exception):
                    a["href"] = urljoin(url, a["href"])

        return str(soup)

    except Exception as e:
        logger.warning("html_preprocess_error", error=str(e))
        return html


def _contains_main_content(element, include_ids: set[int]) -> bool:
    """Check if an element contains main content that should be preserved."""
    try:
        if _contains_included_element(element, include_ids):
            return True

        # Check if element has any of the force-include classes/ids
        element_classes = element.get("class", [])
        if isinstance(element_classes, str):
            element_classes = [element_classes]

        element_id = element.get("id", "")

        for tag in FORCE_INCLUDE_TAGS:
            if tag.startswith("."):
                if tag[1:] in element_classes:
                    return True
            elif tag.startswith("#"):
                if tag[1:] == element_id:
                    return True
            elif tag.startswith("["):
                # Skip attribute selectors
                pass
            else:
                # Tag name - check if element or any child is this tag
                if element.name == tag or element.find(tag):
                    return True

        # Also check children
        for child in element.find_all(True):
            child_classes = child.get("class", [])
            if isinstance(child_classes, str):
                child_classes = [child_classes]
            child_id = child.get("id", "")

            for tag in FORCE_INCLUDE_TAGS:
                if tag.startswith(".") and tag[1:] in child_classes:
                    return True
                if tag.startswith("#") and tag[1:] == child_id:
                    return True

        return False
    except Exception:
        return False


def _normalize_selectors(selectors: Iterable[str] | None) -> list[str]:
    if not selectors:
        return []
    return [s.strip() for s in selectors if s and s.strip()]


def _collect_selector_ids(soup, selectors: list[str]) -> set[int]:
    include_ids: set[int] = set()
    for selector in selectors:
        try:
            for el in soup.select(selector):
                include_ids.add(id(el))
        except Exception:
            continue
    return include_ids


def _contains_included_element(element, include_ids: set[int]) -> bool:
    if not include_ids:
        return False
    if id(element) in include_ids:
        return True
    for child in element.descendants:
        if id(child) in include_ids:
            return True
    return False


def _extract_with_trafilatura(
    html: str,
    url: str | None = None,
    include_links: bool = True,
    include_images: bool = False,
    include_tables: bool = True,
    output_format: Literal["markdown", "text"] = "markdown",
    favor_precision: bool = True,
) -> str:
    """Extract content using trafilatura."""
    try:
        import trafilatura

        result = trafilatura.extract(
            html,
            url=url,
            output_format=output_format,
            include_links=include_links,
            include_images=include_images,
            include_tables=include_tables,
            include_formatting=True,
            favor_precision=favor_precision,
            favor_recall=not favor_precision,
        )

        return result or ""

    except ImportError:
        logger.warning("trafilatura_not_installed")
        return ""
    except Exception as e:
        logger.warning("trafilatura_error", error=str(e))
        return ""


def _extract_with_readability(
    html: str,
    url: str | None = None,  # noqa: ARG001
    include_links: bool = True,
) -> str:
    """Extract content using readability + markdownify."""
    try:
        from markdownify import markdownify as md
        from readability import Document

        doc = Document(html)
        clean_html = doc.summary()
        title = doc.title()

        # Convert to markdown
        markdown = md(
            clean_html,
            heading_style="ATX",
            bullets="-",
            code_language="",
            strip=["script", "style", "nav", "footer", "header"],
        )

        # Add title as H1 if available and not already in content
        if title and not markdown.strip().startswith("#"):
            markdown = f"# {title}\n\n{markdown}"

        # Remove links if not requested
        if not include_links:
            markdown = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)

        return markdown

    except ImportError:
        logger.warning("readability_not_installed")
        return ""
    except Exception as e:
        logger.warning("readability_error", error=str(e))
        return ""


def _extract_html_with_readability(html: str) -> str:
    """Extract main content HTML using readability."""
    try:
        from readability import Document

        doc = Document(html)
        return doc.summary() or ""
    except ImportError:
        logger.warning("readability_not_installed")
        return html
    except Exception as e:
        logger.warning("readability_html_error", error=str(e))
        return html


def _postprocess_markdown(markdown: str, base_url: str | None = None) -> str:
    """
    Post-process markdown to fix common issues and normalize output.

    Fixes:
    - Removes duplicate content sections
    - Fixes malformed links (angle brackets, missing spaces)
    - Normalizes whitespace
    - Removes UI text artifacts
    - Converts relative URLs to absolute
    - Fixes code block formatting
    - Fixes bold text running into content
    """
    if not markdown:
        return ""

    text = markdown

    # Fix malformed bold markers with internal spaces (single line only)
    # e.g., "** text:**" -> "**text:**" and "** text **:" -> "**text**:"
    # Use [^\n*] to avoid matching across lines/bold sections
    text = re.sub(r"\*\* ([^\n*]+?) \*\*", r"**\1**", text)  # Both spaces
    text = re.sub(r"\*\* ([^\n*]+?)\*\*", r"**\1**", text)  # Leading space only
    text = re.sub(r"\*\*([^\n*]+?) \*\*", r"**\1**", text)  # Trailing space only

    # Fix links with angle brackets: [text](<url>) -> [text](url)
    text = re.sub(r"\]\(<([^>]+)>\)", r"](\1)", text)

    # Fix missing space before links: text[link] -> text [link]
    text = re.sub(r"(\w)\[([^\]]+)\]\(", r"\1 [\2](", text)

    # Fix missing space after bold/italic before link
    text = re.sub(r"\*\*\[", r"** [", text)
    text = re.sub(r"\*\[", r"* [", text)

    # Fix missing space between sentences and links
    text = re.sub(r"\.([A-Z])", r". \1", text)

    # Fix bold text running into next content (trafilatura issue)
    # e.g., "**Local threads**run" -> "**Local threads** run"
    # Limit to 50 chars to avoid matching across multiple bold sections
    text = re.sub(r"\*\*([^\n*]{1,50}?)\*\*([a-zA-Z])", r"**\1** \2", text)

    # Fix content running into bold text (opening bold)
    # e.g., "model's**context**" -> "model's **context**"
    # Limit to 50 chars to avoid matching across multiple bold sections
    text = re.sub(r"([a-zA-Z0-9])\*\*([^\n\s*][^\n*]{0,50}?)\*\*", r"\1 **\2**", text)

    # Fix sentences running together after links/bold
    # e.g., "...in a [sandbox](url).**Cloud" -> "...in a [sandbox](url).\n\n**Cloud"
    text = re.sub(r"([).])\*\*([A-Z])", r"\1\n\n**\2", text)

    # Convert relative URLs to absolute if base_url provided
    if base_url:
        text = _make_urls_absolute(text, base_url)

    # Remove UI text patterns
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that match UI text patterns
        is_ui_text = False
        for pattern in UI_TEXT_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                is_ui_text = True
                break
        if not is_ui_text:
            cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # Remove duplicate sections (common with navigation rendered twice)
    text = _remove_duplicate_sections(text)

    # Fix code blocks: ensure proper fencing
    text = _fix_code_blocks(text)

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = text.strip()

    return text


def _make_urls_absolute(text: str, base_url: str) -> str:
    """Convert relative URLs in markdown links to absolute URLs."""
    parsed_base = urlparse(base_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    def replace_url(match: re.Match) -> str:
        link_text = match.group(1)
        url = match.group(2)

        # Skip if already absolute
        if url.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            return match.group(0)

        # Handle protocol-relative URLs
        if url.startswith("//"):
            return f"[{link_text}]({parsed_base.scheme}:{url})"

        # Handle root-relative URLs
        if url.startswith("/"):
            return f"[{link_text}]({base_origin}{url})"

        # Handle relative URLs
        return f"[{link_text}]({urljoin(base_url, url)})"

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_url, text)


def _remove_duplicate_sections(text: str) -> str:
    """Remove duplicate content sections."""
    # Split into sections by headings
    sections = re.split(r"(^#{1,6}\s+.+$)", text, flags=re.MULTILINE)

    seen_sections: dict[str, int] = {}
    unique_sections = []

    i = 0
    while i < len(sections):
        section = sections[i]

        # If this is a heading
        if re.match(r"^#{1,6}\s+", section):
            heading = section.strip()
            content = sections[i + 1] if i + 1 < len(sections) else ""

            # Create a key from heading + first 100 chars of content
            key = f"{heading}:{content[:100].strip()}"

            if key not in seen_sections:
                seen_sections[key] = i
                unique_sections.append(section)
                if i + 1 < len(sections):
                    unique_sections.append(sections[i + 1])
                i += 2
            else:
                # Skip duplicate heading and its content
                i += 2
        else:
            unique_sections.append(section)
            i += 1

    return "".join(unique_sections)


def _fix_code_blocks(text: str) -> str:
    """Fix code block formatting issues."""
    # Convert inline code that looks like it should be a block
    # (multiple lines or contains newlines)
    lines = text.split("\n")
    result = []
    in_indented_block = False
    indented_lines: list[str] = []

    for line in lines:
        # Check for consistently indented lines (4+ spaces) that might be code
        if re.match(r"^    .+", line) and not in_indented_block:
            in_indented_block = True
            indented_lines = [line[4:]]  # Remove 4-space indent
        elif in_indented_block:
            if re.match(r"^    .+", line):
                indented_lines.append(line[4:])
            elif line.strip() == "":
                # Empty line might be part of code block
                indented_lines.append("")
            else:
                # End of indented block
                if len(indented_lines) > 1:
                    # Convert to fenced code block
                    result.append("```")
                    result.extend(indented_lines)
                    result.append("```")
                else:
                    # Single line, keep as indented
                    result.extend(["    " + line for line in indented_lines])
                result.append(line)
                in_indented_block = False
                indented_lines = []
        else:
            result.append(line)

    # Handle remaining indented block
    if indented_lines:
        if len(indented_lines) > 1:
            result.append("```")
            result.extend(indented_lines)
            result.append("```")
        else:
            result.extend(["    " + line for line in indented_lines])

    return "\n".join(result)


def extract_metadata(html: str, url: str | None = None) -> dict[str, str | None]:
    """
    Extract metadata from HTML.

    Args:
        html: Raw HTML content
        url: Source URL

    Returns:
        Dictionary with title, description, author, language, etc.
    """
    try:
        import trafilatura

        metadata = trafilatura.extract_metadata(html, url)
        if metadata:
            return {
                "title": metadata.title,
                "description": metadata.description,
                "author": metadata.author,
                "date": metadata.date,
                "sitename": metadata.sitename,
                "language": getattr(metadata, "language", None),
            }
    except Exception as e:
        logger.debug("metadata_extraction_error", error=str(e))

    # Fallback: extract basic metadata with regex
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    desc_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    return {
        "title": title_match.group(1).strip() if title_match else None,
        "description": desc_match.group(1).strip() if desc_match else None,
        "author": None,
        "date": None,
        "sitename": None,
        "language": None,
    }
