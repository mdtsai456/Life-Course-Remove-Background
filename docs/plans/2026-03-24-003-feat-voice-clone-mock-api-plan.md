---
title: "feat: Add Voice Clone Mock API"
type: feat
status: active
date: 2026-03-24
origin: docs/brainstorms/2026-03-24-voice-clone-page-requirements.md
---

# feat: Add Voice Clone Mock API

## Enhancement Summary

**Deepened on:** 2026-03-24
**Sections enhanced:** 6
**Review agents used:** kieran-python-reviewer, security-sentinel, correctness-reviewer, api-contract-reviewer, pattern-recognition-specialist, code-simplicity-reviewer, julik-frontend-races-reviewer, reliability-reviewer, framework-docs-researcher

### Key Improvements

1. **Bug fix: MP3 magic bytes** — `contents[:3]` 與 2-byte 字面值比較永遠不會匹配；改用 `contents[:2]`
2. **Security fix: MIME type None bypass** — 移除 `if file.content_type and ...` 的 None 跳過邏輯，與既有端點一致
3. **Security fix: Response Content-Type** — 使用 server-detected type 而非 client-supplied type
4. **Frontend fix: AbortError handling** — 在 catch 區塊加入 `err.name === 'AbortError'` 過濾
5. **Simplification: 移除 WAV/MPEG** — 瀏覽器 MediaRecorder 不產生這些格式，屬 YAGNI
6. **Simplification: 移除 MAX_TEXT_LENGTH** — mock 忽略文字內容，長度限制留給真實實作

### New Considerations Discovered

- `disposedRef` 在 StrictMode 重新掛載時未重設（既有 bug，不在本次範圍但需注意）
- 422 狀態碼與 FastAPI 自動驗證格式衝突（array vs string），改用 400
- `setLoading(false)` 在 `finally` 中可能在 abort 後誤觸發

---

## Overview

前端 VoiceCloner 元件已完整實作（錄音、文字輸入、播放/下載），但目前使用 inline `setTimeout` mock 回傳原始錄音。本次新增後端 Mock API 端點 `POST /api/clone-voice`，讓前後端完整串接，為日後接入真實 Voice Cloning 模型做好準備。

## Problem Statement / Motivation

- 前端 mock（`setTimeout` + `URL.createObjectURL(audioBlob)`）無法驗證完整的前後端串接流程
- 缺乏後端驗證層（MIME type、檔案大小、magic bytes），無法模擬真實 API 的錯誤處理
- 當真實模型就緒時，只需替換 route handler 內部邏輯即可，不需動前端

## Proposed Solution

遵循 `backend/app/routes/threed.py`（Image to 3D mock）的既有模式，新增 `voice.py` route，接收音檔 + 文字，執行三層驗證後回傳原始音檔作為「克隆結果」。

## Technical Considerations

### 跨瀏覽器音頻格式

瀏覽器 `MediaRecorder` 錄製格式因平台而異：
- Chrome / Firefox: `audio/webm;codecs=opus`
- Safari: `audio/mp4;codecs=mp4a.40.2`
- Firefox fallback: `audio/ogg;codecs=opus`

後端只需接受瀏覽器實際產生的格式，magic bytes 驗證：
| 格式 | Magic Bytes | 偏移量 | 說明 |
|------|------------|--------|------|
| WebM | `\x1A\x45\xDF\xA3` | 0 | EBML header，與 MKV/Matroska 共用 |
| OGG  | `OggS` | 0 | |
| MP4  | `ftyp` | **4**（注意：不是 0） | Safari 錄音使用此格式 |

> ⚠️ MP4 的 `ftyp` 標記在偏移量 4，這是常見錯誤。Safari 錄音會因此被誤拒。

### Research Insights: Magic Bytes

- **WAV / MPEG 已移除**：瀏覽器 `MediaRecorder` 不產生這些格式（`getSupportedMimeType()` 只探測 mp4/webm/ogg），屬 YAGNI。未來支援檔案上傳時再加回。
- **MP3 sync word 是 2 bytes**（`\xFF\xFB` 等），原始計畫錯誤地用 `contents[:3]` 比較 2-byte 字面值，永遠不會匹配。
- **建議在函數頂部加 early return**：`if len(contents) < 8: return None`，統一處理極短檔案。

### 回傳 Content-Type

~~Mock 回傳原始音檔 bytes，`Content-Type` 應使用上傳檔案的原始 `content_type`。~~

**修正**：回應的 `media_type` 應使用 server-detected type（`_detect_audio_type` 回傳值），而非 client-supplied `file.content_type`。原因：
1. **安全性**：client content_type 可被偽造，可能包含 `; text/html` 等注入
2. **一致性**：magic bytes 已驗證實際格式，用 detected type 更準確
3. **codec suffix**：client 可能帶 `codecs=opus` 參數，某些 HTTP client 可能無法正確處理

### Form 參數

