from __future__ import annotations

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, HTTPException, Response, UploadFile
from rembg import remove

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}

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

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, partial(remove, contents))
        if result is None or len(result) == 0:
            raise ValueError("rembg returned empty output")
    except Exception:
        logger.exception("Background removal failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to process image. Please try again.",
        ) from None

    return Response(content=result, media_type="image/png")
