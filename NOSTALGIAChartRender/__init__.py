"""
NOSTALGIA Chart Render v2

将 NOSTALGIA 的 chart XML 渲染为谱面平面图 PNG。
"""

from .parser import parse_chart
from .render import Renderer
from .theme import Theme
from .element import Chart, Note, Timing, VelocityZone
from .service import RenderResult, SongInfo, render_chart_to_file
from .texture_loader import set_assets_dir

__all__ = [
    "parse_chart",
    "Renderer",
    "Theme",
    "Chart",
    "Note",
    "Timing",
    "VelocityZone",
    "RenderResult",
    "SongInfo",
    "render_chart_to_file",
    "set_assets_dir",
]