使用 `multipart/form-data` 同時傳送 `file`（UploadFile）和 `text`（`Form(...)`）。FastAPI 需額外 import `Form`。

**注意**：這是與既有端點的唯一結構差異 — `images.py` 和 `threed.py` 只接受 `UploadFile`，不需 `Form()`。需在 MIME 驗證中加入 `;` 分割處理（因為音頻 MIME type 帶 codec 後綴，圖片 MIME type 不帶）。

### text 驗證

後端須驗證 `text` 非空（strip 後）。~~並設上限 5,000 字元。~~

**修正**：移除 `MAX_TEXT_LENGTH` 限制。mock 完全忽略文字內容，長度限制應由真實模型的實際約束決定。

### Research Insights: 狀態碼

- 使用 **400**（而非 422）回報自訂 text 驗證錯誤。FastAPI 自動產生的 422 錯誤格式為 `{"detail": [{"loc": [...], "msg": "..."}]}`（array），與 `HTTPException(422, detail="string")` 衝突。前端 `errorData.detail` 解析會對 array 格式顯示 `[object Object]`。
- 保持 413（檔案太大）和 415（不支援格式）不變，與既有端點一致。

## Acceptance Criteria

### 後端 — `backend/app/routes/voice.py`

- [ ] 新增 `POST /api/clone-voice` 端點
- [ ] 接受 `file: UploadFile`（音檔）+ `text: str = Form(...)`（文字）
- [ ] `ALLOWED_MIME_TYPES = {"audio/webm", "audio/mp4", "audio/ogg"}`（僅瀏覽器實際產生的格式）
- [ ] 三層驗證：MIME type → 檔案大小（10MB）→ magic bytes
- [ ] MIME 驗證：用 `.split(";")[0].strip()` 處理 codec 後綴，**不跳過 None**（`not file.content_type or ...`）
- [ ] `text` 驗證：非空（strip 後），使用 400 狀態碼
- [ ] `_detect_audio_type(contents: bytes) -> str | None` — 涵蓋 WebM/OGG/MP4，加 early return for short files
- [ ] Mock 行為：回傳原始音檔 bytes，`media_type` 使用 **server-detected type**
- [ ] `-> Response` return type annotation
- [ ] `TODO` 註解標記替換點：`# TODO: 替換成真實 Voice Cloning 模型推理`
- [ ] `response_class=Response` + OpenAPI `responses` dict 宣告 binary response
- [ ] 使用 `logger.info(...)` 記錄 mock 使用
- [ ] 不寫入磁碟（全部 in-memory）
- [ ] HTTP 錯誤碼：400（text 無效）、413（太大）、415（不支援格式）
- [ ] 不在錯誤訊息中反射 user input（使用通用訊息列舉允許的格式）

### 後端 — `backend/app/main.py`

- [ ] `from app.routes.voice import router as voice_router`
- [ ] `app.include_router(voice_router)`

### 前端 — `frontend/src/services/api.js`

- [ ] 新增 `cloneVoice(audioFile, text, signal)` 函數
- [ ] 使用 `FormData` 附加 `file` 和 `text` 欄位
- [ ] 端點：`/api/clone-voice`
- [ ] 錯誤處理：`response.json().detail` fallback（處理 string 和 array 兩種格式）
- [ ] 成功：`response.blob()` → `URL.createObjectURL(blob)`
- [ ] 空回應檢查：`blob.size === 0`

### 前端 — `frontend/src/components/VoiceCloner.jsx`

- [ ] 移除 inline `setTimeout` mock（約 line 198-201）
- [ ] `import { cloneVoice } from '../services/api'`
- [ ] 新增 `abortControllerRef`（參照 `ImageTo3D.jsx` 的模式）
- [ ] 在 `handleSubmit` 中建立新的 AbortController，傳 signal 給 `cloneVoice`
- [ ] **在 catch 區塊加入 `if (err.name === 'AbortError') return`**（關鍵！）
- [ ] **在 finally 中加入 abort guard**：`if (!abortControllerRef.current?.signal.aborted) setLoading(false)`
- [ ] unmount 時 abort 進行中的請求
- [ ] 將 `audioBlob` 包裝成 `File` 物件（帶正確 MIME type），傳給 API

## Dependencies & Risks

- **無新依賴**：不需安裝任何新 Python 套件或 npm 套件
- **低風險**：mock 模式僅回傳原始檔案，無處理邏輯可能失敗
- **MP4 magic bytes**：offset 4 的 `ftyp` 檢測是最易出錯的地方，需特別注意 Safari 相容性
- **既有 bug（不在本次範圍）**：`disposedRef` 在 React StrictMode 重新掛載時未重設為 `false`，導致開發模式下錄音功能無法運作

### Research Insights: Production Hardening（未來考量）

