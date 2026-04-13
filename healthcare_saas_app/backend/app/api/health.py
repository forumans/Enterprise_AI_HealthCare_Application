"""Health check endpoints for Lambda and local development monitoring."""

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from ..core.database import get_engine
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health", tags=["health"])
async def health_check():
    """
    Basic health check endpoint.
    Returns service health and database connectivity status.
    """
    try:
        # Test database connection
        async with get_engine().begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "service": "healthcare-backend",
            "database": "connected",
            "version": "1.0.0"
        }
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "healthcare-backend",
                "database": "disconnected",
                "error": "Database connection failed",
            },
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "healthcare-backend",
                "database": "unknown",
                "error": "Service unavailable",
            },
        )

@router.get("/health/ready", tags=["health"])
async def readiness_check():
    """
    Detailed readiness check — verifies all critical dependencies.
    """
    checks = {
        "database": False,
        "api": True
    }
    
    try:
        # Database check
        async with get_engine().begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            if result.scalar():
                checks["database"] = True
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
    
    all_healthy = all(checks.values())
    
    response_payload = {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "service": "healthcare-backend",
    }
    if all_healthy:
        return response_payload
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=response_payload)

@router.get("/health/live", tags=["health"])
async def liveness_check():
    """
    Liveness check — confirms the process is running and responsive.
    """
    return {
        "status": "alive",
        "service": "healthcare-backend",
        "timestamp": datetime.now(UTC).isoformat(),
    }
