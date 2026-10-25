import os
from datetime import datetime, timezone
from typing import Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from sqlalchemy import text

from backend.app.config import settings
from backend.app.database import engine, init_db
from backend.app.routers.webhook import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    await init_db()
    yield
    # Shutdown
    if engine is not None:
        await engine.dispose()


app = FastAPI(
    title="Saathi AI (Samaran) API",
    description="Emergency WhatsApp voice-complaint reporting assistant for cyber-fraud victims in India.",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for Next.js portal
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(webhook_router)


@app.get("/", tags=["General"])
async def root() -> Dict[str, Any]:
    """
    Root endpoint returning service identity and quick links.
    """
    return {
        "name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "status": "operational",
        "documentation": "/docs",
        "health": "/health",
        "message": "Welcome to Saathi AI. Emergency cybercrime assistance platform.",
    }


@app.get("/health", tags=["Monitoring"])
async def health_check() -> JSONResponse:
    """
    Comprehensive health check reporting database and Ollama availability.
    Strictly safeguards secrets and connection credentials.
    """
    service_status: Dict[str, str] = {
        "backend": "healthy",
        "database": "unknown",
        "ollama": "unknown",
    }
    is_healthy = True

    # 1. Check PostgreSQL Database connection
    if engine:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            service_status["database"] = "connected"
        except Exception:
            service_status["database"] = "disconnected"
            is_healthy = False
    else:
        service_status["database"] = "not_configured"
        is_healthy = False

    # 2. Check Ollama API accessibility
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                service_status["ollama"] = "available"
            else:
                service_status["ollama"] = f"unresponsive (HTTP {resp.status_code})"
                is_healthy = False
    except Exception:
        service_status["ollama"] = "unreachable"
        is_healthy = False

    http_status = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    payload = {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "configured_model": settings.OLLAMA_MODEL,
        "services": service_status,
    }

    return JSONResponse(status_code=http_status, content=payload)
