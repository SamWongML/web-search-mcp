"""Unit tests for content extraction utilities."""

import sys
from types import SimpleNamespace

import pytest

from web_search_mcp.utils import content_extractor as ce


def test_preprocess_html_removes_elements():
    html = """
    <html>
      <body>
        <nav>Nav</nav>
        <div class="promo">Ad</div>
        <main id="main"><p>Hello</p></main>
      </body>
    </html>
    """

    cleaned = ce._preprocess_html(
        html,
        url="https://example.com",
        include_selectors=["#main"],
        exclude_selectors=[".promo"],
    )

    assert "Nav" not in cleaned
    assert "promo" not in cleaned
    assert "Hello" in cleaned


def test_extract_main_content_fallback_to_readability(monkeypatch):
    monkeypatch.setattr(ce, "_extract_with_trafilatura", lambda *args, **kwargs: "")
    monkeypatch.setattr(ce, "_extract_with_readability", lambda *args, **kwargs: "Readability")

    result = ce.extract_main_content("<html><body><p>Test</p></body></html>")
    assert "Readability" in result


def test_extract_main_content_html(monkeypatch):
    monkeypatch.setattr(ce, "_extract_html_with_readability", lambda html: "<main>Hi</main>")

    result = ce.extract_main_content(
        "<html><body><main>Hi</main></body></html>",
        output_format="html",
        only_main_content=False,
    )
    assert "<main>Hi</main>" in result


def test_extract_main_content_empty_html():
    assert ce.extract_main_content("") == ""


def test_preprocess_html_import_error(monkeypatch):
    import builtins

    html = "<html><body><p>Test</p></body></html>"
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "bs4":
            raise ImportError("no bs4")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ce._preprocess_html(html) == html


def test_postprocess_markdown_removes_noise_and_fix_links():
    markdown = (
        "# Title\n\n"
        "Skip to content\n\n"
        "[Link](/path)\n\n"
        "# Title\n\n"
        "Same content\n\n"
        "# Title\n\n"
        "Same content\n\n"
        "    code\n"
    )

    processed = ce._postprocess_markdown(markdown, base_url="https://example.com")

    assert "Skip to content" not in processed
    assert "(https://example.com/path)" in processed
    assert "```" in processed


def test_remove_duplicate_sections():
    text = "# Title\n\nSame content\n\n# Title\n\nSame content\n\n"
    cleaned = ce._remove_duplicate_sections(text)
    assert cleaned.count("# Title") == 1


def test_make_urls_absolute_variants():
    text = "[Root](/root)\n[Rel](page)\n[Proto](//cdn.example.com)\n[Abs](https://example.com)"
    result = ce._make_urls_absolute(text, "https://example.com/base")
    assert "(https://example.com/root)" in result
    assert "(https://example.com/page)" in result
    assert "(https://cdn.example.com)" in result
    assert "(https://example.com)" in result


def test_extract_with_trafilatura_import_error(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "trafilatura":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ce._extract_with_trafilatura("<html></html>") == ""


def test_extract_with_trafilatura_exception(monkeypatch):
    class DummyTrafilatura:
        @staticmethod
        def extract(*args, **kwargs):  # noqa: ARG001
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "trafilatura", DummyTrafilatura)
    assert ce._extract_with_trafilatura("<html></html>") == ""


def test_extract_with_readability_import_error(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "readability":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ce._extract_with_readability("<html></html>") == ""


def test_extract_with_readability_exception(monkeypatch):
    class DummyDoc:
        def __init__(self, html):  # noqa: ARG002
            pass

        def summary(self):
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "readability", SimpleNamespace(Document=DummyDoc))
    monkeypatch.setitem(sys.modules, "markdownify", SimpleNamespace(markdownify=lambda *a, **k: ""))

    assert ce._extract_with_readability("<html></html>") == ""


