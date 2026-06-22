#!/usr/bin/env python3
"""Convert exported chart PNG images to WebP and write a matching chart index."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parent


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def source_path_for(chart: dict[str, Any], input_dir: Path) -> Path:
    output_path = chart.get("output_path")
    if output_path:
        path = Path(output_path)
        if path.exists():
            return path
    image_url = str(chart["image_url"]).lstrip("/")
    parts = Path(image_url).parts
    if parts and parts[0] == input_dir.name:
        return input_dir.joinpath(*parts[1:])
    return ROOT_DIR / "public" / image_url


def target_path_for(chart: dict[str, Any], output_dir: Path) -> Path:
    return output_dir / chart["basename"] / f"{chart['difficulty_code']}.webp"


def convert_one(chart: dict[str, Any], input_dir: Path, output_dir: Path, quality: int, force: bool) -> tuple[str, bool, int]:
    source = source_path_for(chart, input_dir)
    target = target_path_for(chart, output_dir)
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists() and not force and target.stat().st_mtime >= source.stat().st_mtime:
        return str(target), False, target.stat().st_size

    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.save(target, "WEBP", quality=quality, method=6)
    return str(target), True, target.stat().st_size


def rewrite_index(data: dict[str, Any], output_dir: Path, url_prefix: str) -> dict[str, Any]:
    rewritten = dict(data)
    rewritten["image_format"] = "webp"
    rewritten["output_dir"] = str(output_dir)
    rewritten["url_prefix"] = url_prefix.rstrip("/")
    rewritten["charts"] = []
    for chart in data.get("charts", []):
        next_chart = dict(chart)
        target = target_path_for(next_chart, output_dir)
        next_chart["image_url"] = f"{url_prefix.rstrip('/')}/{next_chart['basename']}/{next_chart['difficulty_code']}.webp"
        next_chart["output_path"] = str(target)
        rewritten["charts"].append(next_chart)
    return rewritten


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=ROOT_DIR / "public" / "chart_index_chartonly.json")
    parser.add_argument("--input-dir", type=Path, default=ROOT_DIR / "public" / "charts_chartonly")
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "public" / "charts_chartonly_webp")
    parser.add_argument("--index-output", type=Path, default=ROOT_DIR / "public" / "chart_index_chartonly_webp.json")
    parser.add_argument("--url-prefix", default="/charts_chartonly_webp")
    parser.add_argument("--quality", type=positive_int, default=92)
    parser.add_argument("--workers", type=positive_int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.index.read_text(encoding="utf-8"))
    charts = data.get("charts", [])
    converted = 0
    skipped = 0
    total_size = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(convert_one, chart, args.input_dir, args.output_dir, args.quality, args.force)
            for chart in charts
        ]
        for index, future in enumerate(as_completed(futures), start=1):
            _, did_convert, size = future.result()
            total_size += size
            if did_convert:
                converted += 1
            else:
                skipped += 1
            if index % 50 == 0 or index == len(futures):
                print(f"{index}/{len(futures)} converted={converted} skipped={skipped}", flush=True)

    rewritten = rewrite_index(data, args.output_dir, args.url_prefix)
    args.index_output.write_text(json.dumps(rewritten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "charts": len(charts),
                "converted": converted,
                "skipped": skipped,
                "output_dir": str(args.output_dir),
                "index_output": str(args.index_output),
                "quality": args.quality,
                "bytes": total_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
