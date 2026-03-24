# Phase 0 — 現狀基準線（AS-IS）

**專案：** Life-Course-Remove-Background  
**目的：** 記錄與程式碼一致的 Phase 0 快照，作為整併 PRD／SDD 與後續演進的對照基準。  
**範圍：** 本文件描述之狀態對應至倉庫內 `backend/`、`frontend/` 之實作（不含尚未合併之變更）。

---

## 文件與程式實作差異（本節待更新）

本文件下文仍保留**原敘述**以利對照 PRD／SDD 與既有測試清單；惟經與目前倉庫程式比對，**下列項目與實作不符**，後續應透過**修訂本文件**或**修改程式**擇一對齊。在對齊完成前，請勿將下文表格中相關列視為已驗證之現況。

- **成功回應格式：** 下文 §2.1 記載成功時回傳 JSON `{"url": "/static/outputs/<uuid>.png"}`。目前 `backend/app/routes/images.py` 於成功時回傳 **`Response(..., media_type="image/png")`**，即 **PNG 二進位內容**，**並非** JSON，亦**無** `url` 欄位。
- **靜態檔與儲存：** 下文 §1、§4 描述啟動時建立 `static/uploads`、`static/outputs`、掛載 **`StaticFiles`** 於 `/static`，以及輸出檔寫入磁碟並經 `/static/outputs/...` 提供。目前 `backend/app/main.py` **未**掛載 `StaticFiles`，**未**見於啟動時建立上述目錄；`images.py` **未**將結果寫入 `static/outputs/<uuid>.png`。
- **前端取用結果：** 下文 §3 敘述與「回傳 URL」之前後文一致時，預期前端會以 JSON 內之 `url` 取圖。目前 `frontend/src/services/api.js` 於成功時使用 **`response.blob()`** 處理回應，與**直接回傳圖檔**之後端行為一致，與下文 §2.1／§4 之 **JSON + 靜態路徑** 敘述不一致。

---

## 1. 架構總覽

| 面向 | Phase 0 實際狀態 |
|------|------------------|
| **後端** | 單一 FastAPI 應用程式；於啟動時建立 `static/uploads`、`static/outputs` 目錄；掛載 `StaticFiles` 於 `/static`。 |
| **路由** | 僅透過 `app.routes.images` 註冊之 `APIRouter`（**無** `/api/v1` 前綴、**無** `/tasks` 資源）。 |
| **資料庫** | **未使用**（無 Users／Jobs／Request Log 等 PRD／SDD 所述持久化層）。 |
| **背景工作** | **未使用** FastAPI `BackgroundTasks`、佇列或 broker；推論在請求處理流程內以 `run_in_executor` 執行。 |
| **驗證** | **無** API Key／`X-API-Key` 標頭驗證。 |
| **CORS** | 環境變數 `CORS_ALLOWED_ORIGINS`（預設 `http://localhost:3000,http://localhost:5173`）。 |
| **前端** | Vite + React；開發時透過 proxy 將 `/api`、`/static` 轉發至後端（預設 `http://localhost:8000`）。 |

---

## 2. API（與程式一致）

### 2.1 已實作端點

| 方法 | 路徑 | 行為摘要 |
|------|------|----------|
| **POST** | `/api/remove-background` | `multipart/form-data`，欄位名 **`file`**。成功回傳 JSON：`{"url": "/static/outputs/<uuid>.png"}`（相對於 Gateway 根路徑的靜態輸出路徑）。 |

### 2.2 驗證與錯誤（後端）

- **允許的 `Content-Type`：** `image/png`、`image/jpeg`、`image/webp`（上傳後再以檔頭魔數複核）。
- **單檔大小上限：** **10 MB**（與 `PRD_v1.md` v1.1 **FR-10** 一致）。
- **常見 HTTP 狀態：** `415` 不支援類型、`413` 檔案過大、`500` 處理失敗。

### 2.3 與 PRD／SDD「目標合約」之差異（摘要）

`docs/PRD_v1.md` 與 `docs/sdd_v1.md` 鎖定之 **非同步任務合約**（`POST` → `task_id` → `GET` 輪詢、`202`、`processing`／`done`／`failed`、API Key、DB 任務紀錄、請求日誌等）在 Phase 0 **尚未實作**；目前為 **單一同步 HTTP 往返** 完成去背並回傳結果 URL。

---

## 3. 前端

| 項目 | 說明 |
|------|------|
| **主要畫面** | 單頁：標題「Remove Background」、檔案選擇、送出按鈕、原圖／結果預覽與下載連結。 |
| **呼叫 API** | `POST /api/remove-background`（`fetch`，相對路徑，由 Vite proxy 轉後端）。 |
| **用戶端限制** | 與後端對齊：PNG／JPEG／WEBP、**10 MB**（常數與文案一致）。 |
| **與 PRD 敘述** | PRD 將 MVP 寫成以 **HTTP API** 為主、React **非** MVP 必備；本倉庫 Phase 0 **已含** 輕量 React 前端，屬實作與文件「可並存」之現狀，後續可在 PRD／roadmap 中標註為示範 UI 或開發用 Playground。 |

---

## 4. 靜態檔與儲存

- **上傳暫存：** `backend/static/uploads/`（處理成功後會刪除上傳檔）。
- **輸出：** `backend/static/outputs/<uuid>.png`，透過 `/static/outputs/...` 提供。
- **清理策略：** PRD 提及之容量監控／自動清理政策在 Phase 0 **未於程式中實作**（僅目錄與輸出檔行為如上）。

---

## 5. 規格對照：Phase 0 已具備 vs 待對齊

| 主題 | Phase 0 現狀 | PRD／SDD 目標（摘要） |
|------|--------------|------------------------|
| 去背能力 | `rembg`、輸出 PNG | 2D 去背（合約細節見 OpenAPI／任務模型） |
| 檔案格式 | JPG／PNG／WEBP | 同左 |
| 大小上限 | **10 MB** | **10 MB**（FR-10／SDD §4；`PRD_v1.md` v1.1） |
| API 形狀 | 單端點同步 `POST` | `POST /tasks` + `GET /tasks/{task_id}`（路徑以 OpenAPI 為準；SDD 草案曾用 `/tasks`） |
| 驗證 | 無 | `X-API-Key`、使用者／租戶模型（MVP 單租戶敘述） |
| 持久化 | 無 | Users、Jobs、Request 日誌 |
| 逾時／輪詢 | 不適用（同步請求） | 300s 逾時、建議 5s 輪詢（FR-10） |

---

## 6. 後續演進（本文件邊界）

- **路線圖與 Phase 1+：** 見 `docs/PRD_v1.md` §1、§6.3 與 `docs/sdd_v1.md` §9。
- **PRD／SDD 修改：** 依 PRD、SDD 逐步將 Phase 對照、Feature Matrix、API 路徑與檔案上限檢查清單與實作／規格對齊。

---

## 7. 追溯

| 參考文件 | 用途 |
|----------|------|
| `docs/PRD_v1.md` | 產品需求與 FR-10 任務合約 |
| `docs/sdd_v1.md` | 軟體設計與 API／資料模型草案 |

本基準線應隨 **首次對齊任務型 API、DB、驗證** 等里程碑更新；更新時請同步修訂本文件 §2–§5 與「與程式一致」之聲明。
