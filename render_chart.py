#!/usr/bin/env python3
"""
NOSTALGIA 谱面平面图生成脚本

使用方法：
    python render_chart.py <basename> <difficulty_number>

示例：
    python render_chart.py m_l0061_felys 3
    python render_chart.py m_t0052_summerdiary 2
    python render_chart.py m_t0129_ebonyivory 3 --resize 3 --note-height 24 --note-corner-radius 10 --output-suffix tall
    python render_chart.py m_t0087_turnthestory 3

难度编号：
    0 = Normal, 1 = Hard, 2 = Expert, 3 = Real
"""

import argparse
import os
import xml.etree.ElementTree as ET
from dataclasses import replace

# ======================================================================
# 路径配置（请根据实际情况修改）
# ======================================================================

# NOSTALGIA 游戏 contents 文件夹路径
CONTENTS_DIR = os.environ.get(
    "NOSTALGIA_CONTENTS_DIR",
    "/mnt/e/Nostalgia_test/nostalgia/Nostalgia/PAN/contents",
)

# 素材文件夹路径（内含 notes/ 和 covers/ 子目录）
ASSETS_DIR = os.environ.get(
    "NOSTALGIA_ASSETS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"),
)

# 输出文件夹路径
OUTPUT_DIR = os.environ.get(
    "NOSTALGIA_OUTPUT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"),
)

# ======================================================================

from NOSTALGIAChartRender import render_chart_to_file
from NOSTALGIAChartRender.theme import DEFAULT_THEME


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("必须是整数") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


def non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("必须是整数") from None
    if parsed < 0:
        raise argparse.ArgumentTypeError("必须大于或等于 0")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("必须是数字") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("basename", help="曲目 basename，例如 m_t0129_ebonyivory")
    parser.add_argument("difficulty_number", type=int, help="难度编号：0=Normal, 1=Hard, 2=Expert, 3=Real")
    parser.add_argument(
        "--track-width",
        type=positive_int,
        default=DEFAULT_THEME.track_width,
        help=f"谱面轨道宽度，默认 {DEFAULT_THEME.track_width}",
    )
    parser.add_argument(
        "--resize",
        type=positive_float,
        default=DEFAULT_THEME.resize,
        help=f"时间轴缩放，单位约为 ms/px；越小 note 间距越大，默认 {DEFAULT_THEME.resize}",
    )
    parser.add_argument(
        "--note-height",
        type=positive_int,
        default=DEFAULT_THEME.note_height,
        help=f"普通 note 和长条头尾的纵向高度，默认 {DEFAULT_THEME.note_height}",
    )
    parser.add_argument(
        "--note-width-scale",
        type=positive_float,
        default=DEFAULT_THEME.note_width_scale,
        help=f"note 横向宽度倍率，默认 {DEFAULT_THEME.note_width_scale}",
    )
    parser.add_argument(
        "--note-corner-radius",
        type=non_negative_int,
        default=DEFAULT_THEME.note_corner_radius,
        help=f"note 圆角半径；0 表示关闭圆角，默认 {DEFAULT_THEME.note_corner_radius}",
    )
    parser.add_argument(
        "--output-suffix",
        default="",
        help="输出文件名后缀，例如 tall 会生成 *_chart_tall.png",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    theme = replace(
        DEFAULT_THEME,
        track_width=args.track_width,
        resize=args.resize,
        note_height=args.note_height,
        note_width_scale=args.note_width_scale,
        note_corner_radius=args.note_corner_radius,
    )

    try:
        result = render_chart_to_file(
            basename=args.basename,
            difficulty_number=args.difficulty_number,
            contents_dir=CONTENTS_DIR,
            assets_dir=ASSETS_DIR,
            output_dir=OUTPUT_DIR,
            theme=theme,
            output_suffix=args.output_suffix,
        )
    except (FileNotFoundError, ValueError, ET.ParseError) as e:
        raise SystemExit(f"[ERROR] {e}") from None

    print(f"[INFO] 解析谱面: {result.xml_path}")
    print(
        "[INFO] "
        f"Chart(raw_notes={result.raw_note_count}, visible_notes={result.visible_note_count}, "
        f"hidden_notes={result.hidden_note_count}, velocity_zones={result.velocity_zone_count}, "
        f"duration={result.duration_sec:.1f}s)"
    )
    print(
        "[INFO] "
        f"歌曲: {result.song_title} / 艺术家: {result.artist} / "
        f"难度: {result.difficulty_name} {result.level}"
    )
    print(f"[INFO] 已保存: {result.output_path}")


if __name__ == "__main__":
    main()
