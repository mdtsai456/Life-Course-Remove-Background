"""Shared constants used across route modules."""

from __future__ import annotations

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
WEBP_MAGIC_RIFF = b"RIFF"
WEBP_MAGIC_TAG = b"WEBP"

FILE_TOO_LARGE_DETAIL = "檔案過大，最大允許 10 MB。"

# Voice route constants
MAX_PCM_SIZE = 50 * 1024 * 1024  # 50 MB decompressed PCM limit
MAX_XTTS_PENDING = 4  # 1 running + 3 queued; beyond this → 503
MIME_TO_FORMAT: dict[str, str] = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/ogg": "ogg",
}

# Allowed MIME types per route
ALLOWED_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/webp"}
)
ALLOWED_3D_MIME_TYPES: frozenset[str] = frozenset({"image/png"})
