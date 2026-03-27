# Model Preload Design

## Problem

The rembg model is loaded fresh on every request to `POST /api/remove-background`. This causes:
- Unnecessary latency per request (model re-initialization)
- Memory churn (allocate/free ~170MB per request)
- Poor first-request experience (model download + load)

## Decision

Use **FastAPI lifespan + app.state** (Option A) to load the model once at startup.

### Alternatives considered

| Approach | Pros | Cons |
|----------|------|------|
| **A. FastAPI lifespan (chosen)** | Official pattern, clean, easy to mock | Startup blocks 2-3s |
| B. Lazy singleton | Zero startup cost | First request slow, global state, thread safety |
| C. Background thread preload | Non-blocking startup | Complex Future management, still slow if request arrives early |

Option A was chosen because the app runs as a single process, 2-3s startup delay is acceptable, and it is the simplest to implement and test.

## Architecture

```
App startup (lifespan)
    ├─ new_session() → load rembg model into memory
    └─ store in app.state.rembg_session

Request (POST /api/remove-background)
    ├─ read session from request.app.state
    ├─ remove(contents, session=session) in thread pool
    └─ return PNG

App shutdown
    └─ session released with process (no manual cleanup)
```

## Changes

### `backend/app/main.py`
- Add `lifespan` async context manager
- Call `rembg.new_session()` at startup, store on `app.state.rembg_session`
- Pass `lifespan` to `FastAPI()` constructor

### `backend/app/routes/images.py`
- Accept `request: Request` parameter
- Read `session` from `request.app.state.rembg_session`
- Pass `session` to `remove(contents, session=session)`

### Frontend
- No changes required.

## Error Handling

Startup failure (network, corrupt cache, OOM) causes the app to not start. This is correct behavior — the model is a core dependency. No retry or fallback logic.

Request-time errors remain unchanged (500 on `rembg.remove()` failure).

## Testing

New file: `backend/tests/test_images.py`

1. Verify `app.state.rembg_session` exists after startup
2. Verify `rembg.remove` is called with `session` parameter
3. Existing validation logic (file type, size) does not regress

Mock strategy: patch `rembg.new_session` and `rembg.remove` to avoid real model download in tests/CI.

No performance benchmarks or output quality tests.
