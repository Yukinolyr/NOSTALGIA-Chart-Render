#!/usr/bin/env python3
"""
Batch-export pre-rendered NOSTALGIA chart preview images.

Default behavior is intentionally small: export 10 charts to public/charts/
and write public/chart_index.json for frontend use.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from NOSTALGIAChartRender import Renderer, parse_chart, set_assets_dir
from NOSTALGIAChartRender.theme import DEFAULT_THEME, Theme


Image.MAX_IMAGE_PIXELS = None

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_LIBRARY_INDEX = Path(os.environ.get("NOSTALGIA_LIBRARY_INDEX", ROOT_DIR / "library_index.json"))
DEFAULT_ASSETS_DIR = Path(os.environ.get("NOSTALGIA_ASSETS_DIR", ROOT_DIR / "assets"))
DEFAULT_OUTPUT_DIR = Path(os.environ.get("NOSTALGIA_BATCH_OUTPUT_DIR", ROOT_DIR / "public" / "charts"))
DEFAULT_INDEX_PATH = Path(os.environ.get("NOSTALGIA_BATCH_INDEX", ROOT_DIR / "public" / "chart_index.json"))
DEFAULT_URL_PREFIX = os.environ.get("NOSTALGIA_BATCH_URL_PREFIX", "/charts")


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be greater than or equal to 0")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def iter_chart_entries(library_index: dict[str, Any]):
    for song in library_index["songs"]:
        difficulties = sorted(song["difficulties"].values(), key=lambda item: int(item["difficulty_number"]))
        for difficulty in difficulties:
            yield song, difficulty


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def chart_output_path(output_dir: Path, basename: str, difficulty_code: str, image_format: str) -> Path:
    return output_dir / basename / f"{difficulty_code}.{image_format}"


def chart_url(basename: str, difficulty_code: str, image_format: str, url_prefix: str) -> str:
    return f"{url_prefix.rstrip('/')}/{basename}/{difficulty_code}.{image_format}"


def display_level_for_export(difficulty: dict[str, Any]) -> str:
    if difficulty.get("difficulty_code") == "03real" or difficulty.get("difficulty_name") == "Real":
        return difficulty.get("display_level", "")
    return difficulty.get("display_level") or difficulty.get("level", "")


def render_chart_entry(
    *,
    song: dict[str, Any],
    difficulty: dict[str, Any],
    output_dir: Path,
    assets_dir: Path,
    theme: Theme,
    force: bool,
    image_format: str,
    webp_quality: int,
    url_prefix: str,
) -> dict[str, Any]:
    set_assets_dir(str(assets_dir))
    basename = song["basename"]
    difficulty_code = difficulty["difficulty_code"]
    output_path = chart_output_path(output_dir, basename, difficulty_code, image_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    xml_path = Path(difficulty["xml_path"])
    chart = parse_chart(str(xml_path))
    rendered = force or not output_path.exists()
    save_kwargs: dict[str, Any] = {}
    if image_format == "webp":
        save_kwargs = {"format": "WEBP", "quality": webp_quality, "method": 6}

    if rendered:
        renderer = Renderer(
            chart=chart,
            song_title=song.get("title", basename),
            artist=song.get("artist", ""),
            difficulty=difficulty["difficulty_name"],
            cover_path=song.get("cover_path") or None,
            level=display_level_for_export(difficulty),
            theme=theme,
        )
        renderer.save(str(output_path), **save_kwargs)
        size = renderer.size
    else:
        try:
            size = image_size(output_path)
        except Exception:
            renderer = Renderer(
                chart=chart,
                song_title=song.get("title", basename),
                artist=song.get("artist", ""),
                difficulty=difficulty["difficulty_name"],
                cover_path=song.get("cover_path") or None,
                level=display_level_for_export(difficulty),
                theme=theme,
            )
            renderer.save(str(output_path), **save_kwargs)
            size = renderer.size
            rendered = True

    return {
        "basename": basename,
        "title": song.get("title", basename),
        "artist": song.get("artist", ""),
        "cover_url": song.get("cover_url", ""),
        "difficulty_number": difficulty["difficulty_number"],
        "difficulty_code": difficulty_code,
        "difficulty_name": difficulty["difficulty_name"],
        "level": difficulty.get("level", ""),
        "display_level": display_level_for_export(difficulty),
        "source": difficulty.get("source", ""),
        "xml_path": str(xml_path),
        "image_url": chart_url(basename, difficulty_code, image_format, url_prefix),
        "output_path": str(output_path),
        "image_size": list(size),
        "raw_note_count": chart.raw_note_count,
        "visible_note_count": chart.visible_note_count,
        "hidden_note_count": chart.hidden_note_count,
        "velocity_zone_count": len(chart.velocity_zone_list),
        "duration_sec": chart.end_time / 1000,
        "status": "rendered" if rendered else "skipped",
    }


def render_chart_task(task: dict[str, Any]) -> dict[str, Any]:
    theme = replace(DEFAULT_THEME, **task["theme"])
    return render_chart_entry(
        song=task["song"],
        difficulty=task["difficulty"],
        output_dir=Path(task["output_dir"]),
        assets_dir=Path(task["assets_dir"]),
        theme=theme,
        force=task["force"],
        image_format=task["image_format"],
        webp_quality=task["webp_quality"],
        url_prefix=task["url_prefix"],
    )


def write_index(path: Path, payload: dict[str, Any], *, pretty: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def build_index_payload(
    *,
    args: argparse.Namespace,
    theme_params: dict[str, Any],
    requested_count: int,
    exported: list[dict[str, Any]],
    failures: list[dict[str, str]],
    completed_count: int,
) -> dict[str, Any]:
    sorted_exported = sorted(exported, key=lambda item: item["input_index"])
    sorted_failures = sorted(failures, key=lambda item: item["input_index"])
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_library_index": str(args.library_index),
        "assets_dir": str(args.assets_dir),
        "output_dir": str(args.output_dir),
        "image_format": args.format,
        "url_prefix": args.url_prefix,
        "theme": theme_params,
        "requested_count": requested_count,
        "completed_count": completed_count,
        "exported_count": len(sorted_exported),
        "rendered_count": sum(1 for item in sorted_exported if item["status"] == "rendered"),
        "skipped_count": sum(1 for item in sorted_exported if item["status"] == "skipped"),
        "failure_count": len(sorted_failures),
        "charts": sorted_exported,
        "failures": sorted_failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-index", type=Path, default=DEFAULT_LIBRARY_INDEX)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--index-output", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--all", action="store_true", help="export all chart entries after offset")
    parser.add_argument("--limit", type=positive_int, default=10, help="maximum number of charts to export")
    parser.add_argument("--offset", type=non_negative_int, default=0, help="number of chart entries to skip first")
    parser.add_argument("--workers", type=positive_int, default=1, help="parallel worker processes")
    parser.add_argument("--checkpoint-every", type=positive_int, default=10, help="write JSON index every N completed charts")
    parser.add_argument("--force", action="store_true", help="re-render existing output images")
    parser.add_argument("--format", choices=("png", "webp"), default="png", help="image output format")
    parser.add_argument("--url-prefix", default=DEFAULT_URL_PREFIX, help="URL prefix used in image_url entries")
    parser.add_argument("--webp-quality", type=positive_int, default=82, help="WebP quality for --format webp")
    parser.add_argument("--pretty", action="store_true", help="write indented JSON index")
    parser.add_argument("--track-width", type=positive_int, default=DEFAULT_THEME.track_width)
    parser.add_argument("--resize", type=positive_float, default=DEFAULT_THEME.resize)
    parser.add_argument("--note-height", type=positive_int, default=DEFAULT_THEME.note_height)
    parser.add_argument("--note-width-scale", type=positive_float, default=DEFAULT_THEME.note_width_scale)
    parser.add_argument("--note-corner-radius", type=non_negative_int, default=DEFAULT_THEME.note_corner_radius)
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.library_index.exists():
        raise SystemExit(f"[ERROR] library index not found: {args.library_index}")
    if not args.assets_dir.is_dir():
        raise SystemExit(f"[ERROR] assets directory not found: {args.assets_dir}")

    theme_params = {
        "track_width": args.track_width,
        "resize": args.resize,
        "note_height": args.note_height,
        "note_width_scale": args.note_width_scale,
        "note_corner_radius": args.note_corner_radius,
    }
    theme = replace(DEFAULT_THEME, **theme_params)

    set_assets_dir(str(args.assets_dir))
    library_index = json.loads(args.library_index.read_text(encoding="utf-8"))
    all_entries = list(iter_chart_entries(library_index))
    selected = all_entries[args.offset :] if args.all else all_entries[args.offset : args.offset + args.limit]

    exported: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    completed_count = 0

    tasks = []
    for input_index, (song, difficulty) in enumerate(selected, start=args.offset + 1):
        tasks.append({
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
        })

    def checkpoint():
        payload = build_index_payload(
            args=args,
            theme_params=theme_params,
            requested_count=len(selected),
            exported=exported,
            failures=failures,
            completed_count=completed_count,
        )
        write_index(args.index_output, payload, pretty=args.pretty)

    def handle_result(input_index: int, song: dict[str, Any], difficulty: dict[str, Any], result: dict[str, Any] | None, exc: Exception | None):
        label = f"{song['basename']} {difficulty['difficulty_code']}"
        nonlocal completed_count
        completed_count += 1
        if exc is None and result is not None:
            result["input_index"] = input_index
            exported.append(result)
            print(f"[{completed_count}/{len(selected)}] {result['status']}: {label} -> {result['image_url']}", flush=True)
        else:
            failures.append({
                "input_index": input_index,
                "basename": song["basename"],
                "difficulty_code": difficulty["difficulty_code"],
                "error": str(exc),
            })
            print(f"[{completed_count}/{len(selected)}] failed: {label}: {exc}", flush=True)

        if completed_count % args.checkpoint_every == 0 or completed_count == len(selected):
            checkpoint()

    if args.workers == 1:
        for task in tasks:
            song = task["song"]
            difficulty = task["difficulty"]
            input_index = task["input_index"]
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
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(render_chart_task, task): task for task in tasks}
            for future in as_completed(futures):
                task = futures[future]
                song = task["song"]
                difficulty = task["difficulty"]
                input_index = task["input_index"]
                try:
                    result = future.result()
                    handle_result(input_index, song, difficulty, result, None)
                except Exception as exc:
                    handle_result(input_index, song, difficulty, None, exc)

    # Ensure the final index is present even if the selected set is empty.
    if completed_count == 0:
        checkpoint()

    print(f"[INFO] wrote index: {args.index_output}", flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
