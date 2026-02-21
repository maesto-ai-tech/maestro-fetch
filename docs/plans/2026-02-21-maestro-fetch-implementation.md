# maestro-fetch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a universal data acquisition toolkit (CLI + Python SDK + MCP) that fetches data from any source — web, PDF, cloud storage, video, images — with swappable LLM providers.

**Architecture:** Plugin architecture with a URL Router that dispatches to source-specific Adapters. Each Adapter implements a two-method interface (`supports` + `fetch`). LLM extraction uses a pluggable Provider abstraction so callers can swap Claude, GPT-4V, Gemini, or Ollama without changing calling code.

**Tech Stack:** Python 3.11+, asyncio, crawl4ai, docling, openpyxl, yt-dlp, openai-whisper, typer, fastmcp, anthropic SDK, openai SDK, pandas, pytest, pyproject.toml (hatch build backend)

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `maestro_fetch/__init__.py`
- Create: `maestro_fetch/core/__init__.py`
- Create: `maestro_fetch/adapters/__init__.py`
- Create: `maestro_fetch/providers/__init__.py`
- Create: `maestro_fetch/interfaces/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/fixtures/sample.xlsx` (generate in step)
- Create: `.gitignore`

**Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "maestro-fetch"
version = "0.1.0"
description = "Fetch data from any URL — web, PDF, cloud, video, images"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Maestro AI", email = "hello@maestro.onl" }]
keywords = ["web-scraping", "data-acquisition", "pdf", "llm", "mcp"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3.11",
]

dependencies = [
    "crawl4ai>=0.4.0",
    "httpx>=0.27",
    "typer>=0.12",
    "pandas>=2.2",
    "aiofiles>=23.0",
]

[project.optional-dependencies]
pdf = ["docling>=2.0", "openpyxl>=3.1"]
media = ["yt-dlp>=2024.1", "openai-whisper>=20231117"]
vision = []  # uses providers; no extra deps
anthropic = ["anthropic>=0.34"]
openai = ["openai>=1.40"]
gemini = ["google-generativeai>=0.7"]
ollama = ["ollama>=0.3"]
mcp = ["fastmcp>=0.1"]
all = [
    "maestro-fetch[pdf]",
    "maestro-fetch[media]",
    "maestro-fetch[vision]",
    "maestro-fetch[anthropic]",
    "maestro-fetch[openai]",
    "maestro-fetch[mcp]",
]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "pytest-mock>=3.14"]

[project.scripts]
maestro-fetch = "maestro_fetch.interfaces.cli:app"
maestro-fetch-mcp = "maestro_fetch.interfaces.mcp_server:run"

