---
title: feat: Add Voice Clone Page
type: feat
status: active
date: 2026-03-24
deepened: 2026-03-24
origin: docs/brainstorms/2026-03-24-voice-clone-page-requirements.md
---

# feat: Add Voice Clone Page

---

## Enhancement Summary

**Deepened on:** 2026-03-24
**Research agents used:** best-practices-researcher, framework-docs-researcher, julik-frontend-races-reviewer, security-sentinel, performance-oracle, correctness-reviewer, maintainability-reviewer, testing-reviewer, architecture-strategist

### Key Improvements Discovered

1. **Critical: `MediaStream` tracks must be explicitly stopped** — `recorder.stop()` does NOT release the microphone. A dedicated `streamRef` is required, with `getTracks().forEach(t => t.stop())` in both the stop handler and unmount cleanup. Without this, the browser mic indicator stays on indefinitely — a user-visible privacy bug.
2. **Critical: `getUserMedia` must be called on user gesture, not in `useEffect`** — React 19 StrictMode double-invokes effects. Calling `getUserMedia` in a click handler avoids this entirely.
3. **Critical: `chunksRef` must be reset at the start of every recording** — without `chunksRef.current = []`, a second recording appends chunks from the previous session, silently producing a corrupted Blob.
4. **`onstop` async gap**: Final `ondataavailable` may fire after `onstop`. Defer Blob assembly with `Promise.resolve().then(...)` inside `onstop`.
5. **Cross-browser MIME type**: Safari requires `audio/mp4`; use `MediaRecorder.isTypeSupported()` probe with MP4 first in priority order.
6. **`isAcquiringMic` state needed**: Guards the async gap between click and `getUserMedia` resolving (disables buttons, prevents double-click race).
7. **Maintainability**: Inline the `cloneVoice` mock in `VoiceCloner.jsx` instead of adding a dead-code stub to the live `services/api.js`. Keep `services/api.js` for real network calls only.
8. **App.jsx subtitle bug**: The current hardcoded subtitle "Upload a PNG, JPEG, or WebP..." will display on the Voice Clone tab. Must be removed or made tab-conditional.

### New Risks Discovered

- Safari < 14.1 has zero MediaRecorder support (no polyfill available)
- `getUserMedia` requires HTTPS in production; `navigator.mediaDevices` is `undefined` on HTTP
- Audio Blobs can be several MB for long recordings; no size cap is planned
- Tab-switch unmount while recording leaves microphone active without proper cleanup effect

---

## Overview

在現有「移除背景」App 中新增「Voice Clone」功能頁面，讓使用者可以錄音、輸入文字、送出後取得一段以自己聲音朗讀該文字的新音檔。本次只實作前端介面，後端 API 以 mock/stub 代替。
(see origin: docs/brainstorms/2026-03-24-voice-clone-page-requirements.md)

## Problem Statement / Motivation

目前 App 功能單一，只有移除背景。新增聲音克隆功能以擴充使用情境。因後端尚未就緒，先完成前端介面，讓 UI/UX 可獨立開發與驗收，不受後端阻塞。

## Proposed Solution

1. **`App.jsx`**：加入頂部 Tab 導覽（state 切換，無 React Router），控制顯示 `<ImageUploader>` 或 `<VoiceCloner>`；移除現有的硬編碼 subtitle
2. **`VoiceCloner.jsx`**：新元件，整合錄音（MediaRecorder API）、文字輸入、送出、結果播放；mock API 直接內聯
3. **`index.css`**：追加 Tab 導覽與 VoiceCloner 所需 CSS 類別
4. **`services/api.js`**：本次**不修改** — mock 直接內聯在元件中

### Research Insights

**Cloning Voice 服務位置決策：**
- `services/api.js` 目前只含真實網路呼叫（`removeBackground`）。加入一個 mock stub 會污染一個 live module，且後端就緒時開發者必須「記得移除 mock 行為」而非「填入真實 fetch」。
- **更好的邊界**：mock 直接內聯在 `VoiceCloner.jsx` 的 `handleSubmit` 中，加上明顯的 `TODO: Replace with real API` 註解。當後端就緒時，在 `services/api.js` 新增 `cloneVoice()` 真實函式，並在元件中 import 它。

---

## Technical Considerations

### MediaRecorder API

- 瀏覽器原生 API，無需安裝額外套件
- **跨瀏覽器 MIME type 必須使用 `isTypeSupported()` 動態探測**，不可硬編碼

