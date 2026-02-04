"""Unit tests for __main__ entrypoint."""

from types import SimpleNamespace


def test_main_invokes_uvicorn(monkeypatch):
    """Ensure main configures structlog and calls uvicorn.run."""
    import structlog
    import uvicorn

    from web_search_mcp.__main__ import main
    from web_search_mcp.config import settings

    called = {"run": False, "configure": False}

    def fake_run(app, host, port, reload, log_level, access_log):  # noqa: ARG001
        called["run"] = True
        assert app == "web_search_mcp.app:app"
        assert host == settings.host
        assert port == settings.port

    def fake_configure(*args, **kwargs):  # noqa: ARG001
        called["configure"] = True

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr(structlog, "configure", fake_configure)

    main()

    assert called["run"] is True
    assert called["configure"] is True


def test_module_main_executes(monkeypatch):
    """Ensure __main__ guard executes without errors."""
    import runpy
    import structlog
    import uvicorn

    monkeypatch.setattr(structlog, "configure", lambda *args, **kwargs: None)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)

    runpy.run_module("web_search_mcp.__main__", run_name="__main__")
