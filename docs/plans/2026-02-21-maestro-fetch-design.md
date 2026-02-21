# maestro-fetch Design Document

**Date**: 2026-02-21
**Status**: Approved
**GitHub**: maestro-ai-tech/maestro-fetch
**PyPI**: maestro-fetch

---

## 1. Positioning

**Tagline**: One line to fetch data from anywhere — web, PDF, cloud, video, images.

### Market Gap

No single open source tool unifies all data acquisition needs:

| Source         | wget | Crawl4AI | Firecrawl | maestro-fetch |
|----------------|------|----------|-----------|---------------|
| Static HTML    | yes  | yes      | yes       | yes           |
| JS-rendered    | no   | yes      | yes       | yes           |
| PDF tables     | no   | no       | no        | yes           |
| Dropbox/GDrive | no   | no       | no        | yes           |
| YouTube/audio  | no   | no       | no        | yes           |
| Swap LLM model | n/a  | partial  | no        | yes           |
| Cost           | free | free     | paid      | free          |

### Target Users

1. Researchers / RA: fetch data from any source without writing custom scripts
2. AI agent developers: connect Claude/GPT to real-world data via MCP
3. Internal (Maestro RA Data): all client data acquisition pipelines

### SEO Backlink Path

- GitHub README -> maestro.onl
- PyPI page -> maestro.onl
- Product Hunt + Show HN -> maestro.onl

---

## 2. Architecture

### Core Design Principle

URL Router automatically detects source type and dispatches to the correct Adapter.
LLM Provider is pluggable — swap Claude, GPT-4V, Gemini, or Ollama without changing calling code.

### Data Flow

```
Input URL
    |
[ URL Router ]  -- detects type via regex + HEAD request
    |
    +-- web    --> WebAdapter   (Crawl4AI: JS rendering, HTML -> Markdown)
    +-- cloud  --> CloudAdapter (Dropbox/GDrive public link -> file download)
    +-- doc    --> DocAdapter   (PDF via Docling, Excel via openpyxl)
    +-- media  --> MediaAdapter (yt-dlp download + Whisper transcription)
    +-- image  --> ImageAdapter (Vision LLM table extraction)
                        |
             [ LLM Provider (optional) ]
             schema extraction / structured output
             Claude / GPT-4V / Gemini / Ollama
                        |
             [ Output Normalizer ]
             CSV / JSON / Parquet / Markdown
```

### Package Structure

```
maestro_fetch/
├── core/
│   ├── router.py        -- URL type detection (regex + HEAD request)
│   ├── result.py        -- FetchResult dataclass (unified output)
│   └── config.py        -- global config (provider, timeout, cache dir)
├── adapters/
│   ├── base.py          -- BaseAdapter interface: supports() + fetch()
│   ├── web.py           -- WebAdapter: Crawl4AI
│   ├── cloud.py         -- CloudAdapter: Dropbox/GDrive public links
│   ├── doc.py           -- DocAdapter: PDF (Docling) + Excel (openpyxl)
│   ├── media.py         -- MediaAdapter: yt-dlp + Whisper
│   └── image.py         -- ImageAdapter: Vision LLM
├── providers/
│   ├── base.py          -- LLMProvider interface
│   ├── anthropic.py     -- Claude (claude-sonnet-4-6 default)
│   ├── openai.py        -- GPT-4V / Whisper API
│   ├── gemini.py        -- Gemini Vision
│   └── ollama.py        -- local Ollama
├── interfaces/
│   ├── cli.py           -- typer CLI (entry point: maestro-fetch)
│   ├── mcp_server.py    -- MCP Server via FastMCP
│   └── sdk.py           -- public Python SDK (fetch, batch_fetch)
└── skill/
    └── maestro-data-fetch.md  -- Claude Code skill definition
```

### BaseAdapter Contract

```python
class BaseAdapter:
    def supports(self, url: str) -> bool:
        """Called by Router: does this adapter handle this URL?"""

    async def fetch(self, url: str, config: FetchConfig) -> FetchResult:
        """Execute fetch, return unified FetchResult."""
```

### FetchResult (Unified Output)

```python
@dataclass
class FetchResult:
    url: str
    source_type: str            # "web" | "pdf" | "excel" | "cloud" | "media" | "image"
    content: str                # Markdown text
    tables: list[pd.DataFrame]  # extracted structured tables
    metadata: dict              # source, timestamp, adapter version, provenance
    raw_path: Path | None       # cached raw file path
```

### Installation Modes (avoid dependency explosion)

```bash
pip install maestro-fetch            # base: web + cloud (lightweight)
pip install maestro-fetch[pdf]       # + Docling
pip install maestro-fetch[media]     # + yt-dlp + openai-whisper
pip install maestro-fetch[vision]    # + Vision LLM support
pip install maestro-fetch[all]       # everything
```

---

## 3. Interfaces

### CLI

