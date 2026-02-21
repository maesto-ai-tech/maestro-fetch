"""Integration tests that make real HTTP requests.

These tests hit real URLs so they may fail if network is unavailable.
Mark with pytest.mark.network so they can be skipped in CI.
"""
import pytest
from maestro_fetch.core.fetcher import Fetcher
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.adapters.web import WebAdapter
from maestro_fetch.adapters.doc import DocAdapter

network = pytest.mark.network


@network
class TestRealWebFetch:
    """Actually fetch real web pages."""

    @pytest.mark.asyncio
    async def test_fetch_example_com(self):
        """Fetch example.com -- a stable, simple HTML page."""
        adapter = WebAdapter()
        config = FetchConfig(timeout=30)
        result = await adapter.fetch("https://example.com", config)

        assert result.source_type == "web"
        assert len(result.content) > 50
        assert "example" in result.content.lower()

    @pytest.mark.asyncio
    async def test_fetch_via_fetcher(self):
        """Full pipeline: Fetcher -> WebAdapter -> real page."""
        fetcher = Fetcher()
        config = FetchConfig(timeout=30)
        result = await fetcher.fetch("https://example.com", config)

        assert result.source_type == "web"
        assert result.content != ""


@network
class TestRealDocFetch:
    """Actually fetch and parse real documents."""

    @pytest.mark.asyncio
    async def test_fetch_csv_from_github(self, tmp_path):
        """Fetch a real CSV from a public GitHub raw URL."""
        adapter = DocAdapter()
        config = FetchConfig(cache_dir=tmp_path, timeout=30)
        # Small public CSV -- iris dataset
        url = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"
        result = await adapter.fetch(url, config)

        assert result.source_type == "doc"
        assert len(result.tables) == 1
        df = result.tables[0]
        assert "sepal_length" in df.columns
        assert len(df) == 150  # iris has 150 rows
        assert result.raw_path is not None
        assert result.raw_path.exists()