以下項目不在本次 mock 範圍內，但真實模型整合時須處理：
- 加入 `X-Content-Type-Options: nosniff` 全域 header
- 加入 rate limiting（mock 回傳原始檔案無所謂，真實推理非常耗資源）
- `file.read()` 加 try/except 處理 client 斷線的 IOError
- 回應加入 `Content-Disposition: attachment` header
- 考慮 streaming response 以處理大檔案

## MVP

### backend/app/routes/voice.py

```python
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
    response_class=Response,
    responses={
        200: {
            "content": {"audio/*": {"schema": {"type": "string", "format": "binary"}}},
            "description": "Cloned voice audio",
        }
    },
)
async def clone_voice(file: UploadFile, text: str = Form(...)) -> Response:
    # Validate MIME type (strip codec suffix, reject None)
    mime = (file.content_type or "").split(";")[0].strip()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio type. Allowed: audio/webm, audio/mp4, audio/ogg.",
        )

    # Validate text
    stripped = text.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="Text must not be empty.")

    # Validate file size
    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 10 MB.")

    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 10 MB.")

    # Validate magic bytes
    detected = _detect_audio_type(contents)
    if detected is None:
        raise HTTPException(status_code=415, detail="File content does not appear to be a valid audio file.")

    # TODO: 替換成真實 Voice Cloning 模型推理
    logger.info("Returning mock cloned voice (file size: %d bytes, text length: %d)", len(contents), len(stripped))
    return Response(content=contents, media_type=detected)
```

### frontend/src/services/api.js — 新增 cloneVoice

```javascript
export async function cloneVoice(audioFile, text, signal) {
  const formData = new FormData()
  formData.append('file', audioFile)
  formData.append('text', text)

  const response = await fetch('/api/clone-voice', {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    let message = 'Failed to clone voice.'
    try {
      const errorData = await response.json()
      if (typeof errorData.detail === 'string') {
        message = errorData.detail
      } else if (Array.isArray(errorData.detail)) {
        message = errorData.detail.map(e => e.msg).join('; ')
      }
    } catch {
      // ignore JSON parse failure
    }
    throw new Error(message)
  }

  const blob = await response.blob()
  if (blob.size === 0) {
    throw new Error('Received empty response from server.')
  }
  return URL.createObjectURL(blob)
}
```

### frontend/src/components/VoiceCloner.jsx — 關鍵修改

```javascript
// 新增 import
import { cloneVoice } from '../services/api'

// 新增 ref（在元件頂層，與其他 ref 一起）
const abortControllerRef = useRef(null)

// unmount cleanup（新增獨立 effect）
useEffect(() => {
  return () => abortControllerRef.current?.abort()
}, [])

// handleSubmit 中替換 setTimeout mock：
async function handleSubmit(e) {
  e.preventDefault()
  if (!audioBlob || !text.trim()) return

  // ... existing client-side validation ...

  abortControllerRef.current?.abort()
  abortControllerRef.current = new AbortController()
  setLoading(true)
  setError('')
  if (resultUrl) { URL.revokeObjectURL(resultUrl); setResultUrl(null) }

  const ext = resultMimeType ? mimeTypeToExtension(resultMimeType) : 'audio'
  const audioFile = new File([audioBlob], `recording.${ext}`, { type: audioBlob.type })

  try {
    const url = await cloneVoice(audioFile, text.trim(), abortControllerRef.current.signal)
    setResultUrl(url)
  } catch (err) {
    if (err.name === 'AbortError') return  // unmount or re-submit
    setError(err.message || 'Something went wrong. Please try again.')
  } finally {
    if (!abortControllerRef.current?.signal.aborted) {
      setLoading(false)
    }
  }
}
```

## Sources

- **Origin document:** [docs/brainstorms/2026-03-24-voice-clone-page-requirements.md](docs/brainstorms/2026-03-24-voice-clone-page-requirements.md) — 前端 UI 需求與決策（本次延伸至後端 Mock API）
- **Mock API pattern:** `backend/app/routes/threed.py` — Image to 3D mock 端點
- **Validation pattern:** `backend/app/routes/images.py` — 三層驗證（MIME + size + magic bytes）
- **Frontend API pattern:** `frontend/src/services/api.js` — `removeBackground()` / `convertTo3D()`
- **AbortController pattern:** `frontend/src/components/ImageTo3D.jsx:17-21,80-81,106-107`
- **VoiceCloner TODO:** `frontend/src/components/VoiceCloner.jsx:198` — `// TODO: Replace with import { cloneVoice } from '../services/api'`

### Research References

- [FastAPI: Request Forms and Files](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/)
- [FastAPI: Additional Responses in OpenAPI](https://fastapi.tiangolo.com/advanced/additional-responses/)
- [FastAPI: Custom Response Classes](https://fastapi.tiangolo.com/advanced/custom-response/)
- FastAPI 0.135.1 Release Notes — python-multipart 0.0.22 strips directory paths from filenames (security fix)
- Security review: OWASP A04 (Insecure Design) — never echo raw uploads with client-supplied Content-Type
