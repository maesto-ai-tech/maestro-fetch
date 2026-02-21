import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from maestro_fetch.adapters.web import WebAdapter
from maestro_fetch.core.config import FetchConfig


def test_supports_html():
    a = WebAdapter()
    assert a.supports("https://example.com") is True
    assert a.supports("https://example.com/page.html") is True

def test_does_not_support_pdf():
    a = WebAdapter()
    assert a.supports("https://example.com/report.pdf") is False

def test_does_not_support_dropbox():
    a = WebAdapter()
    assert a.supports("https://dropbox.com/sh/abc") is False

@pytest.mark.asyncio
async def test_fetch_returns_markdown():
    a = WebAdapter()
    config = FetchConfig()

    mock_result = MagicMock()
    mock_result.markdown = "# Hello\n\nWorld"
    mock_result.success = True

    with patch("crawl4ai.AsyncWebCrawler") as mock_crawler_class:
        mock_crawler = AsyncMock()
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=False)
        mock_crawler.arun = AsyncMock(return_value=mock_result)
        mock_crawler_class.return_value = mock_crawler

        result = await a.fetch("https://example.com", config)

    assert result.source_type == "web"
    assert result.content == "# Hello\n\nWorld"
    assert result.tables == []
