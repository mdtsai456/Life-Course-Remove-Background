# 生活教案 Life Course — Remove Background

A web app that removes image backgrounds using a FastAPI backend (powered by `rembg`) and a React + Vite frontend.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm 9+

---

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed frontend origins |

Example:

```bash
CORS_ALLOWED_ORIGINS=http://localhost:5173 uvicorn app.main:app --reload --port 8000
```

---

## Frontend Setup

```bash
cd frontend
npm install
```

### Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the dev server at `http://localhost:5173` |
| `npm run build` | Build for production (output: `dist/`) |
| `npm run preview` | Preview the production build locally |
| `npm run lint` | Run ESLint |

The Vite dev server proxies `/api` requests to `http://localhost:8000` — make sure the backend is running first.

---

## Running Locally

1. Start the backend (port 8000)
2. Start the frontend dev server (port 5173)
3. Open `http://localhost:5173` in your browser

---

## API Endpoints

### `POST /api/remove-background`

Removes the background from an uploaded image.

**Request** — `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | File | Image to process |

**Success response** — `200 OK`

Returns the processed image as a binary PNG stream (`Content-Type: image/png`).
The response body can be used directly as an `<img>` src (via `URL.createObjectURL`) or downloaded.

**Error responses**

| Status | Meaning |
|---|---|
| `413` | File exceeds the 10 MB limit |
| `415` | File type not supported |
| `500` | Processing failed |

**Example curl request**

```bash
curl -X POST http://localhost:8000/api/remove-background \
  -F "file=@photo.jpg"
```

---

## Upload Limits & Supported Types

- **Max file size:** 10 MB
- **Accepted formats:** PNG, JPEG, WebP
- The file type is validated both by MIME type (client-side) and by magic bytes (server-side), so renaming a non-image file will not bypass the check.

### How errors are displayed

Validation errors (wrong type, file too large) are shown inline below the upload form in red before the request is sent. Server errors are surfaced the same way after the request completes.

---

## Optional Configuration

### React Compiler

Not enabled by default due to build performance impact. See the [React Compiler installation guide](https://react.dev/learn/react-compiler/installation) to opt in.

### ESLint

For production use, consider enabling TypeScript with type-aware lint rules. See the [Vite TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) and [`typescript-eslint`](https://typescript-eslint.io) for setup instructions.

---

## Troubleshooting

**CORS errors in the browser**
Ensure `CORS_ALLOWED_ORIGINS` includes the exact origin your frontend is served from (scheme + host + port).

**`rembg` first-run is slow**
On the first request, `rembg` downloads its model weights (~170 MB). Subsequent requests are faster.

**Port conflicts**
If port 8000 or 5173 is already in use, change the backend port with `--port <n>` and update the Vite proxy config in `vite.config.js` accordingly.
