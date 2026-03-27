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

The `/api/clone-voice` endpoint is fully wired end-to-end (frontend → validation → WAV conversion → response) but contains a `# TODO` placeholder where actual AI inference should run. The WAV conversion step (pydub + anyio) is already shipped and tested. This plan replaces only the TODO block onward — the validation pipeline is not touched.

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

- **lifespan pattern**: `backend/app/main.py` — `@asynccontextmanager async def lifespan`, stores `rembg_session` on `app.state`; XTTS model follows identical pattern
- **model-not-ready guard**: `backend/app/routes/images.py:56-59` — `getattr(request.app.state, "rembg_session", None)` returning 503; copy-paste this into `voice.py`
- **anyio thread offload**: `backend/app/routes/voice.py` — `await anyio.to_thread.run_sync(lambda: ..., abandon_on_cancel=True)` already used for `_convert_to_wav`; apply same pattern to XTTS inference
- **domain exception pattern**: `voice.py` — `class AudioConversionError(Exception)` raised by helper, caught in route and mapped to HTTP status; add `VoiceInferenceError` following the same shape
- **static error strings**: `voice.py` — never puts `str(e)` or FFmpeg stderr in `detail`; carry forward for all new error paths
- **conftest rembg mock**: `backend/tests/conftest.py:17-38` — `sys.modules` patch prevents model load on import; extend with matching `TTS` module patches
- **WAV conversion tests**: `backend/tests/test_voice.py` — `TestConvertToWav` asserts on `bytes` return type; all must be updated when Unit 1 changes `_convert_to_wav` to return a temp-file path

### Institutional Learnings

- **lifespan failure is intentional and fatal** (`docs/plans/2026-03-27-002-model-preload-design.md`): No retry or fallback on startup failure; OOM/download failure should crash the process
- **temp-file handoff is explicitly deferred** to this integration (`docs/plans/2026-03-27-001-feat-pydub-wav-conversion-plan.md`): `_convert_to_wav` returns `bytes` today but must return a path; this is Unit 1
- **memory-bomb guard must be preserved** (`docs/plans/2026-03-27-001`): `MAX_PCM_SIZE = 50 MB` check on `len(audio.raw_data)` must remain in `_convert_to_wav` after the temp-file refactor
- **pydub mock side_effect pattern** (`docs/plans/2026-03-27-001`): `mock_seg.export.side_effect = lambda buf, format, parameters=None: buf.write(WAV_STUB)` — `return_value` is a silent bug

### External References

- XTTS v2 supported languages include `zh-cn` and `en` (17 total)
- XTTS output is always 24000 Hz WAV; handles input resampling to 22050 Hz internally
- Speaker WAV minimum recommended: 6 seconds (this plan enforces ≥3 seconds as a practical minimum)
- Speaker latents (`get_conditioning_latents`) are recomputed per-request (no persistent speaker cache)
- Model size: ~2.09 GB total (model.pth 1.87 GB + dvae.pth 211 MB + misc)
- `COQUI_TOS_AGREED=1` env var required to suppress interactive license prompt in headless environments
- **Package**: `pip install coqui-tts` — maintained Idiap fork; original `pip install TTS` is unmaintained
- Inference is NOT thread-safe: concurrent calls against a shared model instance can corrupt state; serialize with `asyncio.Lock`

## Key Technical Decisions

- **High-level `TTS` API（非低階 `Xtts` class）**: 使用 `TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)` 與 `tts.tts_to_file(text, speaker_wav, language, file_path)` — 與官方範例一致，程式碼最簡單。`tts_to_file` 寫到 output temp file，route 再讀回 bytes 回傳。不需要手動 torchaudio / numpy 操作。

- **`_convert_to_wav` 返回 `(bytes, duration_secs)`，route 層負責寫檔**: `_convert_to_wav` 保持純 bytes 轉換語意，只額外回傳 duration。Route 在 thread lambda 內建立一個 `TemporaryDirectory`，把 bytes 寫成 `tmpdir/speaker.wav`，再把 `tmpdir/synth.wav` 作為 `tts_to_file` 的 output path。單一 `TemporaryDirectory` 擁有兩個檔案，thread 結束時統一清除。無 ownership 分裂，測試改動最小（只加 duration assertion）。

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

- **Docker / deployment strategy**: Not yet decided; Unit 5 is intentionally left for later; dev flow uses first-run model download to `~/.local/share/tts/`
- **Exact torch CUDA version**: Use `torch>=2.2.0+cu121` as starting point; verify against actual driver during setup
- **`espeak-ng` requirement for Chinese**: `zh-cn` may require `apt-get install -y espeak-ng` in deployment env; verify during iteration
- **VRAM on actual hardware**: RTX 50 series expected; verify OOM behavior on real device
- **`_convert_to_wav` non-XTTS callers**: Confirm no code outside `voice.py` calls `_convert_to_wav` before changing its return type

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

