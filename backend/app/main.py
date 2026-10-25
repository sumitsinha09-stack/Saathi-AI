import os
from datetime import datetime, timezone
from typing import Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Load environment configuration safely
load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Saathi AI Cybercrime Reporting Assistant")
APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg://samaran_user:samaran_dev_pass_2026@127.0.0.1:5432/samaran"
)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

# Initialize database engine (async psycopg)
db_engine = None
try:
    db_engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
except Exception:
    db_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle
    yield
    # Shutdown lifecycle
    if db_engine is not None:
        await db_engine.dispose()


app = FastAPI(
    title="Saathi AI (Samaran) API",
    description="Emergency WhatsApp voice-complaint reporting assistant for cyber-fraud victims in India.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for future Next.js portal integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root() -> Dict[str, Any]:
    """
    Root endpoint returning service identity and quick links.
    """
    return {
        "name": APP_NAME,
        "environment": APP_ENV,
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
    if db_engine:
        try:
            async with db_engine.connect() as conn:
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
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
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
        "configured_model": OLLAMA_MODEL,
        "services": service_status,
    }

    return JSONResponse(status_code=http_status, content=payload)