[tool.hatch.build.targets.wheel]
packages = ["maestro_fetch"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create all empty `__init__.py` files**

```bash
mkdir -p maestro_fetch/{core,adapters,providers,interfaces}
mkdir -p tests/{unit/fixtures,integration}
touch maestro_fetch/__init__.py
touch maestro_fetch/core/__init__.py
touch maestro_fetch/adapters/__init__.py
touch maestro_fetch/providers/__init__.py
touch maestro_fetch/interfaces/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
```

**Step 3: Create `.gitignore`**

```
__pycache__/
*.py[cod]
.venv/
dist/
*.egg-info/
.pytest_cache/
.ruff_cache/
```

**Step 4: Install in dev mode**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[pdf,anthropic,openai,dev]"
```

Expected: no errors, `maestro-fetch --help` works (will error on missing cli.py — that's fine for now).

**Step 5: Commit**

```bash
git add pyproject.toml maestro_fetch/ tests/ .gitignore
git commit -m "chore: scaffold project structure"
```

---

## Task 2: Core Types (FetchResult, FetchConfig, Errors)

**Files:**
- Create: `maestro_fetch/core/result.py`
- Create: `maestro_fetch/core/config.py`
- Create: `maestro_fetch/core/errors.py`
- Create: `tests/unit/test_result.py`

**Step 1: Write failing test**

```python
# tests/unit/test_result.py
import pandas as pd
from maestro_fetch.core.result import FetchResult
from maestro_fetch.core.errors import FetchError, UnsupportedURLError


def test_fetch_result_defaults():
    r = FetchResult(url="https://example.com", source_type="web", content="hello")
    assert r.tables == []
    assert r.metadata == {}
    assert r.raw_path is None


def test_fetch_result_with_table():
    df = pd.DataFrame({"a": [1, 2]})
    r = FetchResult(url="https://example.com", source_type="pdf", content="", tables=[df])
    assert len(r.tables) == 1
    assert list(r.tables[0].columns) == ["a"]


def test_error_hierarchy():
    e = UnsupportedURLError("ftp://bad")
    assert isinstance(e, FetchError)
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_result.py -v
```

Expected: `ImportError: No module named 'maestro_fetch.core.result'`

**Step 3: Implement**

```python
# maestro_fetch/core/result.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd


@dataclass
class FetchResult:
    url: str
    source_type: str  # "web" | "pdf" | "excel" | "cloud" | "media" | "image"
    content: str
    tables: list[pd.DataFrame] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    raw_path: Path | None = None
```

```python
# maestro_fetch/core/errors.py
class FetchError(Exception):
    """Base error for all maestro-fetch failures."""

class UnsupportedURLError(FetchError):
    """No adapter supports this URL."""

class DownloadError(FetchError):
    """Network or HTTP error during download."""

class ParseError(FetchError):
    """Document parsing failed."""

class ProviderError(FetchError):
    """LLM provider call failed."""
```

```python
# maestro_fetch/core/config.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FetchConfig:
    provider: str = "anthropic"          # default LLM provider name
    model: str | None = None             # None = use provider default
    schema: dict | None = None           # JSON schema for structured extraction
    output_format: str = "markdown"      # "markdown" | "csv" | "json" | "parquet"
    cache_dir: Path = Path(".maestro_cache")
    timeout: int = 60                    # seconds
    max_retries: int = 3
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_result.py -v
```

Expected: 3 PASSED

**Step 5: Commit**

```bash
git add maestro_fetch/core/ tests/unit/test_result.py
git commit -m "feat(core): add FetchResult, FetchConfig, error hierarchy"
```

---

## Task 3: URL Router

**Files:**
- Create: `maestro_fetch/core/router.py`
- Create: `tests/unit/test_router.py`

**Step 1: Write failing test**

```python
# tests/unit/test_router.py
from maestro_fetch.core.router import detect_type


def test_dropbox_url():
    assert detect_type("https://www.dropbox.com/sh/abc/def/file.csv") == "cloud"

def test_gdrive_url():
    assert detect_type("https://drive.google.com/file/d/abc123/view") == "cloud"

def test_youtube_url():
    assert detect_type("https://www.youtube.com/watch?v=abc123") == "media"

def test_youtube_short_url():
    assert detect_type("https://youtu.be/abc123") == "media"

def test_pdf_url():
    assert detect_type("https://example.com/report.pdf") == "doc"

def test_excel_url():
    assert detect_type("https://example.com/data.xlsx") == "doc"

def test_csv_url():
    assert detect_type("https://example.com/data.csv") == "doc"

def test_html_url():
    assert detect_type("https://example.com/page") == "web"

def test_html_url_with_html_ext():
    assert detect_type("https://example.com/page.html") == "web"
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_router.py -v
```

Expected: `ImportError`

**Step 3: Implement**

```python
# maestro_fetch/core/router.py
from __future__ import annotations
import re

# Ordered: more specific patterns first
_RULES: list[tuple[str, str]] = [
    # cloud storage
    (r"dropbox\.com/", "cloud"),
    (r"drive\.google\.com/", "cloud"),
    (r"docs\.google\.com/", "cloud"),
    # media
    (r"youtube\.com/watch", "media"),
    (r"youtu\.be/", "media"),
    (r"vimeo\.com/", "media"),
    # documents by extension
    (r"\.pdf(\?|$)", "doc"),
    (r"\.(xlsx|xls|ods)(\?|$)", "doc"),
    (r"\.csv(\?|$)", "doc"),
]


def detect_type(url: str) -> str:
    """Return source type string for URL. Falls back to 'web'."""
    for pattern, source_type in _RULES:
        if re.search(pattern, url, re.IGNORECASE):
            return source_type
    return "web"
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_router.py -v
```

Expected: 9 PASSED

**Step 5: Commit**

```bash
git add maestro_fetch/core/router.py tests/unit/test_router.py
git commit -m "feat(core): add URL router with regex-based type detection"
```

---

## Task 4: BaseAdapter Interface

**Files:**
- Create: `maestro_fetch/adapters/base.py`
- Create: `tests/unit/test_adapters/__init__.py`
- Create: `tests/unit/test_adapters/test_base.py`

**Step 1: Write failing test**

```python
# tests/unit/test_adapters/test_base.py
import pytest
from maestro_fetch.adapters.base import BaseAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult


class ConcreteAdapter(BaseAdapter):
    def supports(self, url: str) -> bool:
        return url.startswith("fake://")

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        return FetchResult(url=url, source_type="test", content="ok")


def test_supports():
    adapter = ConcreteAdapter()
    assert adapter.supports("fake://anything") is True
    assert adapter.supports("https://example.com") is False


@pytest.mark.asyncio
async def test_fetch():
    adapter = ConcreteAdapter()
    config = FetchConfig()
    result = await adapter.fetch("fake://x", config)
    assert result.content == "ok"
    assert result.source_type == "test"


def test_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseAdapter()
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_adapters/test_base.py -v
```

Expected: `ImportError`

**Step 3: Implement**

```python
# maestro_fetch/adapters/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult


class BaseAdapter(ABC):
    """Contract for all source adapters.

    Responsibilities:
    - supports(): tell the Router whether this adapter handles a URL
    - fetch(): download/parse the source, return unified FetchResult

    Invariants:
    - fetch() must always return FetchResult (never None)
    - fetch() raises FetchError subclasses on failure, never swallows
    """

    @abstractmethod
    def supports(self, url: str) -> bool:
        """Return True if this adapter can handle the given URL."""

    @abstractmethod
    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        """Fetch and parse data from url. Raises FetchError on failure."""
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_adapters/test_base.py -v
```

Expected: 3 PASSED

**Step 5: Commit**

```bash
git add maestro_fetch/adapters/base.py tests/unit/test_adapters/
git commit -m "feat(adapters): add BaseAdapter ABC interface"
```

---

## Task 5: CloudAdapter (Dropbox + GDrive Public Links)

**Files:**
- Create: `maestro_fetch/adapters/cloud.py`
- Create: `tests/unit/test_adapters/test_cloud.py`

**Step 1: Write failing test**

```python
# tests/unit/test_adapters/test_cloud.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from maestro_fetch.adapters.cloud import CloudAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.errors import DownloadError


def test_supports_dropbox():
    a = CloudAdapter()
    assert a.supports("https://www.dropbox.com/sh/abc/def/file.xlsx") is True

def test_supports_gdrive():
    a = CloudAdapter()
    assert a.supports("https://drive.google.com/file/d/abc/view") is True

def test_does_not_support_other():
    a = CloudAdapter()
    assert a.supports("https://example.com/file.xlsx") is False

def test_dropbox_direct_url_transform():
    from maestro_fetch.adapters.cloud import _to_direct_url
    url = "https://www.dropbox.com/sh/abc/def/report.pdf?dl=0"
    assert _to_direct_url(url) == "https://www.dropbox.com/sh/abc/def/report.pdf?dl=1"

def test_gdrive_direct_url_transform():
    from maestro_fetch.adapters.cloud import _to_direct_url
    url = "https://drive.google.com/file/d/FILE_ID/view?usp=sharing"
    direct = _to_direct_url(url)
    assert "export=download" in direct or "uc?id=" in direct

@pytest.mark.asyncio
async def test_fetch_dropbox_csv(tmp_path):
    a = CloudAdapter()
    config = FetchConfig(cache_dir=tmp_path)
    fake_csv = b"col1,col2\n1,2\n3,4\n"

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_csv
        mock_response.headers = {"content-type": "text/csv"}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await a.fetch(
            "https://www.dropbox.com/sh/abc/def/data.csv?dl=0", config
        )

    assert result.source_type == "cloud"
    assert len(result.tables) == 1
    assert list(result.tables[0].columns) == ["col1", "col2"]
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_adapters/test_cloud.py -v
```

Expected: `ImportError`

**Step 3: Implement**

```python
# maestro_fetch/adapters/cloud.py
from __future__ import annotations
import re
import io
from pathlib import Path
import httpx
import pandas as pd
from maestro_fetch.adapters.base import BaseAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult
from maestro_fetch.core.errors import DownloadError

_CLOUD_PATTERNS = [
    r"dropbox\.com/",
    r"drive\.google\.com/",
    r"docs\.google\.com/",
]


def _to_direct_url(url: str) -> str:
    """Convert share URL to direct download URL."""
    # Dropbox: replace dl=0 with dl=1 (or add dl=1)
    if "dropbox.com" in url:
        if "dl=0" in url:
            return url.replace("dl=0", "dl=1")
        if "?" in url:
            return url + "&dl=1"
        return url + "?dl=1"
    # Google Drive: /file/d/FILE_ID/view -> /uc?export=download&id=FILE_ID
    gdrive_match = re.search(r"/file/d/([^/]+)", url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def _parse_content(content: bytes, filename: str) -> tuple[str, list[pd.DataFrame]]:
    """Parse downloaded bytes into markdown text and tables."""
    ext = Path(filename).suffix.lower()
    tables: list[pd.DataFrame] = []
    text = ""

    if ext == ".csv":
        df = pd.read_csv(io.BytesIO(content))
        tables = [df]
        text = df.to_markdown(index=False)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(content))
        tables = [df]
        text = df.to_markdown(index=False)
    else:
        # treat as text
        text = content.decode("utf-8", errors="replace")

    return text, tables


class CloudAdapter(BaseAdapter):
    """Downloads files from public Dropbox and Google Drive share links."""

    def supports(self, url: str) -> bool:
        return any(re.search(p, url, re.IGNORECASE) for p in _CLOUD_PATTERNS)

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        direct_url = _to_direct_url(url)
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=config.timeout) as client:
                response = await client.get(direct_url)
                if response.status_code != 200:
                    raise DownloadError(f"HTTP {response.status_code} for {url}")
                content = response.content
        except httpx.RequestError as e:
            raise DownloadError(f"Network error fetching {url}: {e}") from e

        # Infer filename from URL path
        filename = url.split("?")[0].rstrip("/").split("/")[-1] or "download"
        text, tables = _parse_content(content, filename)

        # Cache raw file
        config.cache_dir.mkdir(parents=True, exist_ok=True)
        raw_path = config.cache_dir / filename
        raw_path.write_bytes(content)

        return FetchResult(
            url=url,
            source_type="cloud",
            content=text,
            tables=tables,
            metadata={"direct_url": direct_url, "filename": filename},
            raw_path=raw_path,
        )
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_adapters/test_cloud.py -v
```

Expected: 6 PASSED

**Step 5: Commit**

```bash
git add maestro_fetch/adapters/cloud.py tests/unit/test_adapters/test_cloud.py
git commit -m "feat(adapters): add CloudAdapter for Dropbox and GDrive public links"
```

---

## Task 6: DocAdapter (PDF + Excel)

**Files:**
- Create: `maestro_fetch/adapters/doc.py`
- Create: `tests/unit/test_adapters/test_doc.py`
- Create: `tests/unit/fixtures/sample.xlsx` (generate via script)
- Create: `tests/unit/fixtures/sample.pdf` (generate via script)

**Step 1: Generate test fixtures**

```python
# Run once to create fixtures:
import openpyxl, os
os.makedirs("tests/unit/fixtures", exist_ok=True)
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["name", "value"])
ws.append(["alpha", 10])
ws.append(["beta", 20])
wb.save("tests/unit/fixtures/sample.xlsx")
print("Created sample.xlsx")
```

```bash
python -c "
import openpyxl, os
os.makedirs('tests/unit/fixtures', exist_ok=True)
wb = openpyxl.Workbook()
ws = wb.active
ws.append(['name', 'value'])
ws.append(['alpha', 10])
ws.append(['beta', 20])
wb.save('tests/unit/fixtures/sample.xlsx')
print('Created sample.xlsx')
"
```

**Step 2: Write failing test**

```python
# tests/unit/test_adapters/test_doc.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from maestro_fetch.adapters.doc import DocAdapter
from maestro_fetch.core.config import FetchConfig

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_supports_pdf():
    a = DocAdapter()
    assert a.supports("https://example.com/report.pdf") is True

