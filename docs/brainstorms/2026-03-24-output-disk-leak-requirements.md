---
date: 2026-03-24
topic: output-disk-leak
---

# 輸出檔案磁碟洩漏修復

## Problem Frame

後端每次去背處理後，將結果存至 `/static/outputs/{uuid}.png`，但從未刪除這些檔案。長期運作將導致磁碟空間耗盡。同時，上傳的原始圖片也被暫時寫入磁碟再立刻刪除，是不必要的 I/O。

前端僅在當前 session 內使用結果 URL（顯示預覽 + 下載），無跨 session 或分享需求。

## Requirements

- R1. 後端 `POST /api/remove-background` 直接回傳去背後的圖片 bytes（`image/png`），不再將結果存至磁碟。
- R2. 後端移除將上傳原始檔案暫存至 `UPLOADS_DIR` 的邏輯（`rembg.remove()` 直接吃 bytes，不需要暫存檔）。
- R3. 前端 `removeBackground()` 改為從 response 讀取 blob 並建立 `URL.createObjectURL(blob)`，取代原本的 JSON `{ url }` 解析。
- R4. 前端在圖片不再顯示時，呼叫 `URL.revokeObjectURL()` 釋放記憶體（已有 `useEffect` 可擴充）。

## Success Criteria

- 處理完成後，伺服器磁碟上不留下任何與本次請求相關的檔案。
- 前端仍可正常顯示去背結果圖及下載。

## Scope Boundaries

- 不改動 CORS、速率限制、認證等其他功能。
- 不移除 `/static` 靜態服務掛載（保留給未來潛在用途）。
- `UPLOADS_DIR` / `OUTPUTS_DIR` 目錄本身保留（`static/` 資料夾結構不動）。

## Key Decisions

- **串流回傳而非 URL**: 前端只在當前 session 使用結果，無需持久化 URL，blob URL 完全足夠。
- **同步移除暫存上傳**: 既然改架構，順便清掉多餘的磁碟寫入，降低 I/O 並縮小攻擊面。

## Next Steps

→ `/ce:plan` 進行結構化實作規劃
