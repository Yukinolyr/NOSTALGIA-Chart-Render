"""
Service-level helpers for finding metadata and rendering charts.

These functions are safe to call from a web API or worker process: they return
structured results and raise exceptions instead of exiting the interpreter.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from .parser import parse_chart
from .render import Renderer
from .texture_loader import set_assets_dir
from .theme import DEFAULT_THEME, Theme


DIFFICULTY_MAP = {
    0: ("00normal", "Normal"),
    1: ("01hard", "Hard"),
    2: ("02extreme", "Expert"),
    3: ("03real", "Real"),
}


@dataclass(frozen=True)
class SongInfo:
    title: str
    artist: str
    level: str
    cover_path: str


@dataclass(frozen=True)
class RenderResult:
    basename: str
    difficulty_number: int
    difficulty_code: str
    difficulty_name: str
    xml_path: str
    output_path: str
    song_title: str
    artist: str
    level: str
    display_level: str
    image_size: tuple[int, int]
    raw_note_count: int
    visible_note_count: int
    hidden_note_count: int
    velocity_zone_count: int
    duration_sec: float


def get_music_dirs(contents_dir: str) -> list[str]:
    return [
        os.path.join(contents_dir, "data_op3", "sound", "music"),
        os.path.join(contents_dir, "data_op2", "sound", "music"),
        os.path.join(contents_dir, "data", "sound", "music"),
    ]


def get_music_list_paths(contents_dir: str) -> list[str]:
    return [
        os.path.join(contents_dir, "data_op3", "sound", "music_list.xml"),
        os.path.join(contents_dir, "data_op2", "sound", "music_list.xml"),
        os.path.join(contents_dir, "data", "sound", "music_list.xml"),
    ]


def find_chart_xml(contents_dir: str, basename: str, diff_code: str) -> Optional[str]:
    """Find a chart XML by basename and difficulty code."""
    for music_dir in get_music_dirs(contents_dir):
        folder = os.path.join(music_dir, basename)
        if not os.path.isdir(folder):
            continue

        candidates = [
            os.path.join(folder, f"{basename}_{diff_code}.xml"),
            os.path.join(folder, f"{basename}_april_{diff_code}.xml"),
            os.path.join(folder, f"{basename}_pre_{diff_code}.xml"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
    return None


def extract_song_info(contents_dir: str, assets_dir: str, basename: str, diff_code: str) -> SongInfo:
    """Read title, artist, level, and cover path for a chart."""
    title = basename
    artist = ""
    level = ""
    cover_path = ""

    cover_dir = os.path.join(assets_dir, "covers")
    for ext in (".jpg", ".png"):
        candidate = os.path.join(cover_dir, f"{basename}{ext}")
        if os.path.exists(candidate):
            cover_path = candidate
            break

    level_tag_map = {
        "00normal": "level_normal",
        "01hard": "level_hard",
        "02extreme": "level_extreme",
        "03real": "level_real",
    }
    level_tag = level_tag_map.get(diff_code, "")

    for music_list_path in get_music_list_paths(contents_dir):
        if not os.path.exists(music_list_path):
            continue

        with open(music_list_path, "rb") as f:
            text = f.read().decode("cp932", errors="replace")
        text = text.replace("encoding='Shift_JIS'", "encoding='UTF-8'")
        root = ET.fromstring(text.encode("utf-8"))

        for spec in root.findall("music_spec"):
            basename_elem = spec.find("basename")
            if basename_elem is None or not basename_elem.text:
                continue
            if basename_elem.text.strip().lower() != basename.lower():
                continue

            title_elem = spec.find("title")
            artist_elem = spec.find("artist")
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
            if artist_elem is not None and artist_elem.text:
                artist = artist_elem.text.strip()

            if level_tag:
                level_elem = spec.find(level_tag)
                if level_elem is not None and level_elem.text:
                    value = level_elem.text.strip()
                    if value and value != "0":
                        level = value

            return SongInfo(title=title, artist=artist, level=level, cover_path=cover_path)

    return SongInfo(title=title, artist=artist, level=level, cover_path=cover_path)


def display_level_for(difficulty_name: str, level: str) -> str:
    if difficulty_name == "Real" and level.isdigit():
        raw_level = int(level)
        if 9 <= raw_level <= 11:
            return "1"
        if 12 <= raw_level <= 13:
            return "2"
        if 14 <= raw_level <= 15:
            return "3"
        return ""
    return level


def render_chart_to_file(
    *,
    basename: str,
    difficulty_number: int,
    contents_dir: str,
    assets_dir: str,
    output_dir: str,
    theme: Theme = DEFAULT_THEME,
    output_suffix: str = "",
) -> RenderResult:
    """Render one chart to a PNG file and return structured metadata."""
    if difficulty_number not in DIFFICULTY_MAP:
        raise ValueError(f"Invalid difficulty_number: {difficulty_number}; expected 0-3")

    diff_code, diff_name = DIFFICULTY_MAP[difficulty_number]
    xml_path = find_chart_xml(contents_dir, basename, diff_code)
    if xml_path is None:
        raise FileNotFoundError(f"Chart XML not found: {basename} / {diff_name}")

    set_assets_dir(assets_dir)
    chart = parse_chart(xml_path)
    info = extract_song_info(contents_dir, assets_dir, basename, diff_code)
    display_level = display_level_for(diff_name, info.level)

    renderer = Renderer(
        chart=chart,
        song_title=info.title,
        artist=info.artist,
        difficulty=diff_name,
        cover_path=info.cover_path or None,
        level=display_level,
        theme=theme,
    )

    os.makedirs(output_dir, exist_ok=True)
    suffix = f"_{output_suffix}" if output_suffix else ""
    output_path = os.path.join(output_dir, f"{basename}_{diff_code}_chart{suffix}.png")
    renderer.save(output_path)

    return RenderResult(
        basename=basename,
        difficulty_number=difficulty_number,
        difficulty_code=diff_code,
        difficulty_name=diff_name,
        xml_path=xml_path,
        output_path=output_path,
        song_title=info.title,
        artist=info.artist,
        level=info.level,
        display_level=display_level,
        image_size=renderer.size,
        raw_note_count=chart.raw_note_count,
        visible_note_count=chart.visible_note_count,
        hidden_note_count=chart.hidden_note_count,
        velocity_zone_count=len(chart.velocity_zone_list),
        duration_sec=chart.end_time / 1000,
    )
