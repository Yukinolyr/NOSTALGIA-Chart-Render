from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from NOSTALGIAChartRender import parse_chart, render_chart_to_file
from NOSTALGIAChartRender.service import DIFFICULTY_MAP, display_level_for, find_chart_xml
from NOSTALGIAChartRender.theme import DEFAULT_THEME


ROOT_DIR = Path(__file__).resolve().parent
CONTENTS_DIR = Path(os.environ.get("NOSTALGIA_CONTENTS_DIR", "/mnt/e/Nostalgia_test/nostalgia/Nostalgia/PAN/contents"))
ASSETS_DIR = Path(os.environ.get("NOSTALGIA_ASSETS_DIR", ROOT_DIR / "assets"))
OUTPUT_DIR = Path(os.environ.get("NOSTALGIA_OUTPUT_DIR", ROOT_DIR / "output"))
INDEX_PATH = Path(os.environ.get("NOSTALGIA_LIBRARY_INDEX", ROOT_DIR / "library_index.json"))
PUBLIC_DIR = ROOT_DIR / "public"
STATIC_DIR = PUBLIC_DIR / "static"
CHARTONLY_INDEX_PATH = Path(os.environ.get("NOSTALGIA_CHARTONLY_INDEX", PUBLIC_DIR / "chart_index_chartonly.json"))
CHARTONLY_WEBP_INDEX_PATH = Path(os.environ.get("NOSTALGIA_CHARTONLY_WEBP_INDEX", PUBLIC_DIR / "chart_index_chartonly_webp.json"))
CHARTONLY_R2_INDEX_PATH = Path(os.environ.get("NOSTALGIA_CHARTONLY_R2_INDEX", PUBLIC_DIR / "chart_index_chartonly_r2.json"))
BATCH_INDEX_PATH = Path(os.environ.get("NOSTALGIA_BATCH_INDEX", CHARTONLY_INDEX_PATH))


class RenderParams(BaseModel):
    track_width: int = Field(default=DEFAULT_THEME.track_width, gt=0)
    resize: float = Field(default=DEFAULT_THEME.resize, gt=0)
    note_height: int = Field(default=DEFAULT_THEME.note_height, gt=0)
    note_width_scale: float = Field(default=DEFAULT_THEME.note_width_scale, gt=0)
    note_corner_radius: int = Field(default=DEFAULT_THEME.note_corner_radius, ge=0)


class RenderRequest(BaseModel):
    basename: str
    difficulty_number: int = Field(ge=0, le=3)
    params: RenderParams = Field(default_factory=RenderParams)


def load_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        raise RuntimeError(f"library index not found: {INDEX_PATH}. Run index_library.py first.")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


LIBRARY_INDEX = load_index()
SONGS_BY_BASENAME = {song["basename"]: song for song in LIBRARY_INDEX["songs"]}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(PUBLIC_DIR / "charts_chartonly").mkdir(parents=True, exist_ok=True)
(PUBLIC_DIR / "charts_chartonly_webp").mkdir(parents=True, exist_ok=True)
(PUBLIC_DIR / "covers").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="NOSTALGIA Chart Render API", version="0.1.0")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/charts", StaticFiles(directory=str(PUBLIC_DIR / "charts")), name="charts")
app.mount("/charts_chartonly", StaticFiles(directory=str(PUBLIC_DIR / "charts_chartonly")), name="charts_chartonly")
app.mount("/charts_chartonly_webp", StaticFiles(directory=str(PUBLIC_DIR / "charts_chartonly_webp")), name="charts_chartonly_webp")
app.mount("/covers", StaticFiles(directory=str(PUBLIC_DIR / "covers")), name="covers")

RENDER_EXECUTOR = ThreadPoolExecutor(max_workers=int(os.environ.get("NOSTALGIA_RENDER_WORKERS", "1")))
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def difficulty_list(song: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        diff
        for _, diff in sorted(song["difficulties"].items(), key=lambda item: int(item[0]))
    ]


def song_summary(song: dict[str, Any]) -> dict[str, Any]:
    return {
        "basename": song["basename"],
        "title": song["title"],
        "artist": song["artist"],
        "cover_path": song.get("cover_path", ""),
        "difficulties": difficulty_list(song),
    }


def render_cache_key(request: RenderRequest) -> str:
    payload = {
        "renderer_version": "service-v4-original-segments-velocity-zones",
        "basename": request.basename,
        "difficulty_number": request.difficulty_number,
        "params": request.params.model_dump(),
    }
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()[:16]


def output_url(path: Path) -> str:
    return f"/outputs/{path.name}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_output_path(request: RenderRequest, cache_key: str) -> Path:
    diff_code = DIFFICULTY_MAP[request.difficulty_number][0]
    return OUTPUT_DIR / f"{request.basename}_{diff_code}_chart_api_{cache_key}.png"


def render_result_payload(result: Any, *, cached: bool, cache_key: str) -> dict[str, Any]:
    payload = asdict(result)
    payload["cached"] = cached
    payload["cache_key"] = cache_key
    payload["title"] = result.song_title
    payload["image_url"] = output_url(Path(result.output_path))
    return payload


