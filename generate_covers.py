#!/usr/bin/env python3
"""
Generate web cover images from extracted NOSTALGIA jacket PNGs.

The game stores official jackets in IFS containers. This script consumes already
extracted files such as jk0701_s.png or jk0701_l.png, copies them to
public/covers/{basename}.webp, and updates chart indexes with cover_url.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTENTS_DIR = Path(
    os.environ.get(
        "NOSTALGIA_CONTENTS_DIR",
        "/mnt/e/Nostalgia_test/nostalgia/Nostalgia/PAN/contents",
    )
)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "public" / "covers"
DEFAULT_SCAN_ROOTS = [
    ROOT_DIR / "assets" / "covers",
    Path("/mnt/e/Nostalgia_test/nostalgia/Nostalgia/PAN/contents/data_mods"),
    Path("/home/yukino/code/nostalgia_fanmade/reference"),
    Path("/home/yukino/code/nostalgia_fanmade/work"),
]
SOURCE_DIRS = [
    ("data_op3", ("data_op3", "sound", "music_list.xml")),
    ("data_op2", ("data_op2", "sound", "music_list.xml")),
    ("data", ("data", "sound", "music_list.xml")),
]
JACKET_TAGS = ("jk_jpn", "jk_asia", "jk_kor", "jk_idn")
INDEX_PATHS = [
    ROOT_DIR / "library_index.json",
    ROOT_DIR / "public" / "chart_index_chartonly.json",
    ROOT_DIR / "public" / "chart_index.json",
]


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


def load_jacket_metadata(contents_dir: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for _, parts in SOURCE_DIRS:
        music_list = contents_dir.joinpath(*parts)
        if not music_list.exists():
            continue
        root = read_xml_cp932(music_list)
        for spec in root.findall("music_spec"):
            basename = elem_text(spec, "basename").lower()
            if not basename or basename in metadata:
                continue
            for tag in JACKET_TAGS:
                value = elem_text(spec, tag)
                if value and value != "0":
                    metadata[basename] = value.zfill(4)
                    break
    return metadata


def index_extracted_pngs(scan_roots: list[Path]) -> dict[str, Path]:
    candidates: dict[str, tuple[int, Path]] = {}
    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.rglob("jk*.png"):
            stem = path.stem.lower()
            if not stem.startswith("jk") or len(stem) < 8:
                continue
            jacket_id = stem[2:6]
            if not jacket_id.isdigit():
                continue
            score = 2 if stem.endswith("_l") else 1
            current = candidates.get(jacket_id)
            if current is None or score > current[0]:
                candidates[jacket_id] = (score, path)
    return {jacket_id: path for jacket_id, (_, path) in candidates.items()}


def convert_cover(source: Path, target: Path, size: int, quality: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width != size or image.height != size:
            image = image.resize((size, size), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)


def copy_existing_cover(source: Path, target: Path, size: int, quality: int) -> None:
    if source.suffix.lower() == ".webp":
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return
    convert_cover(source, target, size, quality)


def scan_basename_covers(scan_roots: list[Path]) -> dict[str, Path]:
    covers: dict[str, Path] = {}
    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            covers.setdefault(path.stem.lower(), path)
    return covers


def load_song_basenames(index_path: Path) -> list[str]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if "songs" in data:
        return [song["basename"] for song in data["songs"]]
    if "charts" in data:
        seen: dict[str, None] = {}
        for chart in data["charts"]:
            seen.setdefault(chart["basename"], None)
        return list(seen)
    return []


def update_index_cover_urls(index_path: Path, output_dir: Path) -> int:
    if not index_path.exists():
        return 0
    data = json.loads(index_path.read_text(encoding="utf-8"))
    updated = 0

    def cover_url_for(basename: str) -> str:
        cover = output_dir / f"{basename}.webp"
        return f"/covers/{cover.name}" if cover.exists() else ""

    if "songs" in data:
        for song in data["songs"]:
            url = cover_url_for(song["basename"])
            if url and song.get("cover_url") != url:
                song["cover_url"] = url
                updated += 1
    if "charts" in data:
        for chart in data["charts"]:
            url = cover_url_for(chart["basename"])
            if url and chart.get("cover_url") != url:
                chart["cover_url"] = url
                updated += 1

    if updated:
        index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contents-dir", type=Path, default=DEFAULT_CONTENTS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scan-root", type=Path, action="append", default=[])
    parser.add_argument("--size", type=int, default=160)
    parser.add_argument("--quality", type=int, default=88)
    args = parser.parse_args()

    scan_roots = args.scan_root or DEFAULT_SCAN_ROOTS
    jacket_by_basename = load_jacket_metadata(args.contents_dir)
    png_by_jacket = index_extracted_pngs(scan_roots)
    cover_by_basename = scan_basename_covers(scan_roots)
    basenames = load_song_basenames(ROOT_DIR / "library_index.json")

    generated = 0
    missing: list[dict[str, str]] = []
    for basename in basenames:
        key = basename.lower()
        jacket_id = jacket_by_basename.get(key, "")
        source = png_by_jacket.get(jacket_id) if jacket_id else None
        if source is None:
            source = cover_by_basename.get(key)
        if source is None:
            missing.append({"basename": basename, "jacket_id": jacket_id})
            continue
        target = args.output_dir / f"{basename}.webp"
        copy_existing_cover(source, target, args.size, args.quality)
        generated += 1

    updated_indexes = {str(path): update_index_cover_urls(path, args.output_dir) for path in INDEX_PATHS}
    report = {
        "generated": generated,
        "missing": len(missing),
        "missing_sample": missing[:30],
        "scan_roots": [str(path) for path in scan_roots],
        "updated_indexes": updated_indexes,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
