---
title: "feat: Add pydub WAV conversion in voice clone endpoint"
type: feat
status: completed
date: 2026-03-27
origin: docs/brainstorms/2026-03-27-voice-clone-audio-format-requirements.md
---

# feat: Add pydub WAV conversion in voice clone endpoint

## Overview

後端 `/api/clone-voice` endpoint 在驗證通過後，以 `pydub` 將上傳音檔（webm/mp4/ogg）轉換為 WAV 格式，為後續整合 Coqui TTS XTTS 模型（`speaker_wav` 需要 WAV 路徑）做好準備。前端僅調整下載檔名（僅修改 `download` 屬性）。

## Problem Frame

MediaRecorder API 依瀏覽器輸出不同格式（Chrome → webm/opus，Safari → mp4/aac），`torchaudio.load()` 無法可靠解析 webm。後端目前為 mock 實作，驗證後直接回傳原始音檔。需要在呼叫 XTTS 之前加入 WAV 轉換層。

（see origin: docs/brainstorms/2026-03-27-voice-clone-audio-format-requirements.md）

## Requirements Trace

- R1. 前端維持現有行為：直接上傳原始瀏覽器格式（webm/mp4/ogg），不做任何轉換。
- R2. 後端驗證通過後，以 pydub 將音檔轉為 WAV；XTTS 內部會自動 resample 至 22050Hz 及轉 mono，不需手動設定。
- R3. 格式轉換使用 `pydub` 套件，加入 `requirements.txt`。
- R4. 部署環境需安裝 FFmpeg（pydub 的系統依賴）。

## Scope Boundaries

- 前端僅調整下載檔名（僅修改 `download` 屬性，hardcode `"cloned-voice.wav"`），其他前端邏輯不動。
- 不整合真實 XTTS 模型（另見 `docs/brainstorms/2026-03-25-voice-cloning-real-implementation-requirements.md`）。
- 不加入「上傳本地音檔」功能。
- 不更動輸入驗證邏輯或 API 介面。
- 本計劃不建立 Dockerfile（R4 記錄為部署注意事項）。

## Context & Research

### Relevant Code and Patterns

- `backend/app/routes/voice.py` — 唯一需要修改的後端路由；現有 `_detect_audio_type` helper 是提取 pure function 的模式範例
- `backend/requirements.txt` — 加入 `pydub` 依賴
- `backend/tests/test_voice.py` — 使用合成魔術位元組作為測試音檔；加入 pydub 後需 mock `AudioSegment.from_file`
- `backend/app/routes/images.py` — 可參考 `rembg` 的引入方式（第三方 AI 相關套件）

### Institutional Learnings

- `docs/solutions/` 目錄不存在，無歷史解決方案可參考。

### External References

- 不需外部研究：pydub API 穩定，本地模式充足。

## Key Technical Decisions

- **In-memory 轉換（不使用 temp file）**：以 `io.BytesIO` 作為 pydub 的輸入與輸出緩衝區，無需 temp file 管理。10MB 上限的壓縮音檔解壓後可能達 50MB 以上，因此服務以 `MAX_PCM_SIZE`（50MB）為上限，超過即回傳 422。未來整合 XTTS 時，才需改為 temp file（`speaker_wav` 接受路徑而非 bytes）；此時再加入 `tempfile.NamedTemporaryFile` + `try/finally` 清理。
- **Mock 改為回傳 WAV**：目前 mock 直接回傳原始音檔。加入轉換後，mock 改為回傳 WAV bytes，`content-type: audio/wav`，`filename: cloned.wav`。這樣可驗證轉換管線正確運作，且更接近最終 XTTS 行為（輸出為 WAV）。
- **提取 `_convert_to_wav` helper（domain exception 模式）**：helper 不應直接 raise `HTTPException`（FastAPI 框架類別），以免在未來的 CLI 工具或 Celery task 中難以重用。改為定義一個輕量 `AudioConversionError(Exception)` domain exception，由 helper raise；endpoint 捕捉後轉為 `HTTPException`。
- **pydub 失敗分三類，各自對應不同 HTTP 狀態碼**：
  - `pydub.exceptions.CouldntDecodeError` → HTTP 422（音檔損壞，使用者問題）
  - `FileNotFoundError` → HTTP 503（FFmpeg 未安裝，server 設定問題）
  - 其他 `Exception` → re-raise（讓 FastAPI 回傳 500，不隱藏未知錯誤）
  - 全部 detail 字串使用靜態常數，**絕不** 將 `str(e)` / `repr(e)` 或 FFmpeg stderr 放入 detail（避免洩漏系統資訊給前端）。
