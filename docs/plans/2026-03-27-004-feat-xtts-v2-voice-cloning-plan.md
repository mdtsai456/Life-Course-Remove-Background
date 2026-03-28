---
title: "feat: Integrate Coqui XTTS v2 for Real Voice Cloning"
type: feat
status: active
date: 2026-03-27
origin: docs/brainstorms/2026-03-25-voice-cloning-real-implementation-requirements.md
---

# feat: Integrate Coqui XTTS v2 for Real Voice Cloning

## Overview

Replace the mock `/api/clone-voice` implementation — which currently validates input and returns the original audio unchanged — with a real Coqui XTTS v2 zero-shot voice cloning inference pipeline. The backend receives a speaker reference audio sample and a text string, runs GPU inference, and returns a WAV file spoken in the reference speaker's voice.

## Problem Frame

The `/api/clone-voice` endpoint currently performs input validation (MIME type, file size, magic bytes, text-not-empty) and then echoes the original uploaded audio bytes back unchanged, with a `# TODO` comment marking where real inference should go. No WAV conversion (`_convert_to_wav`), pydub, anyio, or domain exceptions (`AudioConversionError`) exist yet — they must all be created by this plan. The validation pipeline is complete and tested (9 endpoint tests + 7 helper tests in `test_voice.py`) and is not touched by this plan.

(see origin: `docs/brainstorms/2026-03-25-voice-cloning-real-implementation-requirements.md`)

## Requirements Trace

- R1. `/api/clone-voice` accepts audio sample (≤10MB, webm/mp4/ogg) + text, returns a WAV spoken in the reference voice
- R2. Self-hosted Coqui XTTS v2 model; no external paid API
- R3. Supports Chinese (`zh-cn`) and English (`en`) text input
- R4. GPU inference completes in ≤15 seconds
- R5. Meaningful HTTP error responses on inference failure (not silent 500 with opaque body)

## Scope Boundaries

- No frontend UI changes (language is auto-detected server-side)
- No model training — inference only
- No voice library / multi-speaker storage
- No streaming audio response (single-shot WAV only)
- No migration of existing endpoints (images, 3d) to this pattern

## Context & Research

### Relevant Code and Patterns

- **`backend/app/routes/voice.py`** — `_detect_audio_type(contents)` magic-bytes helper detecting webm/ogg/mp4; `clone_voice()` async route with MIME stripping, text validation, file-size check, magic-bytes validation, then a `# TODO` block that echoes the original audio bytes back. No WAV conversion, no domain exceptions, no anyio. This plan creates `_convert_to_wav` and `AudioConversionError` from scratch here.
- **`backend/app/routes/images.py`** — uses `asyncio.get_running_loop()` + `loop.run_in_executor(None, partial(remove, contents))` for CPU-bound rembg work. No model guard, no `app.state`. Provides a pattern for thread offloading via the standard library (not anyio).
- **`backend/app/main.py`** — plain `FastAPI()` instance with `CORSMiddleware` and a custom `add_security_headers` HTTP middleware; no lifespan handler, no `app.state` usage. A lifespan must be added from scratch by Unit 2.
- **`backend/tests/test_voice.py`** — `TestDetectAudioType` (7 cases) and `TestCloneVoiceEndpoint` (9 cases). No `TestConvertToWav` class, no `conftest.py` fixture file — both are created by this plan.
- **`backend/requirements.txt`** — fastapi, uvicorn, python-multipart, rembg, pillow, httpx, pytest, pytest-asyncio. Does **not** include pydub, anyio, torch, torchaudio, or coqui-tts — all must be added by this plan.

### Institutional Learnings

- **Lifespan failure is intentional and fatal**: No retry or fallback on startup failure; OOM/download failure should crash the process.
- **`_convert_to_wav` is created from scratch by Unit 1**: There is no existing implementation to refactor. The function is new, returning `(bytes, duration_secs)` from the start — no "refactor from bytes to path" is needed.
- **Memory-bomb guard must be included**: The new `_convert_to_wav` function must check `len(audio.raw_data) > MAX_PCM_SIZE` (50 MB) and raise `AudioConversionError` to prevent decompression bombs.
- **pydub mock side_effect pattern**: `mock_seg.export.side_effect = lambda buf, format, parameters=None: buf.write(WAV_STUB)` — using `return_value` instead of `side_effect` is a silent bug because `export()` writes to the buffer passed to it, not via return value.

### External References

