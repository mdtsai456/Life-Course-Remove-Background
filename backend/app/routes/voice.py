from __future__ import annotations

import io
import logging
import os
import tempfile

import anyio
from fastapi import APIRouter, Form, HTTPException, Request, Response, UploadFile
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

try:
    from torch.cuda import OutOfMemoryError as CudaOOMError
except (ImportError, AttributeError):
    CudaOOMError = None

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PCM_SIZE = 50 * 1024 * 1024  # 50 MB decompressed PCM limit
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


class VoiceInferenceError(Exception):
    """Domain exception for XTTS v2 inference failures."""


def _convert_to_wav(contents: bytes, fmt: str) -> tuple[bytes, float]:
    """Convert audio bytes to 16-bit PCM WAV using pydub.

    Returns:
        (wav_bytes, duration_secs): WAV bytes and audio duration in seconds.

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

    duration_secs = len(audio) / 1000.0

    wav_buffer = io.BytesIO()
    try:
        audio.export(wav_buffer, format="wav")
    except Exception as exc:
        raise AudioConversionError("音訊編碼失敗。") from exc
    return wav_buffer.getvalue(), duration_secs


def _detect_language(text: str) -> str:
    """Detect language from text using Unicode script heuristics.

    Priority: Japanese (hiragana/katakana) > Korean (hangul)
    > Chinese (CJK ideographs) > English.
    Ambiguous kanji-only text defaults to 'zh-cn'.
    """
    has_cjk = False
    has_korean = False
    for ch in text:
        if '\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff':
            return "ja"
        if '\uac00' <= ch <= '\ud7af':
            has_korean = True
        elif '\u4e00' <= ch <= '\u9fff':
            has_cjk = True
    if has_korean:
        return "ko"
    if has_cjk:
        return "zh-cn"
    return "en"


def _run_xtts(tts, wav_bytes: bytes, text: str, language: str) -> bytes:
    """Run XTTS v2 inference synchronously.

    Creates a TemporaryDirectory to own both speaker.wav and synth.wav;
    both are cleaned up atomically on function exit.

    Raises:
        VoiceInferenceError: On XTTS-specific failures.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        speaker_path = f"{tmpdir}/speaker.wav"
        synth_path = f"{tmpdir}/synth.wav"
        with open(speaker_path, "wb") as f:
            f.write(wav_bytes)
        try:
            tts.tts_to_file(
                text=text,
                speaker_wav=speaker_path,
                language=language,
                file_path=synth_path,
            )
        except ValueError as exc:
            raise VoiceInferenceError("short_audio") from exc
        except Exception as exc:
            if CudaOOMError is not None and isinstance(exc, CudaOOMError):
                raise VoiceInferenceError("OOM") from exc
            raise
        if not os.path.isfile(synth_path):
            raise VoiceInferenceError("no_output")
        with open(synth_path, "rb") as f:
            return f.read()


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
async def clone_voice(request: Request, file: UploadFile, text: str | None = Form(None)) -> Response:
    # Validate MIME type (strip codec suffix, reject None)
    mime = (file.content_type or "").split(";")[0].strip()
    if mime not in MIME_TO_FORMAT:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio type. Allowed: audio/webm, audio/mp4, audio/ogg.",
        )

    # Validate text
    stripped = (text or "").strip()
    if text is None or stripped == "":
        raise HTTPException(status_code=400, detail="Text must not be empty.")
    if len(stripped) > 500:
        raise HTTPException(status_code=400, detail="文字不得超過 500 個字元。")

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
        wav_bytes, duration_secs = await anyio.to_thread.run_sync(
            lambda: _convert_to_wav(contents, fmt),
            abandon_on_cancel=True,
        )
    except AudioConversionError as exc:
        logger.warning("Audio conversion failed: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None
    except FileNotFoundError:
        logger.error("FFmpeg binary not found")
        raise HTTPException(
            status_code=503,
            detail="音訊轉換服務暫時無法使用。",
        ) from None

    # Duration validation
    if duration_secs < 3.0:
        raise HTTPException(status_code=400, detail="音訊樣本太短，至少需要 3 秒。")

    # Model guard
    tts_model = getattr(request.app.state, "tts_model", None)
    if tts_model is None:
        raise HTTPException(status_code=503, detail="語音克隆服務尚未就緒。")

    language = _detect_language(stripped)

    try:
        async with request.app.state.xtts_lock:
            result_bytes = await anyio.to_thread.run_sync(
                lambda: _run_xtts(tts_model, wav_bytes, stripped, language),
                abandon_on_cancel=False,
            )
    except VoiceInferenceError as exc:
        logger.warning("XTTS inference failed: %s", exc)
        if exc.args[0] == "OOM":
            raise HTTPException(status_code=503, detail="語音克隆服務資源不足，請稍後再試。") from None
        if exc.args[0] == "no_output":
            raise HTTPException(status_code=503, detail="語音合成未產生輸出檔案。") from None
        raise HTTPException(status_code=422, detail="音訊樣本太短，無法進行語音克隆。") from None
    except Exception:
        logger.exception("Unexpected XTTS error")
        raise

    return Response(
        content=result_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="cloned.wav"'},
    )