- **同步 pydub 在 async endpoint 的 event loop 阻塞**：`pydub.AudioSegment.from_file()` 是同步呼叫（spawn FFmpeg subprocess），在 `async def clone_voice` 中直接呼叫會阻塞 uvicorn event loop。建議方案：`await anyio.to_thread.run_sync(lambda: _convert_to_wav(contents))`（anyio 已為 FastAPI/Starlette 依賴，無需加入 requirements）。此方案保留 `async def` 與 `await file.read()` 不變。
- **不做 streaming**：檔案上限 10MB，BytesIO in-memory 處理足夠，無需 streaming。

## Open Questions

### Resolved During Planning

- **XTTS 輸入格式規格**：`sample_rate=22050`、`output_sample_rate=24000`；內部自動 resample 與轉 mono，只需提供可被 `torchaudio.load()` 讀取的 WAV 即可。不需手動設定 sample rate。
- **pydub 大檔案記憶體問題**：10MB 壓縮音檔解壓後可能超過 50MB，服務以 `MAX_PCM_SIZE`（50MB）為硬上限，超過即拒絕（422）；50MB 以內在後端 RAM 可接受，無需 streaming。

### Deferred to Implementation

- **XTTS 整合時的 temp file 策略**：`speaker_wav` 需要檔案路徑而非 bytes，目前只需記錄此 TODO 即可，等實際整合 XTTS 時再處理。
- **WAV header 驗證**：轉換後的 WAV 是否需要加上 magic bytes 驗證？等整合 XTTS 確認後再決定。

## High-Level Technical Design

> *此圖為 directional guidance，供 reviewer 驗證方向，非實作規格。*

```text
POST /api/clone-voice  (async def, runs in uvicorn event loop)
       │
[1-5] existing validation steps (415 / 400 / 413)
       │
[6] await anyio.to_thread.run_sync(                    ← NEW (thread pool)
      lambda: _convert_to_wav(contents)
    )
    ┌─────────────────────────────────────────────────┐
    │ _convert_to_wav(contents: bytes) -> bytes        │
    │  AudioSegment.from_file(BytesIO(contents))       │
    │  .export(buf, format="wav")                       │
    │  return buf.getvalue()                           │
    │                                                  │
    │  CouldntDecodeError → raise AudioConversionError │
    │  FileNotFoundError  → re-raise                   │
    │  other Exception    → re-raise (500)             │
    └─────────────────────────────────────────────────┘
       │                 AudioConversionError → HTTP 422
       │                 FileNotFoundError   → HTTP 503
       ▼
[7] mock: return Response(wav_bytes, "audio/wav", "cloned.wav")
    (future: save to tempfile → tts.tts_to_file(speaker_wav=path) → return output.wav)
```

## Implementation Units

- [x] **Unit 1: 加入 pydub 依賴**

  **Goal:** 確保 pydub 套件可在後端環境安裝使用。

  **Requirements:** R3

  **Dependencies:** 無

  **Files:**
  - Modify: `backend/requirements.txt`

  **Approach:**
  - 在 `requirements.txt` 末尾加入 `pydub==0.25.1`（目前最新穩定版）。
  - 不鎖定 FFmpeg 版本（系統依賴，由部署環境管理）。

  **Patterns to follow:**
  - 參考現有格式：每行一個套件，`name==version` 格式。

  **Test scenarios:**
  - `pip install -r requirements.txt` 成功安裝。

  **Verification:**
  - `python -c "from pydub import AudioSegment; print('ok')"` 不報錯。

---

