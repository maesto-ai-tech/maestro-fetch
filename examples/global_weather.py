"""Example: Fetch global weather data -- US, Japan, Europe, China.

Demonstrates 4 data acquisition strategies using maestro-fetch:

  1. Open-Meteo Archive API   -- Global historical, 1940-present, free, no auth
  2. NOAA NWS API             -- US current observations, free, no API key
  3. NOAA GHCN-Daily          -- US historical station data (CSV), free
  4. DWD Open Data            -- German/European historical, free, no auth

All strategies are fully functional with no API keys required.

Usage:
    python examples/global_weather.py
    python examples/global_weather.py --strategy all
    python examples/global_weather.py --strategy open-meteo --start 1980-01-01 --end 2024-12-31
    python examples/global_weather.py --output global_2024.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from maestro_fetch import fetch, batch_fetch

# ---------------------------------------------------------------------------
# City registry: 30 cities across 4 continents
# ---------------------------------------------------------------------------

CITIES: dict[str, tuple[float, float, str]] = {
    # Asia
    "Beijing": (39.9042, 116.4074, "Asia"),
    "Shanghai": (31.2304, 121.4737, "Asia"),
    "Tokyo": (35.6762, 139.6503, "Asia"),
    "Osaka": (34.6937, 135.5023, "Asia"),
    "Seoul": (37.5665, 126.9780, "Asia"),
    "Singapore": (1.3521, 103.8198, "Asia"),
    "Mumbai": (19.0760, 72.8777, "Asia"),
    "Bangkok": (13.7563, 100.5018, "Asia"),
    # Americas
    "New York": (40.7128, -74.0060, "Americas"),
    "Los Angeles": (34.0522, -118.2437, "Americas"),
    "Chicago": (41.8781, -87.6298, "Americas"),
    "Houston": (29.7604, -95.3698, "Americas"),
    "Sao Paulo": (-23.5505, -46.6333, "Americas"),
    "Mexico City": (19.4326, -99.1332, "Americas"),
    "Toronto": (43.6532, -79.3832, "Americas"),
    # Europe
    "London": (51.5074, -0.1278, "Europe"),
    "Paris": (48.8566, 2.3522, "Europe"),
    "Berlin": (52.5200, 13.4050, "Europe"),
    "Madrid": (40.4168, -3.7038, "Europe"),
    "Rome": (41.9028, 12.4964, "Europe"),
    "Amsterdam": (52.3676, 4.9041, "Europe"),
    "Moscow": (55.7558, 37.6173, "Europe"),
    "Stockholm": (59.3293, 18.0686, "Europe"),
    # Africa & Oceania
    "Cairo": (30.0444, 31.2357, "Africa"),
    "Lagos": (6.5244, 3.3792, "Africa"),
    "Nairobi": (-1.2921, 36.8219, "Africa"),
    "Cape Town": (-33.9249, 18.4241, "Africa"),
    "Sydney": (-33.8688, 151.2093, "Oceania"),
    "Melbourne": (-37.8136, 144.9631, "Oceania"),
    "Auckland": (-36.8485, 174.7633, "Oceania"),
}

# NOAA NWS station IDs for US cities (for current observations)
NWS_STATIONS: dict[str, str] = {
    "New York": "KNYC",
    "Los Angeles": "KLAX",
    "Chicago": "KORD",
    "Houston": "KIAH",
}

# DWD station IDs for German cities (for historical CSV download)
DWD_STATIONS: dict[str, str] = {
    "Berlin": "00433",
    "Hamburg": "01975",
    "Munich": "03379",
    "Frankfurt": "01420",
}


@dataclass
class DailyRecord:
    city: str
    region: str
    date: str
    temp_max: float | None = None
    temp_min: float | None = None
    temp_mean: float | None = None
    precipitation_mm: float | None = None
    wind_speed_max: float | None = None


# ---------------------------------------------------------------------------
# Strategy 1: Open-Meteo Archive API (global, 1940-present)
# ---------------------------------------------------------------------------

def _chunk_dates(start: str, end: str, days: int = 365) -> list[tuple[str, str]]:
    fmt = "%Y-%m-%d"
    s = datetime.strptime(start, fmt)
    e = datetime.strptime(end, fmt)
    chunks = []
    while s < e:
        ce = min(s + timedelta(days=days - 1), e)
        chunks.append((s.strftime(fmt), ce.strftime(fmt)))
        s = ce + timedelta(days=1)
    return chunks


async def fetch_open_meteo(
    cities: list[str],
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
) -> list[DailyRecord]:
    """Global historical weather via Open-Meteo Archive (ERA5 reanalysis).

    Coverage: worldwide, 1940-present, ~10km grid.
    Auth: none. Rate limit: 10,000 req/day.
    """
    print(f"\n{'='*60}")
    print(f"Strategy 1: Open-Meteo Archive ({start_date} -> {end_date})")
    print(f"Cities: {len(cities)}")
    print(f"{'='*60}")

    all_records: list[DailyRecord] = []

    for city in cities:
        lat, lon, region = CITIES[city]
        chunks = _chunk_dates(start_date, end_date)
        urls = [
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude={lat}&longitude={lon}"
            f"&start_date={cs}&end_date={ce}"
            f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
            f"precipitation_sum,wind_speed_10m_max"
            f"&timezone=auto"
            for cs, ce in chunks
        ]
        results = await batch_fetch(urls, concurrency=3)

        city_records = 0
        for result in results:
            raw = result.content.strip().strip("`").strip()
            data = json.loads(raw)
            if data.get("error"):
                continue
            daily = data["daily"]
            for i, date in enumerate(daily["time"]):
                all_records.append(DailyRecord(
                    city=city, region=region, date=date,
                    temp_max=daily["temperature_2m_max"][i],
                    temp_min=daily["temperature_2m_min"][i],
                    temp_mean=daily["temperature_2m_mean"][i],
                    precipitation_mm=daily["precipitation_sum"][i],
                    wind_speed_max=daily["wind_speed_10m_max"][i],
                ))
                city_records += 1
        print(f"  {city:15s} ({region:8s}): {city_records:5d} days")

    print(f"  {'TOTAL':15s}          : {len(all_records):5d} records")
    return all_records


# ---------------------------------------------------------------------------
# Strategy 2: NOAA NWS API (US current observations, no auth)
# ---------------------------------------------------------------------------

async def fetch_nws_current() -> list[dict]:
    """Fetch current weather observations from US NWS stations.

    Auth: none (User-Agent header recommended).
    Coverage: US only, current observations.
    """
    print(f"\n{'='*60}")
    print("Strategy 2: NOAA NWS API (US current observations)")
    print(f"{'='*60}")

    observations = []
    for city, station in NWS_STATIONS.items():
        url = f"https://api.weather.gov/stations/{station}/observations/latest"
        result = await fetch(
            url,
            headers={"User-Agent": "(maestro-fetch-example, demo@example.com)"},
        )
        raw = result.content.strip().strip("`").strip()
        try:
            data = json.loads(raw)
            props = data.get("properties", {})
            temp_c = props.get("temperature", {}).get("value")
            wind = props.get("windSpeed", {}).get("value")
            desc = props.get("textDescription", "N/A")
            timestamp = props.get("timestamp", "N/A")[:19]

            print(f"  {city:15s}: {temp_c}C, wind={wind} km/h, {desc} ({timestamp})")
            observations.append({
                "city": city, "temp_c": temp_c,
                "wind_kmh": wind, "description": desc,
                "timestamp": timestamp,
            })
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  {city:15s}: parse error ({e})")

    return observations


# ---------------------------------------------------------------------------
# Strategy 3: NOAA GHCN-Daily by year (bulk CSV download, no auth)
# ---------------------------------------------------------------------------

async def fetch_ghcn_sample() -> None:
    """Demonstrate GHCN-Daily: download station inventory and show US station count.

    The full by-year files are large (100MB+). This demo downloads the
    station inventory to show what's available.
    Auth: none. Format: fixed-width text.
    """
    print(f"\n{'='*60}")
    print("Strategy 3: NOAA GHCN-Daily (station inventory)")
    print(f"{'='*60}")

    url = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
    result = await fetch(url)
    content = result.content

    # Count stations by country prefix
    lines = [l for l in content.split("\n") if l.strip()]
    country_counts: dict[str, int] = {}
    for line in lines:
        # Station IDs: first 2 chars are country code
        if len(line) >= 2:
            cc = line[:2]
            country_counts[cc] = country_counts.get(cc, 0) + 1

    total = sum(country_counts.values())
    print(f"  Total stations worldwide: {total:,}")
    print(f"\n  Top 15 countries by station count:")

    for cc, count in sorted(country_counts.items(), key=lambda x: -x[1])[:15]:
        bar = "#" * (count // 500)
        print(f"    {cc}: {count:6,} {bar}")

    # Show specific countries of interest
    print(f"\n  Countries of interest:")
    for cc, name in [("US", "USA"), ("JA", "Japan"), ("GM", "Germany"),
                     ("CH", "China"), ("UK", "UK"), ("FR", "France"),
                     ("AS", "Australia"), ("IN", "India"), ("BR", "Brazil")]:
        count = country_counts.get(cc, 0)
        print(f"    {name:12s} ({cc}): {count:,} stations")


# ---------------------------------------------------------------------------
# Strategy 4: DWD Open Data (German weather, no auth, direct CSV)
# ---------------------------------------------------------------------------

async def fetch_dwd_stations() -> None:
    """Fetch DWD (German Weather Service) open station data.

    Auth: none. Format: fixed-width text / ZIP archives.
    Coverage: Germany primary, some European data.
    Historical: 1800s-present (varies by station).
    """
    print(f"\n{'='*60}")
    print("Strategy 4: DWD Open Data (German weather stations)")
    print(f"{'='*60}")

    url = (
        "https://opendata.dwd.de/climate_environment/CDC/"
        "observations_germany/climate/daily/kl/recent/"
        "KL_Tageswerte_Beschreibung_Stationen.txt"
    )
    result = await fetch(url)
    content = result.content

    # Parse the fixed-width station list
    lines = content.split("\n")
    # Skip header lines (first 2-3 lines)
    data_lines = [l for l in lines[2:] if l.strip() and not l.startswith("-")]

    stations = []
    for line in data_lines:
        parts = line.split()
        if len(parts) >= 7:
            stations.append({
                "id": parts[0],
                "from": parts[1],
                "to": parts[2],
                "height": parts[3],
                "lat": parts[4],
                "lon": parts[5],
                "name": " ".join(parts[6:-2]) if len(parts) > 8 else parts[6],
            })

    print(f"  Active DWD stations: {len(stations)}")
    print(f"\n  Sample stations:")
    for s in stations[:10]:
        print(f"    [{s['id']}] {s['name']:25s} ({s['lat']}N, {s['lon']}E) "
              f"height={s['height']}m, data: {s['from']}-{s['to']}")

    print(f"\n  Download pattern for station data:")
    print(f"    https://opendata.dwd.de/climate_environment/CDC/")
    print(f"    observations_germany/climate/daily/kl/historical/")
    print(f"    tageswerte_KL_{{STATION_ID}}_{{FROM}}_{{TO}}_hist.zip")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_csv(records: list[DailyRecord], path: str) -> None:
    fields = [
        "city", "region", "date", "temp_max", "temp_min",
        "temp_mean", "precipitation_mm", "wind_speed_max",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({f: getattr(r, f) for f in fields})
    print(f"\nExported {len(records)} records to {path}")


def print_summary(records: list[DailyRecord]) -> None:
    if not records:
        return

    print(f"\n{'='*60}")
    print(f"Global Summary: {len(records):,} daily records")
    print(f"{'='*60}")

    # Per-region stats
    regions: dict[str, list[DailyRecord]] = {}
    for r in records:
        regions.setdefault(r.region, []).append(r)

    print(f"\n{'Region':10s} {'Cities':>6} {'Records':>8} {'Avg C':>7} {'Rain mm':>8}")
    print("-" * 45)
    for region in sorted(regions.keys()):
        recs = regions[region]
        temps = [r.temp_mean for r in recs if r.temp_mean is not None]
        precip = [r.precipitation_mm for r in recs if r.precipitation_mm is not None]
        n_cities = len(set(r.city for r in recs))
        avg_t = sum(temps) / len(temps) if temps else 0
        total_p = sum(precip)
        print(f"{region:10s} {n_cities:6d} {len(recs):8,} {avg_t:7.1f} {total_p:8.0f}")

    # Per-city temperature ranking
    city_temps: dict[str, list[float]] = {}
    for r in records:
        if r.temp_mean is not None:
            city_temps.setdefault(r.city, []).append(r.temp_mean)

    print(f"\nCity temperature ranking (annual mean):")
    ranked = sorted(city_temps.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
    for i, (city, temps) in enumerate(ranked, 1):
        avg = sum(temps) / len(temps)
        region = CITIES[city][2]
        print(f"  {i:2d}. {city:15s} ({region:8s}): {avg:5.1f} C")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch global weather data")
    p.add_argument("--strategy", default="all",
                   choices=["all", "open-meteo", "nws", "ghcn", "dwd"])
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2024-12-31")
    p.add_argument("--cities", nargs="*", help="Specific cities (default: all 30)")
    p.add_argument("--output", help="Export Open-Meteo data to CSV")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    strategy = args.strategy
    cities = args.cities or list(CITIES.keys())

    # Validate
    for c in cities:
        if c not in CITIES:
            print(f"Unknown city: {c}. Available: {', '.join(CITIES.keys())}")
            sys.exit(1)

    records: list[DailyRecord] = []

    if strategy in ("all", "open-meteo"):
        records = await fetch_open_meteo(cities, args.start, args.end)

    if strategy in ("all", "nws"):
        await fetch_nws_current()

    if strategy in ("all", "ghcn"):
        await fetch_ghcn_sample()

    if strategy in ("all", "dwd"):
        await fetch_dwd_stations()

    if records:
        print_summary(records)

    if args.output and records:
        export_csv(records, args.output)


if __name__ == "__main__":
    asyncio.run(main())
