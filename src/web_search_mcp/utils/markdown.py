"""Markdown processing utilities."""

import re
from typing import Any


def clean_markdown(text: str) -> str:
    """
    Clean and normalize markdown text.

    Args:
        text: Raw markdown text

    Returns:
        Cleaned markdown text
    """
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove trailing whitespace from lines
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def truncate_markdown(text: str, max_chars: int = 50000) -> str:
    """
    Truncate markdown to a maximum character count while preserving structure.

    Args:
        text: Markdown text
        max_chars: Maximum characters

    Returns:
        Truncated markdown text
    """
    if len(text) <= max_chars:
        return text

    # Find a good break point (paragraph boundary)
    truncated = text[:max_chars]

    # Try to break at a paragraph boundary
    last_para = truncated.rfind("\n\n")
    if last_para > max_chars * 0.8:  # Only if we keep at least 80%
        truncated = truncated[:last_para]

    # Add truncation notice
    truncated += "\n\n[Content truncated...]"

    return truncated


def extract_title_from_markdown(markdown: str) -> str | None:
    """
    Extract the title (first H1) from markdown.

    Args:
        markdown: Markdown text

    Returns:
        Title or None
    """
    # Look for ATX-style heading
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Look for setext-style heading
    match = re.search(r"^(.+)\n=+\s*$", markdown, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return None


def extract_links_from_markdown(markdown: str) -> list[dict[str, str]]:
    """
    Extract all links from markdown.

    Args:
        markdown: Markdown text

    Returns:
        List of dicts with 'url' and 'text' keys
    """
    links: list[dict[str, str]] = []

    # Match [text](url) pattern
    pattern = r"\[([^\]]*)\]\(([^)]+)\)"
    matches = re.findall(pattern, markdown)

    for text, url in matches:
        links.append({"text": text.strip(), "url": url.strip()})

    return links


def html_to_markdown_simple(html: str) -> str:
    """
    Simple HTML to Markdown conversion for basic cases.

    This is a fallback when trafilatura/html2text aren't available.

    Args:
        html: HTML string

    Returns:
        Markdown string
    """
    if not html:
        return ""

    text = html

    # Remove script and style tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert headers
    for i in range(6, 0, -1):
        text = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            r"\n" + "#" * i + r" \1\n",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Convert paragraphs
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert line breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Convert bold
    text = re.sub(r"<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>", r"**\1**", text, flags=re.IGNORECASE)

    # Convert italic
    text = re.sub(r"<(?:i|em)[^>]*>(.*?)</(?:i|em)>", r"*\1*", text, flags=re.IGNORECASE)

    # Convert links
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.IGNORECASE)

    # Convert unordered lists
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = decode_html_entities(text)

    # Clean up whitespace
    text = clean_markdown(text)

    return text


def decode_html_entities(text: str) -> str:
    """
    Decode common HTML entities.

    Args:
        text: Text with HTML entities

    Returns:
        Decoded text
    """
    entities = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&apos;": "'",
        "&#39;": "'",
        "&mdash;": "—",
        "&ndash;": "–",
        "&hellip;": "…",
        "&copy;": "©",
        "&reg;": "®",
        "&trade;": "™",
    }

    for entity, char in entities.items():
        text = text.replace(entity, char)

    # Handle numeric entities
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)

    return text


def format_metadata_as_markdown(metadata: dict[str, Any]) -> str:
    """
    Format metadata dictionary as markdown front matter.

    Args:
        metadata: Metadata dictionary

    Returns:
        Markdown front matter string
    """
    if not metadata:
        return ""

    lines = ["---"]
    for key, value in metadata.items():
        if value is not None:
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: {value}")
    lines.append("---")

    return "\n".join(lines)