- [x] **Unit 2: 實作 `_convert_to_wav` helper 並整合到 endpoint**

  **Goal:** 在驗證通過後加入音檔 WAV 轉換步驟，mock 改為回傳 WAV 回應。

  **Requirements:** R1, R2

  **Dependencies:** Unit 1

  **Files:**
  - Modify: `backend/app/routes/voice.py`

  **Approach:**
  - 新增 `import io` 與 `from pydub import AudioSegment`（頂部 import 區塊）。
  - 新增 `class AudioConversionError(Exception): pass`（module-level，輕量 domain exception）。
  - 新增 `_convert_to_wav(contents: bytes, fmt: str) -> bytes`，接受 `fmt` 參數（來自 `detected` 變數，如 `"webm"`、`"mp4"`、`"ogg"`），位置跟在 `_detect_audio_type` 之後：
    - `AudioSegment.from_file(io.BytesIO(contents), format=fmt)` — 明確傳入格式（BytesIO 無副檔名，FFmpeg 無法靠 filename 猜測；明確比 probing 更快且更可靠）
    - `.export(wav_buffer, format="wav")`（pydub 預設即輸出 16-bit signed PCM）
    - 解碼後立即檢查 `len(audio.raw_data) > 50 * 1024 * 1024`（50MB 上限，即 `MAX_PCM_SIZE`），超過 raise `AudioConversionError("音訊解壓後超過大小限制。")`（防記憶體炸彈）
    - 回傳 `wav_buffer.getvalue()`（**不用** `read()`；export 後 stream position 在末尾，`read()` 回傳空 bytes）
    - 捕捉 `pydub.exceptions.CouldntDecodeError` → raise `AudioConversionError`
    - 捕捉 `FileNotFoundError` → re-raise（讓上層處理為 503）
    - 其他 `Exception` → re-raise（讓 FastAPI 回傳 500）
    - **不將 `str(e)` 或 FFmpeg stderr 放入 detail**：detail 字串用靜態常數
  - 在 endpoint 中呼叫 helper（`detected` 已含格式資訊）：`fmt = {"audio/webm": "webm", "audio/mp4": "mp4", "audio/ogg": "ogg"}[detected]`，然後 `wav_bytes = await anyio.to_thread.run_sync(lambda: _convert_to_wav(contents, fmt))`（避免阻塞 event loop；anyio 為 FastAPI 現有依賴，無需加入 requirements）
  - 在 endpoint 中捕捉：`AudioConversionError` → `HTTPException(422, "無法解碼音訊檔案，請確認錄音是否完整後重試。")`；`FileNotFoundError` → `HTTPException(503, "音訊轉換服務暫時無法使用。")`
  - 更新 mock 回傳：`content=wav_bytes`、`media_type="audio/wav"`、`filename="cloned.wav"`。
  - 移除舊的 `ext = {...}[detected]` 對映（已不需要決定回傳格式）。
  - 更新 logger.info 訊息反映 WAV 轉換已發生。

  **Patterns to follow:**
  - `_detect_audio_type` 的 pure function 模式（同檔案，domain exception 而非 HTTPException）。
  - 現有 `HTTPException` raise 格式（`status_code` + 靜態 `detail` 字串常數）。

  **Test scenarios:**
  - 合法 webm/mp4/ogg 上傳 → 回傳 `audio/wav`、`cloned.wav`、WAV bytes（16-bit PCM RIFF header）。
  - `CouldntDecodeError`（音檔通過 magic bytes 但 FFmpeg 拒絕）→ HTTP 422。
  - `FileNotFoundError`（FFmpeg 未安裝）→ HTTP 503。
  - BytesIO in-memory 轉換，無 temp file，無 GC 洩漏風險。

  **Verification:**
  - 成功請求的 `content-type` 為 `audio/wav`。
  - 成功請求的 `Content-Disposition` 為 `attachment; filename="cloned.wav"`。
  - `_detect_audio_type` 的行為不受影響（現有 unit tests 仍通過）。

---

