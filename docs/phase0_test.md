# Phase 0 測試清單

**參考：** `docs/PHASE0_AS_IS.md`、`docs/sdd_v1.md` §9.0  

**用途：** 檢查 Phase 0 現有實作（同步去背 API、React 前端）是否符合 `PHASE0_AS_IS.md` 所述；**僅驗證 Phase 0 基準線是否有問題**，不驗證 Phase 1+ 或整份專案完成度。

---

## 不在本檢查範圍（Phase 1+）

以下項目 **不屬於 Phase 0**，本清單 **不檢查**：

- `/api/v1/tasks`、`GET /tasks/{task_id}` 等非同步任務 API
- API Key / `X-API-Key` 驗證
- 資料庫、BackgroundTasks、任務輪詢
- OpenAPI 規格、請求日誌

---

## 測試前準備（首次或環境重建時）

若尚未建置環境，需先完成以下步驟。

### Backend 建構（使用 conda）

1. 進入專案根目錄
2. 建立 conda 環境：`conda create -n life-course-backend python=3.11 -y`
3. 啟動環境：`conda activate life-course-backend`
4. 進入 `backend`：`cd backend`
5. 安裝依賴：`pip install -r requirements.txt`

### Frontend 建構

1. 進入 `frontend`：`cd frontend`
2. 安裝依賴：`npm install`

### 環境需求

- conda（Anaconda 或 Miniconda）
- Python 3.11+
- Node.js 18+
- npm 9+

### 測試環境版本資訊（參考）

```powershell
conda --version
python --version
node --version
npm --version
```

以下為一次實測記錄：`conda activate life-course-backend` 後，於 `frontend` 目錄執行版本指令。

| 項目 | 版本 |
|------|------|
| conda | 4.12.0 |
| Python（`life-course-backend`） | 3.11.15 |
| Node.js | v22.14.0 |
| npm | 10.9.2 |

---

## 前置條件

- [x] Backend 已啟動：`conda activate life-course-backend` 後，在 `backend` 目錄執行 `uvicorn app.main:app --reload`，確認終端顯示 `Uvicorn running on http://127.0.0.1:8000`
- [x] Frontend 已啟動：在 `frontend` 目錄執行 `npm run dev`，確認可開啟 http://localhost:5173

---

## 測試項目

### 1. API 端點存在與路徑正確

**預期：** 存在 `POST /api/remove-background`，`multipart/form-data` 欄位名 `file`。

**測試方式：**

