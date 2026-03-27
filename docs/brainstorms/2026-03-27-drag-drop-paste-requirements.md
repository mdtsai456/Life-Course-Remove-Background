---
date: 2026-03-27
topic: drag-drop-paste
---

# Drag & Drop / 貼上圖片

## Problem Frame

`ImageUploader` 目前只支援 file picker 選檔。使用者習慣透過拖拉或 Ctrl+V 貼上截圖，缺少這兩種操作會讓互動感覺過時且不流暢。

## Requirements

- R1. 使用者可以將圖片拖拉到上傳區域來選取圖片（drag & drop）
- R2. 拖拉時上傳區域應有視覺回饋（例如邊框高亮）表示可放置
- R3. 使用者可以用 Ctrl+V（或 Cmd+V）貼上剪貼簿中的圖片來選取圖片
- R4. Drag & Drop 與貼上的圖片須通過與 file picker 相同的驗證邏輯（類型、大小）
- R5. 若拖入的是不支援的類型或超過大小，顯示相同的錯誤訊息
- R6. 貼上事件僅在 `ImageUploader` 所在的 tab 為可見狀態時有效（避免背景 tab 干擾）

## Success Criteria

- 三種輸入方式（file picker、drag & drop、貼上）行為一致，驗證邏輯相同
- 拖拉時有明確的視覺提示
- 不影響現有 file picker 功能

## Scope Boundaries

- 不支援拖入多張圖片（批次處理為獨立功能）
- 不處理非圖片類型的拖拉（例如文字、連結）
- 不新增後端改動

## Key Decisions

- **重用 `handleFileChange` 驗證邏輯**：drop/paste 取得 `File` 物件後直接走相同驗證，不重複寫
- **Paste 監聽掛在 `window`**：只要 tab 可見（`visible` prop 為 true）就監聽，切換 tab 時移除

## Deferred to Planning

- Affects R2（Technical）drag-over 視覺回饋用 CSS class toggle 還是 inline state？
- Affects R3（Technical）paste 事件從 `ClipboardEvent.clipboardData.items` 取得 `File` 的相容性確認

## Next Steps

→ `/ce:plan` for structured implementation planning
