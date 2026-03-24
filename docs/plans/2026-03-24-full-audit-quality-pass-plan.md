# Full Audit & Quality Pass Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix stale README docs, remove dead backend code, and align ErrorBoundary styling with the project's CSS-class convention.

**Architecture:** Four isolated file edits — no logic changes, no new dependencies. Each task is a targeted find-and-fix with a commit. Order doesn't matter; tasks are independent.

**Tech Stack:** FastAPI (Python), React + Vite (JavaScript), CSS

---

### Task 1: Fix README — API Success Response

**Files:**
- Modify: `README.md:82-100`

**Step 1: Open the file and locate the section**

The stale block starts at the `**Success response**` heading under `### POST /api/remove-background`.

Current content (lines ~82-84):
```
**Success response** — `200 OK`

```json
{ "url": "/static/outputs/<id>.png" }
```
```

**Step 2: Replace with the correct description**

Replace that block with:
```markdown
**Success response** — `200 OK`

Returns the processed image as a binary PNG stream (`Content-Type: image/png`).
The response body can be used directly as an `<img>` src (via `URL.createObjectURL`) or downloaded.
```

**Step 3: Verify the change looks right**

Read `README.md` and confirm:
- No JSON block remains under Success response
- The new text accurately describes binary streaming

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update API response description to reflect binary stream"
```

---

### Task 2: Fix README — Remove Stale Troubleshooting Entry

**Files:**
- Modify: `README.md` (Troubleshooting section, near end of file)

**Step 1: Locate the stale entry**

Find this block (around line 139-140):
```
**Static files not found after processing**
Make sure `backend/static/uploads/` and `backend/static/outputs/` exist, or start the backend once — the lifespan handler creates them automatically.
```

**Step 2: Delete the entire entry**

Remove both lines (the bold heading and the body). Leave no blank line gap — keep the surrounding troubleshooting entries tidy.

**Step 3: Verify**

Read the Troubleshooting section and confirm:
- The static-files entry is gone
- Remaining entries are intact and properly spaced

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: remove stale static-files troubleshooting entry"
```

---

### Task 3: Clean Up `config.py` — Remove Dead Code and Stale CORS Origin

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Read the current file**

Current content:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def get_cors_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
```

**Step 2: Apply both changes**

Remove `from pathlib import Path` and `BASE_DIR`. Trim the CORS default to Vite's port only.

Result:
```python
import os


def get_cors_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
```

**Step 3: Verify nothing imports BASE_DIR**

Run:
```bash
grep -r "BASE_DIR" backend/
```
Expected: no output (nothing uses it).

**Step 4: Commit**

```bash
git add backend/app/config.py
git commit -m "refactor: remove unused BASE_DIR and stale CRA CORS origin"
```

---

### Task 4: Fix `ErrorBoundary.jsx` — Replace Inline Style with CSS Class

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/components/ErrorBoundary.jsx`

**Step 1: Add the CSS class to `index.css`**

Append at the end of `frontend/src/index.css`:
```css
.error-boundary {
  padding: 2rem;
}
```

**Step 2: Update `ErrorBoundary.jsx`**

Locate the render method's error state return. Current:
```jsx
<div style={{ padding: '2rem' }}>
```

Replace with:
```jsx
<div className="error-boundary">
```

**Step 3: Verify no inline styles remain**

Run:
```bash
grep -r "style={{" frontend/src/
```
Expected: no output.

**Step 4: Sanity check the component renders**

Start the dev server (`npm run dev` in `frontend/`) and verify the page loads without errors. No automated test needed — this is a pure style attribute swap.

**Step 5: Commit**

```bash
git add frontend/src/index.css frontend/src/components/ErrorBoundary.jsx
git commit -m "style: move ErrorBoundary inline padding to CSS class"
```

---

## Done

After all four tasks, run a final check:

```bash
git log --oneline -6
```

Expected: four new commits above the baseline, each scoped to one change.