1. 準備一張小圖（`.png`，建議 ≤ 1MB），放在已知路徑，例如 `C:\temp\test.png`
2. 開啟 PowerShell，執行（請將路徑改為實際圖片路徑）：
   ```
   curl.exe -X POST "http://localhost:8000/api/remove-background" -F "file=@C:/temp/test.png"
   curl.exe -X POST "http://localhost:8000/api/remove-background" -F "file=@C:/temp/test.png" -s -o D:/ChingH100/APIgateway/test/last_response.json -w "HTTP %{http_code}`n"
   ```

3. **Pass 條件：** HTTP status 200，回應 body 為 JSON 且包含 `url` 欄位
4. **Fail 條件：** HTTP 404 或連線失敗

- [ ] Pass

**測試結果（實測紀錄，與上列 Pass 條件對照）：**

- **已確認：** `POST /api/remove-background` 存在且可呼叫；`multipart/form-data` 欄位名 **`file`**；HTTP **200**（curl `-w` 顯示 `HTTP 200`；Uvicorn：`127.0.0.1:54984 - "POST /api/remove-background HTTP/1.1" 200 OK`）。
- **與本項 Pass 條件不一致（須誠實記錄）：** 上列 Pass 要求回應為 **JSON 且含 `url`**。目前後端 `backend/app/routes/images.py` 實作為回傳 **`Content-Type: image/png`** 之**圖檔二進位**，**不是** JSON。故**無法**宣稱已滿足「body 為 JSON 且包含 `url`」；若將回應以 `-o` 存成 `.json` 再以文字讀取，會出現亂碼，因內容實為 PNG。
- **結論：** 僅「端點／上傳／200」已實測；**完整 Pass** 須待後端改為回傳 JSON（或本項 Pass 條件改寫為與現行實作一致）後再勾選。

---

### 2. 成功流程回傳格式

**預期：** 成功時回傳 `200`，JSON 為 `{"url": "/static/outputs/<uuid>.png"}`。

**測試方式：**

1. 使用項目 1 的 curl 指令上傳合規圖片（PNG/JPEG/WEBP，≤ 10 MB）

2. 檢查回應：
   - HTTP status 須為 `200`
   - Content-Type 應為 `application/json`
   - body 須為 JSON，含 `url` 欄位
   - `url` 格式須為 `/static/outputs/` 開頭、`.png` 結尾，中間為 UUID（例如 `/static/outputs/a1b2c3d4-e5f6-7890-abcd-ef1234567890.png`）
3. **Pass 條件：** 以上皆符合
4. **Fail 條件：** status 非 200、無 `url`、格式不符

- [ ] Pass

---

### 3. 輸出檔可存取

**預期：** 回傳的 `url` 可透過 Gateway 取得圖片。

**測試方式：**

1. 依項目 2 取得回應中的 `url`（例如 `/static/outputs/xxx.png`）
2. 在瀏覽器開啟 `http://localhost:8000` + `url`（例如 `http://localhost:8000/static/outputs/xxx.png`）
3. 或使用 curl：`curl -o result.png "http://localhost:8000/static/outputs/xxx.png"`
4. **Pass 條件：** HTTP 200，可取得檔案，用圖片檢視器開啟為有效 PNG
5. **Fail 條件：** 404、無法下載、或檔案損壞

- [ ] Pass

---

### 4. 單檔 10 MB 上限（>10MB 應拒絕）

**預期：** 超過 10 MB 回傳 `413 Payload Too Large`。

**測試方式：**

1. 準備 >10 MB 的檔案：
   - 方式 A：用大圖檔（可複製小圖數次合併）
   - 方式 B：建立假檔：`fsutil file createnew C:\temp\bigfile.png 11000000`（約 10.5 MB）
2. 執行：`curl -X POST "http://localhost:8000/api/remove-background" -F "file=@C:\temp\bigfile.png" -w "\nHTTP Status: %{http_code}\n"`
3. **Pass 條件：** HTTP status 為 `413`
4. **Fail 條件：** 回傳 200（不應接受）、或非 413 的錯誤碼

- [ ] Pass

---

### 5. 單檔 10 MB 上限（≤10MB 應接受）

**預期：** 10 MB 以內合規圖片可成功處理。

**測試方式：**

1. 準備 ≤10 MB 的 PNG（例如 5 MB 的圖片）
2. 執行：`curl -X POST "http://localhost:8000/api/remove-background" -F "file=@<你的圖片路徑>" -w "\nHTTP Status: %{http_code}\n"`
3. **Pass 條件：** HTTP status 200，body 含 `url`
4. **Fail 條件：** 回傳 413 或其他錯誤（合規檔不應被拒）

- [ ] Pass

---

### 6. 支援格式：PNG

**預期：** PNG 檔可成功處理。

**測試方式：**

1. 準備 `.png` 檔案（真實 PNG 圖片，非改名）
2. 執行：`curl -X POST "http://localhost:8000/api/remove-background" -F "file=@<png路徑>"`
3. **Pass 條件：** HTTP 200，body 含有效 `url`
4. **Fail 條件：** 415 或其他錯誤

- [ ] Pass

---

### 7. 支援格式：JPEG

**預期：** JPEG 檔可成功處理。

**測試方式：**