```bash
# Basic usage - auto-detect source type
maestro-fetch "https://dropbox.com/sh/xxx/data.xlsx"
maestro-fetch "https://epa.gov/data/water-quality.html"
maestro-fetch "https://worldbank.org/report.pdf"
maestro-fetch "https://youtube.com/watch?v=xxx"

# Output format
maestro-fetch <url> --output csv
maestro-fetch <url> --output json
maestro-fetch <url> --output parquet

# Schema-guided LLM extraction
maestro-fetch <url> --schema schema.json --provider anthropic

# Batch
maestro-fetch --batch urls.txt --output-dir ./data/

# Provider selection
maestro-fetch <url> --provider ollama --model llama3.2
maestro-fetch <url> --provider gemini --model gemini-2.0-flash
```

### Python SDK

```python
from maestro_fetch import fetch, batch_fetch

# Single URL, auto-detect
result = await fetch("https://dropbox.com/sh/xxx/data.xlsx")
df = result.tables[0]

# Schema extraction
result = await fetch(
    "https://worldbank.org/report.pdf",
    schema={"country": str, "gdp": float, "year": int},
    provider="anthropic"
)

# Batch with concurrency control
results = await batch_fetch(["url1", "url2"], concurrency=5)

# Custom provider instance
from maestro_fetch.providers import OllamaProvider
result = await fetch(url, provider=OllamaProvider(model="llama3.2"))
```

### MCP Server

Exposed tools:
- `fetch_url` -- single URL fetch, returns FetchResult as JSON
- `batch_fetch` -- list of URLs, returns list of FetchResult
- `detect_type` -- detect URL type without downloading

Config (claude_desktop_config.json):
```json
{
  "mcpServers": {
    "maestro-fetch": {
      "command": "maestro-fetch-mcp"
    }
  }
}
```

### Claude Code Skill

Trigger keywords: scrape, download, fetch, crawl, dropbox, google drive,
pdf extract, excel download, video transcribe, image table, data acquisition

---

## 4. Error Handling & Testing

### Error Hierarchy

```python
class FetchError(Exception): ...
class UnsupportedURLError(FetchError): ...  # no adapter supports this URL
class DownloadError(FetchError): ...        # network / HTTP error
class ParseError(FetchError): ...          # document parsing failed
class ProviderError(FetchError): ...       # LLM provider call failed
```

Behavior:
- CLI: print clear message + exit code != 0
- SDK: raise, never swallow exceptions
- MCP: return error field, do not crash server

### Retry Strategy

- Network errors: exponential backoff, max 3 attempts
- LLM provider errors: fallback to next available provider
- Expired cloud links: return explicit error, no silent redirect

### Test Structure

```
tests/
├── unit/
│   ├── test_router.py       -- URL type detection (pure functions, no network)
│   ├── test_result.py       -- FetchResult serialization
│   └── test_adapters/
│       ├── test_cloud.py    -- mock requests
│       └── test_doc.py      -- real fixtures (PDF, Excel)
├── integration/
│   ├── test_web.py          -- against stable pages (example.com)
│   └── test_mcp.py          -- MCP server end-to-end
└── fixtures/
    ├── sample.pdf
    ├── sample.xlsx
    └── sample_dropbox_url.txt
```

CI:
- `pytest unit/` -- every PR, no network, fast
- `pytest integration/` -- daily scheduled, requires network
- LLM calls mocked in all tests, no real API credit consumption

---

## 5. Roadmap

### V1 Scope (4-5 weeks)

| Priority | Feature | Dependency |
|----------|---------|------------|
| P0 | URL Router + WebAdapter (Crawl4AI) | crawl4ai |
| P0 | CloudAdapter (Dropbox/GDrive public links) | requests |
| P0 | DocAdapter (PDF via Docling, Excel via openpyxl) | docling, openpyxl |
| P0 | CLI (typer) + Python SDK | typer |
| P0 | AnthropicProvider + OpenAIProvider | anthropic, openai |
| P1 | MCP Server (FastMCP) | fastmcp |
| P1 | MediaAdapter (yt-dlp + Whisper) | yt-dlp, openai-whisper |
| P1 | ImageAdapter (Vision LLM) | reuses LLM providers |
| P2 | OllamaProvider + GeminiProvider | ollama, google-genai |
| P2 | Claude Code Skill | - |

### V1 Explicit Non-Goals

- Web UI / Dashboard
- Paid plans / API key management
- Authenticated page login handling
- CAPTCHA solving

### Launch Sequence

```
Week 1-2: Core implementation (Router + P0 adapters + CLI/SDK)
Week 3:   P1 features (MCP + Media + Image adapters)
Week 4:   README + benchmark table + docs
Week 5:   GitHub publish under maestro-ai-tech org
Week 6:   Product Hunt launch
Week 7:   Show HN: "Show HN: maestro-fetch – fetch anything (web/PDF/Dropbox/YouTube) in one Python call"
Ongoing:  One blog post per adapter -> maestro.onl internal linking
```

---

## 6. Risks

| Risk | Mitigation |
|------|-----------|
| Docling heavy install (CUDA deps) | Make pdf extra optional; fallback to pdfplumber for basic use |
| Crawl4AI API changes | Pin version; isolate behind WebAdapter so swap is one file |
| Dropbox/GDrive URL format changes | Unit test against regex fixtures; update as formats evolve |
| Whisper local model too slow | Default to OpenAI Whisper API; local model as opt-in |
| LLM provider rate limits in batch | Add per-provider rate limiter with configurable RPS |
