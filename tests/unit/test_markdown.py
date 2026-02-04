"""Unit tests for markdown utilities."""

from web_search_mcp.utils.markdown import (
    clean_markdown,
    decode_html_entities,
    extract_links_from_markdown,
    extract_title_from_markdown,
    format_metadata_as_markdown,
    html_to_markdown_simple,
    markdown_to_text,
    truncate_markdown,
    truncate_text,
)


class TestCleanMarkdown:
    """Tests for clean_markdown function."""

    def test_removes_excessive_newlines(self):
        """Test that excessive newlines are reduced."""
        text = "Line 1\n\n\n\n\nLine 2"
        result = clean_markdown(text)
        assert result == "Line 1\n\nLine 2"

    def test_removes_trailing_whitespace(self):
        """Test that trailing whitespace is removed from lines."""
        text = "Line 1   \nLine 2\t\nLine 3"
        result = clean_markdown(text)
        assert result == "Line 1\nLine 2\nLine 3"

    def test_strips_leading_trailing_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        text = "   \n\nContent\n\n   "
        result = clean_markdown(text)
        assert result == "Content"

    def test_empty_string(self):
        """Test handling of empty string."""
        assert clean_markdown("") == ""
        assert clean_markdown(None) == ""  # type: ignore


class TestTruncateMarkdown:
    """Tests for truncate_markdown function."""

    def test_no_truncation_needed(self):
        """Test that short text is not truncated."""
        text = "Short text"
        result = truncate_markdown(text, max_chars=100)
        assert result == text

    def test_truncation_at_paragraph(self):
        """Test truncation at paragraph boundary."""
        text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        result = truncate_markdown(text, max_chars=25)
        assert "Paragraph 1" in result
        assert "[Content truncated...]" in result

    def test_truncation_prefers_paragraph_boundary(self):
        """Test paragraph boundary selection when near the limit."""
        text = "Para 1\n\n" + ("A" * 200)
        result = truncate_markdown(text, max_chars=80)
        assert result.endswith("[Content truncated...]")
        assert "Para 1" in result


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_no_truncation_needed(self):
        """Test that short text is not truncated."""
        text = "Short text"
        result = truncate_text(text, max_chars=100)
        assert result == text

    def test_truncation_with_notice(self):
        """Test that truncation notice is added."""
        text = "A" * 100
        result = truncate_text(text, max_chars=50)
        assert len(result) < 100
        assert "[Content truncated...]" in result

    def test_truncation_breaks_on_newline(self):
        """Test truncation prefers newline boundary."""
        text = ("A" * 90) + "\n" + ("B" * 50)
        result = truncate_text(text, max_chars=100)
        assert result.endswith("[Content truncated...]")
        assert "B" not in result.split("[Content truncated...]")[0]

    def test_truncation_with_notice(self):
        """Test that truncation notice is added."""
        text = "A" * 100
        result = truncate_markdown(text, max_chars=50)
        assert len(result) < 100
        assert "[Content truncated...]" in result


class TestExtractTitleFromMarkdown:
    """Tests for extract_title_from_markdown function."""

    def test_extract_atx_heading(self):
        """Test extracting ATX-style H1."""
        markdown = "# My Title\n\nContent here"
        title = extract_title_from_markdown(markdown)
        assert title == "My Title"

    def test_extract_setext_heading(self):
        """Test extracting setext-style H1."""
        markdown = "My Title\n========\n\nContent here"
        title = extract_title_from_markdown(markdown)
        assert title == "My Title"

    def test_no_title(self):
        """Test when no title is present."""
        markdown = "Just some content without a heading"
        title = extract_title_from_markdown(markdown)
        assert title is None


class TestMarkdownToText:
    """Tests for markdown_to_text function."""

    def test_strips_markdown(self):
        """Test basic markdown is stripped to text."""
        markdown = "# Title\n\nThis is **bold** and a [link](https://example.com)."
        text = markdown_to_text(markdown)
        assert "Title" in text
        assert "bold" in text
        assert "https://example.com" not in text

    def test_empty_markdown_returns_empty(self):
        assert markdown_to_text("") == ""

    def test_h2_not_extracted(self):
        """Test that H2 is not extracted as title."""
        markdown = "## Subtitle\n\nContent"
        title = extract_title_from_markdown(markdown)
        assert title is None