```js
// 放在元件外（never recreated）
function getSupportedMimeType() {
  const candidates = [
    'audio/mp4;codecs=mp4a.40.2', // Safari 14.1+ (必須優先)
    'audio/mp4',                   // Safari fallback
    'audio/webm;codecs=opus',      // Chrome / Edge / Firefox
    'audio/webm',                  // Chrome / Edge fallback
    'audio/ogg;codecs=opus',       // Firefox fallback
  ]
  return candidates.find(t => MediaRecorder.isTypeSupported(t)) ?? ''
}

function mimeTypeToExtension(mimeType) {
  if (mimeType.startsWith('audio/webm')) return 'webm'
  if (mimeType.startsWith('audio/ogg'))  return 'ogg'
  if (mimeType.startsWith('audio/mp4'))  return 'mp4'
  return 'audio'
}
```

**瀏覽器相容性：**

| 瀏覽器 | 支援情況 | 格式 |
|--------|----------|------|
| Chrome / Edge | 完整支援 | `audio/webm;codecs=opus` |
| Firefox | 完整支援 | `audio/webm;codecs=opus` 或 `audio/ogg;codecs=opus` |
| Safari 14.1+ | 支援 | `audio/mp4`（AAC），不支援 WebM |
| Safari < 14.1 | **不支援** | 需顯示 "not supported" 訊息 |
| iOS Safari 14.3+ | 支援 | `audio/mp4` |

### getUserMedia 必須在 User Gesture 中呼叫（不可在 useEffect）

React 19 StrictMode 會雙重呼叫 `useEffect`（mount → cleanup → mount），若在 effect 中呼叫 `getUserMedia`，第一次取得的 stream 會被遺棄但仍保持麥克風開啟，導致 OS 麥克風指示燈常亮。

**正確做法：僅在按鈕 click handler 中呼叫 `getUserMedia`，不在任何 effect 中呼叫。**

### State 設計：避免 Boolean Soup

使用 `isAcquiringMic` state 來涵蓋 `getUserMedia` 的非同步等待期（async gap），防止使用者在這段時間內點擊其他按鈕：

```
State:
  isAcquiringMic   (boolean)       - getUserMedia 正在等待中
  audioBlob        (Blob | null)   - 錄製完成的音頻 Blob（null = 尚未錄音或正在錄音中）
  recordingSeconds (number)        - 計時器秒數（每次錄音前需重置為 0）
  isRecording      (boolean)       - 是否正在錄音
  text             (string)        - textarea 輸入文字
  resultUrl        (string | null) - API 回傳的 Blob URL
  loading          (boolean)       - 送出中
  error            (string)        - 錯誤訊息（空字串代表無錯誤）

Refs:
  mediaRecorderRef  - MediaRecorder instance
  streamRef         - MediaStream（必須！用於停止 mic tracks）
  chunksRef         - 錄音資料 chunks []（每次錄音前必須清空）
  timerRef          - setInterval id
```

### `onstop` 非同步間隙：Blob 組合需延遲一個 microtask

瀏覽器不保證 `onstop` 與最後一個 `ondataavailable` 的執行順序。若在 `onstop` 中直接組合 Blob，可能遺失最後一個 chunk，造成音頻結尾截斷：

```js
recorder.onstop = () => {
  // 等一個 microtask，確保最後的 ondataavailable 已執行
  Promise.resolve().then(() => {
    const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
    setAudioBlob(blob)
    chunksRef.current = [] // 清空，釋放記憶體
    stopMicTracks()        // 停止 mic tracks（見下方）
  })
}
```

### MediaStream Tracks 必須手動停止（Privacy Critical）

`recorder.stop()` **不會**停止底層 `MediaStream` tracks。不呼叫 `.stop()` 會讓瀏覽器麥克風指示燈持續亮著，使用者可見，屬 privacy bug：

```js
// 必須同時出現在以下兩處：
// 1. handleStopRecording() 呼叫後（或 onstop 內）
// 2. useEffect cleanup（元件 unmount 時）
function stopMicTracks() {
  streamRef.current?.getTracks().forEach(t => t.stop())
  streamRef.current = null
}
```

### getUserMedia 錯誤映射

各瀏覽器使用不同錯誤名稱（Chrome 有 legacy 名稱），必須兩種都處理：

