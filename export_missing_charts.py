#!/usr/bin/env python3
"""Export charts present in one library index but missing from another chart index."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from batch_export import build_index_payload, iter_chart_entries, render_chart_entry, render_chart_task, write_index
from NOSTALGIAChartRender.theme import DEFAULT_THEME


ROOT_DIR = Path(__file__).resolve().parent


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return parsed


def chart_key(basename: str, difficulty_code: str) -> tuple[str, str]:
    return basename.casefold(), difficulty_code


def load_existing_charts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("charts", [])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-index", type=Path, default=ROOT_DIR / "library_index.json")
    parser.add_argument("--existing-index", type=Path, default=ROOT_DIR / "public" / "chart_index_chartonly_webp.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "public" / "charts_chartonly_webp")
    parser.add_argument("--assets-dir", type=Path, default=ROOT_DIR / "assets")
    parser.add_argument("--index-output", type=Path, default=ROOT_DIR / "public" / "chart_index_chartonly_webp.json")
    parser.add_argument("--format", choices=("png", "webp"), default="webp")
    parser.add_argument("--url-prefix", default="/charts_chartonly_webp")
    parser.add_argument("--webp-quality", type=positive_int, default=82)
    parser.add_argument("--workers", type=positive_int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--track-width", type=positive_int, default=DEFAULT_THEME.track_width)
    parser.add_argument("--resize", type=positive_float, default=DEFAULT_THEME.resize)
    parser.add_argument("--note-height", type=positive_int, default=DEFAULT_THEME.note_height)
    parser.add_argument("--note-width-scale", type=positive_float, default=DEFAULT_THEME.note_width_scale)
    parser.add_argument("--note-corner-radius", type=non_negative_int, default=DEFAULT_THEME.note_corner_radius)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    library_index = json.loads(args.library_index.read_text(encoding="utf-8"))
    existing_charts = load_existing_charts(args.existing_index)
    existing_by_key = {
        chart_key(chart["basename"], chart["difficulty_code"]): chart
        for chart in existing_charts
    }

    all_entries = list(iter_chart_entries(library_index))
    missing_entries: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for input_index, (song, difficulty) in enumerate(all_entries, start=1):
        key = chart_key(song["basename"], difficulty["difficulty_code"])
        if key not in existing_by_key:
            missing_entries.append((input_index, song, difficulty))

    theme_params = {
        "track_width": args.track_width,
        "resize": args.resize,
        "note_height": args.note_height,
        "note_width_scale": args.note_width_scale,
        "note_corner_radius": args.note_corner_radius,
    }
    theme = replace(DEFAULT_THEME, **theme_params)

    print(
        f"[INFO] library charts={len(all_entries)} existing={len(existing_by_key)} missing={len(missing_entries)}",
        flush=True,
    )

    rendered: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    completed = 0

    def handle_result(
        input_index: int,
        song: dict[str, Any],
        difficulty: dict[str, Any],
        result: dict[str, Any] | None,
        exc: Exception | None,
    ) -> None:
        nonlocal completed
        completed += 1
        label = f"{song['basename']} {difficulty['difficulty_code']}"
        if exc is None and result is not None:
            result["input_index"] = input_index
            rendered.append(result)
            print(f"[{completed}/{len(missing_entries)}] {result['status']}: {label}", flush=True)
        else:
            failures.append({
                "input_index": input_index,
                "basename": song["basename"],
                "difficulty_code": difficulty["difficulty_code"],
                "error": str(exc),
            })
            print(f"[{completed}/{len(missing_entries)}] failed: {label}: {exc}", flush=True)

    if args.workers == 1:
        for input_index, song, difficulty in missing_entries:
            try:
                result = render_chart_entry(
                    song=song,
                    difficulty=difficulty,
                    output_dir=args.output_dir,
                    assets_dir=args.assets_dir,
                    theme=theme,
                    force=args.force,
                    image_format=args.format,
                    webp_quality=args.webp_quality,
                    url_prefix=args.url_prefix,
                )
                handle_result(input_index, song, difficulty, result, None)
            except Exception as exc:
                handle_result(input_index, song, difficulty, None, exc)
    else:
        tasks = [
            {
                "input_index": input_index,
                "song": song,
                "difficulty": difficulty,
                "output_dir": str(args.output_dir),
                "assets_dir": str(args.assets_dir),
                "theme": theme_params,
                "force": args.force,
                "image_format": args.format,
                "webp_quality": args.webp_quality,
                "url_prefix": args.url_prefix,
            }
            for input_index, song, difficulty in missing_entries
        ]
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(render_chart_task, task): task for task in tasks}
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                    handle_result(task["input_index"], task["song"], task["difficulty"], result, None)
                except Exception as exc:
                    handle_result(task["input_index"], task["song"], task["difficulty"], None, exc)

    merged_by_key = dict(existing_by_key)
    for chart in rendered:
        merged_by_key[chart_key(chart["basename"], chart["difficulty_code"])] = chart

    class PayloadArgs:
        library_index = args.library_index
        assets_dir = args.assets_dir
        output_dir = args.output_dir
        format = args.format
        url_prefix = args.url_prefix

    payload = build_index_payload(
        args=PayloadArgs,
        theme_params=theme_params,
        requested_count=len(all_entries),
        exported=list(merged_by_key.values()),
        failures=failures,
        completed_count=len(merged_by_key),
    )
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["merged_from_existing_index"] = str(args.existing_index)
    payload["newly_rendered_count"] = sum(1 for chart in rendered if chart["status"] == "rendered")

    write_index(args.index_output, payload, pretty=args.pretty)
    print(f"[INFO] wrote merged index: {args.index_output}", flush=True)

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
