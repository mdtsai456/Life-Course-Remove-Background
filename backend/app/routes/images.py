from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from functools import partial
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from rembg import remove

from app.config import OUTPUTS_DIR, UPLOADS_DIR

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MIME_TO_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

logger = logging.getLogger(__name__)

router = APIRouter()


def _detect_image_type(contents: bytes) -> str | None:
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contents.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return "image/webp"
    return None


def _cleanup(path: Path) -> None:
    with suppress(FileNotFoundError):
        path.unlink()


@router.post("/api/remove-background")
async def remove_background(file: UploadFile):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: png, jpeg, webp.",
        )

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 10 MB.",
        )

    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 10 MB.",
        )

    detected_type = _detect_image_type(contents)
    if detected_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: png, jpeg, webp.",
        )

    unique_id = uuid.uuid4().hex
    ext = MIME_TO_EXT[detected_type]
    upload_path = UPLOADS_DIR / f"{unique_id}.{ext}"
    output_path = OUTPUTS_DIR / f"{unique_id}.png"

    upload_path.write_bytes(contents)

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, partial(remove, contents))
        output_path.write_bytes(result)
    except Exception:
        logger.exception("Background removal failed for upload %s", unique_id)
        _cleanup(upload_path)
        _cleanup(output_path)
        raise HTTPException(
            status_code=500,
            detail="Failed to process image. Please try again.",
        ) from None

    _cleanup(upload_path)
    return {"url": f"/static/outputs/{unique_id}.png"}
