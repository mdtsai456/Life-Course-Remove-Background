# Full Audit & Quality Pass — Design

**Date:** 2026-03-24

## Overview

A targeted audit covering README, backend config, and frontend style consistency. No structural changes; scope is limited to confirmed stale content and code quality issues.

---

## 1. README Fixes

### API Response Format (Success)

The current docs describe a JSON response that no longer exists:

```json
{ "url": "/static/outputs/<id>.png" }
```

The endpoint now returns a binary PNG stream directly. Update the Success response section to:

- Status: `200 OK — binary PNG image (Content-Type: image/png)`
- Remove the JSON block
- Add a note that the response can be used directly as an `<img>` src or downloaded

### Troubleshooting — Remove Stale Entry

Delete the "Static files not found after processing" entry. The `backend/static/uploads/` and `backend/static/outputs/` directories no longer exist and the lifespan handler that created them was removed. This entry misleads users.

---

## 2. Backend — `config.py`

### Remove `BASE_DIR`

`BASE_DIR` is set but never referenced anywhere in the codebase. Remove the `Path` import and the variable.

### Trim CORS Default Origins

The default for `CORS_ALLOWED_ORIGINS` includes `http://localhost:3000` (Create React App convention). This project uses Vite on port 5173. Remove the stale origin to avoid confusion.

Before:
```python
"http://localhost:3000,http://localhost:5173"
```

After:
```python
"http://localhost:5173"
```

---

## 3. Frontend — `ErrorBoundary.jsx`

### Move Inline Style to CSS Class

`ErrorBoundary` uses `style={{ padding: '2rem' }}` — the only inline style in the entire codebase. Extract it to `index.css` as:

```css
.error-boundary {
  padding: 2rem;
}
```

Replace the inline style with `className="error-boundary"` to match the project's CSS-class-only convention.

---

## Files Changed

| File | Change |
|---|---|
| `README.md` | Update API success response; remove stale troubleshooting entry |
| `backend/app/config.py` | Remove `BASE_DIR`; trim CORS default to `5173` only |
| `frontend/src/index.css` | Add `.error-boundary` class |
| `frontend/src/components/ErrorBoundary.jsx` | Replace inline style with `className="error-boundary"` |