- XTTS v2 supported languages include `zh-cn` and `en` (17 total)
- XTTS output is always 24000 Hz WAV; handles input resampling to 22050 Hz internally
- Speaker WAV minimum recommended: 6 seconds (this plan enforces ≥3 seconds as a practical minimum; shorter samples still yield usable cloning quality and reduce friction for end users uploading short recordings)
- Speaker latents (`get_conditioning_latents`) are recomputed per-request (no persistent speaker cache)
- Model size: ~2.09 GB total (model.pth 1.87 GB + dvae.pth 211 MB + misc)
- `COQUI_TOS_AGREED=1` env var required to suppress interactive license prompt in headless environments
- **Package**: `pip install coqui-tts` — maintained Idiap fork; original `pip install TTS` is unmaintained
- Inference is NOT thread-safe: concurrent calls against a shared model instance can corrupt state; serialize with `asyncio.Lock`

## Key Technical Decisions

- **High-level `TTS` API（非低階 `Xtts` class）**: 使用 `TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)` 與 `tts.tts_to_file(text, speaker_wav, language, file_path)` — 與官方範例一致，程式碼最簡單。`tts_to_file` 寫到 output temp file，route 再讀回 bytes 回傳。不需要手動 torchaudio / numpy 操作。

- **`_convert_to_wav` 為全新建立，返回 `(bytes, duration_secs)`，route 層負責寫檔**: Unit 1 從零建立 `_convert_to_wav(contents, fmt)` 函數，無既有實作可沿用。函數以 pydub 解碼音訊、檢查 PCM 大小防止 decompression bomb、匯出 WAV bytes 並計算 duration，返回 `(wav_bytes, duration_secs)`。Route 在 thread lambda 內建立一個 `TemporaryDirectory`，把 bytes 寫成 `tmpdir/speaker.wav`，再把 `tmpdir/synth.wav` 作為 `tts_to_file` 的 output path。單一 `TemporaryDirectory` 擁有兩個檔案，thread 結束時統一清除。

- **Language auto-detection via Unicode CJK range check**: No frontend API change. The route inspects the `text` field: if any character falls in Unicode CJK Unified Ideographs (U+4E00–U+9FFF), language is `"zh-cn"`; otherwise `"en"`. Mixed text → `"zh-cn"` wins. No extra dependency required.

- **`asyncio.Lock` serializes GPU inference, concurrent requests queue naturally**: `app.state.xtts_lock = asyncio.Lock()` is acquired before and released after `anyio.to_thread.run_sync`. If a second request arrives while inference is running, it waits — no 503 "busy" response. This is intentional for a single-GPU personal-use deployment where queuing is acceptable.

- **Model loads at startup via `TTS(...).to(device)`**: `os.environ["COQUI_TOS_AGREED"] = "1"` is set before import; `tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)` runs in lifespan. On first run the model downloads to `~/.local/share/tts/`; subsequent runs use the cached files. Docker model-baking strategy is deferred (see Open Questions).

- **`VoiceInferenceError` domain exception**: Mirrors `AudioConversionError`. The helper raises typed exceptions; the route maps them to HTTP codes. `RuntimeError`/`torch.cuda.OutOfMemoryError` → 503 static string; `ValueError` (audio too short for XTTS) → 422 static string; model not loaded → 503 static string.

- **Tests are pure mock — `coqui-tts` is NOT installed in the test environment**: `conftest.py` uses `sys.modules` patches to replace `TTS.api.TTS` with a `MagicMock` before `from app.main import app`. No real download, no GPU required in CI.

- **Input validation additions**:
  - Minimum audio duration: ≥3 seconds checked after WAV conversion (pydub `len(audio_segment) / 1000`)
  - Maximum text length: 500 characters checked in the existing text validation block

## Open Questions

### Resolved During Planning

- **API style**: High-level `TTS` class (`tts.tts_to_file()`), matching official sample code; simpler than low-level `Xtts` class
- **Language parameter strategy**: Auto-detect from Unicode CJK ranges server-side; zh-cn + en only; fallback `zh-cn`; no frontend change
- **Minimum reference audio duration**: ≥3 seconds enforced post-conversion; 400 with static Chinese error string
- **Max text length**: 500 characters; 400 with static string
- **Concurrency**: `asyncio.Lock` serializes inference; concurrent requests queue naturally; no 503 for busy lock (personal tool)
- **Temp-file cleanup**: `_convert_to_wav` returns bytes (unchanged semantics). `_run_xtts` creates ONE `TemporaryDirectory` owning both `speaker.wav` (written from bytes) and `synth.wav` (tts_to_file output); atomically cleaned on thread exit
- **Test environment**: `coqui-tts` NOT installed in test env; pure `sys.modules` mock in `conftest.py`
- **Package name**: `coqui-tts` (Idiap fork); `COQUI_TOS_AGREED=1` set at module top before import

