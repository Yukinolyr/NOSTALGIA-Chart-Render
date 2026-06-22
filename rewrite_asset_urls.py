#!/usr/bin/env python3
"""Rewrite chart and cover URLs to an external asset base URL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin


ROOT_DIR = Path(__file__).resolve().parent


def external_url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Asset base URL, for example https://assets.example.com")
    parser.add_argument("--index", type=Path, default=ROOT_DIR / "public" / "chart_index_chartonly_webp.json")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "public" / "chart_index_chartonly_r2.json")
    parser.add_argument("--in-place", action="store_true", help="Overwrite --index instead of writing --output")
    args = parser.parse_args()

    data = json.loads(args.index.read_text(encoding="utf-8"))
    data["asset_base_url"] = args.base_url.rstrip("/")
    for chart in data.get("charts", []):
        chart["image_url"] = external_url(args.base_url, chart["image_url"])
        if chart.get("cover_url"):
            chart["cover_url"] = external_url(args.base_url, chart["cover_url"])

    output = args.index if args.in_place else args.output
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
