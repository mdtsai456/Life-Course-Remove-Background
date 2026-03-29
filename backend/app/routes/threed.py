from __future__ import annotations

import json
import logging
import struct

from fastapi import APIRouter, HTTPException, Response, UploadFile

from app.constants import ALLOWED_3D_MIME_TYPES, PNG_MAGIC
from app.validation import read_and_validate_upload

logger = logging.getLogger(__name__)

router = APIRouter()


def _detect_png(contents: bytes) -> str | None:
    """Return 'image/png' if contents start with the PNG magic bytes."""
    if contents.startswith(PNG_MAGIC):
        return "image/png"
    return None


def _make_mock_glb() -> bytes:
    """Return a minimal valid GLB (empty glTF scene) for development."""
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": []}],
    }
    json_bytes = json.dumps(gltf).encode()
    # GLB JSON chunk must be 4-byte aligned, padded with spaces
    padding = (4 - len(json_bytes) % 4) % 4
    json_chunk_data = json_bytes + b" " * padding

    json_chunk_len = len(json_chunk_data)
    total_len = 12 + 8 + json_chunk_len  # file header + chunk header + chunk data

    # GLB file header: magic "glTF", version 2, total file length
    file_header = struct.pack("<III", 0x46546C67, 2, total_len)
    # JSON chunk header: chunk data length, chunk type 0x4E4F534A ("JSON")
    chunk_header = struct.pack("<II", json_chunk_len, 0x4E4F534A)

    return file_header + chunk_header + json_chunk_data


@router.post(
    "/api/image-to-3d",
    response_class=Response,
    responses={
        200: {
            "content": {
                "model/gltf-binary": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
async def image_to_3d(file: UploadFile):
    if file.content_type not in ALLOWED_3D_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"不支援的檔案類型「{file.content_type}」。僅接受 image/png。",
        )

    contents, _ = await read_and_validate_upload(
        file,
        detect_type=_detect_png,
        allowed_types=ALLOWED_3D_MIME_TYPES,
        type_error_detail="檔案內容不是有效的 PNG 圖片。",
    )

    # TODO: 替換成真實 2D→3D 模型推理（TripoSR、Meshy 等）
    logger.info("Returning mock GLB for development (file size: %d bytes)", len(contents))
    glb = _make_mock_glb()

    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": 'attachment; filename="model.glb"'},
    )
