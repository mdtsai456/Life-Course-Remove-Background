---
date: 2026-03-25
topic: voice-cloning-real-implementation
---

# Voice Cloning 真實實作

## Problem Frame

後端 `/api/clone-voice` 目前為 mock 實作：接收音訊檔與文字後，直接回傳原始音檔而非真正複製聲音。使用者看到的功能完全無效，需要替換為真實 AI 模型推理。

## Requirements

- R1. `/api/clone-voice` 接收使用者的音訊樣本（≤10MB，webm/mp4/ogg）與一段文字，回傳以該聲音念出該段文字的音訊。
- R2. 模型自架於後端，不依賴外部付費 API。
- R3. 支援中文與英文文字輸入。
- R4. 回應應在可接受時間內完成（有 GPU 時 ≤15 秒；無 GPU 時可接受較長）。
- R5. 若模型推理失敗（模型未載入、記憶體不足等），回傳有意義的錯誤訊息而非靜默失敗。

## Success Criteria

- 上傳一段真實人聲音訊樣本，輸入任意文字，API 回傳的音訊聽起來與原始聲音相似。
- 原有的輸入驗證（MIME type、magic bytes、file size、text not empty）全數保留。

## Scope Boundaries

- 不包含前端 UI 的修改（只改後端 route）。
- 不包含 2D→3D 功能（獨立任務）。
- 不要求模型訓練，只做推理（inference）。
- 不需要聲音模型管理介面或多聲音儲存。

## Key Decisions

- **自架方案**：不依賴 ElevenLabs 等外部付費 API，選用開源模型。
- **優先方案**：有 GPU 環境選 Coqui XTTS v2；無 GPU 環境選 OpenVoice V2。

## Outstanding Questions

### Resolve Before Planning

- [Affects R1, R4][User decision] 部署環境是否有 NVIDIA GPU？這決定模型選型與效能預期。

### Deferred to Planning

- [Affects R2][Technical] Coqui XTTS v2 或 OpenVoice V2 如何以 FastAPI lifespan 載入模型（避免每次請求重新載入）？
- [Affects R4][Needs research] 無 GPU 環境下，哪個模型的 CPU 推理時間最實際？
- [Affects R2][Technical] 模型檔案體積與下載策略（是否需要 Docker layer 分層或 model registry）？

## Next Steps
→ 解決 GPU 環境確認問題後，執行 `/ce:plan`