**Request flow after Unit 1-3 are complete:**

```
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

```
app startup:
  os.environ["COQUI_TOS_AGREED"] = "1"
  device = "cuda" if torch.cuda.is_available() else "cpu"
  tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
  app.state.tts_model = tts
  app.state.xtts_lock = asyncio.Lock()
```

## Implementation Units

- [ ] **Unit 1: Refactor `_convert_to_wav` to return temp-file path + duration**

**Goal:** Extend `_convert_to_wav` to also return `duration_secs`, changing the return type from `bytes` to `(bytes, float)`. The bytes semantics are unchanged — only duration is added.

**Requirements:** R1 (prerequisite for XTTS integration)

**Dependencies:** None

**Files:**
- Modify: `backend/app/routes/voice.py`
- Test: `backend/tests/test_voice.py` (all `TestConvertToWav` assertions change from bytes to path)

**Approach:**
- `_convert_to_wav(contents, fmt)` decodes with pydub as before, then returns `(wav_bytes, len(audio) / 1000.0)` where `wav_bytes` is obtained from `audio.export(buf, format="wav")` — same as today but wrapped in a tuple
- The PCM memory-bomb guard (`MAX_PCM_SIZE` on `len(audio.raw_data)`) stays unchanged
- The existing route currently passes the returned bytes directly to `Response()`; Unit 3 will unpack the tuple and use bytes differently (write to tmpdir), but Unit 1 itself needs no route-level changes — just the return shape

**Patterns to follow:**
- `docs/plans/2026-03-27-001-feat-pydub-wav-conversion-plan.md` — pydub mock `side_effect` pattern
- `backend/tests/test_voice.py` `TestConvertToWav` — minimal update: unpack tuple, assert `result[0] == WAV_STUB` and `result[1] > 0`

**Test scenarios:**
- Valid webm/mp4/ogg → returns `(WAV_STUB_bytes, positive_float)`
- `CouldntDecodeError` → still raises `AudioConversionError` (unchanged)
- PCM exceeds 50 MB → still raises `AudioConversionError` (unchanged)

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
- Modify: `backend/tests/conftest.py` (extend `sys.modules` patch to cover `TTS.api.TTS`)

**Approach:**
- Set `os.environ["COQUI_TOS_AGREED"] = "1"` at module top (before any TTS import)
- Follow the exact pattern of the existing `rembg_session` lifespan block (see `main.py`)
- `tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda" if torch.cuda.is_available() else "cpu")`
- Store `app.state.tts_model = tts` and `app.state.xtts_lock = asyncio.Lock()`
- Log loading time with `time.monotonic()` (same pattern as rembg)
- `conftest.py`: `coqui-tts` is NOT installed in test environment. Use `sys.modules` patch to replace `TTS.api` with a module containing a mock `TTS` class. The mock `TTS(...)` constructor should return a `MagicMock` with a `to()` method that returns itself and a `tts_to_file()` method configurable per test. Ensure `sys.modules.pop("app.main", None)` is called before re-importing.

**Patterns to follow:**
- `backend/app/main.py` — existing lifespan block for `rembg_session`
- `backend/tests/conftest.py:17-38` — `sys.modules` patch pattern for `rembg`

**Test scenarios:**
- On `TestClient(app)` creation, model load is mocked and does not download or touch GPU
- `app.state.tts_model` is set after lifespan runs
- `app.state.xtts_lock` is an `asyncio.Lock` instance

**Verification:**
- `backend/tests/test_voice.py` suite passes without `coqui-tts` installed
- `python -c "from app.main import app"` succeeds in a dev environment with the package installed

---

- [ ] **Unit 3: Replace TODO in `voice.py` with real XTTS inference**

**Goal:** Implement the full post-conversion inference pipeline: audio duration check, text length check, language detection, model-not-ready guard, XTTS inference inside lock, WAV bytes construction, and error mapping.

**Requirements:** R1, R3, R4, R5

**Dependencies:** Unit 1 (returns path + duration), Unit 2 (model on `app.state`)

**Files:**
- Modify: `backend/app/routes/voice.py`
- Test: `backend/tests/test_voice.py` (new test cases for all new validation paths and inference success/failure)

**Approach:**
- Post-conversion checks (after `_convert_to_wav` succeeds):
  - `duration_secs < 3.0` → 400, static string `"音訊樣本太短，至少需要 3 秒。"`
  - `len(text) > 500` → 400, static string `"文字不得超過 500 個字元。"`