def cached_render_response(request: RenderRequest, output_path: Path, cache_key: str) -> dict[str, Any]:
    song = SONGS_BY_BASENAME[request.basename]
    difficulty = song["difficulties"][str(request.difficulty_number)]
    diff_name = difficulty["difficulty_name"]
    level = difficulty.get("level", "")
    xml_path = difficulty.get("xml_path") or find_chart_xml(str(CONTENTS_DIR), request.basename, difficulty["difficulty_code"])
    if not xml_path:
        raise HTTPException(status_code=404, detail="chart XML not found")

    chart = parse_chart(xml_path)
    with Image.open(output_path) as image:
        image_size = image.size

    return {
        "cached": True,
        "cache_key": cache_key,
        "basename": request.basename,
        "title": song["title"],
        "artist": song["artist"],
        "difficulty_number": request.difficulty_number,
        "difficulty_code": difficulty["difficulty_code"],
        "difficulty_name": diff_name,
        "level": level,
        "display_level": display_level_for(diff_name, level),
        "raw_note_count": chart.raw_note_count,
        "visible_note_count": chart.visible_note_count,
        "hidden_note_count": chart.hidden_note_count,
        "velocity_zone_count": len(chart.velocity_zone_list),
        "duration_sec": chart.end_time / 1000,
        "image_size": image_size,
        "image_url": output_url(output_path),
        "output_path": str(output_path),
    }


def validate_render_request(request: RenderRequest):
    song = SONGS_BY_BASENAME.get(request.basename)
    if song is None:
        raise HTTPException(status_code=404, detail="song not found")
    if str(request.difficulty_number) not in song["difficulties"]:
        raise HTTPException(status_code=404, detail="difficulty not available for this song")


def run_render_job(job_id: str, request: RenderRequest, cache_key: str, output_path: Path):
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["started_at"] = now_iso()

    try:
        if output_path.exists():
            result_payload = cached_render_response(request, output_path, cache_key)
        else:
            theme = replace(DEFAULT_THEME, **request.params.model_dump())
            result = render_chart_to_file(
                basename=request.basename,
                difficulty_number=request.difficulty_number,
                contents_dir=str(CONTENTS_DIR),
                assets_dir=str(ASSETS_DIR),
                output_dir=str(OUTPUT_DIR),
                theme=theme,
                output_suffix=f"api_{cache_key}",
            )
            result_payload = render_result_payload(result, cached=False, cache_key=cache_key)

        with JOBS_LOCK:
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["finished_at"] = now_iso()
            JOBS[job_id]["result"] = result_payload
    except Exception as exc:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["finished_at"] = now_iso()
            JOBS[job_id]["error"] = str(exc)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/chart_index.json")
def batch_chart_index() -> FileResponse:
    if not BATCH_INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="batch chart index not found")
    return FileResponse(BATCH_INDEX_PATH)


@app.get("/chart_index_chartonly.json")
def chartonly_batch_chart_index() -> FileResponse:
    if not CHARTONLY_INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="chart-only batch chart index not found")
    return FileResponse(CHARTONLY_INDEX_PATH)


@app.get("/chart_index_chartonly_webp.json")
def chartonly_webp_batch_chart_index() -> FileResponse:
    if not CHARTONLY_WEBP_INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="chart-only WebP batch chart index not found")
    return FileResponse(CHARTONLY_WEBP_INDEX_PATH)


@app.get("/chart_index_chartonly_r2.json")
def chartonly_r2_batch_chart_index() -> FileResponse:
    if not CHARTONLY_R2_INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="chart-only R2 batch chart index not found")
    return FileResponse(CHARTONLY_R2_INDEX_PATH)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "song_count": LIBRARY_INDEX["song_count"],
        "chart_count": LIBRARY_INDEX["chart_count"],
        "index_path": str(INDEX_PATH),
        "output_dir": str(OUTPUT_DIR),
    }


@app.get("/songs")
def search_songs(q: str = "", limit: int = 30) -> dict[str, Any]:
    query = q.casefold().strip()
    limit = max(1, min(limit, 100))

    songs = LIBRARY_INDEX["songs"]
    if query:
        songs = [
            song
            for song in songs
            if query in song["basename"].casefold()
            or query in song["title"].casefold()
            or query in song["artist"].casefold()
        ]

    return {
        "total": len(songs),
        "items": [song_summary(song) for song in songs[:limit]],
    }


@app.get("/songs/{basename}")
def get_song(basename: str) -> dict[str, Any]:
    song = SONGS_BY_BASENAME.get(basename)
    if song is None:
        raise HTTPException(status_code=404, detail="song not found")
    return song_summary(song)


@app.post("/render")
def render_chart(request: RenderRequest) -> dict[str, Any]:
    validate_render_request(request)

    cache_key = render_cache_key(request)
    output_path = render_output_path(request, cache_key)

    if output_path.exists():
        return cached_render_response(request, output_path, cache_key)

    theme = replace(DEFAULT_THEME, **request.params.model_dump())
    try:
        result = render_chart_to_file(
            basename=request.basename,
            difficulty_number=request.difficulty_number,
            contents_dir=str(CONTENTS_DIR),
            assets_dir=str(ASSETS_DIR),
            output_dir=str(OUTPUT_DIR),
            theme=theme,
            output_suffix=f"api_{cache_key}",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return render_result_payload(result, cached=False, cache_key=cache_key)


@app.post("/render-jobs")
def create_render_job(request: RenderRequest) -> dict[str, Any]:
    validate_render_request(request)

    cache_key = render_cache_key(request)
    output_path = render_output_path(request, cache_key)
    if output_path.exists():
        return {
            "status": "done",
            "cached": True,
            "cache_key": cache_key,
            "result": cached_render_response(request, output_path, cache_key),
        }

    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now_iso(),
            "started_at": None,
            "finished_at": None,
            "cache_key": cache_key,
            "request": request.model_dump(),
            "result": None,
            "error": None,
        }

    RENDER_EXECUTOR.submit(run_render_job, job_id, request, cache_key, output_path)

    return {
        "job_id": job_id,
        "status": "queued",
        "cached": False,
        "cache_key": cache_key,
    }


@app.get("/render-jobs/{job_id}")
def get_render_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="render job not found")
        return dict(job)
