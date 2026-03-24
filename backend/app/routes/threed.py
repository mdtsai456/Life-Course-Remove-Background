from __future__ import annotations

import json
import logging
import struct

from fastapi import APIRouter, HTTPException, Response, UploadFile

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/png"}

logger = logging.getLogger(__name__)

router = APIRouter()


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
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Expected image/png.",
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

    if not contents.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(
            status_code=415,
            detail="File content does not appear to be a valid PNG.",
        )

    # TODO: 替換成真實 2D→3D 模型推理（TripoSR、Meshy 等）
    logger.info("Returning mock GLB for development (file size: %d bytes)", len(contents))
    glb = _make_mock_glb()

    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": "attachment; filename=\"model.glb\""},
    )
