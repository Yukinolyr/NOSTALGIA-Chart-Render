#!/usr/bin/env python3
"""
Build a JSON index for the NOSTALGIA chart library.

The index is intended for the future web API: it lets the server search songs
and resolve a selected song/difficulty to the chart XML without scanning the
contents folder on every request.
"""

from __future__ import annotations

import argparse
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from NOSTALGIAChartRender.service import DIFFICULTY_MAP, display_level_for


DEFAULT_CONTENTS_DIR = os.environ.get(
    "NOSTALGIA_CONTENTS_DIR",
    "/mnt/e/Nostalgia_test/nostalgia/Nostalgia/PAN/contents",
)
DEFAULT_ASSETS_DIR = os.environ.get(
    "NOSTALGIA_ASSETS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"),
)
DEFAULT_OUTPUT_PATH = os.environ.get(
    "NOSTALGIA_LIBRARY_INDEX",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "library_index.json"),
)

SOURCE_DIRS = [
    ("data_op3", ("data_op3", "sound", "music")),
    ("data_op2", ("data_op2", "sound", "music")),
    ("data", ("data", "sound", "music")),
]

LEVEL_TAGS = {
    "00normal": "level_normal",
    "01hard": "level_hard",
    "02extreme": "level_extreme",
    "03real": "level_real",
}

JACKET_TAGS = ("jk_jpn", "jk_asia", "jk_kor", "jk_idn")


def read_xml_cp932(path: Path) -> ET.Element:
    text = path.read_bytes().decode("cp932", errors="replace")
    text = text.replace("encoding='Shift_JIS'", "encoding='UTF-8'")
    text = text.replace('encoding="Shift_JIS"', 'encoding="UTF-8"')
    return ET.fromstring(text.encode("utf-8"))


def elem_text(parent: ET.Element, tag: str, default: str = "") -> str:
    elem = parent.find(tag)
    if elem is None or elem.text is None:
        return default
    return elem.text.strip()


def load_music_metadata(contents_dir: Path) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}

    for source, parts in SOURCE_DIRS:
        music_list = contents_dir.joinpath(*parts[:-1], "music_list.xml")
        if not music_list.exists():
            continue

        root = read_xml_cp932(music_list)
        for spec in root.findall("music_spec"):
            basename = elem_text(spec, "basename")
            metadata_key = basename.lower()
            if not basename or metadata_key in metadata:
                continue

            item = {
                "basename": basename,
                "title": elem_text(spec, "title", basename),
                "artist": elem_text(spec, "artist"),
                "metadata_source": source,
            }
            for level_tag in LEVEL_TAGS.values():
                item[level_tag] = elem_text(spec, level_tag)
            for jacket_tag in JACKET_TAGS:
                item[jacket_tag] = elem_text(spec, jacket_tag)
            metadata[metadata_key] = item

    return metadata


def find_cover(assets_dir: Path, basename: str) -> str:
    cover_dir = assets_dir / "covers"
    for ext in (".jpg", ".png"):
        candidate = cover_dir / f"{basename}{ext}"
        if candidate.exists():
            return str(candidate)
    return ""


def find_cover_url(basename: str) -> str:
    cover_dir = Path(__file__).resolve().parent / "public" / "covers"
    for stem in (basename, basename.lower(), basename.upper()):
        for ext in (".webp", ".png", ".jpg", ".jpeg"):
            candidate = cover_dir / f"{stem}{ext}"
            if candidate.exists():
                return f"/covers/{candidate.name}"
    return ""


def chart_candidates(song_dir: Path, basename: str, diff_code: str) -> list[Path]:
    return [
        song_dir / f"{basename}_{diff_code}.xml",
        song_dir / f"{basename}_april_{diff_code}.xml",
        song_dir / f"{basename}_pre_{diff_code}.xml",
    ]


def discover_charts(contents_dir: Path) -> dict[str, dict[str, Any]]:
    songs: dict[str, dict[str, Any]] = {}

    for source, parts in SOURCE_DIRS:
        music_dir = contents_dir.joinpath(*parts)
        if not music_dir.is_dir():
            continue

        for song_dir in sorted(p for p in music_dir.iterdir() if p.is_dir()):
            basename = song_dir.name
            song = songs.setdefault(
                basename,
                {
                    "basename": basename,
                    "sources": [],
                    "difficulties": {},
                },
            )
            if source not in song["sources"]:
                song["sources"].append(source)

            for difficulty_number, (diff_code, diff_name) in DIFFICULTY_MAP.items():
                if str(difficulty_number) in song["difficulties"]:
                    continue
                xml_path = next((path for path in chart_candidates(song_dir, basename, diff_code) if path.exists()), None)
                if xml_path is None:
                    continue

                song["difficulties"][str(difficulty_number)] = {
                    "difficulty_number": difficulty_number,
                    "difficulty_code": diff_code,
                    "difficulty_name": diff_name,
                    "xml_path": str(xml_path),
                    "source": source,
                }

    return songs


def build_index(contents_dir: Path, assets_dir: Path) -> dict[str, Any]:
    metadata = load_music_metadata(contents_dir)
    songs = discover_charts(contents_dir)

    for basename, song in songs.items():
        meta = metadata.get(basename.lower(), {})
        song["title"] = meta.get("title", basename)
        song["artist"] = meta.get("artist", "")
        song["metadata_source"] = meta.get("metadata_source", "")
        song["cover_path"] = find_cover(assets_dir, basename)
        song["cover_url"] = find_cover_url(basename)
        for jacket_tag in JACKET_TAGS:
            song[jacket_tag] = meta.get(jacket_tag, "")

        for difficulty in song["difficulties"].values():
            diff_code = difficulty["difficulty_code"]
            level = meta.get(LEVEL_TAGS[diff_code], "")
            difficulty["level"] = level
            difficulty["display_level"] = display_level_for(difficulty["difficulty_name"], level)

    sorted_songs = sorted(
        songs.values(),
        key=lambda song: (song.get("title", "").casefold(), song["basename"]),
    )
    chart_count = sum(len(song["difficulties"]) for song in sorted_songs)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contents_dir": str(contents_dir),
        "assets_dir": str(assets_dir),
        "song_count": len(sorted_songs),
        "chart_count": chart_count,
        "songs": sorted_songs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contents-dir", default=DEFAULT_CONTENTS_DIR)
    parser.add_argument("--assets-dir", default=DEFAULT_ASSETS_DIR)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--pretty", action="store_true", help="write indented JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    contents_dir = Path(args.contents_dir)
    assets_dir = Path(args.assets_dir)
    output_path = Path(args.output)

    if not contents_dir.is_dir():
        raise SystemExit(f"[ERROR] contents directory not found: {contents_dir}")
    if not assets_dir.is_dir():
        raise SystemExit(f"[ERROR] assets directory not found: {assets_dir}")

    index = build_index(contents_dir, assets_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2 if args.pretty else None),
        encoding="utf-8",
    )

    print(f"[INFO] songs: {index['song_count']}")
    print(f"[INFO] charts: {index['chart_count']}")
    print(f"[INFO] saved: {output_path}")


if __name__ == "__main__":
    main()