class TestExtractLinksFromMarkdown:
    """Tests for extract_links_from_markdown function."""

    def test_extract_links(self):
        """Test extracting markdown links."""
        markdown = "Check [Google](https://google.com) and [Example](https://example.com)"
        links = extract_links_from_markdown(markdown)

        assert len(links) == 2
        assert links[0]["text"] == "Google"
        assert links[0]["url"] == "https://google.com"
        assert links[1]["text"] == "Example"
        assert links[1]["url"] == "https://example.com"

    def test_empty_link_text(self):
        """Test links with empty text."""
        markdown = "[](https://example.com)"
        links = extract_links_from_markdown(markdown)

        assert len(links) == 1
        assert links[0]["text"] == ""
        assert links[0]["url"] == "https://example.com"

    def test_no_links(self):
        """Test when no links are present."""
        markdown = "Just plain text"
        links = extract_links_from_markdown(markdown)
        assert links == []


class TestHtmlToMarkdownSimple:
    """Tests for html_to_markdown_simple function."""

    def test_convert_headers(self):
        """Test converting HTML headers to markdown."""
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        result = html_to_markdown_simple(html)
        assert "# Title" in result
        assert "## Subtitle" in result

    def test_convert_paragraphs(self):
        """Test converting paragraphs."""
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        result = html_to_markdown_simple(html)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_convert_bold_italic(self):
        """Test converting bold and italic."""
        html = "<strong>bold</strong> and <em>italic</em>"
        result = html_to_markdown_simple(html)
        assert "**bold**" in result
        assert "*italic*" in result

    def test_convert_links(self):
        """Test converting links."""
        html = '<a href="https://example.com">Example</a>'
        result = html_to_markdown_simple(html)
        assert "[Example](https://example.com)" in result

    def test_convert_lists(self):
        """Test converting list items."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = html_to_markdown_simple(html)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_removes_script_style(self):
        """Test that script and style tags are removed."""
        html = "<script>alert('x')</script><style>.x{}</style><p>Content</p>"
        result = html_to_markdown_simple(html)
        assert "alert" not in result
        assert ".x" not in result
        assert "Content" in result

    def test_empty_html(self):
        """Test handling of empty HTML."""
        assert html_to_markdown_simple("") == ""


class TestDecodeHtmlEntities:
    """Tests for decode_html_entities function."""

    def test_common_entities(self):
        """Test decoding common HTML entities."""
        text = "&amp; &lt; &gt; &quot; &apos;"
        result = decode_html_entities(text)
        assert result == "& < > \" '"

    def test_nbsp_and_special(self):
        """Test decoding nbsp and special entities."""
        text = "Hello&nbsp;World &mdash; test &hellip;"
        result = decode_html_entities(text)
        assert result == "Hello World — test …"

    def test_numeric_entities(self):
        """Test decoding numeric entities."""
        text = "&#65; &#x42;"  # A and B
        result = decode_html_entities(text)
        assert result == "A B"


class TestFormatMetadataAsMarkdown:
    """Tests for format_metadata_as_markdown function."""

    def test_format_metadata(self):
        """Test formatting metadata as front matter."""
        metadata = {
            "title": "Test Title",
            "author": "John Doe",
            "date": "2024-01-01",
        }
        result = format_metadata_as_markdown(metadata)

        assert "---" in result
        assert "title: Test Title" in result
        assert "author: John Doe" in result

    def test_format_with_list(self):
        """Test formatting metadata with list values."""
        metadata = {
            "title": "Test",
            "tags": ["python", "testing"],
        }
        result = format_metadata_as_markdown(metadata)

        assert "tags:" in result
        assert "  - python" in result
        assert "  - testing" in result

    def test_empty_metadata(self):
        """Test with empty metadata."""
        result = format_metadata_as_markdown({})
        assert result == ""

    def test_none_values_excluded(self):
        """Test that None values are excluded."""
        metadata = {"title": "Test", "author": None}
        result = format_metadata_as_markdown(metadata)

        assert "title: Test" in result
        assert "author" not in result