- [x] **Unit 3: 更新測試**

  **Goal:** 使現有測試通過新的 WAV 回傳行為，並補充轉換邏輯的 unit tests。

  **Requirements:** R2（驗證成功轉換場景）

  **Dependencies:** Unit 2

  **Files:**
  - Modify: `backend/tests/test_voice.py`

  **Approach:**

  **A. 更新現有 integration tests（`TestCloneVoiceEndpoint`）：**

  需更新的三支 success 測試（`test_success_webm` L63-74、`test_success_ogg` L76-85、`test_success_mp4` L87-96）：
  - 以 `unittest.mock.patch("app.routes.voice.AudioSegment")` 作 context manager：
    - `mock_cls.from_file.return_value = mock_seg`（MagicMock）
    - **`mock_seg.export.side_effect = lambda buf, format, parameters=None: buf.write(WAV_STUB)`**（關鍵：`export` 是副作用寫入 buffer，不是 return value；用 `side_effect` 而非 `return_value`）
    - `WAV_STUB` 可定義為 module 頂部常數：`b"RIFF\x00\x00\x00\x00WAVEfmt "`（最小 WAV 辨識頭）
  - 更新三項 assertions（全部三支測試）：
    - `content-type` → `"audio/wav"`
    - `content-disposition` → `'attachment; filename="cloned.wav"'`
    - `resp.content == audio`（舊 → 刪除或改為 `resp.content == WAV_STUB`）
  - `test_reject_mime_with_codec_suffix` 也需同樣的 mock（成功路徑）。
  - 所有 4xx 驗證失敗測試（415、400、413）在到達 pydub 之前 raise，**不需要 mock**，維持原狀。

  **B. 新增 `TestConvertToWav` unit test class：**
  - 直接測試 `_convert_to_wav` function（從 `app.routes.voice` import）。
  - 測試場景：
    - 成功路徑：mock `AudioSegment.from_file` + `export` side_effect → 驗證回傳 `WAV_STUB` bytes。
    - `CouldntDecodeError` 路徑：`from_file` raise `CouldntDecodeError` → 驗證 `AudioConversionError` 被拋出（**不是** `HTTPException`，helper 只 raise domain exception）。
    - `FileNotFoundError` 路徑：`from_file` raise `FileNotFoundError` → 驗證 `FileNotFoundError` 被 re-raise。
  - Import 新增：`from unittest.mock import MagicMock, patch`、`from pydub.exceptions import CouldntDecodeError`、`from app.routes.voice import AudioConversionError`

  **Patterns to follow:**
  - 現有 `TestDetectAudioType` 的 unit test class 模式（直接 import 並測試 helper function）。
  - 現有 `TestCloneVoiceEndpoint` 的 `_make_audio` + `client.post` 模式。

  **Test scenarios:**
  - `test_success_webm` mock pydub (side_effect) → response `audio/wav`, `cloned.wav`, `WAV_STUB` body ✓
  - `test_success_ogg` mock pydub (side_effect) → response `audio/wav`, `cloned.wav` ✓
  - `test_success_mp4` mock pydub (side_effect) → response `audio/wav`, `cloned.wav` ✓
  - `test_convert_to_wav_success` — mock `AudioSegment` side_effect → 回傳 `WAV_STUB` bytes ✓
  - `test_convert_to_wav_decode_error` — `CouldntDecodeError` → `AudioConversionError` 被拋出（**非** HTTPException）✓
  - `test_convert_to_wav_ffmpeg_not_found` — `FileNotFoundError` → `FileNotFoundError` re-raise ✓
  - `test_convert_to_wav_oversized_pcm` — mock `audio.raw_data` 為 201MB → `AudioConversionError` 被拋出 ✓
  - integration test: `AudioConversionError` → endpoint 回傳 HTTP 422 ✓
  - integration test: `FileNotFoundError` → endpoint 回傳 HTTP 503 ✓
  - 所有現有的 4xx 驗證測試維持不變（無需 mock）。

  **Verification:**
  - `pytest tests/` 全數通過，無新的 skip 或 xfail。

---

