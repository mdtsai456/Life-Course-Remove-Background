---
title: "fix: Stream processed image directly, remove disk writes"
type: fix
status: completed
date: 2026-03-24
origin: docs/brainstorms/2026-03-24-output-disk-leak-requirements.md
---

# fix: Stream processed image directly, remove disk writes

## Overview

Every call to `POST /api/remove-background` currently saves the processed PNG to
`/static/outputs/{uuid}.png` and returns a URL to it — but never deletes it.
This fix eliminates both disk writes (upload buffer + output file) by streaming the
result bytes directly in the HTTP response and converting to a blob URL on the client.

(see origin: docs/brainstorms/2026-03-24-output-disk-leak-requirements.md)

## Problem Statement

- `OUTPUTS_DIR` accumulates one PNG per request forever → disk fills up eventually.
- `upload_path.write_bytes(contents)` writes the upload to disk immediately before
  calling `rembg.remove(contents)` — which takes the bytes directly and ignores the file.
  The file is deleted right after. Zero benefit, pure I/O overhead.
- The frontend only needs the image while the page is open; a persistent URL is not required.

## Proposed Solution

**Backend:** replace the `try/except` block in `remove_background()` with a bare
`rembg.remove()` call and return `Response(content=result, media_type="image/png")`.
No files touch the filesystem.

**Frontend:** `removeBackground()` reads the binary response as a `Blob` and returns
`URL.createObjectURL(blob)`. `ImageUploader` revokes the blob URL when `resultUrl`
changes or the component unmounts, using the same `useEffect` pattern already in place
for `originalUrl`.

## Key Decisions

- **`api.js` returns a blob URL string** — maintains the current return-type contract so
  `ImageUploader.jsx`'s call site is unchanged. (see origin)
- **Remove dead static infrastructure** — `UPLOADS_DIR`, `OUTPUTS_DIR`, lifespan hook, `StaticFiles` mount, and `backend/static/` directory all removed; no application code references them.
- **No `AbortController`** — deferred; the in-flight-unmount blob leak is minor for this
  single-page app and out of scope for this fix.
- **No `Content-Disposition` header** — the frontend `download` attribute already controls
  the suggested filename.

## Technical Considerations

### Files changed

| File | Change |
|---|---|
| `backend/app/routes/images.py` | Core change — remove disk writes, add `Response`, guard empty result separately from rembg exceptions |
| `backend/app/main.py` | Remove lifespan hook, `StaticFiles` mount, and related imports |
| `backend/app/config.py` | Remove `UPLOADS_DIR` and `OUTPUTS_DIR` constants |
| `backend/static/` | Entire directory deleted |
| `frontend/src/services/api.js` | Replace `response.json()` success path with `response.blob()` |
| `frontend/src/components/ImageUploader.jsx` | Add `useEffect` to revoke `resultUrl` blob URL; dynamic download filename |
| `frontend/vite.config.js` | Remove dead `/static` proxy block |

### Backend changes — `images.py`

Remove dead imports and helpers; slim the route down to validation + `rembg` call + stream:

```python
# backend/app/routes/images.py (after)
from __future__ import annotations

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, HTTPException, Response, UploadFile

from app.config import ALLOWED_MIME_TYPES  # kept for validation

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}

@router.post("/api/remove-background")
async def remove_background(file: UploadFile):
    # ... validation unchanged ...
    contents = await file.read(MAX_FILE_SIZE + 1)
    # ... magic-byte check unchanged ...

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, partial(remove, contents))
        if not result:
            raise ValueError("rembg returned empty output")
    except Exception:
        logger.exception("Background removal failed")
        raise HTTPException(status_code=500, detail="Failed to process image.") from None

    return Response(content=result, media_type="image/png")
```

**Imports to remove:** `uuid`, `suppress`, `Path` (all only used by the disk-write block and `_cleanup`).
**Symbols to remove:** `_cleanup`, `MIME_TO_EXT`, `upload_path`, `output_path`, `unique_id`, `ext`.
**Import to add:** `Response` (from `fastapi`).
**Import to remove:** `OUTPUTS_DIR, UPLOADS_DIR` (no longer referenced in this file).

### Frontend changes — `api.js`

Replace the success-path body parsing only. The error path (`!response.ok` → `response.json()`) is **preserved unchanged**.

```js
// frontend/src/services/api.js (success path, after)
const blob = await response.blob()
return URL.createObjectURL(blob)
```

### Frontend changes — `ImageUploader.jsx`

Add a `useEffect` to revoke the previous blob URL whenever `resultUrl` changes.
The cleanup function runs on change AND on unmount.

```jsx
// Parallel to the existing originalUrl useEffect (lines 14-22)
useEffect(() => {
  return () => {
    if (resultUrl) URL.revokeObjectURL(resultUrl)
  }
}, [resultUrl])
```

> ⚠️ The cleanup function must **return** the revoke call (not call it inline), so it fires
> on the *previous* value, not the new one. Writing `URL.revokeObjectURL(resultUrl)` without
> a return would revoke the newly-set URL immediately.

## Acceptance Criteria

- [ ] R1: After a successful request, no file exists under `static/outputs/`.
- [ ] R2: After a successful request, no file exists under `static/uploads/`.
- [ ] R3: Frontend displays the processed image and the Download button works using a blob URL.
- [ ] R4: Switching images or revisiting the page does not accumulate blob URLs in browser memory.
- [ ] Error messages from the backend (413, 415, 500) still display correctly in the UI.
- [ ] Passing an empty-output edge case from `rembg` returns a 500, not a broken image.

## System-Wide Impact

- **`/static/outputs/` and `/static/uploads/`** no longer exist on disk; the `StaticFiles` mount and lifespan `mkdir` calls have been removed from `main.py`.
- **`UPLOADS_DIR` and `OUTPUTS_DIR`** are removed from `config.py`; no application code references them.
- The Vite dev proxy rule for `/static` has been removed from `vite.config.js`.

## Dependencies & Risks

- `rembg.remove()` signature: the executor call passes `contents` (bytes), which is the
  documented API. No change to async offload pattern.
- FastAPI `Response(content=bytes, media_type=str)` is a synchronous, in-memory response —
  appropriate since `result` is fully materialized before the return.
- Blob URLs are revoked on `resultUrl` change, but an unmount *during an in-flight fetch*
  can still create one dangling blob. Accepted as minor for this single-page app.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-03-24-output-disk-leak-requirements.md](../brainstorms/2026-03-24-output-disk-leak-requirements.md)
  — Key decisions carried forward: stream-instead-of-URL strategy, keep static mount, remove both disk writes.
- `backend/app/routes/images.py:39-87` — current route implementation
- `frontend/src/services/api.js:21-26` — current JSON success path being replaced
- `frontend/src/components/ImageUploader.jsx:14-22` — existing `originalUrl` useEffect, model for R4
