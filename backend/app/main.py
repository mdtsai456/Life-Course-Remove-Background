import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

os.environ["COQUI_TOS_AGREED"] = "1"  # must precede TTS import

import torch
from TTS.api import TTS
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from rembg import new_session

from app.config import get_cors_allowed_origins, is_docs_enabled
from app.routes.images import router as images_router
from app.routes.threed import router as threed_router
from app.routes.voice import router as voice_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load rembg model
    start = time.monotonic()
    app.state.rembg_session = new_session()
    elapsed = time.monotonic() - start
    logger.info("rembg model loaded in %.1fs", elapsed)

    # Load XTTS v2 model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    start = time.monotonic()
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    elapsed = time.monotonic() - start
    logger.info("XTTS v2 model loaded in %.1fs (device: %s)", elapsed, device)
    app.state.tts_model = tts
    app.state.xtts_lock = asyncio.Lock()
    app.state.xtts_pending = 0

    yield

    # Teardown: release models in reverse order
    del app.state.xtts_pending
    del app.state.xtts_lock
    del app.state.tts_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    del app.state.rembg_session
    logger.info("Models unloaded")


_docs_enabled = is_docs_enabled()
app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response

app.include_router(images_router)
app.include_router(threed_router)
app.include_router(voice_router)


@app.get("/health")
async def health():
    checks = {
        "rembg": getattr(app.state, "rembg_session", None) is not None,
        "xtts_v2": getattr(app.state, "tts_model", None) is not None,
    }
    healthy = all(checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "loading", "checks": checks},
    )