```js
function mapGetUserMediaError(err) {
  const name = err.name
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError')
    return '麥克風存取被拒絕。請在瀏覽器網址列允許麥克風，然後重試。'
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError')
    return '找不到麥克風裝置。請連接麥克風後重試。'
  if (name === 'NotReadableError' || name === 'TrackStartError')
    return '麥克風正被其他應用程式使用。關閉其他使用中的應用程式後重試。'
  if (name === 'SecurityError')
    return '麥克風存取需要 HTTPS 連線。'
  return `無法存取麥克風：${err.message}`
}
```

### Mock API（R7 決策）

- `cloneVoice` mock **內聯在 `VoiceCloner.jsx` 的 `handleSubmit` 中**，不加入 `services/api.js`
- 延遲 1500ms 後，直接回傳原始 `audioBlob` 的 Blob URL（echo back）
- 後端就緒時，在 `services/api.js` 新增真實 `cloneVoice()` 函式，元件中 import 它並移除 inline mock

### Blob URL 生命週期管理

- `resultUrl` 在 `useEffect` cleanup 中呼叫 `URL.revokeObjectURL` 釋放記憶體（沿用 `ImageUploader.jsx` 模式）
- **新增**：`handleStartRecording` 開始時應主動呼叫 `setResultUrl(null)` + `setError('')`，清除舊的結果

### Tab 切換

- `App.jsx` 加入 `const [activeTab, setActiveTab] = useState('remove-bg')`
- 兩個值：`'remove-bg'` / `'voice-clone'`
- **移除現有的靜態 subtitle 段落**（"Upload a PNG, JPEG, or WebP image..."）— 它會在 Voice Clone Tab 時錯誤顯示

---

## System-Wide Impact

- **`App.jsx`**：從無狀態 layout shell 轉為持有一個 `activeTab` state；移除硬編碼 subtitle；`<ImageUploader>` 行為完全不受影響
- **`index.css`**：純追加新類別，不修改任何既有規則
- **`services/api.js`**：**本次不修改**
- **`ErrorBoundary`**：`main.jsx` 已在最外層包覆整個 App，新元件自動受保護，無需額外處理
- **React StrictMode**：`main.jsx` 使用 `<StrictMode>`，意味著 dev 模式下元件會 mount → unmount → mount 各一次。`handleStartRecording` 在按鈕 click 中呼叫（非 effect），不受影響

### Research Insights

**Tab 切換的 unmount 行為：**

`VoiceCloner` 使用條件渲染（`activeTab === 'voice-clone' && <VoiceCloner />`），意味著切換 Tab 時元件 unmount。這實際上是正確的行為：

- 切換離開時，unmount cleanup effect 會停止錄音 + 停止 mic tracks + 清除計時器
- 切換回來時，元件從初始狀態重新掛載（state 重置），符合使用者預期

**唯一要求**：`useEffect` cleanup 必須實作完整，否則 unmount 時麥克風仍會繼續開著。

**架構約束（防止未來 Router 遷移困難）：**

功能元件（`ImageUploader`、`VoiceCloner`）絕不應接收 `setActiveTab` 作為 props。跨 tab 的導覽邏輯只能由 `App.jsx` 的 tab bar 觸發。若未來需要 "前往 Voice Clone" 的跨元件導覽，屆時引入 React Router 是正確時機。

---

## Acceptance Criteria

- [ ] R1: 頂部顯示「Remove Background」和「Voice Clone」兩個 Tab；點擊可切換；預設顯示 Remove Background Tab
- [ ] R1: 切換 Tab 時，兩頁各自的狀態互不干擾（條件渲染確保 unmount 重置）
- [ ] R2: Voice Clone 頁面有「開始錄音」按鈕；錄音中顯示計時器（秒數遞增，每次從 0 開始）並切換為「停止」按鈕；停止後顯示已錄製時長
- [ ] R2: 若使用者拒絕麥克風權限，顯示對應錯誤訊息（含具體操作指引）
- [ ] R2: 在非 HTTPS 環境或不支援錄音的瀏覽器下，顯示「不支援」提示訊息
- [ ] R2: 錄音結束後，瀏覽器麥克風指示燈立即熄滅（mic tracks 已停止）
- [ ] R3: 有 `<textarea>` 供輸入文字，含有適當的 placeholder 文字；錄音中及送出中為 disabled
- [ ] R4: 「送出」按鈕在 `audioBlob === null || text.trim() === '' || loading || isRecording || isAcquiringMic` 時為 `disabled`；送出中顯示 loading spinner
- [ ] R5: 送出成功後顯示 `<audio key={resultUrl} controls src={resultUrl}>` 播放器和「下載音檔」按鈕，下載檔名含正確副檔名（.webm / .mp4 / .ogg）
- [ ] R6: API 錯誤或錄音失敗時，以 `.error-message` 樣式顯示錯誤訊息；loading 在 finally 中確保重置
- [ ] R7: inline mock 模擬延遲並回傳可播放的音檔 Blob URL

