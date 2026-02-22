# maestro-fetch

> Universal data acquisition toolkit for AI agents and developers. Fetch structured data from any URL -- APIs, web pages, PDFs, spreadsheets, cloud storage, video/audio -- with a single function call.

**[maestro.onl](https://maestro.onl)** | [Dataset Catalog](https://ra.maestro.onl/data/datasets) | [Examples](./examples/) | [Professional Data Services](https://ra.maestro.onl/data)

---

## For AI Agents (MCP Server)

maestro-fetch is an MCP (Model Context Protocol) server. Any AI agent that supports MCP (Claude Code, Claude Desktop, Cursor, Windsurf, etc.) can use it as a tool.

### Setup for Claude Code

```bash
pip install maestro-fetch[mcp]
```

Add to your project's `.mcp.json` or `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "maestro-fetch": {
      "command": "maestro-fetch-mcp"
    }
  }
}
```

### Setup for Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "maestro-fetch": {
      "command": "maestro-fetch-mcp"
    }
  }
}
```

### MCP Tools Available

Once connected, the AI agent gets 3 tools:

| Tool | Description | Parameters |
|------|-------------|------------|
| `fetch_url` | Fetch data from any single URL. Auto-detects source type (web, PDF, Excel, CSV, cloud, video). Returns content as markdown. | `url` (required), `output_format` ("markdown"\|"json"\|"csv"), `provider` ("anthropic"\|"openai") |
| `batch_fetch_urls` | Fetch multiple URLs concurrently. Returns list of results. | `urls` (required, list), `output_format`, `concurrency` (default 5) |
| `detect_url_type` | Classify a URL into source type without downloading. | `url` (required) |

### What the AI Agent Can Do With maestro-fetch

```
"Fetch the latest GDP data from the World Bank API for all countries"
  -> AI calls fetch_url with World Bank API endpoint
  -> Gets JSON response as structured markdown

"Download this PDF report and extract the tables"
  -> AI calls fetch_url with PDF URL
  -> Gets tables extracted as markdown/CSV

"Scrape weather data for 30 cities from Open-Meteo"
  -> AI calls batch_fetch_urls with 30 API URLs, concurrency=5
  -> Gets all results in parallel

"What type of data source is this URL?"
  -> AI calls detect_url_type
  -> Returns "web", "doc", "cloud", or "media"
```

### URL Types Auto-Detected

| Pattern | Type | Adapter | What Happens |
|---------|------|---------|--------------|
| `*.pdf` | doc | DocAdapter | Download + extract text and tables (Docling/pdfplumber) |
| `*.xlsx`, `*.csv` | doc | DocAdapter | Download + parse into DataFrames |
| `dropbox.com/*`, `drive.google.com/*` | cloud | CloudAdapter | Resolve share link + download + parse |
| `youtube.com/watch*` | media | MediaAdapter | Download audio + transcribe (yt-dlp + Whisper) |
| Everything else | web | WebAdapter | Headless browser render + extract (Crawl4AI) |

---

## For Developers (Python SDK)

### Install

```bash
pip install maestro-fetch            # core: web + cloud + doc (no API key needed)
pip install maestro-fetch[pdf]       # + advanced PDF/Excel parsing (Docling)
pip install maestro-fetch[media]     # + YouTube/audio transcription (yt-dlp + Whisper)
pip install maestro-fetch[anthropic] # + Claude LLM extraction (requires ANTHROPIC_API_KEY)
pip install maestro-fetch[openai]    # + GPT-4o LLM extraction (requires OPENAI_API_KEY)
pip install maestro-fetch[mcp]       # + MCP server
pip install maestro-fetch[all]       # everything
```

> Core fetching (`fetch`, `batch_fetch`) works without any API key. LLM keys are only needed when using `schema` or `provider` for structured extraction.

### Python API

```python
from maestro_fetch import fetch, batch_fetch

# Fetch any URL -- auto-detects type
result = await fetch("https://example.com/data")
print(result.content)          # markdown text
print(result.source_type)      # "web" | "doc" | "cloud" | "media"
print(result.tables)           # list[pd.DataFrame] (if tables found)
print(result.metadata)         # provenance info

# Fetch with custom headers (for APIs that need User-Agent, auth tokens, etc.)
result = await fetch(
    "https://api.weather.gov/stations/KNYC/observations/latest",
    headers={"User-Agent": "(my-app, me@example.com)"},
)

# Batch fetch with concurrency control
urls = [f"https://api.example.com/data?page={i}" for i in range(100)]
results = await batch_fetch(urls, concurrency=10)

# LLM-powered structured extraction (requires API key)
result = await fetch(
    "https://worldbank.org/report.pdf",
    schema={"country": str, "gdp": float, "year": int},
    provider="anthropic",  # or "openai"
)
```

