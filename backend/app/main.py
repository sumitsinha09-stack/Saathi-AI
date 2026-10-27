import os
from datetime import datetime, timezone
from typing import Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import httpx
from sqlalchemy import text

from backend.app.config import settings
from backend.app.database import engine, init_db
from backend.app.routers.webhook import router as webhook_router
from backend.app.routers.voice import router as voice_router
from backend.app.routers.complaints import router as complaints_router

LANDING_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "saathi-ai-landing")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist
    await init_db()
    # Ensure voice upload directory exists
    os.makedirs(settings.VOICE_UPLOAD_DIR, exist_ok=True)
    # Pre-warm Faster-Whisper model in background thread
    from backend.app.services.transcription_service import TranscriptionService
    import asyncio
    asyncio.create_task(asyncio.to_thread(TranscriptionService.get_model))
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

# Enable CORS for frontend and mobile access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(webhook_router)
app.include_router(voice_router)
app.include_router(complaints_router)


@app.api_route("/", methods=["GET", "HEAD"], tags=["General"])
async def root(request: Request) -> Any:
    """
    Root endpoint.
    Serves the modern mobile-friendly voice-recording home page by default,
    or service identity JSON when explicitly requested via Accept: application/json.
    """
    index_file = os.path.join(LANDING_DIR, "index.html")
    accept = request.headers.get("accept", "").lower()

    if accept == "application/json" or not os.path.exists(index_file):
        return {
            "name": settings.APP_NAME,
            "environment": settings.APP_ENV,
            "status": "operational",
            "documentation": "/docs",
            "health": "/health",
            "voice_api": "/api/voice",
            "message": "Welcome to Saathi AI. Emergency cybercrime assistance platform.",
        }

    return FileResponse(index_file)


@app.api_route("/styles.css", methods=["GET", "HEAD"], include_in_schema=False)
async def styles_css() -> FileResponse:
    return FileResponse(
        os.path.join(LANDING_DIR, "styles.css"),
        media_type="text/css",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )


@app.api_route("/script.js", methods=["GET", "HEAD"], include_in_schema=False)
async def script_js() -> FileResponse:
    return FileResponse(
        os.path.join(LANDING_DIR, "script.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )


@app.get("/c/{token}", include_in_schema=False)
async def review_page(token: str) -> FileResponse:
    """Serves the mobile-friendly Complaint Review, Editing, and Confirmation page."""
    review_file = os.path.join(LANDING_DIR, "review.html")
    if not os.path.exists(review_file):
        # Fallback to index if review.html not yet created
        return FileResponse(os.path.join(LANDING_DIR, "index.html"))
    return FileResponse(review_file)


@app.api_route("/review.js", methods=["GET", "HEAD"], include_in_schema=False)
async def review_js() -> FileResponse:
    return FileResponse(
        os.path.join(LANDING_DIR, "review.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )


@app.api_route("/review.css", methods=["GET", "HEAD"], include_in_schema=False)
async def review_css() -> FileResponse:
    return FileResponse(
        os.path.join(LANDING_DIR, "review.css"),
        media_type="text/css",
        headers={"Cache-Control": "no-cache, must-revalidate"}
    )


@app.get("/helpline", include_in_schema=False)
async def helpline_page() -> FileResponse:
    """Serves the mobile-friendly Complaint Lookup and Helpline Status page."""
    helpline_file = os.path.join(LANDING_DIR, "helpline.html")
    if not os.path.exists(helpline_file):
        return FileResponse(os.path.join(LANDING_DIR, "index.html"))
    return FileResponse(helpline_file)


@app.api_route("/helpline.js", methods=["GET", "HEAD"], include_in_schema=False)
async def helpline_js() -> FileResponse:
    return FileResponse(os.path.join(LANDING_DIR, "helpline.js"), media_type="application/javascript")


@app.api_route("/helpline.css", methods=["GET", "HEAD"], include_in_schema=False)
async def helpline_css() -> FileResponse:
    return FileResponse(os.path.join(LANDING_DIR, "helpline.css"), media_type="text/css")


@app.api_route("/samples/{filename}", methods=["GET", "HEAD"], include_in_schema=False)
async def sample_audio(filename: str) -> FileResponse:
    candidate_paths = [
        os.path.join(LANDING_DIR, "samples", filename),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "test_data", "synthetic_scams", filename)),
    ]
    for sample_path in candidate_paths:
        if os.path.exists(sample_path) and (filename.endswith(".wav") or filename.endswith(".webm") or filename.endswith(".mp3")):
            return FileResponse(sample_path, media_type="audio/wav")
    return JSONResponse(status_code=404, content={"detail": "Sample not found"})





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
