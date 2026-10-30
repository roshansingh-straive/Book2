"""FastAPI server for replay and actual bookshelf recognition."""
import asyncio
import contextlib
import json
import hashlib
import re
import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from server.accuracy import OVERLAP, TILE_EDGE, select_profile
from server.comparison import compare_books
from server.recognition import MAX_IMAGE_BYTES, RecognitionError, RUNS_DIR, merge_readings, reprocess_audit, run_recognition
from server.uploads import get_upload, save_upload, saved_analysis_path, save_analysis, upload_directory

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "app" / "dist"
DATA_DIR = ROOT / "app" / "public" / "data"
PHOTOS_DIR = ROOT / "app" / "public" / "photos"

app = FastAPI(title="Shelf Check API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3000, 5173, 8000, 8001)],
    allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Authorization", "Content-Type"],
)
# One active live scan per server avoids accidentally multiplying paid crop runs.
_live_scan_lock = asyncio.Lock()


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bay_id: str = Field(pattern=r"^bay_[a-z0-9]+$", max_length=40)
    mode: Literal["replay", "live"] = "replay"
    upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


@app.get("/api/health")
def health():
    return {
        "status": "healthy", "default_mode": "replay",
        "live_mode_available": True,
        "live_available_by_difficulty": {"easy": True, "medium": True, "hard": True},
        "upload_analysis_available": True,
        "inference_authentication_required": True,
        "inference_access": "per-user-session",
        "accuracy_settings": {"tile_edge": TILE_EDGE, "overlap": OVERLAP, "independent_rotated_verification": False, "reading_mode": "single_pass"},
        "disclaimer": "Simulated store data",
    }


@app.get("/api/model-comparison")
def model_comparison_results():
    """Read recorded benchmark runs only; never trigger inference on page load."""
    static_results = DATA_DIR / "model_comparison_results.json"
    if static_results.is_file():
        return json.loads(static_results.read_text(encoding="utf-8"))

    reports = ROOT / "qa" / "model_comparison_results"
    runs = []
    if reports.exists():
        for path in sorted(reports.glob("run_*/results.json"), reverse=True)[:15]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                runs.append({"name": path.parent.name, "metadata": data.get("metadata", {}),
                             "summary": data.get("summary", []), "calls": data.get("calls", [])})
            except (OSError, ValueError):
                continue
    return {"runs": runs}


@app.get("/api/store")
def get_store():
    path = DATA_DIR / "store.json"
    if not path.exists():
        raise HTTPException(404, "Store data not generated")
    return json.loads(path.read_text(encoding="utf-8"))


def get_bay(bay_id):
    store = get_store()
    bay = next((b for b in store["bays"] if b["id"] == bay_id and b.get("scannable")), None)
    if bay is None:
        raise HTTPException(404, "Scannable bay not found")
    return store, bay


@app.get("/api/scan/{bay_id}")
def get_bay_scan(bay_id: str):
    get_bay(bay_id)
    path = DATA_DIR / "scans" / f"{bay_id}.json"
    if not path.exists():
        raise HTTPException(404, "Saved scan not generated")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/uploads", status_code=201)
async def upload_photo(request: Request, filename: str = "shelf-photo"):
    # Read incrementally so a misleading Content-Length cannot bypass the limit.
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Choose an image smaller than 20 MB.")
        chunks.append(chunk)
    return await asyncio.to_thread(save_upload, b"".join(chunks), filename)


@app.get("/api/uploads/{upload_id}")
def uploaded_photo(upload_id: str):
    return get_upload(upload_id)