- [x] **Unit 4: 修正前端下載副檔名**

  **Goal:** 防止使用者下載到副檔名為 `.webm`/`.m4a` 但實際為 WAV 格式的檔案。

  **Requirements:** R1（前端不做格式轉換，但需對應後端輸出格式調整 download 屬性）

  **Dependencies:** Unit 2

  **Files:**
  - Modify: `frontend/src/components/VoiceCloner.jsx`

  **Approach:**
  - 找到 `<a>` 下載連結的 `download` 屬性（目前為 `download={\`cloned-voice.${ext}\``，ext 來自錄音 MIME type）。
  - 改為 `download="cloned-voice.wav"`（hardcode）。
  - `recordingMimeType` 和 `ext` 變數仍用於其他地方（例如錄音 UI 顯示），不刪除，只改 download 屬性。

  **Patterns to follow:**
  - 現有 `VoiceCloner.jsx` 的 `<a>` 下載按鈕渲染邏輯。

  **Test scenarios:**
  - 錄音後成功處理 → 下載按鈕 href 對應的檔案副檔名為 `.wav`。
  - 不同瀏覽器（Chrome webm、Safari mp4）錄音，下載檔名均為 `cloned-voice.wav`。

  **Verification:**
  - `download` 屬性值為 `"cloned-voice.wav"`（靜態字串）。

## System-Wide Impact

- **Interaction graph:** 只影響 `POST /api/clone-voice`；`images.py` 和 `threed.py` 路由不受影響。
- **Error propagation:** pydub decode 失敗 → 422（新增錯誤碼），呼叫端需處理 422。前端目前以 `cloneVoice()` 捕捉所有非 200 錯誤並顯示 detail 字串，不需修改。
- **State lifecycle risks:** BytesIO in-memory，無持久狀態，無洩漏風險。
- **API surface parity:** 無 agent tool 介面，N/A。
- **Integration coverage:** 單元測試以 mock 覆蓋轉換邏輯；真實 FFmpeg 解碼需手動或 CI 環境測試。

## Risks & Dependencies

- **FFmpeg 未安裝**：`FileNotFoundError` → HTTP 503（本計劃已在 Unit 2 明確處理，不再是靜默失敗）。開發環境需手動 `brew install ffmpeg`（macOS）或 `apt-get install -y ffmpeg`（Linux）。**測試不需 FFmpeg**：所有 unit tests 和 integration tests 均 mock pydub，CI 無需安裝 FFmpeg 即可全數通過。
- **pydub 0.25.1 與 FFmpeg 版本相容性**：pydub 長期未維護（2023 後無更新），但與主流 FFmpeg 版本相容性穩定。若遇問題可降版至 `pydub==0.25.0`。
- **解壓後 PCM 記憶體炸彈**：10MB 壓縮音檔解壓後無上限，惡意製作的高採樣率多聲道容器可能在 10MB 壓縮內產生數百 MB 至 GB 的 PCM，導致 OOM。Unit 2 需在 `AudioSegment.from_file()` 後立即檢查 `len(audio.raw_data)` 並設上限（50MB，即 `MAX_PCM_SIZE`），超過時 raise `AudioConversionError`。
- **FFmpeg CVE 風險**：本計劃接受的三種格式（webm/mp4/ogg）在 FFmpeg 的 demuxer 層均有歷史 CVE 記錄（Matroska、OGG、MP4 parser）。建議部署環境使用 FFmpeg >= 6.0，並在 Dockerfile 建立時固定 base image 版本。這是部署層的 out-of-band 風險，不影響本計劃的實作，記錄供運維參考。
- **未來 XTTS 整合需要 temp file**：`speaker_wav` 需要檔案路徑。目前 BytesIO 方案在整合時需改為 `tempfile.NamedTemporaryFile(suffix=".wav")` + `try/finally` 清理。屆時測試 mock 策略也需對應更新。

## Documentation / Operational Notes

- **R4 Dockerfile（未實作）**：部署環境需 `apt-get install -y ffmpeg`。Dockerfile 尚不存在，需在部署前建立。
- **開發環境 FFmpeg 安裝**：`brew install ffmpeg`（macOS）。

## Sources & References

- **Origin document:** [docs/brainstorms/2026-03-27-voice-clone-audio-format-requirements.md](../brainstorms/2026-03-27-voice-clone-audio-format-requirements.md)
- **Related brainstorm:** [docs/brainstorms/2026-03-25-voice-cloning-real-implementation-requirements.md](../brainstorms/2026-03-25-voice-cloning-real-implementation-requirements.md)
- Related code: `backend/app/routes/voice.py`, `backend/tests/test_voice.py`
- External: Coqui TTS XTTS source — `TTS/tts/models/xtts.py` (`load_audio`, `sample_rate=22050`, `output_sample_rate=24000`)