### Deferred to Implementation

- **Docker / deployment strategy**: Covered by Unit 4 in this plan; dev flow uses first-run model download to `~/.local/share/tts/`
- **Exact torch CUDA version**: Use `torch>=2.2.0+cu121` as starting point; verify against actual driver during setup
- **`espeak-ng` requirement for Chinese**: `zh-cn` may require `apt-get install -y espeak-ng` in deployment env; verify during iteration
- **VRAM on actual hardware**: RTX 50 series expected; verify OOM behavior on real device
- **`_convert_to_wav` internal usage**: After Unit 1 completes, confirm `_convert_to_wav` is only called from within `voice.py` and is not imported or invoked by any other module.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

**Request flow after Unit 1-3 are complete:**

```text
POST /api/clone-voice (multipart: file + text)
  │
  ├─ [existing] MIME + text + size + magic-bytes validation
  │
  ├─ [Unit 1] anyio thread: _convert_to_wav(contents, fmt)
  │     → returns (wav_bytes: bytes, duration_secs: float)
  │
  ├─ [Unit 3] duration check: < 3s → 400
  ├─ [Unit 3] text length check: > 500 → 400
  ├─ [Unit 3] model guard: tts_model is None → 503
  ├─ [Unit 3] language = detect_language(text) → "zh-cn" | "en"
  │
  └─ [Unit 3] async with app.state.xtts_lock:
        anyio thread (inside ONE TemporaryDirectory tmpdir):
          write wav_bytes → tmpdir/speaker.wav
          tts.tts_to_file(text, speaker_wav=tmpdir/speaker.wav,
                          language=language, file_path=tmpdir/synth.wav)
          result = open(tmpdir/synth.wav, "rb").read()
        → VoiceInferenceError on failure
        → tmpdir.__exit__ cleans both files atomically
  │
  └─ Response(result, media_type="audio/wav")
```

**Lifespan (Unit 2):**

```text
app startup:
  os.environ["COQUI_TOS_AGREED"] = "1"
  device = "cuda" if torch.cuda.is_available() else "cpu"
  tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
  app.state.tts_model = tts
  app.state.xtts_lock = asyncio.Lock()
```

## Implementation Units

- [ ] **Unit 1: Create `_convert_to_wav` helper returning `(bytes, duration_secs)`**

**Goal:** Create the `_convert_to_wav` helper function and `AudioConversionError` exception in `voice.py` from scratch, add pydub + anyio dependencies, and write full unit tests. The function does not exist yet.

**Requirements:** R1 (prerequisite for XTTS integration)

**Dependencies:** Requires adding `pydub` and `anyio` to `backend/requirements.txt`. Requires `ffmpeg` system binary available at runtime.

**Files:**
- Modify: `backend/app/routes/voice.py`
- Modify: `backend/requirements.txt` (add `pydub`, `anyio`)
- Test: `backend/tests/test_voice.py` (create `TestConvertToWav` class)

**Approach:**
- Declare module-level constant `MAX_PCM_SIZE = 50 * 1024 * 1024` at the top of `voice.py` (50 MB PCM decompression bomb guard)
- Create new `class AudioConversionError(Exception)` domain exception in `voice.py`
- Create new `_convert_to_wav(contents: bytes, fmt: str) -> tuple[bytes, float]` helper function in `voice.py` (function does not exist yet)
- The function uses `AudioSegment.from_file(io.BytesIO(contents), format=fmt)` to decode audio
- Check `len(audio.raw_data) > MAX_PCM_SIZE` (50 MB) → raise `AudioConversionError` to prevent decompression bombs
- Catch `pydub.exceptions.CouldntDecodeError` → raise `AudioConversionError`
- Export to WAV bytes via `io.BytesIO` buffer and `audio.export(buf, format="wav")`
- Compute duration: `len(audio) / 1000.0`
- Return `(wav_bytes, duration_secs)` — the route layer (Unit 3) is responsible for writing these bytes to a temp file for XTTS
- Unit 1 itself makes no changes to the route; the existing `# TODO` echo behavior is unchanged until Unit 3

