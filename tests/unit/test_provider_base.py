"""Unit tests for provider base protocol."""

import pytest

from web_search_mcp.providers.base import SearchProvider


def test_protocol_properties_callable():
    dummy = object()
    # Access property getter functions directly
    assert SearchProvider.name.fget(dummy) is None  # type: ignore[arg-type]
    assert SearchProvider.is_configured.fget(dummy) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_protocol_is_available_callable():
    dummy = object()
    result = await SearchProvider.is_available(dummy)  # type: ignore[arg-type]
    assert result is None