1. 準備 `.jpg` 或 `.jpeg` 檔案（真實 JPEG 圖片）
2. 執行：`curl -X POST "http://localhost:8000/api/remove-background" -F "file=@<jpg路徑>"`
3. **Pass 條件：** HTTP 200，body 含有效 `url`
4. **Fail 條件：** 415 或其他錯誤

- [ ] Pass

---

### 8. 支援格式：WEBP

**預期：** WEBP 檔可成功處理。

**測試方式：**

1. 準備 `.webp` 檔案（真實 WEBP 圖片）
2. 執行：`curl -X POST "http://localhost:8000/api/remove-background" -F "file=@<webp路徑>"`
3. **Pass 條件：** HTTP 200，body 含有效 `url`
4. **Fail 條件：** 415 或其他錯誤

- [ ] Pass

---

### 9. 無 API Key 即可呼叫（Phase 0 無驗證）

**預期：** 不帶 `X-API-Key` 即可成功呼叫；Phase 0 無 API Key 驗證。

**測試方式：**

1. 確認 curl 指令 **未** 加入 `-H "X-API-Key: xxx"` 或類似 header
2. 上傳合規圖片，執行：`curl -X POST "http://localhost:8000/api/remove-background" -F "file=@<圖片路徑>" -w "\nHTTP Status: %{http_code}\n"`
3. **Pass 條件：** HTTP 200（不需任何 Key 即可成功）
4. **Fail 條件：** 回傳 401、403 或要求提供 API Key（Phase 0 不應有驗證）

- [ ] Pass

---

### 10. 不支援格式應回傳 415

**預期：** 不支援類型回傳 `415 Unsupported Media Type`。

**測試方式：**

1. 準備非圖片檔（例如 `.pdf`、`.txt`），或將 `.txt` 副檔名改為 `.png` 但內容仍為純文字
2. 執行：`curl -X POST "http://localhost:8000/api/remove-background" -F "file=@<檔案路徑>" -w "\nHTTP Status: %{http_code}\n"`
3. **Pass 條件：** HTTP status 為 `415`
4. **Fail 條件：** 回傳 200（不應接受）、或非 415 的錯誤碼

- [ ] Pass

---

### 11. 前端：完整上傳與下載流程

**預期：** React 頁面可完成選檔 → 上傳 → 顯示結果 → 可下載。

**測試方式：**

1. 開啟瀏覽器，前往 http://localhost:5173
2. 確認頁面顯示標題「Remove Background」、檔案選擇區、送出按鈕
3. 點擊選擇檔案，選一張合規 PNG/JPEG/WEBP（≤ 10 MB）
4. 點擊送出按鈕
5. 等待處理完成（同步回應，通常數秒內）
6. **Pass 條件：**
   - 顯示原圖與去背後結果
   - 有下載連結或預覽圖可點擊下載
   - 下載的檔案為有效 PNG 圖片
7. **Fail 條件：** 無法上傳、無結果、無法下載、或畫面錯誤

- [ ] Pass

---

### 12. 前端：10 MB 限制與格式提示

**預期：** 前端 UI 限制與文案與後端一致：10 MB、PNG/JPEG/WEBP。

**測試方式：**

1. 開啟 http://localhost:5173
2. 檢查頁面文案或提示是否提及：
   - 檔案大小限制（10 MB）
   - 支援格式（PNG、JPEG、WEBP 或同等描述）
3. （可選）嘗試選取 >10 MB 檔案，觀察是否有阻止或警告提示
4. （可選）嘗試選取非支援格式（如 .pdf），觀察是否有阻止或警告提示
5. **Pass 條件：** 文案或限制與後端一致（10 MB、三種格式）
6. **Fail 條件：** 無提示、或數字/格式與後端不一致

- [ ] Pass

---

## Phase 0 檢查結論

- [ ] 以上 12 項全部 Pass
- [ ] `POST /api/remove-background` 行為與 `PHASE0_AS_IS.md` 一致
- [ ] 10 MB 限制在後端與前端皆符合