**Patterns to follow:**
- pydub mock `side_effect` pattern: `mock_seg.export.side_effect = lambda buf, format, parameters=None: buf.write(WAV_STUB)` — `return_value` is a silent bug
- `backend/tests/test_voice.py` — `TestDetectAudioType` and `TestCloneVoiceEndpoint` show the test class structure and `MagicMock` usage to follow when creating `TestConvertToWav`

**Test scenarios:**
- Create `TestConvertToWav` class in `test_voice.py`
- Valid webm/mp4/ogg → returns `(WAV_STUB_bytes, positive_float)`
- `CouldntDecodeError` → raises `AudioConversionError` (new function, not "unchanged")
- PCM exceeds 50 MB → raises `AudioConversionError`
- Note: pydub's `AudioSegment` must be mocked in these tests; `coqui-tts` is not involved

**Verification:**
- All `TestConvertToWav` tests pass with tuple-unpacking assertions
- No `TestCloneVoiceEndpoint` tests regress

---

- [ ] **Unit 2: Load XTTS v2 model in FastAPI lifespan**

**Goal:** Load high-level `TTS` model at application startup via `TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)`, store on `app.state.tts_model` and `app.state.xtts_lock`. Startup failure is fatal and intentional.

**Requirements:** R2, R4

**Dependencies:** `coqui-tts` installed (dev env); model auto-downloads to `~/.local/share/tts/` on first run

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/requirements.txt` (add `coqui-tts`, `torch`, `torchaudio`)
- Create: `backend/tests/conftest.py` (`sys.modules` patches for TTS; file does not exist today)

**Approach:**
- Set `os.environ["COQUI_TOS_AGREED"] = "1"` at module top (before any TTS import)
- Add a new `@asynccontextmanager async def lifespan(app)` function to `main.py` and pass it to `FastAPI(lifespan=lifespan)` — this is net-new code; `main.py` currently has no lifespan handler or `app.state` usage
- `tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda" if torch.cuda.is_available() else "cpu")`
- Store `app.state.tts_model = tts` and `app.state.xtts_lock = asyncio.Lock()`
- Log loading time with `time.monotonic()` (same pattern as rembg)
- Create `backend/tests/conftest.py` from scratch (file does not exist yet): use `sys.modules` patches to replace `TTS.api` with a module containing a mock `TTS` class. The mock `TTS(...)` constructor should return a `MagicMock` with a `to()` method that returns itself and a `tts_to_file()` method configurable per test. Call `sys.modules.pop("app.main", None)` before re-importing to ensure the mocked lifespan is exercised.

**Patterns to follow:**
- `backend/app/main.py` — the `add_security_headers` middleware shows the FastAPI middleware pattern; `FastAPI()` call is the constructor to extend with `lifespan=lifespan`
- No prior `conftest.py` exists; create from scratch using `sys.modules` patching: inject mock modules before `from app.main import app` is evaluated to prevent real model import

**Test scenarios:**
- `TestClient(app)` construction succeeds without `coqui-tts` installed (validated by `conftest.py` mock preventing import)
- `app.state.tts_model` is set after lifespan runs
- `app.state.xtts_lock` is an `asyncio.Lock` instance

**Verification:**
- `backend/tests/test_voice.py` suite passes without `coqui-tts` installed
- `python -c "from app.main import app"` succeeds in a dev environment with the package installed

---

- [ ] **Unit 3: Replace TODO in `voice.py` with real XTTS inference**

**Goal:** Implement the full post-conversion inference pipeline: audio duration check, text length check, language detection, model-not-ready guard, XTTS inference inside lock, WAV bytes construction, and error mapping.

**Requirements:** R1, R3, R4, R5

**Dependencies:** Unit 1 (returns (wav_bytes, duration_secs)), Unit 2 (model on `app.state`)

**Files:**
- Modify: `backend/app/routes/voice.py`
- Test: `backend/tests/test_voice.py` (new test cases for all new validation paths and inference success/failure)

**Approach:**
- Post-conversion checks (after `_convert_to_wav` succeeds):
  - `duration_secs < 3.0` → 400, static string `"音訊樣本太短，至少需要 3 秒。"`
  - `len(text) > 500` → 400, static string `"文字不得超過 500 個字元。"`
