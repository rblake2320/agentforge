"""
AgentForge API — FastAPI application entry point.

Port: 8400 (to avoid conflicts with existing services)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import auth_router, agents_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Agent Identity & Licensing Platform — Cryptographic identities for AI agents",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(agents_router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "version": settings.app_version, "service": settings.app_name}