def test_supports_excel():
    a = DocAdapter()
    assert a.supports("https://example.com/data.xlsx") is True

def test_does_not_support_html():
    a = DocAdapter()
    assert a.supports("https://example.com/page.html") is False

@pytest.mark.asyncio
async def test_fetch_excel_from_url(tmp_path):
    a = DocAdapter()
    config = FetchConfig(cache_dir=tmp_path)
    xlsx_bytes = (FIXTURES / "sample.xlsx").read_bytes()

    with patch("httpx.AsyncClient") as mock_class:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = xlsx_bytes
        mock_client = MagicMock()
        mock_client.__aenter__ = MagicMock(return_value=mock_client)
        mock_client.__aexit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(return_value=mock_resp)
        mock_class.return_value = mock_client

        result = await a.fetch("https://example.com/sample.xlsx", config)

    assert result.source_type == "doc"
    assert len(result.tables) == 1
    assert "name" in result.tables[0].columns
    assert "value" in result.tables[0].columns
```

**Step 3: Run to verify failure**

```bash
pytest tests/unit/test_adapters/test_doc.py -v
```

Expected: `ImportError`

**Step 4: Implement**

```python
# maestro_fetch/adapters/doc.py
from __future__ import annotations
import re
import io
from pathlib import Path
import httpx
import pandas as pd
from maestro_fetch.adapters.base import BaseAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult
from maestro_fetch.core.errors import DownloadError, ParseError

_DOC_PATTERNS = [
    r"\.pdf(\?|$)",
    r"\.(xlsx|xls|ods)(\?|$)",
    r"\.csv(\?|$)",
]


