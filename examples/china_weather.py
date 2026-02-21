"""Example: Fetch China weather data using maestro-fetch.

Demonstrates 3 real data acquisition strategies:
  1. Open-Meteo CMA API  -- JSON API, no auth, CMA GRAPES model data
  2. weather.com.cn       -- HTML scraping, 40-day forecast + history
  3. data.cma.cn          -- CMA official portal, dataset catalog scraping

Usage:
    python examples/china_weather.py
    python examples/china_weather.py --cities Beijing Shanghai
    python examples/china_weather.py --strategy all
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from dataclasses import dataclass

# maestro-fetch public SDK
from maestro_fetch import fetch, batch_fetch

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

CITY_COORDS: dict[str, tuple[float, float]] = {
    "Beijing": (39.9042, 116.4074),
    "Shanghai": (31.2304, 121.4737),
    "Guangzhou": (23.1291, 113.2644),
    "Shenzhen": (22.5431, 114.0579),
    "Chengdu": (30.5728, 104.0668),
    "Wuhan": (30.5928, 114.3055),
    "Hangzhou": (30.2741, 120.1551),
    "Harbin": (45.8038, 126.5350),
    "Lhasa": (29.6520, 91.1721),
    "Urumqi": (43.8256, 87.6168),
}

# weather.com.cn city codes (subset)
WEATHER_COM_CODES: dict[str, str] = {
    "Beijing": "101010100",
    "Shanghai": "101020100",
    "Guangzhou": "101280101",
    "Shenzhen": "101280601",
    "Chengdu": "101270101",
    "Wuhan": "101200101",
    "Hangzhou": "101210101",
    "Harbin": "101050101",
    "Lhasa": "101140101",
    "Urumqi": "101130101",
}


@dataclass
class DailyWeather:
    city: str
    date: str
    temp_max: float | None
    temp_min: float | None
    precipitation_mm: float | None


# ---------------------------------------------------------------------------
# Strategy 1: Open-Meteo CMA GRAPES API (JSON, no auth)
# ---------------------------------------------------------------------------

async def fetch_via_open_meteo(
    cities: list[str],
    past_days: int = 30,
) -> list[DailyWeather]:
    """Fetch weather from Open-Meteo CMA GRAPES model.

    Pros: structured JSON, no auth, free for non-commercial use.
    Cons: rolling window only (~3 months), not deep historical.
    """
    urls = []
    city_names = []
    for city in cities:
        lat, lon = CITY_COORDS[city]
        url = (
            f"https://api.open-meteo.com/v1/cma?"
            f"latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&timezone=Asia/Shanghai"
            f"&past_days={past_days}&forecast_days=0"
        )
        urls.append(url)
        city_names.append(city)

    results = await batch_fetch(urls, concurrency=3)

    records: list[DailyWeather] = []
    for city, result in zip(city_names, results):
        # Open-Meteo returns JSON wrapped in markdown code fences by crawl4ai
        raw = result.content.strip().strip("`").strip()
        data = json.loads(raw)
        daily = data["daily"]
        for i, date in enumerate(daily["time"]):
            records.append(DailyWeather(
                city=city,
                date=date,
                temp_max=daily["temperature_2m_max"][i],
                temp_min=daily["temperature_2m_min"][i],
                precipitation_mm=daily["precipitation_sum"][i],
            ))
    return records


# ---------------------------------------------------------------------------
# Strategy 2: Scrape weather.com.cn (HTML, public, JS-rendered)
# ---------------------------------------------------------------------------

async def fetch_via_weather_com(cities: list[str]) -> dict[str, str]:
    """Scrape weather.com.cn 40-day forecast pages.

    Returns raw markdown content per city for downstream parsing.
    Pros: official China Weather Network, rich content.
    Cons: HTML scraping, content structure may change.
    """
    urls = []
    city_names = []
    for city in cities:
        code = WEATHER_COM_CODES.get(city)
        if code:
            urls.append(f"http://www.weather.com.cn/weather40d/{code}.shtml")
            city_names.append(city)

    results = await batch_fetch(urls, concurrency=2)

    output: dict[str, str] = {}
    for city, result in zip(city_names, results):
        output[city] = result.content
    return output


# ---------------------------------------------------------------------------
# Strategy 3: Scrape data.cma.cn catalog (official CMA portal)
# ---------------------------------------------------------------------------

@dataclass
class CMADataset:
    name: str
    url: str
    data_code: str


async def fetch_cma_catalog() -> list[CMADataset]:
    """Scrape the CMA data portal to discover available datasets.

    This demonstrates: scrape a catalog page -> extract structured links.
    Actual data download from CMA requires registration (free).
    """
    result = await fetch("https://data.cma.cn/")
    content = result.content

    # Extract dataset detail links with data codes
    pattern = r"https://data\.cma\.cn/data/detail/dataCode/([\w.]+)\.html"
    matches = re.findall(pattern, content)

    # Also extract dataset names (Chinese text before the links)
    datasets: list[CMADataset] = []
    seen = set()
    for code in matches:
        if code in seen:
            continue
        seen.add(code)
        url = f"https://data.cma.cn/data/detail/dataCode/{code}.html"
        # Try to find the name near this URL in the content
        idx = content.find(url)
        name = code  # fallback
        if idx > 0:
            # Look backwards for the link text (typically in [...](url) format)
            before = content[max(0, idx - 200):idx]
            # Find the last [...] before the URL
            bracket_match = re.findall(r"\[([^\]]+)\]", before)
            if bracket_match:
                name = bracket_match[-1]
        datasets.append(CMADataset(name=name, url=url, data_code=code))

    return datasets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def print_table(records: list[DailyWeather]) -> None:
    """Print weather records as a simple table."""
    print(f"{'City':<12} {'Date':<12} {'Max C':>6} {'Min C':>6} {'Rain mm':>8}")
    print("-" * 48)
    for r in records:
        tmax = f"{r.temp_max:.1f}" if r.temp_max is not None else "N/A"
        tmin = f"{r.temp_min:.1f}" if r.temp_min is not None else "N/A"
        rain = f"{r.precipitation_mm:.1f}" if r.precipitation_mm is not None else "N/A"
        print(f"{r.city:<12} {r.date:<12} {tmax:>6} {tmin:>6} {rain:>8}")


async def main() -> None:
    cities = sys.argv[1:] if len(sys.argv) > 1 else ["Beijing", "Shanghai", "Guangzhou"]

    # Validate city names
    for city in cities:
        if city not in CITY_COORDS:
            print(f"Unknown city: {city}. Available: {', '.join(CITY_COORDS.keys())}")
            sys.exit(1)

    # --- Strategy 1: Open-Meteo CMA API ---
    print("=" * 60)
    print("Strategy 1: Open-Meteo CMA GRAPES API (last 7 days)")
    print("=" * 60)
    records = await fetch_via_open_meteo(cities, past_days=7)
    print_table(records)
    print(f"\nTotal records: {len(records)}")

    # --- Strategy 2: weather.com.cn scraping ---
    print("\n" + "=" * 60)
    print("Strategy 2: weather.com.cn (40-day forecast page)")
    print("=" * 60)
    pages = await fetch_via_weather_com(cities)
    for city, content in pages.items():
        print(f"\n[{city}] scraped {len(content)} chars")
        # Extract temperature mentions
        temps = re.findall(r"(-?\d+)℃", content)
        if temps:
            nums = [int(t) for t in temps]
            print(f"  Temperature range found: {min(nums)}~{max(nums)} C")
            print(f"  Temperature data points: {len(temps)}")

    # --- Strategy 3: CMA catalog discovery ---
    print("\n" + "=" * 60)
    print("Strategy 3: data.cma.cn dataset catalog")
    print("=" * 60)
    datasets = await fetch_cma_catalog()
    print(f"Discovered {len(datasets)} datasets:\n")
    for ds in datasets:
        print(f"  [{ds.data_code}] {ds.name}")
        print(f"    -> {ds.url}")

    print("\n" + "=" * 60)
    print("Done. All data fetched via maestro-fetch SDK.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