def test_extract_html_with_readability_import_error(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "readability":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ce._extract_html_with_readability("<html></html>") == "<html></html>"


def test_contains_main_content_with_include_ids():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<div><main id='main'><p>Hi</p></main></div>", "html.parser")
    container = soup.find("div")
    main_el = soup.find("main")
    include_ids = {id(main_el)}

    assert ce._contains_main_content(container, include_ids) is True


def test_extract_metadata_fallback():
    class DummyTrafilatura:
        @staticmethod
        def extract_metadata(*args, **kwargs):  # noqa: ARG001
            raise RuntimeError("boom")

    html = "<title>My Title</title><meta name='description' content='Desc'>"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(sys.modules, "trafilatura", DummyTrafilatura)
    meta = ce.extract_metadata(html)
    monkeypatch.undo()
    assert meta["title"] == "My Title"
    assert meta["description"] == "Desc"


def test_extract_with_trafilatura_stub(monkeypatch):
    class DummyTrafilatura:
        @staticmethod
        def extract(*args, **kwargs):  # noqa: ARG001
            return "Content"

        @staticmethod
        def extract_metadata(*args, **kwargs):  # noqa: ARG001
            return None

    monkeypatch.setitem(sys.modules, "trafilatura", DummyTrafilatura)
    assert ce._extract_with_trafilatura("<html></html>") == "Content"


def test_extract_with_readability_stub(monkeypatch):
    class DummyDoc:
        def __init__(self, html):  # noqa: ARG002
            pass

        def summary(self):
            return "<p>Body</p>"

        def title(self):
            return "Doc Title"

    def dummy_markdownify(html, **kwargs):  # noqa: ARG001
        return "Body"

    monkeypatch.setitem(sys.modules, "readability", SimpleNamespace(Document=DummyDoc))
    monkeypatch.setitem(sys.modules, "markdownify", SimpleNamespace(markdownify=dummy_markdownify))

    result = ce._extract_with_readability("<html></html>", include_links=False)
    assert result.startswith("# Doc Title")
    assert "Body" in result


def test_extract_html_with_readability_stub(monkeypatch):
    class DummyDoc:
        def __init__(self, html):  # noqa: ARG002
            pass

        def summary(self):
            return "<main>Body</main>"

    monkeypatch.setitem(sys.modules, "readability", SimpleNamespace(Document=DummyDoc))
    result = ce._extract_html_with_readability("<html></html>")
    assert "<main>Body</main>" in result


def test_preprocess_html_selector_branches(monkeypatch):
    html = """
    <html>
      <body>
        <div class="header"><div id="keep" class="content" role="main">Keep</div></div>
        <div class="header">Drop</div>
        <div id="header">Drop header</div>
        <div data-test="x">Attr</div>
        <img src="/img.png">
        <a href="/a">Link</a>
      </body>
    </html>
    """

    monkeypatch.setattr(ce, "EXCLUDE_NON_MAIN_TAGS", [".header", "#header", "[data-test]"])

    cleaned = ce._preprocess_html(
        html,
        url="https://example.com/base",
        include_selectors=["#keep", "[invalid"],
        exclude_selectors=["[bad["],
    )

    assert "Keep" in cleaned
    assert "Drop" not in cleaned
    assert "Drop header" not in cleaned
    assert 'src="https://example.com/img.png"' in cleaned
    assert 'href="https://example.com/a"' in cleaned


def test_contains_included_element_empty_and_self():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<div id='x'><span>Hi</span></div>", "html.parser")
    div = soup.find("div")

    assert ce._contains_included_element(div, set()) is False
    assert ce._contains_included_element(div, {id(div)}) is True


def test_postprocess_markdown_empty():
    assert ce._postprocess_markdown("") == ""


def test_fix_code_blocks_variants():
    text = "Intro\n    code line 1\n    code line 2\nAfter\n    single\n"
    fixed = ce._fix_code_blocks(text)

    assert "```" in fixed
    assert "code line 1" in fixed
    assert "single" in fixed


def test_remove_duplicate_sections_no_heading():
    text = "plain text only"
    assert ce._remove_duplicate_sections(text) == text


def test_extract_metadata_trafilatura_success(monkeypatch):
    class DummyMeta:
        title = "Title"
        description = "Desc"
        author = "Author"
        date = "2024-01-01"
        sitename = "Site"
        language = "en"

    class DummyTrafilatura:
        @staticmethod
        def extract_metadata(*args, **kwargs):  # noqa: ARG001
            return DummyMeta()

    monkeypatch.setitem(sys.modules, "trafilatura", DummyTrafilatura)

    meta = ce.extract_metadata("<html></html>")
    assert meta["title"] == "Title"
    assert meta["description"] == "Desc"
    assert meta["sitename"] == "Site"
    assert meta["language"] == "en"


def test_extract_html_with_readability_exception(monkeypatch):
    class DummyDoc:
        def __init__(self, html):  # noqa: ARG002
            pass

        def summary(self):
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "readability", SimpleNamespace(Document=DummyDoc))

    html = "<html><body><main>Hi</main></body></html>"
    assert ce._extract_html_with_readability(html) == html