def _parse_excel(content: bytes) -> tuple[str, list[pd.DataFrame]]:
    df = pd.read_excel(io.BytesIO(content))
    return df.to_markdown(index=False) or "", [df]


def _parse_csv(content: bytes) -> tuple[str, list[pd.DataFrame]]:
    df = pd.read_csv(io.BytesIO(content))
    return df.to_markdown(index=False) or "", [df]


def _parse_pdf(content: bytes) -> tuple[str, list[pd.DataFrame]]:
    # Docling is optional; fallback to pdfplumber if not installed
    try:
        from docling.document_converter import DocumentConverter
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            text = result.document.export_to_markdown()
            # Extract tables from docling result
            tables = []
            for table in result.document.tables:
                df = table.export_to_dataframe()
                if df is not None:
                    tables.append(df)
            return text, tables
        finally:
            os.unlink(tmp_path)
    except ImportError:
        # Fallback: pdfplumber for text extraction
        import pdfplumber
        tables = []
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
                for table_data in page.extract_tables():
                    if table_data:
                        df = pd.DataFrame(table_data[1:], columns=table_data[0])
                        tables.append(df)
        return "\n".join(text_parts), tables


class DocAdapter(BaseAdapter):
    """Parses PDF (via Docling), Excel, and CSV files from URLs."""

    def supports(self, url: str) -> bool:
        return any(re.search(p, url, re.IGNORECASE) for p in _DOC_PATTERNS)

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=config.timeout) as client:
                response = client.get(url)
                if response.status_code != 200:
                    raise DownloadError(f"HTTP {response.status_code} for {url}")
                content = response.content
        except httpx.RequestError as e:
            raise DownloadError(f"Network error: {e}") from e

        filename = url.split("?")[0].rstrip("/").split("/")[-1]
        ext = Path(filename).suffix.lower()

        try:
            if ext == ".pdf":
                text, tables = _parse_pdf(content)
            elif ext in (".xlsx", ".xls", ".ods"):
                text, tables = _parse_excel(content)
            elif ext == ".csv":
                text, tables = _parse_csv(content)
            else:
                text = content.decode("utf-8", errors="replace")
                tables = []
        except Exception as e:
            raise ParseError(f"Failed to parse {filename}: {e}") from e

        config.cache_dir.mkdir(parents=True, exist_ok=True)
        raw_path = config.cache_dir / filename
        raw_path.write_bytes(content)

        return FetchResult(
            url=url,
            source_type="doc",
            content=text,
            tables=tables,
            metadata={"filename": filename, "ext": ext},
            raw_path=raw_path,
        )
```

**Step 5: Fix async mock issue in test** (note: `client.get` is sync in current impl — make it async)

Update `doc.py` fetch method to use `await client.get(url)`:

```python
        async with httpx.AsyncClient(follow_redirects=True, timeout=config.timeout) as client:
            response = await client.get(url)
```

And update the test mock accordingly:
```python
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
```

**Step 6: Run tests**

```bash
pytest tests/unit/test_adapters/test_doc.py -v
```

Expected: 4 PASSED

**Step 7: Commit**

```bash
git add maestro_fetch/adapters/doc.py tests/unit/test_adapters/test_doc.py tests/unit/fixtures/
git commit -m "feat(adapters): add DocAdapter for PDF (Docling) and Excel/CSV"
```

---

## Task 7: WebAdapter (Crawl4AI)

**Files:**
- Create: `maestro_fetch/adapters/web.py`
- Create: `tests/unit/test_adapters/test_web.py`

**Step 1: Write failing test**

```python
# tests/unit/test_adapters/test_web.py
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
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_adapters/test_web.py -v
```

Expected: `ImportError`

**Step 3: Implement**

```python
# maestro_fetch/adapters/web.py
from __future__ import annotations
import re
from maestro_fetch.adapters.base import BaseAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult
from maestro_fetch.core.errors import DownloadError

# Patterns that other adapters handle — WebAdapter is the fallback
_NON_WEB_PATTERNS = [
    r"dropbox\.com/",
    r"drive\.google\.com/",
    r"docs\.google\.com/",
    r"youtube\.com/watch",
    r"youtu\.be/",
    r"\.pdf(\?|$)",
    r"\.(xlsx|xls|ods|csv)(\?|$)",
]


class WebAdapter(BaseAdapter):
    """Fetches JS-rendered web pages via Crawl4AI, outputs Markdown."""

    def supports(self, url: str) -> bool:
        return not any(re.search(p, url, re.IGNORECASE) for p in _NON_WEB_PATTERNS)

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        try:
            from crawl4ai import AsyncWebCrawler
        except ImportError as e:
            raise ImportError("crawl4ai is required for WebAdapter: pip install crawl4ai") from e

        try:
            async with AsyncWebCrawler() as crawler:
                crawl_result = await crawler.arun(url=url)
                if not crawl_result.success:
                    raise DownloadError(f"Crawl4AI failed for {url}")
                content = crawl_result.markdown or ""
        except Exception as e:
            if isinstance(e, DownloadError):
                raise
            raise DownloadError(f"Web fetch failed for {url}: {e}") from e

        return FetchResult(
            url=url,
            source_type="web",
            content=content,
            tables=[],
            metadata={"adapter": "crawl4ai"},
        )
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_adapters/test_web.py -v
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add maestro_fetch/adapters/web.py tests/unit/test_adapters/test_web.py
git commit -m "feat(adapters): add WebAdapter backed by Crawl4AI"
```

---

## Task 8: LLM Providers (Base + Anthropic + OpenAI)

**Files:**
- Create: `maestro_fetch/providers/base.py`
- Create: `maestro_fetch/providers/anthropic.py`
- Create: `maestro_fetch/providers/openai.py`
- Create: `maestro_fetch/providers/registry.py`
- Create: `tests/unit/test_providers.py`

**Step 1: Write failing test**

```python
# tests/unit/test_providers.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from maestro_fetch.providers.base import LLMProvider
from maestro_fetch.providers.registry import get_provider