- Language detection: pure function `_detect_language(text) -> str` — check `any('\u4e00' <= ch <= '\u9fff' for ch in text)` → `"zh-cn"`, else `"en"`
- Model guard: `model = getattr(request.app.state, "xtts_model", None)` → 503 if `None` (mirror `images.py:56-59`)
- Unpack conversion result: `wav_bytes, duration_secs = await anyio.to_thread.run_sync(lambda: _convert_to_wav(...))`
- Temp-file lifecycle: a single `TemporaryDirectory` is created inside the thread lambda that runs XTTS inference; it owns both `speaker.wav` (written from `wav_bytes`) and `synth.wav` (tts_to_file output); cleaned up atomically on thread exit
- Inference offload: `async with app.state.xtts_lock: result_bytes = await anyio.to_thread.run_sync(lambda: _run_xtts(...), abandon_on_cancel=True)`
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
- `backend/app/routes/images.py:56-59` — model-not-ready guard pattern
- `backend/app/routes/voice.py` — `AudioConversionError` domain exception + static error string pattern
- `backend/app/routes/voice.py` — existing `anyio.to_thread.run_sync` usage

**Test scenarios:**
- Duration < 3s → 400 with Chinese error message
- Text > 500 chars → 400
- Model not loaded (`xtts_model=None`) → 503
- Successful inference → 200 `audio/wav` response with non-empty body
- XTTS raises `ValueError` (short audio) → 422 static string
- XTTS raises `torch.cuda.OutOfMemoryError` → 503 static string
- XTTS raises unexpected `RuntimeError` → 500 (not 422 or 503)
- Language detection: Chinese text → `"zh-cn"`, Latin text → `"en"`, mixed → `"zh-cn"`

**Verification:**
- Full endpoint test for happy path: mock returns dummy `{"wav": [0.0] * 24000}` array, response is valid WAV
- All new validation paths return the expected status code and static `detail` string
- No temp file leaked on inference failure (assert temp file does not exist after an exception test)

---

- [ ] **Unit 4: Update test mocks in `conftest.py` and `test_voice.py`**

**Goal:** All existing and new tests pass in a CI environment that does NOT have the `coqui-tts` package or GPU available.

**Requirements:** (supporting all R1-R5 test coverage)

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_voice.py`

**Approach:**
- `conftest.py`: add `sys.modules` patches for `TTS.tts.configs.xtts_config.XttsConfig`, `TTS.tts.models.xtts.Xtts`, and `torch.cuda.OutOfMemoryError` (if not available without GPU). Ensure `sys.modules.pop("app.main", None)` is called before re-importing, so the new lifespan XTTS code is covered by the mock.
- In the mock lifespan, `app.state.xtts_model` should be a `MagicMock()` with `get_conditioning_latents`, `inference`, and `cuda` attributes that are also `MagicMock()`.
- For success-path tests, configure `mock_model.get_conditioning_latents.return_value = (MagicMock(), MagicMock())` and `mock_model.inference.return_value = {"wav": [0.0] * 24000}`.
- All `TestConvertToWav` assertions: update from `assert result == WAV_STUB` to `wav_bytes, duration = result; assert wav_bytes == WAV_STUB; assert duration > 0` — minimal change, no file path logic needed.

**Patterns to follow:**
- `backend/tests/conftest.py` — existing `rembg` mock structure

**Test scenarios:**
- `TestClient(app)` construction does not download model or fail in CI
- All 9 existing `TestCloneVoiceEndpoint` tests continue to pass
- New Unit 3 test cases (happy path, all error paths) pass without GPU

**Verification:**
- `pytest backend/tests/test_voice.py -v` passes with zero real model loading
- No file handles or temp files leaked after each test

---

- [ ] **Unit 5: Create Dockerfile with CUDA + coqui-tts + pre-baked model**

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
- **State lifecycle risks**: The `asyncio.Lock` serializes inference. If a request is cancelled with `abandon_on_cancel=True`, the thread runs to completion holding GPU memory; the lock is released when the thread's lambda returns. Concurrency is effectively 1 GPU inference at a time — this is intentional for a single-GPU self-hosted deployment.
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
- **WAV conversion plan:** [`docs/plans/2026-03-27-001-feat-pydub-wav-conversion-plan.md`](docs/plans/2026-03-27-001-feat-pydub-wav-conversion-plan.md)
- **Model preload design:** [`docs/plans/2026-03-27-002-model-preload-design.md`](docs/plans/2026-03-27-002-model-preload-design.md)
- **Audio format brainstorm:** [`docs/brainstorms/2026-03-27-voice-clone-audio-format-requirements.md`](docs/brainstorms/2026-03-27-voice-clone-audio-format-requirements.md)
- Coqui XTTS v2 maintained fork: https://github.com/idiap/coqui-ai-TTS
- Related code: `backend/app/routes/voice.py`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_voice.py`
