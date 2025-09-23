"""
Base models and mixins for common functionality
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class TimestampMixin(SQLModel):
    """Mixin for created_at and updated_at timestamps"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)


class BaseResponse(SQLModel):
    """Base response model with common fields"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
