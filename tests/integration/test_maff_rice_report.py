"""Integration test: MAFF Rice Monthly Report page.

Target: https://www.maff.go.jp/j/seisan/keikaku/soukatu/mr.html
    Japanese Ministry of Agriculture -- "Rice Monthly Report" (米に関するマンスリーレポート)

This page contains:
    - A listing of monthly rice market reports (PDF + Excel)
    - Price, inventory, contract/sales data in PDF and Excel formats
    - Hundreds of historical report links

Tests exercise the full pipeline: WebAdapter scrape -> link extraction ->
DocAdapter fetch -> real Excel parsing. No mocks.
"""
import re
import pytest
from pathlib import Path

from maestro_fetch.core.fetcher import Fetcher
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.router import detect_type
from maestro_fetch.adapters.web import WebAdapter
from maestro_fetch.adapters.doc import DocAdapter

MAFF_URL = "https://www.maff.go.jp/j/seisan/keikaku/soukatu/mr.html"

network = pytest.mark.network


@network
class TestMAFFPageScrape:
    """Scrape the MAFF rice report listing page."""

    @pytest.fixture
    async def page_result(self):
        """Fetch the MAFF page once, share across tests in this class."""
        fetcher = Fetcher()
        config = FetchConfig(timeout=30)
        return await fetcher.fetch(MAFF_URL, config)

    @pytest.mark.asyncio
    async def test_page_detected_as_web(self):
        assert detect_type(MAFF_URL) == "web"

    @pytest.mark.asyncio
    async def test_page_fetches_successfully(self, page_result):
        assert page_result.source_type == "web"
        assert len(page_result.content) > 10000

    @pytest.mark.asyncio
    async def test_page_contains_japanese_title(self, page_result):
        assert "米に関するマンスリーレポート" in page_result.content

    @pytest.mark.asyncio
    async def test_page_contains_pdf_links(self, page_result):
        pdf_links = re.findall(
            r"https://www\.maff\.go\.jp[^\s\)]+\.pdf", page_result.content
        )
        # Page has hundreds of historical PDF reports
        assert len(pdf_links) > 100, f"Expected >100 PDF links, got {len(pdf_links)}"

    @pytest.mark.asyncio
    async def test_page_contains_excel_links(self, page_result):
        xlsx_links = re.findall(
            r"https://www\.maff\.go\.jp[^\s\)]+\.xlsx", page_result.content
        )
        assert len(xlsx_links) > 50, f"Expected >50 Excel links, got {len(xlsx_links)}"

    @pytest.mark.asyncio
    async def test_extract_latest_report_links(self, page_result):
        """Extract the latest monthly report PDF and Excel links."""
        content = page_result.content

        # Find the latest report section (最新号)
        latest_idx = content.find("最新号")
        assert latest_idx > 0, "Could not find latest report section"

        # Extract links from the latest section (next 2000 chars)
        latest_section = content[latest_idx : latest_idx + 2000]

        pdf_links = re.findall(
            r"https://www\.maff\.go\.jp[^\s\)]+\.pdf", latest_section
        )
        xlsx_links = re.findall(
            r"https://www\.maff\.go\.jp[^\s\)]+\.xlsx", latest_section
        )

        assert len(pdf_links) >= 3, "Latest section should have >= 3 PDF links"
        assert len(xlsx_links) >= 2, "Latest section should have >= 2 Excel links"

        # Verify links are well-formed
        for link in pdf_links + xlsx_links:
            assert link.startswith("https://www.maff.go.jp/")
            assert detect_type(link) == "doc"


@network
class TestMAFFExcelDownload:
    """Download and parse a real Excel file from MAFF."""

    @pytest.mark.asyncio
    async def test_fetch_price_excel(self, tmp_path):
        """Fetch the price data Excel (価格編) and verify it parses."""
        # First scrape the page to get the latest Excel link
        fetcher = Fetcher()
        config = FetchConfig(timeout=30)
        page = await fetcher.fetch(MAFF_URL, config)

        # Find the price section Excel link (価格編)
        content = page.content
        latest_idx = content.find("最新号")
        assert latest_idx > 0
        latest_section = content[latest_idx : latest_idx + 2000]

        xlsx_links = re.findall(
            r"https://www\.maff\.go\.jp[^\s\)]+\.xlsx", latest_section
        )
        assert len(xlsx_links) > 0, "No Excel links found in latest section"

        # Fetch the first Excel file
        excel_url = xlsx_links[0]
        doc_adapter = DocAdapter()
        assert doc_adapter.supports(excel_url)

        doc_config = FetchConfig(cache_dir=tmp_path, timeout=30)
        result = await doc_adapter.fetch(excel_url, doc_config)

        assert result.source_type == "doc"
        assert len(result.tables) >= 1, "Excel should produce at least 1 table"
        assert result.raw_path is not None
        assert result.raw_path.exists()

        df = result.tables[0]
        assert len(df) > 0, "Table should have rows"
        assert len(df.columns) > 0, "Table should have columns"

        # Verify cache file was written
        assert result.raw_path.suffix == ".xlsx"
        assert result.raw_path.stat().st_size > 1000  # real Excel > 1KB

    @pytest.mark.asyncio
    async def test_fetch_inventory_excel(self, tmp_path):
        """Fetch the inventory data Excel (在庫編) and verify it parses."""
        fetcher = Fetcher()
        config = FetchConfig(timeout=30)
        page = await fetcher.fetch(MAFF_URL, config)

        content = page.content
        latest_idx = content.find("最新号")
        latest_section = content[latest_idx : latest_idx + 2000]

        xlsx_links = re.findall(
            r"https://www\.maff\.go\.jp[^\s\)]+\.xlsx", latest_section
        )
        assert len(xlsx_links) >= 2, "Need at least 2 Excel links for inventory"

        # Second Excel link is typically the inventory data
        excel_url = xlsx_links[1]
        doc_adapter = DocAdapter()
        doc_config = FetchConfig(cache_dir=tmp_path, timeout=30)
        result = await doc_adapter.fetch(excel_url, doc_config)

        assert result.source_type == "doc"
        assert len(result.tables) >= 1
        assert result.metadata["ext"] == ".xlsx"


@network
class TestMAFFFullPipeline:
    """End-to-end: scrape page -> extract links -> fetch doc -> parse."""

    @pytest.mark.asyncio
    async def test_scrape_then_fetch_first_excel(self, tmp_path):
        """Full pipeline using only the public SDK-level Fetcher."""
        fetcher = Fetcher()

        # Step 1: Scrape the listing page
        page_config = FetchConfig(timeout=30)
        page = await fetcher.fetch(MAFF_URL, page_config)
        assert page.source_type == "web"

        # Step 2: Extract Excel links
        xlsx_links = re.findall(
            r"https://www\.maff\.go\.jp[^\s\)]+\.xlsx", page.content
        )
        assert len(xlsx_links) > 0

        # Step 3: Fetch the first Excel through the Fetcher (should route to DocAdapter)
        doc_config = FetchConfig(cache_dir=tmp_path, timeout=30)
        excel_result = await fetcher.fetch(xlsx_links[0], doc_config)

        # Step 4: Verify the full chain worked
        assert excel_result.source_type == "doc"
        assert len(excel_result.tables) >= 1
        assert excel_result.raw_path.exists()

        df = excel_result.tables[0]
        assert len(df) > 0
        assert len(df.columns) > 0
