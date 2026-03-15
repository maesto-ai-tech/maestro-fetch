#!/usr/bin/env python3
"""
baidu_get_bduss.py -- Extract BDUSS cookie from a running Chrome/Chromium instance
via Chrome DevTools Protocol (CDP), then optionally download a Baidu Pan share link.

REQUIREMENTS:
  Chrome must be launched with --remote-debugging-port=9222. Do one of:
    Option A: Close Chrome, then run:
      open -a "Google Chrome" --args --remote-debugging-port=9222
    Option B: Add --remote-debugging-port=9222 to Chrome's launch flags in system prefs.

USAGE:
  # Step 1: launch Chrome with CDP port (see above)
  # Step 2: log in to pan.baidu.com in that Chrome
  # Step 3: run this script

  # Print BDUSS (copy to .env)
  .venv/bin/python examples/baidu_get_bduss.py

  # Download a share link directly (no manual copy needed)
  .venv/bin/python examples/baidu_get_bduss.py \
    --url "https://pan.baidu.com/s/1q_q2rxfI31Dh2G-IlfYX6g?pwd=mark" \
    --output-dir ./data/

  # Save BDUSS to .env.local automatically
  .venv/bin/python examples/baidu_get_bduss.py --save-env

DEPENDENCIES: playwright (pip install playwright)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


async def get_bduss(cdp_url: str = "http://localhost:9222") -> str:
    """Connect to a running Chrome via CDP and extract BDUSS cookie.

    Raises RuntimeError if Chrome is not reachable or not logged in to Baidu.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is required: pip install playwright") from exc

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            raise RuntimeError(
                f"Cannot connect to Chrome at {cdp_url}.\n"
                "Launch Chrome with: open -a 'Google Chrome' --args --remote-debugging-port=9222"
            ) from exc

        contexts = browser.contexts
        if not contexts:
            raise RuntimeError("No browser context found. Open a tab in the connected Chrome.")

        # Search all contexts for the BDUSS cookie
        for context in contexts:
            cookies = await context.cookies("https://pan.baidu.com")
            for c in cookies:
                if c["name"] == "BDUSS":
                    await browser.close()
                    return c["value"]

        await browser.close()
        raise RuntimeError(
            "BDUSS cookie not found. "
            "Make sure you are logged in to pan.baidu.com in the connected Chrome."
        )


async def download_share(url: str, bduss: str, output_dir: Path) -> Path:
    """Download a Baidu Pan share link using the given BDUSS cookie.

    Returns the path to the downloaded file.
    """
    import asyncio, sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from maestro_fetch import fetch
    from maestro_fetch.core.config import FetchConfig

    output_dir.mkdir(parents=True, exist_ok=True)
    result = await fetch(
        url,
        cookies={"BDUSS": bduss},
        cache_dir=output_dir,
    )
    if result.raw_path and result.raw_path.exists():
        return result.raw_path
    # Fallback: content written to a generic file
    out = output_dir / "download"
    out.write_text(result.content, encoding="utf-8")
    return out


async def main(args: argparse.Namespace) -> None:
    try:
        bduss = await get_bduss(args.cdp_url)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] BDUSS extracted ({len(bduss)} chars)")
    print(f"     First 20 chars: {bduss[:20]}...")

    if args.save_env:
        env_path = Path(".env.local")
        existing = env_path.read_text() if env_path.exists() else ""
        if "BAIDU_BDUSS=" in existing:
            import re
            existing = re.sub(r"BAIDU_BDUSS=.*\n?", f"BAIDU_BDUSS={bduss}\n", existing)
        else:
            existing += f"\nBAIDU_BDUSS={bduss}\n"
        env_path.write_text(existing)
        print(f"[OK] Saved BAIDU_BDUSS to {env_path}")
    else:
        print(f"\nTo use maestro-fetch with Baidu Pan, run:")
        print(f'  export BAIDU_BDUSS="{bduss}"')
        print(f"  # or add to your .env / shell profile")

    if args.url:
        output_dir = Path(args.output_dir)
        print(f"\n[INFO] Downloading {args.url} -> {output_dir}/")
        try:
            path = await download_share(args.url, bduss, output_dir)
            print(f"[OK] Saved to {path}")
        except Exception as exc:
            print(f"[ERROR] Download failed: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract BDUSS from running Chrome and optionally download Baidu Pan links."
    )
    parser.add_argument(
        "--cdp-url",
        default="http://localhost:9222",
        help="Chrome DevTools Protocol URL (default: http://localhost:9222)",
    )
    parser.add_argument("--url", help="Baidu Pan share URL to download immediately")
    parser.add_argument(
        "--output-dir",
        default="./downloads",
        help="Output directory for downloaded files (default: ./downloads)",
    )
    parser.add_argument(
        "--save-env",
        action="store_true",
        help="Write BAIDU_BDUSS to .env.local automatically",
    )
    asyncio.run(main(parser.parse_args()))
