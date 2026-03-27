# Model Preload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Load the rembg model once at app startup via FastAPI lifespan, eliminating per-request model initialization.

**Architecture:** Add a `lifespan` async context manager to `main.py` that calls `rembg.new_session()` and stores the session on `app.state`. The `/api/remove-background` route reads the session from `request.app.state` and passes it to `rembg.remove()`.

**Tech Stack:** FastAPI lifespan, rembg `new_session()` / `remove()`, pytest + unittest.mock

---

### Task 1: Create test conftest with rembg mock

**Files:**
- Create: `backend/tests/conftest.py`

The lifespan will call `rembg.new_session()` at startup. All tests that create a `TestClient(app)` will trigger this. We need a shared mock to prevent real model loading in tests.

**Step 1: Write conftest.py**

```python
"""Shared fixtures for backend tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Yield a TestClient with rembg.new_session mocked out."""
    mock_session = MagicMock(name="rembg_session")
    with patch("rembg.new_session", return_value=mock_session):
        from app.main import app

        with TestClient(app) as c:
            yield c
```

**Step 2: Verify fixture loads**

Run: `cd backend && python -m pytest tests/conftest.py --collect-only`
Expected: no errors (fixture is collected)

**Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add conftest with mocked rembg session fixture"
```

---

### Task 2: Write failing test for lifespan session preload

**Files:**
- Create: `backend/tests/test_images.py`

**Step 1: Write the failing test**

```python
"""Tests for /api/remove-background endpoint with model preload."""

from __future__ import annotations


class TestModelPreload:
    def test_session_exists_on_app_state(self, client):
        """After startup, app.state.rembg_session should be set."""
        assert hasattr(client.app.state, "rembg_session")
        assert client.app.state.rembg_session is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_images.py::TestModelPreload::test_session_exists_on_app_state -v`
Expected: FAIL — `app.state` has no `rembg_session` attribute (lifespan not yet implemented)

---

### Task 3: Implement lifespan in main.py

**Files:**
- Modify: `backend/app/main.py:1-9`

**Step 1: Add lifespan**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from rembg import new_session

from app.config import get_cors_allowed_origins
from app.routes.images import router as images_router
from app.routes.threed import router as threed_router
from app.routes.voice import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rembg_session = new_session()
    yield


app = FastAPI(lifespan=lifespan)
```

The rest of main.py (middleware, routers) stays unchanged.

**Step 2: Run the preload test to verify it passes**

Run: `cd backend && python -m pytest tests/test_images.py::TestModelPreload::test_session_exists_on_app_state -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/main.py backend/tests/test_images.py
git commit -m "feat: add lifespan to preload rembg model at startup"
```

---

### Task 4: Write failing test for session injection into remove()

**Files:**
- Modify: `backend/tests/test_images.py`

**Step 1: Write the failing test**

Add to `test_images.py`:

```python
from unittest.mock import patch, MagicMock

# -- helpers --
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
FAKE_RESULT = b"\x89PNG\r\n\x1a\nfake-result"


class TestRemoveBackground:
    def test_session_passed_to_remove(self, client):
        """remove() must be called with the preloaded session."""
        with patch("app.routes.images.remove", return_value=FAKE_RESULT) as mock_remove:
            resp = client.post(
                "/api/remove-background",
                files={"file": ("test.png", PNG_HEADER, "image/png")},
            )
        assert resp.status_code == 200
        mock_remove.assert_called_once()
        _, kwargs = mock_remove.call_args
        assert "session" in kwargs
        assert kwargs["session"] is client.app.state.rembg_session
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_images.py::TestRemoveBackground::test_session_passed_to_remove -v`
Expected: FAIL — `session` not in kwargs (images.py not yet updated)

---

### Task 5: Update images.py to use session from app.state

**Files:**
- Modify: `backend/app/routes/images.py:7,28-29,56-58`

**Step 1: Update the route**

Change the import line:

```python
from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
```

Change the function signature:

```python
@router.post("/api/remove-background")
async def remove_background(file: UploadFile, request: Request):
```

Change the remove() call:

```python
    loop = asyncio.get_running_loop()
    try:
        session = request.app.state.rembg_session
        result = await loop.run_in_executor(
            None, partial(remove, contents, session=session)
        )
    except Exception:
```

**Step 2: Run the test to verify it passes**

Run: `cd backend && python -m pytest tests/test_images.py::TestRemoveBackground::test_session_passed_to_remove -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/routes/images.py backend/tests/test_images.py
git commit -m "feat: inject preloaded rembg session into remove-background route"
```

---

### Task 6: Add validation regression tests

**Files:**
- Modify: `backend/tests/test_images.py`

**Step 1: Add validation tests**

Append to `test_images.py`:

```python
class TestRemoveBackgroundValidation:
    def test_reject_unsupported_mime_type(self, client):
        resp = client.post(
            "/api/remove-background",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 415

    def test_reject_oversized_file(self, client):
        big = PNG_HEADER + b"\x00" * (10 * 1024 * 1024)
        resp = client.post(
            "/api/remove-background",
            files={"file": ("big.png", big, "image/png")},
        )
        assert resp.status_code == 413

    def test_reject_bad_magic_bytes(self, client):
        resp = client.post(
            "/api/remove-background",
            files={"file": ("test.png", b"\x00" * 100, "image/png")},
        )
        assert resp.status_code == 415

    def test_success_returns_png(self, client):
        with patch("app.routes.images.remove", return_value=FAKE_RESULT):
            resp = client.post(
                "/api/remove-background",
                files={"file": ("test.png", PNG_HEADER, "image/png")},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == FAKE_RESULT
```

**Step 2: Run all image tests**

Run: `cd backend && python -m pytest tests/test_images.py -v`
Expected: all PASS

**Step 3: Commit**

```bash
git add backend/tests/test_images.py
git commit -m "test: add validation regression tests for remove-background"
```

---

### Task 7: Update test_voice.py to use client fixture

**Files:**
- Modify: `backend/tests/test_voice.py`

The module-level `client = TestClient(app)` may fail now that lifespan calls `new_session()`. Refactor to use the shared `client` fixture from conftest.

**Step 1: Remove module-level client**

Remove these lines from the top of `test_voice.py`:

```python
# REMOVE:
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
```

**Step 2: Add `client` parameter to every test method**

Every test method in `TestCloneVoiceEndpoint` that uses `client` must accept it as a parameter:

```python
class TestCloneVoiceEndpoint:
    def test_success_webm(self, client):
        ...
    def test_success_ogg(self, client):
        ...
    # etc. for all test methods in this class
```

Note: `TestDetectAudioType` and `TestConvertToWav` do NOT use `client` — leave them unchanged.

**Step 3: Run all tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```bash
git add backend/tests/test_voice.py
git commit -m "refactor: use shared client fixture in voice tests"
```

---

### Task 8: Final verification

**Step 1: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: all tests PASS, no warnings about deprecated features

**Step 2: Verify no rembg import at test time**

Run: `cd backend && python -m pytest tests/ -v 2>&1 | grep -i "download\|u2net\|onnx"`
Expected: no output (model is never actually loaded)