def test_registry_returns_anthropic():
    p = get_provider("anthropic")
    from maestro_fetch.providers.anthropic import AnthropicProvider
    assert isinstance(p, AnthropicProvider)

def test_registry_returns_openai():
    p = get_provider("openai")
    from maestro_fetch.providers.openai import OpenAIProvider
    assert isinstance(p, OpenAIProvider)

def test_registry_raises_on_unknown():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("nonexistent")

@pytest.mark.asyncio
async def test_anthropic_extract(monkeypatch):
    from maestro_fetch.providers.anthropic import AnthropicProvider

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"country": "US", "gdp": 25.0}')]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider()
        result = await provider.extract(
            content="US GDP is $25 trillion",
            schema={"country": "str", "gdp": "float"},
        )

    assert result == {"country": "US", "gdp": 25.0}
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_providers.py -v
```

Expected: `ImportError`

**Step 3: Implement base and registry**

```python
# maestro_fetch/providers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interface for LLM-based extraction providers.

    Invariant: extract() always returns a dict (may be empty on failure).
    """

    @abstractmethod
    async def extract(self, content: str, schema: dict) -> dict:
        """Extract structured data from content according to schema."""
```

```python
# maestro_fetch/providers/registry.py
from __future__ import annotations
from maestro_fetch.providers.base import LLMProvider

_REGISTRY: dict[str, type[LLMProvider]] = {}


def register(name: str):
    def decorator(cls):
        _REGISTRY[name] = cls
        return cls
    return decorator


def get_provider(name: str) -> LLMProvider:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown provider '{name}'. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]()
```

```python
# maestro_fetch/providers/anthropic.py
from __future__ import annotations
import json
from maestro_fetch.providers.base import LLMProvider
from maestro_fetch.providers.registry import register
from maestro_fetch.core.errors import ProviderError

DEFAULT_MODEL = "claude-sonnet-4-6"


@register("anthropic")
class AnthropicProvider(LLMProvider):
    """Extracts structured data using Claude."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    async def extract(self, content: str, schema: dict) -> dict:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("pip install maestro-fetch[anthropic]") from e

        client = anthropic.AsyncAnthropic()
        prompt = (
            f"Extract the following fields from the text below.\n"
            f"Schema: {json.dumps(schema)}\n"
            f"Return ONLY valid JSON.\n\n"
            f"Text:\n{content[:8000]}"
        )
        try:
            message = await client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text
            return json.loads(raw)
        except Exception as e:
            raise ProviderError(f"Anthropic extraction failed: {e}") from e
```

```python
# maestro_fetch/providers/openai.py
from __future__ import annotations
import json
from maestro_fetch.providers.base import LLMProvider
from maestro_fetch.providers.registry import register
from maestro_fetch.core.errors import ProviderError

DEFAULT_MODEL = "gpt-4o"


