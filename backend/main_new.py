"""
Enhanced POS System API with modular architecture and advanced security
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from app.core.config import get_settings
from app.core.database import create_db_and_tables, db_manager
from app.core.cache import setup_fastapi_cache, cache_manager
from app.core.logging import setup_logging
from app.middleware import SecurityMiddleware, LoggingMiddleware, setup_cors
from app.api.v1 import api_router

# Initialize logging
setup_logging()
logger = structlog.get_logger()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting POS System API", version=settings.app_version)
    
    try:
        # Initialize database
        create_db_and_tables()
        logger.info("Database initialized successfully")
        
        # Initialize cache
        setup_fastapi_cache()
        if cache_manager.health_check():
            logger.info("Redis cache connected successfully")
        else:
            logger.warning("Redis cache connection failed")
        
        # Check database connection
        if db_manager.check_connection():
            logger.info("Database connection verified")
        else:
            logger.error("Database connection failed")
            raise Exception("Database connection failed")
        
        logger.info("Application startup completed successfully")
        
    except Exception as e:
        logger.error("Application startup failed", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down POS System API")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enhanced Point of Sale System API with enterprise-grade security and performance",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "authentication",
            "description": "Authentication and authorization operations"
        },
        {
            "name": "users",
            "description": "User management operations"
        },
        {
            "name": "products",
            "description": "Product catalog management"
        },
        {
            "name": "categories",
            "description": "Product category management"
        },
        {
            "name": "sales",
            "description": "Sales transaction operations"
        },
        {
            "name": "inventory",
            "description": "Inventory management and tracking"
        },
        {
            "name": "reports",
            "description": "Analytics and reporting"
        },
        {
            "name": "monitoring",
            "description": "System health and monitoring"
        }
    ]
)

# Setup CORS
setup_cors(app)

# Add middleware
app.add_middleware(SecurityMiddleware)
app.add_middleware(LoggingMiddleware)

# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(
        "Validation error",
        url=str(request.url),
        errors=exc.errors(),
        body=exc.body
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "type": "validation_error"
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    logger.warning(
        "HTTP exception",
        url=str(request.url),
        status_code=exc.status_code,
        detail=exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "type": "http_error",
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(
        "Unhandled exception",
        url=str(request.url),
        error=str(exc),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error"
        }
    )


# Health check endpoints
@app.get("/health", tags=["monitoring"])
async def health_check():
    """Application health check"""
    health_status = {
        "status": "healthy",
        "version": settings.app_version,
        "timestamp": "2025-09-23T13:48:59+02:00",
        "services": {
            "database": db_manager.check_connection(),
            "cache": cache_manager.health_check(),
        }
    }
    
    # Check if all services are healthy
    all_healthy = all(health_status["services"].values())
    if not all_healthy:
        health_status["status"] = "degraded"
    
    status_code = 200 if all_healthy else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/health/detailed", tags=["monitoring"])
async def detailed_health_check():
    """Detailed health check with metrics"""
    try:
        db_info = db_manager.get_connection_info()
        cache_stats = cache_manager.get_stats()
        
        return {
            "status": "healthy",
            "version": settings.app_version,
            "timestamp": "2025-09-23T13:48:59+02:00",
            "database": {
                "connected": db_manager.check_connection(),
                "pool_info": db_info
            },
            "cache": {
                "connected": cache_manager.health_check(),
                "stats": cache_stats
            },
            "system": {
                "debug_mode": settings.debug,
                "log_level": settings.log_level
            }
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": "Health check failed"
            },
            status_code=503
        )


@app.get("/", tags=["monitoring"])
async def root():
    """Root endpoint"""
    return {
        "message": "POS System API",
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main_new:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )
