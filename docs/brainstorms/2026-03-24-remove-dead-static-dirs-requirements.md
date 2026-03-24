---
date: 2026-03-24
topic: remove-dead-static-dirs
---

# 刪除死代碼：static 目錄與相關基礎設施

## Problem Frame

Streaming 重構後，後端改為直接回傳 PNG bytes，不再寫檔。但 `config.py`、`main.py` 仍保留 `UPLOADS_DIR`/`OUTPUTS_DIR` 定義、啟動時 `mkdir`、以及 `StaticFiles` mount，造成：

- 新開發者讀 `main.py` 誤以為有磁碟寫入
- 啟動時產生無用的目錄副作用
- `StaticFiles` mount 暴露一個什麼都沒有的路由

## Requirements

- R1. 刪除 `config.py` 中 `UPLOADS_DIR`、`OUTPUTS_DIR` 定義
- R2. 移除 `main.py` 中：`asynccontextmanager` import、`StaticFiles` import、相關 config import、`STATIC_DIR` 變數、`lifespan` 函式（含 mkdir 呼叫）、`FastAPI(lifespan=...)` 參數、`app.mount("/static", ...)` 一行
- R3. 刪除 `backend/static/` 整個目錄（含 `.gitkeep` 檔案）

## Success Criteria

- 啟動後 `backend/static/` 不再存在
- `/static/*` 路由不再被 mount
- `main.py` 只保留 CORS middleware 與 router 掛載，無多餘 import

## Scope Boundaries

- 不修改任何 route 邏輯
- 不引入靜態檔案服務的替代方案
- `config.py` 中的 `BASE_DIR`、`get_cors_allowed_origins` 保留不動

## Key Decisions

- `backend/static/` 整個刪除（YAGNI；未來需要時再加回）
- `lifespan` 整個移除（空的 lifespan 無意義）

## Next Steps

→ 直接執行（範圍清晰，無技術疑問）