@register("openai")
class OpenAIProvider(LLMProvider):
    """Extracts structured data using GPT-4o."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    async def extract(self, content: str, schema: dict) -> dict:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError("pip install maestro-fetch[openai]") from e

        client = AsyncOpenAI()
        prompt = (
            f"Extract fields per schema: {json.dumps(schema)}\n"
            f"Return ONLY valid JSON.\n\nText:\n{content[:8000]}"
        )
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            raise ProviderError(f"OpenAI extraction failed: {e}") from e
```

**Step 4: Import providers in `__init__.py` so registry populates**

```python
# maestro_fetch/providers/__init__.py
from maestro_fetch.providers import anthropic, openai  # noqa: F401 — triggers @register
```

**Step 5: Run tests**

```bash
pytest tests/unit/test_providers.py -v
```

Expected: 4 PASSED

**Step 6: Commit**

```bash
git add maestro_fetch/providers/ tests/unit/test_providers.py
git commit -m "feat(providers): add LLMProvider base, AnthropicProvider, OpenAIProvider, registry"
```

---

## Task 9: Main Router + SDK Entry Point

**Files:**
- Create: `maestro_fetch/core/fetcher.py`
- Create: `maestro_fetch/interfaces/sdk.py`
- Modify: `maestro_fetch/__init__.py`
- Create: `tests/unit/test_fetcher.py`

**Step 1: Write failing test**

```python
# tests/unit/test_fetcher.py
import pytest
from unittest.mock import AsyncMock, patch
from maestro_fetch.core.fetcher import Fetcher
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult
from maestro_fetch.core.errors import UnsupportedURLError


@pytest.mark.asyncio
async def test_fetcher_routes_to_cloud():
    fetcher = Fetcher()
    mock_result = FetchResult(url="https://dropbox.com/sh/x", source_type="cloud", content="data")

    with patch.object(fetcher._adapters[0].__class__, "fetch", new_callable=AsyncMock) as m:
        # Patch CloudAdapter.fetch
        pass

    # Simpler: mock the whole adapter list
    mock_adapter = AsyncMock()
    mock_adapter.supports = lambda url: "dropbox" in url
    mock_adapter.fetch = AsyncMock(return_value=mock_result)
    fetcher._adapters = [mock_adapter]

    config = FetchConfig()
    result = await fetcher.fetch("https://dropbox.com/sh/x/file.csv", config)
    assert result.source_type == "cloud"
    mock_adapter.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_fetcher_raises_on_unsupported():
    fetcher = Fetcher()
    # Replace all adapters with ones that don't support anything
    mock_adapter = AsyncMock()
    mock_adapter.supports = lambda url: False
    fetcher._adapters = [mock_adapter]

    with pytest.raises(UnsupportedURLError):
        await fetcher.fetch("ftp://unsupported.example", FetchConfig())
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_fetcher.py -v
```

Expected: `ImportError`

**Step 3: Implement fetcher**

```python
# maestro_fetch/core/fetcher.py
from __future__ import annotations
from maestro_fetch.adapters.cloud import CloudAdapter
from maestro_fetch.adapters.doc import DocAdapter
from maestro_fetch.adapters.web import WebAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult
from maestro_fetch.core.errors import UnsupportedURLError

# Order matters: more specific adapters before WebAdapter (fallback)
_DEFAULT_ADAPTERS = [CloudAdapter, DocAdapter, WebAdapter]


class Fetcher:
    """Dispatches fetch requests to the correct adapter."""

    def __init__(self):
        self._adapters = [cls() for cls in _DEFAULT_ADAPTERS]

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        for adapter in self._adapters:
            if adapter.supports(url):
                return await adapter.fetch(url, config)
        raise UnsupportedURLError(f"No adapter supports URL: {url}")

    async def batch_fetch(
        self, urls: list[str], config: FetchConfig, concurrency: int = 5
    ) -> list[FetchResult]:
        import asyncio
        semaphore = asyncio.Semaphore(concurrency)

        async def _fetch_one(url: str) -> FetchResult:
            async with semaphore:
                return await self.fetch(url, config)

        return await asyncio.gather(*[_fetch_one(u) for u in urls], return_exceptions=False)
```

**Step 4: Implement SDK entry point**

```python
# maestro_fetch/interfaces/sdk.py
from __future__ import annotations
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.fetcher import Fetcher
from maestro_fetch.core.result import FetchResult

_fetcher = Fetcher()


async def fetch(
    url: str,
    *,
    provider: str = "anthropic",
    model: str | None = None,
    schema: dict | None = None,
    output_format: str = "markdown",
    cache_dir: str = ".maestro_cache",
    timeout: int = 60,
) -> FetchResult:
    """Fetch data from any URL. Auto-detects source type."""
    config = FetchConfig(
        provider=provider,
        model=model,
        schema=schema,
        output_format=output_format,
        cache_dir=__import__("pathlib").Path(cache_dir),
        timeout=timeout,
    )
    return await _fetcher.fetch(url, config)


async def batch_fetch(
    urls: list[str],
    concurrency: int = 5,
    **kwargs,
) -> list[FetchResult]:
    """Fetch multiple URLs concurrently."""
    config = FetchConfig(**{k: v for k, v in kwargs.items() if k in FetchConfig.__dataclass_fields__})
    return await _fetcher.batch_fetch(urls, config, concurrency=concurrency)
```

**Step 5: Update `__init__.py`**

```python
# maestro_fetch/__init__.py
from maestro_fetch.interfaces.sdk import fetch, batch_fetch

__all__ = ["fetch", "batch_fetch"]
__version__ = "0.1.0"
```

**Step 6: Run tests**

```bash
pytest tests/unit/test_fetcher.py -v
```

Expected: 2 PASSED

**Step 7: Commit**

```bash
git add maestro_fetch/core/fetcher.py maestro_fetch/interfaces/sdk.py maestro_fetch/__init__.py tests/unit/test_fetcher.py
git commit -m "feat(core): add Fetcher router and SDK entry point (fetch, batch_fetch)"
```

---

## Task 10: CLI (typer)

**Files:**
- Create: `maestro_fetch/interfaces/cli.py`
- Create: `tests/unit/test_cli.py`

**Step 1: Write failing test**

```python
# tests/unit/test_cli.py
from typer.testing import CliRunner
from unittest.mock import AsyncMock, patch
from maestro_fetch.interfaces.cli import app
from maestro_fetch.core.result import FetchResult

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "fetch" in result.output.lower()


def test_fetch_command_calls_sdk(tmp_path):
    mock_result = FetchResult(
        url="https://example.com",
        source_type="web",
        content="# Hello",
        tables=[],
    )
    with patch("maestro_fetch.interfaces.cli.asyncio") as mock_asyncio:
        mock_asyncio.run.return_value = mock_result
        result = runner.invoke(app, ["https://example.com", "--output", "markdown"])
    assert result.exit_code == 0
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_cli.py -v
```

Expected: `ImportError`

**Step 3: Implement**

```python
# maestro_fetch/interfaces/cli.py
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
import typer
from maestro_fetch.interfaces.sdk import fetch, batch_fetch
from maestro_fetch.core.errors import FetchError

app = typer.Typer(
    name="maestro-fetch",
    help="Fetch data from any URL: web, PDF, cloud, video, images.",
    add_completion=False,
)


@app.command()
def main(
    url: str = typer.Argument(..., help="URL to fetch"),
    output: str = typer.Option("markdown", "--output", "-o", help="Output format: markdown|csv|json|parquet"),
    schema: Optional[Path] = typer.Option(None, "--schema", help="JSON schema file for LLM extraction"),
    provider: str = typer.Option("anthropic", "--provider", help="LLM provider: anthropic|openai|gemini|ollama"),
    model: Optional[str] = typer.Option(None, "--model", help="Model name override"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Directory to save output files"),
    batch: Optional[Path] = typer.Option(None, "--batch", help="File containing one URL per line"),
    cache_dir: str = typer.Option(".maestro_cache", "--cache-dir", help="Cache directory"),
    timeout: int = typer.Option(60, "--timeout", help="Request timeout in seconds"),
):
    """Fetch data from any URL. Auto-detects source type."""
    schema_dict = None
    if schema:
        schema_dict = json.loads(schema.read_text())

    urls = [url]
    if batch:
        urls = [line.strip() for line in batch.read_text().splitlines() if line.strip()]

    try:
        if len(urls) == 1:
            result = asyncio.run(fetch(
                urls[0],
                provider=provider,
                model=model,
                schema=schema_dict,
                output_format=output,
                cache_dir=cache_dir,
                timeout=timeout,
            ))
            _print_result(result, output, output_dir)
        else:
            results = asyncio.run(batch_fetch(urls, provider=provider, output_format=output))
            for r in results:
                _print_result(r, output, output_dir)
    except FetchError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


def _print_result(result, output_format: str, output_dir: Optional[Path]):
    if output_format == "markdown":
        typer.echo(result.content)
    elif output_format == "json":
        import pandas as pd
        if result.tables:
            typer.echo(result.tables[0].to_json(orient="records", indent=2))
        else:
            typer.echo(json.dumps({"content": result.content, "metadata": result.metadata}))
    elif output_format in ("csv", "parquet"):
        if not result.tables:
            typer.echo("No tables found in result.", err=True)
            return
        df = result.tables[0]
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            name = result.url.split("/")[-1].split("?")[0] or "output"
            path = output_dir / f"{name}.{output_format}"
            if output_format == "csv":
                df.to_csv(path, index=False)
            else:
                df.to_parquet(path, index=False)
            typer.echo(f"Saved to {path}")
        else:
            typer.echo(df.to_csv(index=False))
    else:
        typer.echo(result.content)
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_cli.py -v
```

Expected: 2 PASSED

**Step 5: Smoke test manually**

```bash
maestro-fetch --help
```

Expected: usage info printed, exit 0.

**Step 6: Commit**

```bash
git add maestro_fetch/interfaces/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): add typer CLI with fetch, batch, output format options"
```

---

## Task 11: MediaAdapter (yt-dlp + Whisper)

**Files:**
- Create: `maestro_fetch/adapters/media.py`
- Create: `tests/unit/test_adapters/test_media.py`

**Step 1: Write failing test**

```python
# tests/unit/test_adapters/test_media.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from maestro_fetch.adapters.media import MediaAdapter
from maestro_fetch.core.config import FetchConfig


def test_supports_youtube():
    a = MediaAdapter()
    assert a.supports("https://www.youtube.com/watch?v=abc") is True
    assert a.supports("https://youtu.be/abc") is True

def test_supports_vimeo():
    a = MediaAdapter()
    assert a.supports("https://vimeo.com/123456") is True

def test_does_not_support_web():
    a = MediaAdapter()
    assert a.supports("https://example.com") is False

@pytest.mark.asyncio
async def test_fetch_returns_transcript(tmp_path):
    a = MediaAdapter()
    config = FetchConfig(cache_dir=tmp_path)

    with patch("maestro_fetch.adapters.media._download_audio") as mock_dl, \
         patch("maestro_fetch.adapters.media._transcribe") as mock_tr:
        audio_path = tmp_path / "audio.mp3"
        audio_path.write_bytes(b"fake")
        mock_dl.return_value = audio_path
        mock_tr.return_value = "This is the transcript."

        result = await a.fetch("https://www.youtube.com/watch?v=abc", config)

    assert result.source_type == "media"
    assert "transcript" in result.content.lower() or "this is" in result.content.lower()
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_adapters/test_media.py -v
```

Expected: `ImportError`

**Step 3: Implement**

```python
# maestro_fetch/adapters/media.py
from __future__ import annotations
import re
import asyncio
from pathlib import Path
from maestro_fetch.adapters.base import BaseAdapter
from maestro_fetch.core.config import FetchConfig
from maestro_fetch.core.result import FetchResult
from maestro_fetch.core.errors import DownloadError, ParseError

_MEDIA_PATTERNS = [
    r"youtube\.com/watch",
    r"youtu\.be/",
    r"vimeo\.com/\d+",
]


def _download_audio(url: str, out_dir: Path) -> Path:
    """Download audio track from video URL using yt-dlp. Returns path to audio file."""
    try:
        import yt_dlp
    except ImportError as e:
        raise ImportError("pip install maestro-fetch[media]") from e

    out_template = str(out_dir / "audio.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    # Find downloaded file
    for f in out_dir.glob("audio.*"):
        return f
    raise DownloadError(f"yt-dlp did not produce output for {url}")


def _transcribe(audio_path: Path) -> str:
    """Transcribe audio file using OpenAI Whisper (local model)."""
    try:
        import whisper
    except ImportError as e:
        raise ImportError("pip install maestro-fetch[media]") from e

    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path))
    return result["text"]


class MediaAdapter(BaseAdapter):
    """Downloads video/audio and transcribes to text via yt-dlp + Whisper."""

    def supports(self, url: str) -> bool:
        return any(re.search(p, url, re.IGNORECASE) for p in _MEDIA_PATTERNS)

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        config.cache_dir.mkdir(parents=True, exist_ok=True)
        media_dir = config.cache_dir / "media"
        media_dir.mkdir(exist_ok=True)

        try:
            # Run blocking yt-dlp in thread pool
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(None, _download_audio, url, media_dir)
            transcript = await loop.run_in_executor(None, _transcribe, audio_path)
        except (DownloadError, ParseError):
            raise
        except Exception as e:
            raise DownloadError(f"Media fetch failed for {url}: {e}") from e

        content = f"## Transcript\n\n{transcript}"
        return FetchResult(
            url=url,
            source_type="media",
            content=content,
            tables=[],
            metadata={"audio_path": str(audio_path)},
            raw_path=audio_path,
        )
```

**Step 4: Run tests**

```bash
pytest tests/unit/test_adapters/test_media.py -v
```

Expected: 4 PASSED

**Step 5: Commit**

```bash
git add maestro_fetch/adapters/media.py tests/unit/test_adapters/test_media.py
git commit -m "feat(adapters): add MediaAdapter with yt-dlp + Whisper transcription"
```

---

## Task 12: MCP Server (FastMCP)

**Files:**
- Create: `maestro_fetch/interfaces/mcp_server.py`
- Create: `tests/unit/test_mcp.py`

**Step 1: Write failing test**

```python
# tests/unit/test_mcp.py
def test_mcp_server_importable():
    # Just verify the module loads without error
    import maestro_fetch.interfaces.mcp_server as mcp
    assert hasattr(mcp, "mcp")
    assert hasattr(mcp, "run")
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/test_mcp.py -v
```

Expected: `ImportError`

**Step 3: Implement**

```python
# maestro_fetch/interfaces/mcp_server.py
from __future__ import annotations

try:
    from fastmcp import FastMCP
except ImportError as e:
    raise ImportError("pip install maestro-fetch[mcp]") from e

from maestro_fetch.interfaces.sdk import fetch, batch_fetch
from maestro_fetch.core.result import FetchResult

mcp = FastMCP("maestro-fetch")


@mcp.tool()
async def fetch_url(
    url: str,
    output_format: str = "markdown",
    provider: str = "anthropic",
) -> dict:
    """Fetch data from any URL. Auto-detects source type (web/PDF/cloud/video/image)."""
    result = await fetch(url, provider=provider, output_format=output_format)
    return {
        "url": result.url,
        "source_type": result.source_type,
        "content": result.content,
        "table_count": len(result.tables),
        "metadata": result.metadata,
    }


@mcp.tool()
async def batch_fetch_urls(
    urls: list[str],
    output_format: str = "markdown",
    concurrency: int = 5,
) -> list[dict]:
    """Fetch multiple URLs concurrently."""
    results = await batch_fetch(urls, concurrency=concurrency, output_format=output_format)
    return [
        {
            "url": r.url,
            "source_type": r.source_type,
            "content": r.content,
            "table_count": len(r.tables),
        }
        for r in results
    ]


@mcp.tool()
async def detect_url_type(url: str) -> dict:
    """Detect the source type of a URL without downloading."""
    from maestro_fetch.core.router import detect_type
    return {"url": url, "source_type": detect_type(url)}


def run():
    mcp.run()
```

**Step 4: Run test**

```bash
pytest tests/unit/test_mcp.py -v
```

Expected: 1 PASSED (requires `pip install maestro-fetch[mcp]` first)

**Step 5: Commit**

```bash
git add maestro_fetch/interfaces/mcp_server.py tests/unit/test_mcp.py
git commit -m "feat(mcp): add FastMCP server with fetch_url, batch_fetch_urls, detect_url_type tools"
```

---

## Task 13: Full Test Suite Run + README

**Step 1: Run all unit tests**

```bash
pytest tests/unit/ -v --tb=short
```

Expected: all PASSED. Fix any failures before continuing.

**Step 2: Write README.md**

Create `README.md` at project root with:
- One-liner description
- Comparison table (wget / Crawl4AI / Firecrawl / maestro-fetch)
- Install instructions (base + extras)
- Quick start (CLI + Python SDK + MCP)
- Link to maestro.onl in footer

Key section:

```markdown
## Why maestro-fetch?

| Source          | wget | Crawl4AI | Firecrawl | maestro-fetch |
|-----------------|:----:|:--------:|:---------:|:-------------:|
| Static HTML     | yes  | yes      | yes       | yes           |
| JS-rendered     | no   | yes      | yes       | yes           |
| PDF tables      | no   | no       | no        | yes           |
| Excel / CSV     | no   | no       | no        | yes           |
| Dropbox / GDrive| no   | no       | no        | yes           |
| YouTube → text  | no   | no       | no        | yes           |
| Image tables    | no   | no       | no        | yes           |
| Swap LLM model  | n/a  | partial  | no        | yes           |
| Cost            | free | free     | paid      | free          |

Built by [Maestro AI](https://maestro.onl) — Singapore AI product studio.
```

**Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: add README with comparison table and quick start"
```

---

## Task 14: Claude Code Skill

**Files:**
- Create: `maestro_fetch/skill/maestro-data-fetch.md`

**Step 1: Write skill file**

```markdown
---
name: maestro-data-fetch
description: >
  Universal data acquisition. Use when: scraping web pages, downloading files,
  fetching Dropbox or Google Drive public links, extracting PDF tables,
  reading Excel files, transcribing YouTube videos, extracting image tables.
  Wraps maestro-fetch CLI and Python SDK.
triggers:
  - scrape
  - crawl
  - download
  - fetch data
  - dropbox
  - google drive
  - pdf extract
  - excel download
  - video transcribe
  - image table
  - data acquisition
  - get data from url
---

## When to use maestro-fetch

Use this tool for any data acquisition task involving external URLs.
It auto-detects the source type and handles the right parser.

## CLI usage

```bash
# Web page -> Markdown
maestro-fetch "https://example.com/data"

# PDF -> tables
maestro-fetch "https://example.com/report.pdf" --output csv

# Dropbox public link -> download + parse
maestro-fetch "https://www.dropbox.com/sh/xxx/file.xlsx?dl=0" --output csv

# YouTube -> transcript
maestro-fetch "https://youtube.com/watch?v=xxx"

# Schema-based LLM extraction
maestro-fetch "https://example.com/page" --schema schema.json --provider anthropic

# Batch
maestro-fetch --batch urls.txt --output-dir ./data/
```

## Python SDK usage

```python
from maestro_fetch import fetch, batch_fetch

# Single URL
result = await fetch("https://dropbox.com/sh/xxx/data.csv?dl=0")
df = result.tables[0]  # pandas DataFrame

# Schema extraction
result = await fetch(
    "https://worldbank.org/report.pdf",
    schema={"country": str, "gdp": float},
    provider="anthropic"  # or "openai", "gemini", "ollama"
)

# Batch
results = await batch_fetch(["url1", "url2"], concurrency=5)
```

## Output: FetchResult

```python
result.url          # original URL
result.source_type  # "web" | "pdf" | "excel" | "cloud" | "media" | "image"
result.content      # Markdown text
result.tables       # list[pd.DataFrame] - extracted tables
result.metadata     # dict - provenance info
result.raw_path     # Path to cached raw file
```

## Install

```bash
pip install maestro-fetch            # web + cloud
pip install maestro-fetch[pdf]       # + PDF/Excel
pip install maestro-fetch[media]     # + YouTube/audio
pip install maestro-fetch[all]       # everything
```
```

**Step 2: Commit**

```bash
git add maestro_fetch/skill/
git commit -m "docs: add Claude Code skill for maestro-data-fetch"
```

---

## Summary

| Task | What it delivers |
|------|-----------------|
| 1 | Project scaffold, pyproject.toml, virtual env |
| 2 | FetchResult, FetchConfig, error hierarchy |
| 3 | URL Router (regex-based type detection) |
| 4 | BaseAdapter ABC |
| 5 | CloudAdapter (Dropbox/GDrive public links) |
| 6 | DocAdapter (PDF via Docling, Excel/CSV) |
| 7 | WebAdapter (Crawl4AI JS rendering) |
| 8 | LLM Providers (Anthropic, OpenAI, registry) |
| 9 | Fetcher (main router) + SDK entry point |
| 10 | CLI (typer) |
| 11 | MediaAdapter (yt-dlp + Whisper) |
| 12 | MCP Server (FastMCP) |
| 13 | Full test suite + README |
| 14 | Claude Code skill |

After Task 13 passes, the project is ready for GitHub publish and Product Hunt launch.
