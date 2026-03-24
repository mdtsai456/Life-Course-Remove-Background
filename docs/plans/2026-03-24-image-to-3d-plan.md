# Image to 3D Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增第三個 Tab「Image to 3D」，讓使用者兩段式操作（去背 → 轉 3D），最終在頁面內呈現可旋轉的 GLB 3D 預覽並可下載。

**Architecture:** 前端新增 `ImageTo3D.jsx` 元件，使用 `@google/model-viewer` web component 渲染 GLB；後端新增 `/api/image-to-3d` endpoint（本次實作 mock，接收 PNG 回傳最小合法 GLB），之後可替換成真實 3D 模型推理。

**Tech Stack:** React 19, Vite, FastAPI, `@google/model-viewer`, GLB (binary glTF)

---

## Task 1：安裝 `@google/model-viewer` npm 套件

**Files:**
- Modify: `frontend/package.json`（自動由 npm 更新）

**Step 1: 安裝套件**

```bash
cd frontend
npm install @google/model-viewer
```

**Step 2: 確認安裝成功**

```bash
cat package.json | grep model-viewer
```

Expected 輸出包含：`"@google/model-viewer": "^x.x.x"`

**Step 3: Commit**

```bash
cd ..
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(image-to-3d): install @google/model-viewer"
```

---

## Task 2：在 `main.jsx` 引入 model-viewer

**Files:**
- Modify: `frontend/src/main.jsx`

**Step 1: 讀取現有 `main.jsx`**

```bash
cat frontend/src/main.jsx
```

**Step 2: 在最頂部加入 import**

在 `main.jsx` 現有 import 區塊的最前面新增一行：

```js
import '@google/model-viewer'
```

完整結果（依實際內容調整，只需確保此行在最前面）：

```jsx
import '@google/model-viewer'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

**Step 3: 手動確認 dev server 不報錯**

```bash
cd frontend && npm run dev
```

瀏覽器開啟 `http://localhost:5173`，確認現有功能正常，無 console error。

**Step 4: Commit**

```bash
cd ..
git add frontend/src/main.jsx
git commit -m "feat(image-to-3d): register model-viewer custom element"
```

---

## Task 3：建立後端 mock endpoint `/api/image-to-3d`

**Files:**
- Create: `backend/app/routes/threed.py`

**Step 1: 建立新檔案**

建立 `backend/app/routes/threed.py`，內容如下：

```python
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


@router.post("/api/image-to-3d")
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

    return Response(content=glb, media_type="model/gltf-binary")
```

**Step 2: 確認語法無誤**

```bash
cd backend && python -c "from app.routes.threed import router; print('OK')"
```

Expected 輸出：`OK`

**Step 3: Commit**

```bash
cd ..
git add backend/app/routes/threed.py
git commit -m "feat(image-to-3d): add mock /api/image-to-3d backend endpoint"
```

---

## Task 4：掛載新 router 到 `main.py`

**Files:**
- Modify: `backend/app/main.py`

**Step 1: 在 `main.py` 加入 router**

在現有 `from app.routes.images import router as images_router` 下方加一行：

```python
from app.routes.threed import router as threed_router
```

在 `app.include_router(images_router)` 下方加一行：

```python
app.include_router(threed_router)
```

