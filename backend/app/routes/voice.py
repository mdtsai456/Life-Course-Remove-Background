from __future__ import annotations

import io
import logging

import anyio
from fastapi import APIRouter, Form, HTTPException, Response, UploadFile
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PCM_SIZE = 200 * 1024 * 1024  # 200 MB decompressed PCM limit
ALLOWED_MIME_TYPES = {"audio/webm", "audio/mp4", "audio/ogg"}
MIME_TO_FORMAT = {"audio/webm": "webm", "audio/mp4": "mp4", "audio/ogg": "ogg"}

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


class AudioConversionError(Exception):
    """Domain exception for audio conversion failures."""


def _convert_to_wav(contents: bytes, fmt: str) -> bytes:
    """Convert audio bytes to 16-bit PCM WAV using pydub.

    Raises:
        AudioConversionError: If decoding fails or decompressed PCM exceeds limit.
        FileNotFoundError: If FFmpeg is not installed.
    """
    try:
        audio = AudioSegment.from_file(io.BytesIO(contents), format=fmt)
    except FileNotFoundError:
        raise  # FFmpeg missing — let caller handle as 503
    except CouldntDecodeError as exc:
        raise AudioConversionError("無法解碼音訊檔案。") from exc

    if len(audio.raw_data) > MAX_PCM_SIZE:
        raise AudioConversionError("音訊解壓後超過大小限制。")

    wav_buffer = io.BytesIO()
    audio.export(wav_buffer, format="wav", parameters=["-codec:a", "pcm_s16le"])
    return wav_buffer.getvalue()


@router.post(
    "/api/clone-voice",
    summary="Clone a voice",
    description="Upload an audio sample and text to generate speech in the cloned voice.",
    tags=["voice"],
    response_class=Response,
    responses={
        200: {
            "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Cloned voice audio (WAV)",
        },
        422: {"description": "Audio decode failure"},
        503: {"description": "Audio conversion service unavailable"},
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

    # Convert to WAV
    fmt = MIME_TO_FORMAT[detected]
    try:
        wav_bytes = await anyio.to_thread.run_sync(
            lambda: _convert_to_wav(contents, fmt)
        )
    except AudioConversionError as exc:
        logger.warning("Audio conversion failed: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="音訊轉換服務暫時無法使用。",
        )

    # TODO: 替換成真實 Voice Cloning 模型推理
    logger.info(
        "Returning mock cloned voice (wav size: %d bytes, text length: %d)",
        len(wav_bytes),
        len(stripped),
    )
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="cloned.wav"'},
    )