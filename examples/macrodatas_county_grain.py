#!/usr/bin/env python3
"""
macrodatas_county_grain.py -- Download county grain panel from MacroDatas.cn

MacroDatas article 1147468028:
  - Source: 《中国县域统计年鉴》
  - Coverage: nationwide county-level grain output, 2000-2020
  - Versions: raw, linear-interpolated, regression-filled
  - Free (public data), no login required via POST API

USAGE:
    # Print Baidu Pan download link
    .venv/bin/python examples/macrodatas_county_grain.py

    # With custom article IDs
    .venv/bin/python examples/macrodatas_county_grain.py --aids 1147468028 1082860018

API pattern (discovered 2026-02-28):
    POST https://www.macrodatas.cn/index/article/showdata.html
    body: aid=<base64(article_id)>      # plain article ID, no prefix
    response: {"code":200, "data":{"data":"<baidu_pan_link>"}, "url":""}

Note: Baidu Pan requires account login to download. The link + pwd=mark is the
      extract code. Use a Baidu account or a Baidu Pan scraper to download.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys

import httpx

_API_URL = "https://www.macrodatas.cn/index/article/showdata.html"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Default: county grain output 2000-2020
_DEFAULT_AIDS = ["1147468028"]


async def get_download_link(article_id: str) -> dict:
    """Fetch the Baidu Pan download link for a MacroDatas article.

    Inputs: article_id -- numeric string (e.g. "1147468028")
    Outputs: dict with keys: article_id, link, code, msg
    Invariants: always returns dict, never raises on API error
    """
    aid_b64 = base64.b64encode(article_id.encode()).decode()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.post(
                _API_URL,
                data={"aid": aid_b64},
                headers={
                    "User-Agent": _UA,
                    "Referer": f"https://www.macrodatas.cn/article/{article_id}",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        return {"article_id": article_id, "link": None, "code": -1, "msg": str(exc)}

    data_str = payload.get("data", {}).get("data", "") or payload.get("url", "")
    return {
        "article_id": article_id,
        "link": data_str.strip() if data_str else None,
        "code": payload.get("code"),
        "msg": payload.get("msg", ""),
    }


async def main(article_ids: list[str]) -> None:
    results = await asyncio.gather(*(get_download_link(aid) for aid in article_ids))
    for r in results:
        if r["link"]:
            print(f"[OK] article={r['article_id']}  link={r['link']}")
        else:
            print(
                f"[FAIL] article={r['article_id']}  code={r['code']}  msg={r['msg']}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch MacroDatas.cn Baidu Pan download links")
    parser.add_argument(
        "--aids",
        nargs="+",
        default=_DEFAULT_AIDS,
        metavar="ID",
        help="Article IDs (default: county grain 2000-2020)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.aids))
