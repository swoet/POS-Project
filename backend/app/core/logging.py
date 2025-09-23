"""
Structured logging configuration with security and performance monitoring
"""
import sys
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
import structlog
from structlog.stdlib import LoggerFactory
from pythonjsonlogger import jsonlogger

from .config import get_settings

settings = get_settings()


class SecurityLogProcessor:
    """Process security-related log events"""
    
    def __call__(self, logger, method_name, event_dict):
        # Add security context
        if any(keyword in str(event_dict) for keyword in ['login', 'auth', 'token', 'password']):
            event_dict['security_event'] = True
            
        # Sanitize sensitive data
        if 'password' in event_dict:
            event_dict['password'] = '[REDACTED]'
        if 'token' in event_dict:
            event_dict['token'] = '[REDACTED]'
            
        return event_dict


class PerformanceLogProcessor:
    """Process performance-related log events"""
    
    def __call__(self, logger, method_name, event_dict):
        # Add performance context
        if 'duration' in event_dict or 'response_time' in event_dict:
            event_dict['performance_event'] = True
            
        return event_dict


def setup_logging():
    """Configure structured logging"""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            SecurityLogProcessor(),
            PerformanceLogProcessor(),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class AuditLogger:
    """Centralized audit logging"""
    
    def __init__(self):
        self.logger = structlog.get_logger("audit")
    
    def log_user_action(
        self,
        user_id: Optional[int],
        action: str,
        resource: str,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log user action for audit trail"""
        self.logger.info(
            "User action",
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            audit_event=True
        )
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "INFO"
    ):
        """Log security event"""
        log_method = getattr(self.logger, severity.lower())
        log_method(
            "Security event",
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            security_event=True
        )
    
    def log_performance_event(
        self,
        operation: str,
        duration: float,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log performance event"""
        level = "warning" if duration > 1.0 else "info"
        log_method = getattr(self.logger, level)
        
        log_method(
            "Performance event",
            operation=operation,
            duration=duration,
            details=details,
            performance_event=True
        )


class RequestLogger:
    """HTTP request logging middleware"""
    
    def __init__(self):
        self.logger = structlog.get_logger("requests")
    
    def log_request(
        self,
        method: str,
        url: str,
        status_code: int,
        duration: float,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log HTTP request"""
        level = "warning" if status_code >= 400 else "info"
        log_method = getattr(self.logger, level)
        
        log_method(
            "HTTP request",
            method=method,
            url=url,
            status_code=status_code,
            duration=duration,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_event=True
        )


# Global logger instances
audit_logger = AuditLogger()
request_logger = RequestLogger()


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get configured logger instance"""
    return structlog.get_logger(name)


# Initialize logging
setup_logging()