完整結果：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_cors_allowed_origins
from app.routes.images import router as images_router
from app.routes.threed import router as threed_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images_router)
app.include_router(threed_router)
```

**Step 2: 確認 FastAPI 能啟動**

```bash
cd backend && uvicorn app.main:app --reload &
sleep 2
curl -s http://localhost:8000/openapi.json | grep -c '"/image-to-3d'
kill %1
```

Expected 輸出：`1`（路徑出現在 OpenAPI JSON 的 `paths` 中）

**Step 3: Commit**

```bash
cd ..
git add backend/app/main.py
git commit -m "feat(image-to-3d): mount threed router in main.py"
```

---

## Task 5：新增前端 API 函式 `convertTo3D`

**Files:**
- Modify: `frontend/src/services/api.js`

**Step 1: 在 `api.js` 末尾新增函式**

在現有 `removeBackground` 函式之後，新增：

```js
export async function convertTo3D(file, signal) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/image-to-3d', {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    let message = 'Failed to convert to 3D.'
    try {
      const errorData = await response.json()
      message = errorData.detail || message
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

**Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat(image-to-3d): add convertTo3D API service function"
```

---

## Task 6：建立 `ImageTo3D.jsx` 元件

**Files:**
- Create: `frontend/src/components/ImageTo3D.jsx`

**Step 1: 建立元件**

建立 `frontend/src/components/ImageTo3D.jsx`，內容如下：

```jsx
import { useEffect, useRef, useState } from 'react'
import { removeBackground, convertTo3D } from '../services/api'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp']

export default function ImageTo3D() {
  const [file, setFile] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)
  const [removedBgUrl, setRemovedBgUrl] = useState(null)
  const [removedBgBlob, setRemovedBgBlob] = useState(null)
  const [model3dUrl, setModel3dUrl] = useState(null)
  const [step, setStep] = useState('idle') // idle | removing | removed | converting | done
  const [error, setError] = useState('')

  const abortControllerRef = useRef(null)

  // Cleanup on unmount: abort pending requests
  useEffect(() => {
    return () => abortControllerRef.current?.abort()
  }, [])

  // Original image preview URL lifecycle
  useEffect(() => {
    if (!file) {
      setOriginalUrl(null)
      return
    }
    const url = URL.createObjectURL(file)
    setOriginalUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  // Removed BG preview URL lifecycle
  useEffect(() => {
    return () => {
      if (removedBgUrl) URL.revokeObjectURL(removedBgUrl)
    }
  }, [removedBgUrl])

  // 3D model URL lifecycle
  useEffect(() => {
    return () => {
      if (model3dUrl) URL.revokeObjectURL(model3dUrl)
    }
  }, [model3dUrl])

  function handleFileChange(e) {
    const selected = e.target.files?.[0] || null
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)
    setStep('idle')

    if (!selected) {
      setFile(null)
      return
    }

    if (!ALLOWED_TYPES.includes(selected.type)) {
      setError('Unsupported file type. Please upload a PNG, JPEG, or WebP image.')
      setFile(null)
      return
    }

    if (selected.size > MAX_FILE_SIZE) {
      setError('File is too large. Maximum allowed size is 10 MB.')
      setFile(null)
      return
    }

    setFile(selected)
  }

  async function handleRemoveBg(e) {
    e.preventDefault()
    if (!file) return

    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()
    setStep('removing')
    setError('')
    setRemovedBgUrl(null)
    setRemovedBgBlob(null)
    setModel3dUrl(null)

    try {
      const url = await removeBackground(file, abortControllerRef.current.signal)
      // Also store as Blob for re-upload to /api/image-to-3d
      const response = await fetch(url)
      const blob = await response.blob()
      setRemovedBgUrl(url)
      setRemovedBgBlob(blob)
      setStep('removed')
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message || 'Something went wrong. Please try again.')
      setStep('idle')
    }
  }

  async function handleConvertTo3D() {
    if (!removedBgBlob) return

    abortControllerRef.current?.abort()
    abortControllerRef.current = new AbortController()
    setStep('converting')
    setError('')
    setModel3dUrl(null)

    const pngFile = new File([removedBgBlob], 'removed_bg.png', { type: 'image/png' })

    try {
      const url = await convertTo3D(pngFile, abortControllerRef.current.signal)
      setModel3dUrl(url)
      setStep('done')
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message || 'Something went wrong. Please try again.')
      setStep('removed') // 回到 removed 狀態，保留去背結果
    }
  }

  const isRemoving = step === 'removing'
  const isConverting = step === 'converting'
  const showRemovedResult = step === 'removed' || step === 'converting' || step === 'done'
  const show3dResult = step === 'done'

  return (
    <div className="uploader">
      <form className="upload-form" onSubmit={handleRemoveBg}>
        <label htmlFor="img3d-upload" className="file-label">
          <input
            id="img3d-upload"
            type="file"
            accept="image/png, image/jpeg, image/webp"
            onChange={handleFileChange}
            disabled={isRemoving || isConverting}
            className="file-input"
          />
          <span className="file-button">Choose Image</span>
          <span className="file-name">
            {file ? file.name : 'No file chosen'}
          </span>
        </label>
        <button
          type="submit"
          disabled={!file || isRemoving || isConverting}
          className="submit-button"
        >
          {isRemoving ? (
            <span className="spinner-wrapper">
              <span className="spinner" />
              Removing Background…
            </span>
          ) : (
            'Remove Background'
          )}
        </button>
      </form>

      {error && <p className="error-message">{error}</p>}

      {(originalUrl || showRemovedResult) && (
        <div className="preview-grid">
          {originalUrl && (
            <div className="preview-card">
              <h3 className="preview-title">Original</h3>
              <img src={originalUrl} alt="Original" className="preview-image" />
            </div>
          )}
          {showRemovedResult && removedBgUrl && (
            <div className="preview-card">
              <h3 className="preview-title">Background Removed</h3>
              <img
                src={removedBgUrl}
                alt="Background removed"
                className="preview-image checkerboard"
              />
              <a
                href={removedBgUrl}
                download={file ? file.name.replace(/\.[^.]+$/, '') + '_no_bg.png' : 'no_bg.png'}
                className="download-button"
              >
                Download PNG
              </a>
              <button
                onClick={handleConvertTo3D}
                disabled={isConverting}
                className="submit-button"
              >
                {isConverting ? (
                  <span className="spinner-wrapper">
                    <span className="spinner" />
                    Converting to 3D…
                  </span>
                ) : (
                  'Convert to 3D'
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {show3dResult && model3dUrl && (
        <div className="preview-card model-viewer-card">
          <h3 className="preview-title">3D Model</h3>
          {/* eslint-disable-next-line react/no-unknown-property */}
          <model-viewer
            src={model3dUrl}
            auto-rotate
            camera-controls
            className="model-viewer"
          />
          <a
            href={model3dUrl}
            download={file ? file.name.replace(/\.[^.]+$/, '') + '.glb' : 'model.glb'}
            className="download-button"
          >
            Download GLB
          </a>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ImageTo3D.jsx
git commit -m "feat(image-to-3d): add ImageTo3D component with two-step UX"
```

---

## Task 7：新增 CSS 樣式給 model-viewer

**Files:**
- Modify: `frontend/src/index.css`

**Step 1: 在 `index.css` 末尾加入樣式**

```css
/* ── ImageTo3D ── */

.model-viewer-card {
  margin-top: 1.5rem;
}

model-viewer {
  width: 100%;
  height: 400px;
  border-radius: 8px;
  background: #f8f8f8;
}
```

**Step 2: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(image-to-3d): add model-viewer CSS styles"
```

---

## Task 8：在 `App.jsx` 加入第三個 Tab

**Files:**
- Modify: `frontend/src/App.jsx`

**Step 1: 修改 `App.jsx`**

加入 `ImageTo3D` import，並新增第三個 tab button 與對應的條件渲染：

```jsx
import { useState } from 'react'
import ImageUploader from './components/ImageUploader'
import VoiceCloner from './components/VoiceCloner'
import ImageTo3D from './components/ImageTo3D'

export default function App() {
  const [activeTab, setActiveTab] = useState('remove-bg')

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI 工具箱</h1>
        <nav className="nav-tabs">
          <button
            className={`nav-tab${activeTab === 'remove-bg' ? ' active' : ''}`}
            onClick={() => setActiveTab('remove-bg')}
          >
            Remove Background
          </button>
          <button
            className={`nav-tab${activeTab === 'voice-clone' ? ' active' : ''}`}
            onClick={() => setActiveTab('voice-clone')}
          >
            Voice Clone
          </button>
          <button
            className={`nav-tab${activeTab === 'image-to-3d' ? ' active' : ''}`}
            onClick={() => setActiveTab('image-to-3d')}
          >
            Image to 3D
          </button>
        </nav>
      </header>
      <main>
        {activeTab === 'remove-bg' && <ImageUploader />}
        {activeTab === 'voice-clone' && <VoiceCloner />}
        {activeTab === 'image-to-3d' && <ImageTo3D />}
      </main>
    </div>
  )
}
```

**Step 2: 手動驗收測試**

啟動前後端，依序確認：

1. 點擊「Image to 3D」tab → 顯示上傳區
2. 上傳一張 PNG/JPEG/WebP → 按「Remove Background」→ 看到去背結果 + 「Convert to 3D」按鈕
3. 按「Convert to 3D」→ loading spinner → 看到 `<model-viewer>` 區塊（mock 回傳空場景，畫面呈現灰底）
4. 「Download GLB」按鈕可下載 `.glb` 檔案
5. 重新選圖 → 狀態清除，回到初始

```bash
# 前端
cd frontend && npm run dev

# 後端（另一個 terminal）
cd backend && uvicorn app.main:app --reload
```

**Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(image-to-3d): add Image to 3D tab to App"
```

---

## 完成確認清單

- [ ] `npm install @google/model-viewer` 完成
- [ ] `main.jsx` 有 `import '@google/model-viewer'`
- [ ] `POST /api/image-to-3d` 回傳合法 GLB（Content-Type: `model/gltf-binary`）
- [ ] 切換到「Image to 3D」tab 正常
- [ ] 去背流程正常（與原 Remove Background Tab 相同體驗）
- [ ] 去背成功後出現「Convert to 3D」按鈕
- [ ] 3D 轉換後出現 `<model-viewer>` 預覽區
- [ ] 下載 GLB 按鈕可用
- [ ] 重新選圖後狀態完全重置
- [ ] Tab 切換時 pending 請求被 abort

---

## 後續（本計劃範圍外）

當真實 3D API 就緒時，只需修改 `backend/app/routes/threed.py` 中的 `image_to_3d` 函式，將 `_make_mock_glb()` 替換成真實模型推理，前端不需任何改動。
