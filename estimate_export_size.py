#!/usr/bin/env python3
"""Estimate final batch-export size from the current chart index and files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def format_bytes(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=Path("public/chart_index.json"))
    parser.add_argument("--format", choices=("png", "webp"), default=None, help="only count files with this extension")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.index.read_text(encoding="utf-8"))
    charts = data.get("charts", [])
    requested = int(data.get("requested_count") or len(charts))
    completed = int(data.get("completed_count") or len(charts))

    counted = 0
    bytes_total = 0
    missing = 0
    for chart in charts:
        path = Path(chart["output_path"])
        if args.format and path.suffix.lower() != f".{args.format}":
            continue
        if path.exists():
            bytes_total += path.stat().st_size
            counted += 1
        else:
            missing += 1

    average = bytes_total / counted if counted else 0
    projected = average * requested if requested else bytes_total

    print(f"index: {args.index}")
    print(f"image_format: {data.get('image_format', 'unknown')}")
    print(f"requested: {requested}")
    print(f"completed_in_index: {completed}")
    print(f"files_counted: {counted}")
    print(f"missing_indexed_files: {missing}")
    print(f"current_size: {format_bytes(bytes_total)}")
    print(f"average_file_size: {format_bytes(average)}")
    print(f"projected_full_size: {format_bytes(projected)}")


if __name__ == "__main__":
    main()
