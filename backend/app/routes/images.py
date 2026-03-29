from __future__ import annotations

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from rembg import remove

from app.constants import (
    ALLOWED_IMAGE_MIME_TYPES,
    JPEG_MAGIC,
    PNG_MAGIC,
    WEBP_MAGIC_RIFF,
    WEBP_MAGIC_TAG,
)
from app.validation import read_and_validate_upload

logger = logging.getLogger(__name__)

router = APIRouter()


def _detect_image_type(contents: bytes) -> str | None:
    if contents.startswith(PNG_MAGIC):
        return "image/png"
    if contents.startswith(JPEG_MAGIC):
        return "image/jpeg"
    if len(contents) >= 12 and contents[:4] == WEBP_MAGIC_RIFF and contents[8:12] == WEBP_MAGIC_TAG:
        return "image/webp"
    return None


@router.post("/api/remove-background")
async def remove_background(file: UploadFile, request: Request):
    if file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"不支援的檔案類型「{file.content_type}」。允許：png、jpeg、webp。",
        )

    contents, detected_type = await read_and_validate_upload(
        file,
        detect_type=_detect_image_type,
        allowed_types=ALLOWED_IMAGE_MIME_TYPES,
        type_error_detail="不支援的檔案類型。允許：png、jpeg、webp。",
    )

    session = getattr(request.app.state, "rembg_session", None)
    if session is None:
        logger.error("rembg session not initialized — check app startup")
        raise HTTPException(status_code=503, detail="服務尚未就緒。")

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None, partial(remove, contents, session=session)
        )
    except Exception:
        logger.exception("Background removal failed")
        raise HTTPException(
            status_code=500,
            detail="圖片處理失敗，請重試。",
        ) from None

    if result is None or len(result) == 0:
        logger.error("rembg returned empty output for a valid input image")
        raise HTTPException(
            status_code=500,
            detail="圖片處理失敗，請重試。",
        )

    return Response(
        content=result,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="output.png"'},
    )