---

## Success Metrics

- 使用者可在前端完整走完「錄音 → 輸入文字 → 送出 → 播放/下載」流程（mock 回應）
- 後端就緒後，只需在 `services/api.js` 新增真實函式，並替換元件中的 inline mock import，無需其他改動
- 任何時候停止錄音（包括切換 Tab、關閉元件），瀏覽器麥克風指示燈隨即熄滅

---

## Dependencies & Risks

| 項目 | 說明 |
|------|------|
| MediaRecorder 瀏覽器支援 | Safari 14.1+ 支援（音訊格式為 `audio/mp4`）；Safari < 14.1 完全不支援，需顯示提示 |
| 麥克風權限 | 使用者須授予；拒絕時需 graceful error 處理（含具體指引訊息） |
| HTTPS 必要 | `navigator.mediaDevices` 在 HTTP 環境下為 `undefined`；需在元件中加入 Secure Context 檢查 |
| StrictMode 相容性 | `getUserMedia` 在 click handler 中呼叫（非 effect），天然相容 StrictMode |
| Mock 回傳格式 | webm 或 mp4（瀏覽器錄製格式），後端真實格式需求留待後續迭代 |
| MediaRecorder MIME 轉換 | Mock 階段不需轉換；後端就緒後在 `services/api.js` 真實實作中處理 |
| 音頻 Blob 大小 | 60 秒 webm/opus ≈ 400-700 KB，在可接受範圍；建議加入最大錄音時長（60s）自動停止 |

---

## Implementation Files

### 1. 修改：`frontend/src/App.jsx`

加入 `activeTab` state 及頂部 Tab 導覽列，根據 tab 值條件渲染對應元件。**移除現有的靜態 subtitle 段落。**

```
import { useState } from 'react'
import ImageUploader from './components/ImageUploader'
import VoiceCloner from './components/VoiceCloner'

export default function App() {
  const [activeTab, setActiveTab] = useState('remove-bg')

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI 工具箱</h1>
        // 移除原有靜態 subtitle — 各元件自行顯示說明
        <nav className="nav-tabs">
          <button
            className={`nav-tab${activeTab === 'remove-bg' ? ' active' : ''}`}
            onClick={() => setActiveTab('remove-bg')}
          >Remove Background</button>
          <button
            className={`nav-tab${activeTab === 'voice-clone' ? ' active' : ''}`}
            onClick={() => setActiveTab('voice-clone')}
          >Voice Clone</button>
        </nav>
      </header>
      <main>
        {activeTab === 'remove-bg' && <ImageUploader />}
        {activeTab === 'voice-clone' && <VoiceCloner />}
      </main>
    </div>
  )
}
```

### 2. 新建：`frontend/src/components/VoiceCloner.jsx`

完整的聲音克隆功能元件，含所有安全 lifecycle 處理。

