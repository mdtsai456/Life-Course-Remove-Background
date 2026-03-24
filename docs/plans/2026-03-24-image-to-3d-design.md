# Image to 3D — 設計文件

**日期**：2026-03-24
**狀態**：已確認，待實作

---

## 功能概述

新增第三個 Tab「Image to 3D」，讓使用者上傳一張圖片，先去背，再將去背結果轉成 GLB 格式的 3D 模型，並在頁面內以可旋轉的 3D 檢視器呈現，同時可下載。

---

## 整體架構

### 前端新增

| 項目 | 說明 |
|------|------|
| `App.jsx` | 加入第三個 tab `image-to-3d` |
| `src/components/ImageTo3D.jsx` | 主要新元件 |
| `src/services/api.js` | 新增 `convertTo3D(file, signal)` 函式 |
| `@google/model-viewer` | npm 套件，用於瀏覽器渲染 GLB |

### 後端新增

| 項目 | 說明 |
|------|------|
| `backend/app/routes/threed.py` | 新 router |
| `POST /api/image-to-3d` | 接收 PNG，回傳 GLB（現階段可先回傳 mock GLB） |
| `backend/app/main.py` | 掛載新 router |

### 資料流

```
使用者上傳圖片
    → POST /api/remove-background → 回傳 PNG blob
    → 前端顯示去背結果 + 出現「轉成 3D」按鈕
    → 按下按鈕 → POST /api/image-to-3d → 回傳 GLB blob
    → <model-viewer> 載入 GLB → 顯示可旋轉 3D 預覽 + 下載按鈕
```

---

## 元件結構與狀態管理

### `ImageTo3D.jsx` 狀態

| 狀態 | 型別 | 說明 |
|------|------|------|
| `file` | `File \| null` | 使用者選的原始圖片 |
| `originalUrl` | `string \| null` | 原圖預覽 blob URL |
| `removedBgUrl` | `string \| null` | 去背結果 PNG blob URL |
| `model3dUrl` | `string \| null` | 轉換完的 GLB blob URL |
| `step` | `string` | `'idle' \| 'removing' \| 'removed' \| 'converting' \| 'done'` |
| `error` | `string` | 錯誤訊息 |

### UI 狀態機

```
idle      → 上傳區 + 「去背」按鈕
removing  → 按鈕 loading spinner
removed   → 去背結果預覽（PNG）+ 下載PNG + 「轉成 3D」按鈕
converting→ 「轉成 3D」按鈕 loading spinner
done      → <model-viewer> 3D 預覽 + 下載 GLB 按鈕
```

每個非同步操作有各自的 `AbortController`，切換 tab 或重新上傳時自動 abort。

---

## 錯誤處理

### 前端

- **檔案驗證**：上傳時即時檢查，只允許 PNG/JPEG/WebP，最大 10MB
- **去背失敗**：顯示錯誤訊息，保留上傳的圖片，使用者可重試
- **轉 3D 失敗**：顯示錯誤訊息，保留去背結果，使用者可重試轉 3D（不需重新去背）
- **重新選圖**：清除所有狀態，回到 `idle`
- **Tab 切換 / unmount**：abort 所有進行中的請求

### 後端

- 輸入驗證：只接受 PNG（去背結果固定是 PNG）
- 大小限制：10MB
- 模型失敗：回傳 HTTP 500 + 明確錯誤訊息

---

## 技術選型

| 技術 | 選擇 | 理由 |
|------|------|------|
| 3D 格式 | GLB | 瀏覽器最友善，`<model-viewer>` 原生支援 |
| 3D 渲染 | `@google/model-viewer` | 零設定嵌入，支援旋轉、縮放、AR |
| 後端 3D API | 暫用 mock | 先建好介面，之後換真實模型（TripoSR、Meshy 等） |

---

## 超出範圍（本次不做）

- 共用去背邏輯抽成 hook（YAGNI，目前只一個地方用）
- 支援多種 3D 格式（OBJ、PLY）
- 3D 模型的進階編輯功能
