"""
FastAPI Application - Main Entry Point for Backend Service

Initializes:
- Database connection pool
- Route handlers (dashboard API)
- WebSocket routes
- Error handling middleware
- Startup/shutdown hooks
"""

import logging
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database import close_db, init_db
from backend.models import HealthResponse
from backend.dashboard_api import router as dashboard_router

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Aladdin Exclusion Parser Backend",
    description="Phase 3: FastAPI backend with PostgreSQL persistence and human-in-loop approval",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and log startup"""
    logger.info("=" * 80)
    logger.info("Starting Aladdin Exclusion Parser Backend")
    logger.info("=" * 80)

    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections"""
    logger.info("Shutting down Aladdin Exclusion Parser Backend")
    await close_db()
    logger.info("Database connections closed")


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow(),
    )


# Include routers
app.include_router(dashboard_router, prefix="/api", tags=["exclusions"])


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "status_code": 500,
            "error_type": type(exc).__name__,
        }
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": "Aladdin Exclusion Parser Backend",
        "version": "1.0.0",
        "description": "Phase 3: Database persistence, approval workflow, real-time updates",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", 8000)),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