### FetchResult Object

```python
@dataclass
class FetchResult:
    url: str                    # original URL
    source_type: str            # "web" | "pdf" | "excel" | "cloud" | "media"
    content: str                # extracted text (markdown by default)
    tables: list[pd.DataFrame]  # extracted tables (empty if none)
    metadata: dict              # provenance: timestamps, headers, etc.
    raw_path: Path | None       # path to cached raw file (if saved)
```

### FetchConfig Options

```python
await fetch(
    url,
    provider="anthropic",       # LLM provider for schema extraction
    model=None,                 # model override (default: provider's default)
    schema=None,                # JSON schema for structured extraction
    output_format="markdown",   # "markdown" | "json" | "text"
    cache_dir=".maestro_cache", # local cache directory
    timeout=60,                 # HTTP request timeout (seconds)
    headers=None,               # custom HTTP headers (dict)
    cookies=None,               # custom HTTP cookies (dict)
)
```

### CLI

```bash
# Web page -> Markdown
maestro-fetch "https://example.com/data"

# PDF -> CSV tables
maestro-fetch "https://example.com/report.pdf" --output csv

# Batch fetch from file
maestro-fetch dummy --batch urls.txt --output-dir ./data/

# With LLM extraction
maestro-fetch "https://example.com/page" --schema schema.json --provider anthropic
```

---

## Supported Data Sources

maestro-fetch works with 23+ public data sources out of the box across 6 domains:

| Domain | Sources | Examples |
|--------|---------|----------|
| Weather | 7 | Open-Meteo, NOAA GHCN-Daily, NWS, DWD, CMA, NASA POWER |
| Economics | 4 | FRED, World Bank, OECD, Eurostat |
| Labor | 3 | US BLS, ILO ILOSTAT, Japan e-Stat |
| Politics | 3 | V-Dem, World Bank WGI, Freedom House |
| Environment | 3 | WAQI, EPA AQS, Copernicus CDS |
| Urban | 3 | US Census, OpenStreetMap Overpass, GTFS Transit |

Full catalog with API endpoints, auth requirements, and example queries: **[ra.maestro.onl/data/datasets](https://ra.maestro.onl/data/datasets)**

### Working Examples

| Example | What It Does |
|---------|--------------|
| [`global_weather.py`](./examples/global_weather.py) | Fetch weather for 30 cities across 5 continents via 4 strategies (Open-Meteo, NOAA NWS, GHCN-Daily, DWD) |
| [`china_weather_historical.py`](./examples/china_weather_historical.py) | Download decades of daily weather records for Chinese cities (Open-Meteo Archive + CMA API) |
| [`china_weather.py`](./examples/china_weather.py) | Quick start: 10 Chinese cities current + historical weather |

---

## Architecture

```
URL -> Router (detect_type) -> Adapter (fetch) -> FetchResult
         |                        |
         |                  LLM Provider (optional)
         |
    Cloud: dropbox, gdrive
    Doc:   pdf, xlsx, csv
    Media: youtube, vimeo
    Web:   everything else (Crawl4AI headless browser)
```

### Adapter Priority

1. **CloudAdapter** -- Dropbox/GDrive share links (resolve + download)
2. **DocAdapter** -- PDF, Excel, CSV (direct download + parse)
3. **WebAdapter** -- Everything else (headless browser via Crawl4AI)

### LLM Providers (Optional)

| Provider | Env Variable | Models |
|----------|-------------|--------|
| Anthropic | `ANTHROPIC_API_KEY` | Claude Sonnet, Opus, Haiku |
| OpenAI | `OPENAI_API_KEY` | GPT-4o, GPT-4o-mini |

LLM providers are only used when `schema` parameter is set for structured data extraction.

---

## Professional Data Services

Need custom data pipelines, panel data construction, or large-scale data engineering for academic research? **[RA Data](https://ra.maestro.onl/data)** provides professional data services powered by maestro-fetch -- from single API extraction to multi-source panel datasets.

## License

MIT

---

Built by **[Maestro](https://maestro.onl)** -- Singapore AI product studio.
