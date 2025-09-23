"""
Logging middleware for request/response tracking
"""
import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from ..core.logging import audit_logger

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Extract request info
        request_info = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": request.client.host,
        }
        
        # Log request start
        logger.info("Request started", **request_info)
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        response_info = {
            "status_code": response.status_code,
            "process_time": process_time,
            "response_headers": dict(response.headers)
        }
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = "error"
        elif response.status_code >= 400:
            log_level = "warning"
        else:
            log_level = "info"
        
        getattr(logger, log_level)(
            "Request completed",
            **request_info,
            **response_info
        )
        
        # Log security events for sensitive endpoints
        if any(path in request.url.path for path in ["/auth/", "/users/", "/admin/"]):
            audit_logger.log_user_action(
                user_id=getattr(request.state, "user_id", None),
                action=request.method.lower(),
                resource=request.url.path,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent", ""),
                details={
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            )
        
        return response
