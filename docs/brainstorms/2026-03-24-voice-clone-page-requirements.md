---
date: 2026-03-24
topic: voice-clone-page
---

# Voice Clone Page

## Problem Frame

目前 App 只有「移除背景」功能。使用者希望加入「聲音克隆」功能：提供一段自己的聲音樣本與文字，產出一個以自己聲音朗讀該文字的新音檔。

本次範圍限於**前端介面**；後端 API 與 Voice Cloning 引擎留待後續迭代。

## Requirements

- R1. App 頂部新增導覽列，包含「Remove Background」和「Voice Clone」兩個 Tab，可切換顯示對應頁面內容（不使用 URL 路由，僅 state 切換）。
- R2. Voice Clone 頁面包含一個錄音區塊：「開始錄音」按鈕按下後開始錄音並顯示計時器；再次按下「停止」按鈕結束錄音；結束後顯示已錄製的音檔名稱或時長供確認。
- R3. Voice Clone 頁面包含一個文字輸入區（`<textarea>`），讓使用者輸入希望被朗讀的文字。
- R4. 頁面底部有「送出」按鈕；按下後進入載入狀態（按鈕 disabled + loading 指示）。
- R5. 送出成功後，頁面顯示結果音檔的內建播放器（`<audio controls>`）及「下載音檔」按鈕。
- R6. 若發生錯誤（錄音失敗、API 錯誤），顯示錯誤訊息（樣式沿用現有 `.error-message`）。
- R7. 前端 API 呼叫以 stub/mock 實作：模擬延遲後回傳一個假的 Blob URL，待後端就緒後替換。

## Success Criteria

- 使用者能不離開頁面完成：錄音 → 輸入文字 → 送出 → 播放/下載結果
- 在後端 API 尚未就緒的情況下，前端介面可完整展示（透過 mock）
- 兩個 Tab 可正確切換，互不干擾各自的狀態

## Scope Boundaries

- 本次**不實作**後端 API 或 Voice Cloning 引擎
- 不支援上傳現有音檔作為聲音樣本（僅錄音）
- 不加入聲音波形視覺化
- 不加入 URL 路由（React Router）

## Key Decisions

- **頂部 Tab 而非 URL 路由**：專案規模小，避免引入 React Router 的額外複雜度
- **前端先行，API 以 mock 替代**：讓 UI 可以獨立開發與展示，不阻塞進度
- **錄音使用 Web MediaRecorder API**：瀏覽器原生支援，無需額外套件

## Dependencies / Assumptions

- 瀏覽器支援 `MediaRecorder` API（現代瀏覽器均支援）
- 使用者授予麥克風權限後才能錄音；若拒絕需顯示提示
- 後端 API 回傳格式預計為二進位音檔串流（與現有圖片 API 模式一致），細節留待後端迭代確認

## Outstanding Questions

### Resolve Before Planning

（無阻塞問題，可直接進入規劃）

### Deferred to Planning

- （影響 R7，Technical）Mock 應回傳哪種音頻格式？（WAV / MP3 / 瀏覽器預設錄製格式 webm）
- （影響 R2，Needs research）`MediaRecorder` 錄製的預設 MIME type 是否需要在送出前轉換格式以符合後端預期？

## Next Steps

→ `/ce:plan` 進行結構化實作規劃