- Language detection: pure function `_detect_language(text) -> str` — check `any('\u4e00' <= ch <= '\u9fff' for ch in text)` → `"zh-cn"`, else `"en"`. **Note:** this checks only the CJK Unified Ideographs main block (U+4E00–U+9FFF). Characters from Extension A (U+3400–U+4DBF), Compatibility Ideographs (U+F900–U+FAFF), and full-width punctuation (U+3000–U+303F) are not detected as Chinese. Acceptable for MVP; expand if user reports indicate missed Chinese text.
- Model guard: `model = getattr(request.app.state, "xtts_model", None)` → 503 if `None` (this guard is introduced by this plan; `images.py` does not have an equivalent)
- Unpack conversion result: `wav_bytes, duration_secs = await anyio.to_thread.run_sync(lambda: _convert_to_wav(...))`
- Temp-file lifecycle: a single `TemporaryDirectory` is created inside the thread lambda that runs XTTS inference; it owns both `speaker.wav` (written from `wav_bytes`) and `synth.wav` (tts_to_file output); cleaned up atomically on thread exit
- Inference offload: `async with app.state.xtts_lock: result_bytes = await anyio.to_thread.run_sync(lambda: _run_xtts(...), abandon_on_cancel=False)`. Using `False` ensures the lock is held until the thread truly completes, preventing a cancelled request from releasing the lock while GPU inference is still running.
- `_run_xtts(tts, wav_bytes, text, language)` helper (pure sync, raises `VoiceInferenceError`):
  - Opens a `TemporaryDirectory` as context manager
  - Writes `wav_bytes` to `tmpdir/speaker.wav`
  - Calls `tts.tts_to_file(text=text, speaker_wav=tmpdir/speaker.wav, language=language, file_path=tmpdir/synth.wav)`
  - Reads `tmpdir/synth.wav` back as bytes and returns them
  - `TemporaryDirectory.__exit__` cleans up both files when the function returns (normal or exception)
  - Catch `torch.cuda.OutOfMemoryError` → raise `VoiceInferenceError("OOM")`, `ValueError` → `VoiceInferenceError("short_audio")`, others → re-raise
- Route catches `VoiceInferenceError` and maps to 503 / 422 with static strings (no `str(e)` in `detail`)
- Response: `Response(content=wav_bytes, media_type="audio/wav", headers={"Content-Disposition": 'attachment; filename="cloned.wav"'})`

**Patterns to follow:**
- `backend/app/routes/images.py` — `loop.run_in_executor` thread-offload pattern (use anyio equivalent `anyio.to_thread.run_sync` instead, which is the pattern used here)
- `backend/app/routes/voice.py` — `AudioConversionError` created in Unit 1; `VoiceInferenceError` follows the same shape. Never puts `str(e)` in `detail`.
- No existing `anyio.to_thread.run_sync` usage in `voice.py` to follow — this is the first use of anyio in the codebase

**Test scenarios:**
- Duration < 3s → 400 with static error string
- Text > 500 chars → 400 with static error string
- Model not loaded (`xtts_model=None`) → 503
- Successful inference → 200 `audio/wav` response with non-empty body
- XTTS raises `ValueError` (short audio) → 422 static string
- XTTS raises `torch.cuda.OutOfMemoryError` → 503 static string
- XTTS raises unexpected `RuntimeError` → 500
- Language detection: Chinese text → `"zh-cn"`, Latin text → `"en"`, mixed → `"zh-cn"`
- All 9 existing `TestCloneVoiceEndpoint` tests continue to pass (echo behavior replaced by mock XTTS; configure `tts_to_file` mock to write expected bytes to output path)
- No temp file leaked on inference failure

**Verification:**
- Full endpoint test for happy path: mock returns dummy `{"wav": [0.0] * 24000}` array, response is valid WAV
- All new validation paths return the expected status code and static `detail` string
- No temp file leaked on inference failure (assert temp file does not exist after an exception test)

---

- [ ] **Unit 4: Create Dockerfile with CUDA + coqui-tts + pre-baked model**

**Goal:** Produce a `backend/Dockerfile` that builds a runnable image containing: CUDA, FFmpeg, coqui-tts, and the pre-downloaded XTTS v2 model weights (~2.1 GB).

**Requirements:** R2, R4 (GPU inference requires CUDA in container)

**Dependencies:** Unit 1–3 complete (stable requirements.txt)

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/download_model.py` (helper script for model download during build)

**Approach:**
- Base image: `nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04` (or matching version to deployment host driver)
- System packages: `ffmpeg`, `libsndfile1`, `espeak-ng` (for phonemization, required by `zh-cn`)
- Install PyTorch with CUDA first (`pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121`), then `pip install coqui-tts`
- `ENV COQUI_TOS_AGREED=1`
- Run `download_model.py` during build to pre-download model weights to `/models/xtts_v2/`; this layer is large (~2.1 GB) but ensures zero network dependency at runtime
- `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- Add `HEALTHCHECK` calling the existing (or a new minimal) `/health` route — or at minimum a TCP check

