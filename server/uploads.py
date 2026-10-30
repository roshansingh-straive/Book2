"""Validated local shelf-photo uploads, kept outside the public app bundle."""
import io
import json
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image

from server.recognition import RecognitionError, load_image

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"


def upload_directory(upload_id):
    if not re.fullmatch(r"[a-f0-9]{32}", upload_id):
        raise HTTPException(404, "Shelf photo not found")
    directory = UPLOADS_DIR / upload_id
    if not (directory / "metadata.json").is_file() or not (directory / "image").is_file():
        raise HTTPException(404, "Shelf photo not found")
    return directory


def get_upload(upload_id):
    directory = upload_directory(upload_id)
    return json.loads((directory / "metadata.json").read_text(encoding="utf-8"))


def save_upload(raw, filename):
    try:
        image = load_image(raw)
    except RecognitionError as exc:
        raise HTTPException(422, str(exc)) from exc
    with Image.open(io.BytesIO(raw)) as original:
        media_type = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[original.format]
    name = Path(filename.replace("\\", "/")).name
    name = "".join(ch for ch in name if ord(ch) >= 32 and ord(ch) != 127)[:180].strip() or "shelf-photo"
    upload_id = uuid4().hex
    metadata = {"upload_id": upload_id, "filename": name, "photo_url": f"/api/uploads/{upload_id}/image",
                "width": image.width, "height": image.height, "byte_size": len(raw), "media_type": media_type}
    image.close()
    directory = UPLOADS_DIR / upload_id
    directory.mkdir(parents=True)
    (directory / "image").write_bytes(raw)
    (directory / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    return metadata


def saved_analysis_path(upload_id, bay_id):
    if not re.fullmatch(r"bay_[a-z0-9]+", bay_id):
        raise HTTPException(404, "Shelf not found")
    return upload_directory(upload_id) / f"analysis-{bay_id}.json"


def save_analysis(upload_id, bay_id, result):
    """Publish a completed result atomically; a failed scan cannot replace it."""
    path = saved_analysis_path(upload_id, bay_id)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
