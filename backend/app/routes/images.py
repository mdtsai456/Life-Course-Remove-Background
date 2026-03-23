import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from rembg import remove

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = BASE_DIR / "static" / "uploads"
OUTPUTS_DIR = BASE_DIR / "static" / "outputs"

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MIME_TO_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

router = APIRouter()


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

    unique_id = uuid.uuid4().hex
    ext = MIME_TO_EXT[file.content_type]
    upload_path = UPLOADS_DIR / f"{unique_id}.{ext}"
    output_path = OUTPUTS_DIR / f"{unique_id}.png"

    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 10 MB.",
        )

    upload_path.write_bytes(contents)

    result = remove(contents)
    output_path.write_bytes(result)

    return {"url": f"/static/outputs/{unique_id}.png"}
