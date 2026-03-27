---
date: 2026-03-27
topic: voice-clone-audio-format
---

# Voice Clone 音檔格式轉換策略

## Problem Frame

前端 VoiceCloner 元件使用 MediaRecorder API 錄音，輸出格式由瀏覽器決定（Chrome/Edge 輸出 `webm/opus`、Safari 輸出 `mp4/aac`）。後端呼叫 Voice Cloning AI 模型時需要 WAV 格式。需要決定格式轉換應在前端還是後端進行。

## Requirements

- R1. 前端維持現有行為：錄音後直接上傳原始瀏覽器格式（`webm`、`mp4`、`ogg`），不進行任何格式轉換。
- R2. 後端在驗證通過後、呼叫 AI 模型前，將音檔以 `pydub` 轉換為 WAV 格式（不需預設 sample rate，XTTS 內部會自動 resample 至 22050Hz；也不需手動轉 mono，XTTS 內部會自動處理）。
- R3. 格式轉換使用 `pydub` 套件（底層依賴 FFmpeg），加入 `requirements.txt`。
- R4. 部署環境（Docker）需安裝 FFmpeg（`apt-get install -y ffmpeg`）。

## Success Criteria

- 所有瀏覽器（Chrome、Firefox、Safari）錄製的音檔均能成功送達後端並轉換為 WAV。
- 前端 bundle size 不增加，上傳檔案大小維持壓縮格式（不因轉 WAV 暴增）。
- 轉換後的 WAV 可被 `torchaudio.load()` 正常載入，XTTS 自動 resample 至 22050Hz 並轉 mono。

## Scope Boundaries

- 不在前端進行任何音頻格式轉換。
- 本次不加入「上傳本地音檔」功能，維持只支援麥克風錄音。
- 不更動前端驗證邏輯或 API 介面。

## Key Decisions

- **後端轉換 vs 前端轉換**：選擇後端轉換。原因：WAV 為未壓縮格式，若在前端轉換會讓上傳量從 ~500KB 暴增至 ~10MB；瀏覽器缺乏內建 WAV 編碼器，需引入第三方套件增加 bundle size；後端使用 FFmpeg/pydub 方案成熟穩定。
- **轉換工具選擇 `pydub`**：相較於直接 subprocess 呼叫 FFmpeg，pydub 的 API 更易讀，且後續整合真實語音模型時可能需要更多音頻操作（裁切、正規化），擴展性較佳。

## Dependencies / Assumptions

- 部署環境可安裝 FFmpeg（系統依賴）。
- 使用 Coqui TTS XTTS 模型。XTTS 的 `speaker_wav` 接受 WAV 檔案路徑，內部使用 `torchaudio.load()` 載入，自動 resample 至 22050Hz（`sample_rate`），輸出 24000Hz（`output_sample_rate`）。`torchaudio` 不可靠地支援 webm，故需先轉成 WAV。

## Outstanding Questions

### Deferred to Planning

- [Affects R2][已解決] XTTS `sample_rate=22050`、`output_sample_rate=24000`，內部自動 resample 與轉 mono，只需提供可被 `torchaudio.load()` 讀取的 WAV 即可。
- [Affects R3][Technical] `pydub` 在處理大型音檔時的記憶體使用情況，是否需要使用 streaming 方式處理？

## Next Steps

→ `/ce:plan` for structured implementation planning
