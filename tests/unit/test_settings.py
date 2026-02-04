"""Unit tests for settings helpers."""

from web_search_mcp.config.settings import Settings


def test_settings_helpers():
    base = Settings()

    with_jina = base.model_copy(update={"jina_api_key": "token"})
    assert with_jina.is_jina_configured() is True

    list_formats = base.model_copy(update={"default_scrape_formats": ["markdown", "text"]})
    assert list_formats.get_default_scrape_formats() == ["markdown", "text"]

    str_formats = base.model_copy(update={"default_scrape_formats": "markdown, text,"})
    assert str_formats.get_default_scrape_formats() == ["markdown", "text"]
