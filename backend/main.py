"""
AgentForge API — FastAPI application entry point.

Port: 8400 (to avoid conflicts with existing services)
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .config import get_settings
from .database import init_db
from .routers import auth_router, agents_router, wallet_router, tamper_router, ws_router, chat_router, marketplace_router, portability_router, trust_router

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended HTTP security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        # HSTS: 1 year, include subdomains (only meaningful over HTTPS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Prevent caching of API responses that may contain sensitive data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Agent Identity & Licensing Platform — Cryptographic identities for AI agents",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Security headers — must be added BEFORE CORS so it wraps outermost
app.add_middleware(SecurityHeadersMiddleware)

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
app.include_router(wallet_router)
app.include_router(tamper_router)
app.include_router(ws_router)
app.include_router(chat_router)
app.include_router(marketplace_router)
app.include_router(portability_router)
app.include_router(trust_router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "version": settings.app_version, "service": settings.app_name}
