"""
Security middleware for headers and request validation
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from ..core.config import SECURITY_HEADERS
from ..core.logging import request_logger

logger = structlog.get_logger()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware to add headers and validate requests"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Add CORS headers if needed
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-OTP-Code"
        
        # Calculate response time
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log request
        request_logger.log_request(
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            duration=process_time,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", "")
        )
        
        return response
