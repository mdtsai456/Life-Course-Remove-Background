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
    return response

app.include_router(images_router)
app.include_router(threed_router)
app.include_router(voice_router)
