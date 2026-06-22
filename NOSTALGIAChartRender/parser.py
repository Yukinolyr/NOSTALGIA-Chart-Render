"""
NOSTALGIA chart XML 解析器
"""

from __future__ import annotations
import xml.etree.ElementTree as ET

from .element import Chart, Note, Timing, VelocityZone


KNOWN_TYPES = {0, 2, 4, 8, 10, 12, 64}


def _int(elem, tag: str, default: int = 0) -> int:
    child = elem.find(tag)
    if child is not None and child.text:
        try:
            return int(child.text)
        except ValueError:
            pass
    return default


def parse_chart(xml_path: str) -> Chart:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    header = {}
    header_elem = root.find("header")
    if header_elem is not None:
        fb = header_elem.find("first_bpm")
        if fb is not None and fb.text:
            header["first_bpm"] = int(fb.text) / 100000.0

        ft = header_elem.find("music_finish_time_msec")
        if ft is not None and ft.text:
            header["finish_time_ms"] = int(ft.text)

    timing_list: list[Timing] = []
    event_data = root.find("event_data")
    if event_data is not None:
        for event in event_data.findall("event"):
            typ = event.find("type")
            if typ is None or int(typ.text) != 0:
                continue
            t = event.find("start_timing_msec")
            val = event.find("value")
            if t is not None and val is not None and t.text and val.text:
                timing_list.append(Timing(
                    time_ms=int(t.text),
                    bpm=int(val.text) / 100000.0,
                ))

    if not timing_list and "first_bpm" in header:
        timing_list.append(Timing(time_ms=0, bpm=header["first_bpm"]))

    velocity_zone_list: list[VelocityZone] = []
    velocity_zone_data = root.find("velocity_zone_data")
    if velocity_zone_data is not None:
        for elem in velocity_zone_data.findall("velocity_zone"):
            start_ms = _int(elem, "start_timing_msec")
            end_ms = _int(elem, "end_timing_msec")
            if end_ms <= start_ms:
                continue
            velocity_zone_list.append(VelocityZone(
                index=_int(elem, "index"),
                start_ms=start_ms,
                end_ms=end_ms,
                velocity_type=_int(elem, "velocity_type"),
            ))

    raw_note_count = 0
    note_list: list[Note] = []
    note_data = root.find("note_data")
    if note_data is not None:
        for elem in note_data.findall("note"):
            note_type = _int(elem, "note_type")
            if note_type not in KNOWN_TYPES:
                continue
            raw_note_count += 1

            hand = _int(elem, "hand")
            if hand == 2:
                continue

            note_list.append(Note(
                index=_int(elem, "index"),
                start_ms=_int(elem, "start_timing_msec"),
                end_ms=_int(elem, "end_timing_msec"),
                gate_time_ms=_int(elem, "gate_time_msec"),
                scale_piano=_int(elem, "scale_piano"),
                min_key_index=_int(elem, "min_key_index"),
                max_key_index=_int(elem, "max_key_index"),
                note_type=note_type,
                hand=hand,
                param1=_int(elem, "param1"),
                param2=_int(elem, "param2"),
            ))

    return Chart(
        header=header,
        timing_list=timing_list,
        note_list=note_list,
        velocity_zone_list=velocity_zone_list,
        raw_note_count=raw_note_count,
    )