@app.get("/api/uploads/{upload_id}/image")
def uploaded_image(upload_id: str):
    metadata = get_upload(upload_id)
    return FileResponse(upload_directory(upload_id) / "image", media_type=metadata["media_type"],
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


def refreshed_analysis(store, bay, saved):
    """Reapply current deterministic comparison without another model call."""
    observations = saved.get("recognition_readings", saved["shelf_items"])
    if saved.get("comparison_version") != 5:
        run_id = saved.get("run_id", "")
        recovered = None
        if re.fullmatch(r"[a-f0-9]{32}", run_id) and saved.get("upload_id"):
            path = RUNS_DIR / f"{run_id}.json"
            if path.is_file():
                try:
                    audit = json.loads(path.read_text(encoding="utf-8"))
                    raw = (upload_directory(saved["upload_id"]) / "image").read_bytes()
                    if audit.get("run_id") == run_id and audit.get("image_sha256") == hashlib.sha256(raw).hexdigest():
                        recovered = reprocess_audit(audit)
                except (OSError, ValueError, KeyError, TypeError):
                    pass  # retain conservative saved evidence if audit is unusable
        evidence = []
        legacy = []
        for book in observations:
            if book.get("evidence"):
                # Legacy boxes may have passed through mixed-unit guessing.
                # Preserve their text, but do not promote old locations to new
                # verified outlines without a fresh reading.
                evidence.extend({**entry, "box": None, "title": book["title"], "author": book.get("author")} for entry in book["evidence"])
            else:
                legacy.append(book)
        observations = recovered if recovered is not None else merge_readings(evidence) + legacy
    return {**saved, "bay_id": bay["id"], "bay_code": bay["code"], "bay_name": bay["name"],
            **compare_books(store, bay, observations, reading_mode=saved.get("reading_mode", "verified"))}


@app.get("/api/uploads/{upload_id}/analysis/{bay_id}")
def uploaded_analysis(upload_id: str, bay_id: str):
    store, bay = get_bay(bay_id)
    path = saved_analysis_path(upload_id, bay_id)
    if not path.exists():
        return {"result": None}
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("comparison_version") != 5:
        saved = refreshed_analysis(store, bay, saved)
        save_analysis(upload_id, bay_id, saved)
    return {"result": saved}


class RecompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_bay_id: str = Field(pattern=r"^bay_[a-z0-9]+$", max_length=40)
    target_bay_id: str = Field(pattern=r"^bay_[a-z0-9]+$", max_length=40)


@app.post("/api/uploads/{upload_id}/recompare")
def recompare_upload(upload_id: str, request: RecompareRequest):
    store, bay = get_bay(request.target_bay_id)
    get_bay(request.source_bay_id)
    photo = get_upload(upload_id)
    path = saved_analysis_path(upload_id, request.source_bay_id)
    if not path.exists():
        raise HTTPException(409, "Analyze this photo before comparing its recognized titles to another shelf.")
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("upload_id") != upload_id or saved.get("photo_url") != photo["photo_url"]:
        raise HTTPException(409, "The saved result does not match this photo.")
    result = refreshed_analysis(store, bay, saved)
    save_analysis(upload_id, bay["id"], result)
    return {"result": result}


@app.post("/api/scan/stream")
async def stream_scan(req: ScanRequest, authorization: str | None = Header(default=None)):
    store, bay = get_bay(req.bay_id)
    upload = get_upload(req.upload_id) if req.upload_id else None
    if upload and req.mode != "live":
        raise HTTPException(422, "Uploaded photos require a new analysis. Sample results cannot be used for an uploaded photo.")
    if req.mode == "replay":
        result = get_bay_scan(req.bay_id)

        async def replay_events():
            for event in (
                {"step": 0, "status": "replay", "message": "Loading a saved benchmark reply. No model call or zoom verification is performed."},
                {"step": 4, "status": "complete", "result": result},
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        return StreamingResponse(replay_events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to Straive LLM Foundry before starting live recognition.")
    token = authorization[7:].strip()
    if not token or len(token) > 4096 or "\r" in token or "\n" in token:
        raise HTTPException(401, "Sign in to Straive LLM Foundry before starting live recognition.")

    profile = select_profile()
    if _live_scan_lock.locked():
        raise HTTPException(409, "A live shelf scan is already running. Wait for it to finish or cancel it.")
    photo_path = upload_directory(req.upload_id) / "image" if upload else (PHOTOS_DIR / bay["photo"]).resolve()
    if not upload and (photo_path.parent != PHOTOS_DIR.resolve() or not photo_path.is_file()):
        raise HTTPException(404, "Shelf photograph not found")
    raw = photo_path.read_bytes()

    async def events():
        queue = asyncio.Queue()

        async def work():
            # Recheck here to close the gap between HTTP validation and stream
            # startup: a second request must fail, not queue another paid scan.
            if _live_scan_lock.locked():
                await queue.put({"status": "error", "message": "A live shelf scan is already running. No additional scan was queued."})
                return
            async with _live_scan_lock:
                try:
                    books, metadata = await run_recognition(raw, profile, queue.put, token)
                    await queue.put({"step": 3, "status": "comparing", "message": "Matching read titles to the catalogue; unresolved text remains available for review."})
                    result = {"bay_id": bay["id"], "bay_code": bay["code"], "bay_name": bay["name"],
                              "photo_filename": upload["filename"] if upload else bay["photo"],
                              "photo_url": upload["photo_url"] if upload else f"/photos/{bay['photo']}",
                              "source_kind": "upload" if upload else "sample", "upload_id": req.upload_id,
                              **metadata, **compare_books(store, bay, books, reading_mode=metadata.get("reading_mode", "verified"))}
                    if upload:
                        save_analysis(req.upload_id, bay["id"], result)
                    await queue.put({"step": 4, "status": "complete", "result": result})
                except RecognitionError as exc:
                    await queue.put({"status": "error", "message": str(exc), "code": exc.code})
                except Exception:
                    logging.getLogger(__name__).exception("Live shelf scan failed")
                    await queue.put({"status": "error", "message": "Live scan failed. Previous results are unchanged; no replay was substituted."})

        task = asyncio.create_task(work())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["status"] in {"complete", "error"}:
                    break
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if DIST_DIR.exists():
    for folder in ("assets", "photos", "data"):
        if (DIST_DIR / folder).exists():
            app.mount(f"/{folder}", StaticFiles(directory=DIST_DIR / folder), name=folder)

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "API endpoint not found")
        path = (DIST_DIR / full_path).resolve()
        if DIST_DIR.resolve() not in path.parents:
            if full_path:
                raise HTTPException(404, "File not found")
        if path.is_file():
            return FileResponse(path)
        return FileResponse(DIST_DIR / "index.html")