```
// --- 元件外（純函式，never recreated）---

function getSupportedMimeType() {
  const candidates = [
    'audio/mp4;codecs=mp4a.40.2', // Safari 優先
    'audio/mp4',
    'audio/webm;codecs=opus',     // Chrome / Edge / Firefox
    'audio/webm',
    'audio/ogg;codecs=opus',
  ]
  return candidates.find(t => MediaRecorder.isTypeSupported(t)) ?? ''
}

function mimeTypeToExtension(mimeType) {
  if (mimeType.startsWith('audio/webm')) return 'webm'
  if (mimeType.startsWith('audio/ogg'))  return 'ogg'
  if (mimeType.startsWith('audio/mp4'))  return 'mp4'
  return 'audio'
}

function mapGetUserMediaError(err) { /* see Technical Considerations */ }

// --- State ---
  isAcquiringMic   (boolean)       - 等待 getUserMedia 中
  audioBlob        (Blob | null)   - 錄製完成的音頻 Blob
  recordingSeconds (number)        - 計時器秒數
  isRecording      (boolean)       - 是否正在錄音
  text             (string)        - textarea 文字
  resultUrl        (string | null) - Blob URL
  loading          (boolean)       - 送出中
  error            (string)        - 錯誤訊息

// --- Refs ---
  mediaRecorderRef  - MediaRecorder instance
  streamRef         - MediaStream（停止 mic tracks 用）
  chunksRef         - [] chunks（每次錄音前清空）
  timerRef          - setInterval id

// --- Handlers ---
  handleStartRecording() 流程：
    1. 檢查 !window.isSecureContext || !navigator.mediaDevices?.getUserMedia → setError, return
    2. setIsAcquiringMic(true), setError(''), setResultUrl(null)
    3. chunksRef.current = []
    4. await getUserMedia({ audio: true }) → catch → mapGetUserMediaError, setIsAcquiringMic(false), return
    5. streamRef.current = stream
    6. 建立 MediaRecorder（mimeType from getSupportedMimeType()，無 timeslice）
    7. recorder.ondataavailable = 收集 size > 0 的 chunks
    8. recorder.onstop = Promise.resolve().then(() => { 組合 Blob, setAudioBlob, 清空 chunksRef, stopMicTracks() })
    9. recorder.onerror = setError, stopMicTracks(), clearInterval(timerRef)
    10. recorder.start()
    11. setIsAcquiringMic(false), setIsRecording(true), setRecordingSeconds(0)
    12. 啟動計時器

  handleStopRecording() 流程：
    1. guard: recorder.state === 'recording' || 'paused'
    2. recorder.stop() → 觸發 onstop（非同步）
    3. clearInterval(timerRef.current)
    4. setIsRecording(false)
    // 注意：stopMicTracks() 在 onstop 的 Promise.resolve() 中呼叫

  handleSubmit(e) 流程（三段式，沿用 ImageUploader 模式）：
    setLoading(true), setError(''), setResultUrl(null) + revoke old URL
    try:
      // TODO: Replace with import { cloneVoice } from '../services/api'
      await new Promise(resolve => setTimeout(resolve, 1500))
      const url = URL.createObjectURL(audioBlob)
      setResultUrl(url)
    catch (err):
      setError(err.message || 'Something went wrong.')
    finally:
      setLoading(false)

// --- Effects ---
  [resultUrl] → cleanup: URL.revokeObjectURL(resultUrl)

  [] (unmount cleanup) → cleanup:
    clearInterval(timerRef.current)
    if recorder.state !== 'inactive': recorder.stop()
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null

// --- Submit button disabled condition ---
  audioBlob === null || text.trim() === '' || loading || isRecording || isAcquiringMic

// --- JSX key prop for audio ---
  <audio key={resultUrl} controls src={resultUrl} style={{ width: '100%' }} />
```

### 3. 修改：`frontend/src/index.css`

在檔案末端追加以下 class（不修改任何既有規則）：

```
/* Tab navigation */
.nav-tabs           - display flex, border-bottom: 2px solid #d0d0d0, margin-bottom 1.5rem
.nav-tab            - Tab 按鈕（background none, cursor pointer, padding, font-size）
.nav-tab.active     - border-bottom: 2px solid #2563eb（藍色底線），color: #2563eb

/* VoiceCloner */
.voice-cloner       - 主容器，類比 .uploader
.record-section     - 錄音區塊容器（flex align-items center gap）
.record-button      - 錄音按鈕（background #dc2626, color white, hover #b91c1c, 8px radius）
.recording-timer    - 計時器數字（font-variant-numeric tabular-nums）
.recorded-status    - 已錄製時長確認文字（color #555）
.prompt-input       - textarea（全寬，min-height 100px，8px radius，border #d0d0d0，resize vertical）
.audio-result       - 結果區塊容器（padding, background #fff, border-radius 12px）
.download-audio-btn - 下載按鈕（沿用 .download-button 的綠色樣式）
```

**注意**：原計畫的 `.clone-text-input` 重命名為 `.prompt-input`，因現有 CSS 命名慣例為 role-based（`.upload-form`、`.preview-card`），而非 element-based。

---

## Security Considerations

### Secure Context Guard（必須在元件中實作）

```js
// handleStartRecording 的第一步
if (!window.isSecureContext) {
  setError('麥克風存取需要 HTTPS 連線。')
  return
}
if (!navigator.mediaDevices?.getUserMedia) {
  setError('您的瀏覽器不支援音頻錄製。')
  return
}
```

### Audio Blob 驗證（建議在 handleSubmit 中加入）

