"""
POS System Backend - Modular FastAPI Application
Enhanced with security, caching, logging, and monitoring
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.logging import configure_logging, audit_logger
from app.core.cache import cache_manager
from app.middleware import setup_middleware
from app.api import api_router

# Configure logging
configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting POS Backend application")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")
        
        # Initialize cache
        await cache_manager.initialize()
        logger.info("Cache initialized successfully")
        
        # Log startup completion
        audit_logger.log_system_event(
            "application_startup",
            details={"version": "1.0.0", "environment": settings.ENVIRONMENT}
        )
        
        yield
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise
    finally:
        # Shutdown
        logger.info("Shutting down POS Backend application")
        
        try:
            # Close database connections
            await close_db()
            logger.info("Database connections closed")
            
            # Close cache connections
            await cache_manager.close()
            logger.info("Cache connections closed")
            
            # Log shutdown completion
            audit_logger.log_system_event("application_shutdown")
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title="POS System Backend",
    description="Modern Point of Sale System with Enhanced Security",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)

# Setup middleware
setup_middleware(app)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with logging"""
    logger.warning(
        "HTTP exception occurred",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "Unexpected error occurred",
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True
    )
    
    # Log security event for unexpected errors
    audit_logger.log_security_event(
        "unexpected_error",
        details={
            "error": str(exc),
            "path": request.url.path,
            "method": request.method
        },
        severity="ERROR",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error" if not settings.DEBUG else str(exc),
            "status_code": 500
        }
    )


# Health check endpoints
@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": structlog.get_logger().info("Health check")}


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with dependency status"""
    try:
        # Check database
        db_status = await init_db.check_connection()
        
        # Check cache
        cache_status = await cache_manager.health_check()
        
        return {
            "status": "healthy",
            "services": {
                "database": "healthy" if db_status else "unhealthy",
                "cache": "healthy" if cache_status else "unhealthy"
            },
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e) if settings.DEBUG else "Service unavailable"
            }
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_config=None  # Use our custom logging
    )
