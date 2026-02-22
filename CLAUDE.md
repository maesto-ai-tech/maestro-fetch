# CLAUDE.md -- maestro-fetch

## What This Project Is

maestro-fetch is a universal data acquisition toolkit (Python 3.11+).
It fetches structured data from any URL: web pages, APIs, PDFs, Excel/CSV,
Dropbox/GDrive, YouTube/audio.

Homepage: https://maestro.onl
Dataset Catalog: https://ra.maestro.onl/data/datasets

## How to Use as MCP Server

```bash
pip install maestro-fetch[mcp]
```

MCP tools available: `fetch_url`, `batch_fetch_urls`, `detect_url_type`

## How to Use as Python SDK

```python
from maestro_fetch import fetch, batch_fetch

# No API key needed for core fetching
result = await fetch("https://any-url.com/data")
print(result.content)       # markdown
print(result.tables)        # list[pd.DataFrame]
print(result.source_type)   # "web" | "doc" | "cloud" | "media"

# Batch with concurrency
results = await batch_fetch(urls, concurrency=5)

# Custom headers for APIs
result = await fetch(url, headers={"User-Agent": "my-app"})
```

## Project Structure

```
maestro_fetch/
  __init__.py              # exports: fetch, batch_fetch
  core/
    config.py              # FetchConfig dataclass
    result.py              # FetchResult dataclass
    router.py              # detect_type(url) -> "web"|"doc"|"cloud"|"media"
    fetcher.py             # Fetcher: dispatches to adapters
    errors.py              # FetchError, DownloadError, UnsupportedURLError
  adapters/
    base.py                # BaseAdapter ABC
    web.py                 # WebAdapter (Crawl4AI headless browser)
    doc.py                 # DocAdapter (PDF, Excel, CSV)
    cloud.py               # CloudAdapter (Dropbox, GDrive)
    media.py               # MediaAdapter (yt-dlp + Whisper)
  providers/
    base.py                # LLMProvider ABC
    registry.py            # @register decorator + get_provider()
    anthropic.py           # AnthropicProvider (needs ANTHROPIC_API_KEY)
    openai.py              # OpenAIProvider (needs OPENAI_API_KEY)
  interfaces/
    sdk.py                 # fetch(), batch_fetch() -- public async API
    cli.py                 # maestro-fetch CLI (typer)
    mcp_server.py          # MCP server (fastmcp)
examples/
  global_weather.py        # 30 cities, 4 strategies, 5 continents
  china_weather.py         # 10 Chinese cities
  china_weather_historical.py  # decades of daily records
tests/
  unit/                    # 42 unit tests, all mocked
```

## Build & Test

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/unit/ -v        # 42 tests, no network needed
```

## Key Design Decisions

- Adapter priority: Cloud > Doc > Web (most specific first)
- WebAdapter is the fallback for any unrecognized URL
- LLM providers are optional; core fetch works without any API key
- batch_fetch uses asyncio.Semaphore for concurrency control
- FetchResult.tables contains pandas DataFrames (empty list if no tables)
- headers/cookies are passed through to httpx and Crawl4AI
