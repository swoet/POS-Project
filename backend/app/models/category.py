"""
Category models with hierarchical support
"""
from typing import Optional, List
from sqlmodel import Field, SQLModel
from pydantic import validator

from .base import TimestampMixin, BaseResponse


class Category(SQLModel, TimestampMixin, table=True):
    """Category database model with hierarchical support"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=100, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = Field(default=None, foreign_key="category.id", index=True)
    
    # Display and organization
    display_order: int = Field(default=0)
    color: Optional[str] = Field(default=None, max_length=7)  # Hex color code
    icon: Optional[str] = Field(default=None, max_length=50)
    
    # Status
    is_active: bool = Field(default=True)
    
    # Metadata
    image_url: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        table = True


class CategoryCreate(SQLModel):
    """Category creation model"""
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = None
    display_order: int = Field(default=0)
    color: Optional[str] = Field(default=None, max_length=7)
    icon: Optional[str] = Field(default=None, max_length=50)
    image_url: Optional[str] = Field(default=None, max_length=500)
    
    @validator('color')
    def validate_color(cls, v):
        """Validate hex color format"""
        if v and not (v.startswith('#') and len(v) == 7):
            raise ValueError('Color must be in hex format (#RRGGBB)')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        """Validate category name"""
        return v.strip().title()


class CategoryUpdate(SQLModel):
    """Category update model"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = None
    display_order: Optional[int] = None
    color: Optional[str] = Field(default=None, max_length=7)
    icon: Optional[str] = Field(default=None, max_length=50)
    is_active: Optional[bool] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    
    @validator('color')
    def validate_color(cls, v):
        if v and not (v.startswith('#') and len(v) == 7):
            raise ValueError('Color must be in hex format (#RRGGBB)')
        return v


class CategoryResponse(BaseResponse):
    """Category response model"""
    name: str
    description: Optional[str]
    parent_id: Optional[int]
    display_order: int
    color: Optional[str]
    icon: Optional[str]
    is_active: bool
    image_url: Optional[str]
    
    # Computed fields
    product_count: int = 0
    children: List['CategoryResponse'] = []
    parent_name: Optional[str] = None


class CategoryTree(SQLModel):
    """Category tree structure"""
    id: int
    name: str
    children: List['CategoryTree'] = []
    product_count: int = 0
