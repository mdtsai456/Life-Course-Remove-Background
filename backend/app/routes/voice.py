from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"audio/webm", "audio/mp4", "audio/ogg"}

logger = logging.getLogger(__name__)

router = APIRouter()


def _detect_audio_type(contents: bytes) -> str | None:
    """Detect audio format from magic bytes. Returns base MIME type or None."""
    if len(contents) < 8:
        return None
    # EBML header (WebM / Matroska)
    if contents[:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm"
    if contents[:4] == b"OggS":
        return "audio/ogg"
    # MP4: ftyp atom at offset 4 (not 0)
    if contents[4:8] == b"ftyp":
        return "audio/mp4"
    return None


@router.post(
    "/api/clone-voice",
    summary="Clone a voice",
    description="Upload an audio sample and text to generate speech in the cloned voice.",
    tags=["voice"],
    response_class=Response,
    responses={
        200: {
            "content": {"audio/*": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Cloned voice audio",
        }
    },
)
async def clone_voice(file: UploadFile, text: str | None = Form(None)) -> Response:
    # Validate MIME type (strip codec suffix, reject None)
    mime = (file.content_type or "").split(";")[0].strip()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio type. Allowed: audio/webm, audio/mp4, audio/ogg.",
        )

    # Validate text
    stripped = (text or "").strip()
    if text is None or stripped == "":
        raise HTTPException(status_code=400, detail="Text must not be empty.")

    # Validate file size
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum allowed size is 10 MB."
        )

    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum allowed size is 10 MB."
        )

    # Validate magic bytes
    detected = _detect_audio_type(contents)
    if detected is None:
        raise HTTPException(
            status_code=415,
            detail="File content does not appear to be a valid audio file.",
        )

    # TODO: 替換成真實 Voice Cloning 模型推理
    logger.info(
        "Returning mock cloned voice (file size: %d bytes, text length: %d)",
        len(contents),
        len(stripped),
    )
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a"}[detected]
    return Response(
        content=contents,
        media_type=detected,
        headers={"Content-Disposition": f"attachment; filename=\"cloned.{ext}\""},
    )
