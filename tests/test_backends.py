"""Tests for browser backends (backends/).

Covers: availability detection, priority ordering, best-backend selection.
All external tools are mocked -- no network or subprocess calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from maestro_fetch.backends import (
    get_available_backends,
    get_best_backend,
)
from maestro_fetch.backends.bb_browser import BbBrowserBackend
from maestro_fetch.backends.cloudflare import CloudflareBackend
from maestro_fetch.backends.playwright import PlaywrightBackend


# -- individual availability -----------------------------------------------


@pytest.mark.asyncio
async def test_bb_browser_not_available() -> None:
    """When bb-browser is not on PATH, is_available returns False."""
    with patch("maestro_fetch.backends.bb_browser.shutil.which", return_value=None):
        backend = BbBrowserBackend()
        assert await backend.is_available() is False


@pytest.mark.asyncio
async def test_cloudflare_not_available() -> None:
    """When credentials are empty, is_available returns False."""
    backend = CloudflareBackend(account_id="", api_token="")
    assert await backend.is_available() is False


@pytest.mark.asyncio
async def test_playwright_availability() -> None:
    """is_available reflects whether the playwright package can be imported."""
    backend = PlaywrightBackend()
    with patch(
        "maestro_fetch.backends.playwright._playwright_importable", return_value=False
    ):
        assert await backend.is_available() is False

    with patch(
        "maestro_fetch.backends.playwright._playwright_importable", return_value=True
    ):
        assert await backend.is_available() is True


# -- registry functions ----------------------------------------------------


@pytest.mark.asyncio
async def test_get_available_backends() -> None:
    """get_available_backends returns backends in priority order, skipping unavailable."""
    config = {
        "backends": {
            "priority": ["bb-browser", "cloudflare", "playwright"],
        }
    }

    with (
        patch.object(BbBrowserBackend, "is_available", new_callable=AsyncMock, return_value=False),
        patch.object(CloudflareBackend, "is_available", new_callable=AsyncMock, return_value=True),
        patch.object(PlaywrightBackend, "is_available", new_callable=AsyncMock, return_value=True),
    ):
        backends = await get_available_backends(config)
        names = [b.name for b in backends]
        assert names == ["cloudflare", "playwright"]


@pytest.mark.asyncio
async def test_get_best_backend() -> None:
    """get_best_backend returns the first available backend."""
    config = {
        "backends": {
            "priority": ["bb-browser", "playwright"],
        }
    }

    with (
        patch.object(BbBrowserBackend, "is_available", new_callable=AsyncMock, return_value=False),
        patch.object(PlaywrightBackend, "is_available", new_callable=AsyncMock, return_value=True),
    ):
        best = await get_best_backend(config)
        assert best is not None
        assert best.name == "playwright"


@pytest.mark.asyncio
async def test_get_best_backend_none() -> None:
    """get_best_backend returns None when nothing is available."""
    config = {
        "backends": {
            "priority": ["bb-browser"],
        }
    }

    with patch.object(BbBrowserBackend, "is_available", new_callable=AsyncMock, return_value=False):
        best = await get_best_backend(config)
        assert best is None
