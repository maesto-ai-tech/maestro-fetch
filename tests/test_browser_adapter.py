"""Tests for the BrowserAdapter (adapters/browser.py).

Covers: URL support detection, error when no backends available.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from maestro_fetch.adapters.browser import BrowserAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.errors import FetchError


def test_supports_http() -> None:
    """BrowserAdapter.supports returns True for http and https URLs."""
    adapter = BrowserAdapter()
    assert adapter.supports("http://example.com") is True
    assert adapter.supports("https://example.com/page") is True


def test_supports_non_http() -> None:
    """BrowserAdapter.supports returns False for non-HTTP URLs."""
    adapter = BrowserAdapter()
    assert adapter.supports("ftp://files.example.com/data.zip") is False
    assert adapter.supports("file:///tmp/local.html") is False
    assert adapter.supports("s3://bucket/key") is False


@pytest.mark.asyncio
async def test_fetch_no_backends() -> None:
    """fetch() raises FetchError when no backends are available."""
    adapter = BrowserAdapter(config={})
    config = FetchConfig()

    with patch(
        "maestro_fetch.adapters.browser.get_available_backends",
        new_callable=AsyncMock,
        return_value=[],
    ):
        with pytest.raises(FetchError, match="No browser backends available"):
            await adapter.fetch("https://example.com", config)
