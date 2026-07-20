"""
FastAPI application entrypoint.

Run locally / in Codespaces with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Scrapes live job postings, scores CV-to-market fit, and generates an AI gap analysis.",
    version="1.0.0",
)

# CORS: allow the Vite dev server on localhost AND any GitHub Codespaces
# forwarded-port URL (these look like https://<hash>-5173.app.github.dev).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["meta"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}
