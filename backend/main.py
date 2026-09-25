"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import get_settings, ensure_directories
from database import init_database, seed_demo_user

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Create directories
    ensure_directories()

    # Initialize database
    await init_database()
    await seed_demo_user()

    # Log mode
    if settings.demo_mode:
        logger.warning(
            "⚠️  DEMO MODE: No trained model found at %s. "
            "AI inference will return synthetic demonstration outputs.",
            settings.model_weights_path,
        )
    else:
        logger.info("Model weights found. AI inference is available.")

    yield

    logger.info("Application shutting down")


# Create FastAPI app
app = FastAPI(
    title="ROP AI Screener API",
    description="AI-Assisted Retinopathy of Prematurity Screening — Research Prototype",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploaded images and reports
uploads_path = Path(settings.UPLOADS_DIR)
reports_path = Path(settings.REPORTS_DIR)
uploads_path.mkdir(parents=True, exist_ok=True)
reports_path.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")
app.mount("/reports", StaticFiles(directory=str(reports_path)), name="reports")

# Import and register routers
from routers import auth, patients, screening, images, history, reports

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(patients.router, prefix="/api/patients", tags=["Patients"])
app.include_router(screening.router, prefix="/api/screening", tags=["Screening"])
app.include_router(images.router, prefix="/api/images", tags=["Images"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again or contact support.",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )


# Health check
@app.get("/api/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "demo_mode": settings.demo_mode,
        "model_available": settings.is_model_available,
    }


if __name__ == "__main__":
    import uvicorn
    import os

    host = os.environ.get("HOST", settings.HOST)
    port = int(os.environ.get("PORT", str(settings.PORT)))
    uvicorn.run("main:app", host=host, port=port, reload=settings.DEBUG)
