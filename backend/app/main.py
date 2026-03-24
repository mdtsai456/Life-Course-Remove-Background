from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_cors_allowed_origins
from app.routes.images import router as images_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images_router)
