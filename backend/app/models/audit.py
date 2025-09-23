"""
Audit logging models for security and compliance tracking
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from enum import Enum

from .base import TimestampMixin


class AuditAction(str, Enum):
    """Audit action types"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    PASSWORD_CHANGE = "password_change"
    PERMISSION_CHANGE = "permission_change"
    EXPORT = "export"
    IMPORT = "import"
    BACKUP = "backup"
    RESTORE = "restore"


class AuditLog(SQLModel, TimestampMixin, table=True):
    """Comprehensive audit log for security and compliance"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # User and session info
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    session_id: Optional[str] = Field(default=None, max_length=100)
    
    # Action details
    action: AuditAction = Field(index=True)
    resource: str = Field(max_length=100, index=True)
    resource_id: Optional[int] = Field(default=None, index=True)
    
    # Request details
    ip_address: Optional[str] = Field(default=None, max_length=45)  # IPv6 support
    user_agent: Optional[str] = Field(default=None, max_length=500)
    endpoint: Optional[str] = Field(default=None, max_length=200)
    method: Optional[str] = Field(default=None, max_length=10)
    
    # Change tracking
    old_values: Optional[str] = Field(default=None)  # JSON string
    new_values: Optional[str] = Field(default=None)  # JSON string
    
    # Additional context
    details: Optional[str] = Field(default=None, max_length=1000)
    severity: str = Field(default="info", max_length=20)  # info, warning, error, critical
    
    # Status
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        table = True


class SecurityEvent(SQLModel, TimestampMixin, table=True):
    """Security-specific events requiring special attention"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Event details
    event_type: str = Field(max_length=100, index=True)
    severity: str = Field(max_length=20, index=True)  # low, medium, high, critical
    
    # User and source
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    
    # Event data
    description: str = Field(max_length=1000)
    additional_data: Optional[str] = Field(default=None)  # JSON string
    
    # Response tracking
    is_resolved: bool = Field(default=False)
    resolved_by: Optional[int] = Field(default=None, foreign_key="user.id")
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = Field(default=None, max_length=1000)
    
    class Config:
        table = True