```js
// 送出前驗證
if (!audioBlob.type.startsWith('audio/')) {
  setError('無效的音頻格式。')
  return
}
const MAX_BLOB_SIZE = 10 * 1024 * 1024 // 10 MB（對應現有圖片上傳限制）
if (audioBlob.size > MAX_BLOB_SIZE) {
  setError('音頻檔案過大（最大 10 MB）。')
  return
}
```

### Blob URL 安全性

- `blob:` URL 僅在同源（same-origin）可存取，無 XSS 風險
- `<audio src={blobUrl}>` 和 `<a href={blobUrl} download>` 均為安全使用
- 後端就緒後，CSP header 需加入 `media-src 'self' blob:` 才能允許 `<audio>` 播放 Blob URL

### 建議最大錄音時長

在 `handleStartRecording` 中設定 60 秒自動停止：

```js
const MAX_DURATION_MS = 60 * 1000
const autoStopTimer = setTimeout(() => handleStopRecording(), MAX_DURATION_MS)
// 在 handleStopRecording 中加入 clearTimeout(autoStopTimer)
```

---

## Testing Infrastructure（Optional but Recommended）

目前專案零測試基礎設施。以下為最低成本的測試投資方向：

### 需新增的套件

```
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
```

在 `frontend/vite.config.js` 的 `defineConfig` 中加入：

```js
test: {
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.js'],
  globals: true,
}
```

`frontend/src/test/setup.js` 內容：

```js
import '@testing-library/jest-dom'
global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
global.URL.revokeObjectURL = vi.fn()
global.MediaStream = class MediaStream { getTracks() { return [] } }
// FakeMediaRecorder（見下方）
```

### FakeMediaRecorder（供測試使用）

```js
class FakeMediaRecorder {
  constructor(stream, options = {}) {
    this.stream = stream
    this.mimeType = options.mimeType || 'audio/webm'
    this.state = 'inactive'
    this.ondataavailable = null
    this.onstop = null
    this.onerror = null
  }
  start() {
    this.state = 'recording'
    this.ondataavailable?.({ data: new Blob(['fake-audio'], { type: this.mimeType }) })
  }
  stop() {
    this.state = 'inactive'
    this.onstop?.()
  }
  static isTypeSupported() { return true }
}
global.MediaRecorder = FakeMediaRecorder
```

### 最高 ROI 的三個測試

1. **Submit button guard**（R4 驗收）：無錄音時 disabled，有錄音有文字時 enabled
2. **getUserMedia 拒絕**（R2 驗收）：mock `getUserMedia` 拋出 `NotAllowedError`，驗證 `.error-message` 出現
3. **API 錯誤顯示**（R6 驗收）：mock `cloneVoice` 拋錯，驗證錯誤訊息顯示且 loading spinner 消失

---

## Deferred Questions（resolved in this plan）

- **[R7] Mock 格式**：使用瀏覽器 MediaRecorder 原生格式（`recorder.mimeType` 屬性），直接 echo back audioBlob
- **[R2] MediaRecorder MIME 轉換**：Mock 階段不需轉換；後端就緒後在 `cloneVoice()` 真實實作中處理
- **Mock 位置**：內聯在 `VoiceCloner.jsx` handleSubmit 中（不加入 services/api.js）

---

## Sources & References

### Origin

- **Origin document:** [docs/brainstorms/2026-03-24-voice-clone-page-requirements.md](docs/brainstorms/2026-03-24-voice-clone-page-requirements.md)
  - Key decisions carried forward: (1) 頂部 Tab 而非 URL 路由, (2) 前端先行 API 以 mock 替代, (3) 錄音使用 Web MediaRecorder API

### Internal References

- 元件 state/handler/effect 模式：`frontend/src/components/ImageUploader.jsx`
- CSS 命名慣例與色彩 token：`frontend/src/index.css`
- 確認 StrictMode 啟用：`frontend/src/main.jsx:8`

### External References

- MDN MediaRecorder API: https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder
- MDN getUserMedia: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
- MDN MediaRecorder.isTypeSupported(): https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static
- MDN MediaStream Recording API: https://developer.mozilla.org/en-US/docs/Web/API/MediaStream_Recording_API
- Common getUserMedia Errors: https://blog.addpipe.com/common-getusermedia-errors/
- React 19 StrictMode: https://react.dev/reference/react/StrictMode
- React 19 Why is useEffect Running Twice: https://dev.to/hobbada/why-is-useeffect-running-twice-the-complete-guide-to-react-19-strict-mode-and-effect-cleanup-1n60