**Patterns to follow:**
- `backend/requirements.txt` — existing dependency style
- `backend/app/main.py` — startup model path used in lifespan

**Test scenarios:**
- `docker build` completes without network access to HuggingFace (model already downloaded at build time)
- Container starts and `app.state.xtts_model` is not None after startup log
- FFmpeg and espeak-ng are present in the image (`ffmpeg -version`, `espeak-ng --version`)

**Verification:**
- `docker run --gpus all ... curl -f http://localhost:8000/api/clone-voice` (POST with valid audio + text) returns 200 WAV
- Image size is expected (~5–6 GB with base CUDA + model)

## System-Wide Impact

- **Interaction graph**: Only `POST /api/clone-voice` is affected. `main.py` lifespan acquires a new `Xtts` model alongside the existing `rembg_session`. The two models coexist on `app.state` and do not share state.
- **Error propagation**: `VoiceInferenceError` raised in `_run_xtts` helper, caught at route level, converted to `HTTPException`. Uncaught exceptions still produce FastAPI's default 500. Static `detail` strings only — no `str(e)` leak.
- **State lifecycle risks**: The `asyncio.Lock` serializes inference. With `abandon_on_cancel=False`, if a request is cancelled, the coroutine waits for the thread to finish before the cancellation propagates — the lock is therefore not released until GPU inference is truly complete. This prevents a cancelled request from allowing a second concurrent inference on the non-thread-safe model. Concurrency is effectively 1 GPU inference at a time — this is intentional for a single-GPU self-hosted deployment.
- **Temp-file leak risk**: `TemporaryDirectory` or `os.unlink` in `try/finally` covers normal failure and success paths. Cancelled requests may leave a temp file if the thread is abandoned mid-execution; mitigated by using `TemporaryDirectory` inside the thread lambda (not outside it), so the `__exit__` runs when the thread exits, not when the coroutine exits.
- **Memory**: XTTS model ~3–4 GB VRAM + ~6–8 GB system RAM at runtime. rembg is ~200 MB. Both coexist if the GPU has ≥8 GB VRAM; otherwise OOM → 503.
- **Startup blocking**: `model.load_checkpoint` is synchronous and may take 10–30 seconds on first cold start (model files already on disk). This blocks the lifespan coroutine and delays FastAPI's readiness. No mitigation needed for single-instance deployment; note in Dockerfile `HEALTHCHECK` with appropriate start period (`--start-period=60s`).
- **API surface parity**: Frontend `api.js` `cloneVoice()` sends `{ file, text }` — no change needed. The new `language` auto-detection is transparent.

## Risks & Dependencies

- **VRAM OOM on deployment GPU**: Deployment uses RTX 50 series (≥16 GB VRAM); rembg (~200 MB) and XTTS (~3–4 GB) coexist comfortably. OOM protection still implemented as `torch.cuda.OutOfMemoryError` → 503 as a defensive measure.
- **`espeak-ng` missing → silent quality degradation for zh-cn**: XTTS may fall back to character-by-character phonemization without espeak-ng, producing robotic output rather than a hard error. Mitigation: install `espeak-ng` in Dockerfile; add a log warning at startup if import check fails.
- **Model download blocked at build time**: If the build environment has no HuggingFace access, `download_model.py` fails. Mitigation: note in Dockerfile comments that build requires outbound HTTPS to `hf.co`; alternatively, pre-mount the model directory.
- **Python version constraint**: `coqui-tts` requires Python ≥ 3.10. Current dev environment Python version unknown. If < 3.10, a Python upgrade is a prerequisite.
- **No Dockerfile today**: Docker is a net-new artifact. CI pipeline changes (if any) are out of scope for this plan.

## Sources & References

- **Origin document:** [`docs/brainstorms/2026-03-25-voice-cloning-real-implementation-requirements.md`](docs/brainstorms/2026-03-25-voice-cloning-real-implementation-requirements.md)
- Coqui XTTS v2 maintained fork: https://github.com/idiap/coqui-ai-TTS
- Related code: `backend/app/routes/voice.py`, `backend/app/main.py`, `backend/app/routes/images.py`, `backend/tests/test_voice.py`
