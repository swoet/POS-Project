"""
Product models with enhanced validation and inventory tracking
"""
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from sqlmodel import Field, SQLModel
from pydantic import validator

from .base import TimestampMixin, BaseResponse


class Product(SQLModel, TimestampMixin, table=True):
    """Product database model"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=200, index=True)
    barcode: Optional[str] = Field(default=None, unique=True, index=True, max_length=50)
    sku: Optional[str] = Field(default=None, unique=True, index=True, max_length=50)
    category_id: Optional[int] = Field(default=None, foreign_key="category.id", index=True)
    
    # Pricing
    price: Decimal = Field(decimal_places=2, ge=0)
    cost: Decimal = Field(decimal_places=2, ge=0)
    discount_percentage: Optional[Decimal] = Field(default=None, decimal_places=2, ge=0, le=100)
    
    # Inventory
    stock_quantity: int = Field(default=0, ge=0)
    min_stock: int = Field(default=0, ge=0)
    max_stock: Optional[int] = Field(default=None, ge=0)
    reorder_point: Optional[int] = Field(default=None, ge=0)
    
    # Product details
    description: Optional[str] = Field(default=None, max_length=1000)
    unit: str = Field(default="piece", max_length=20)  # piece, kg, liter, etc.
    weight: Optional[Decimal] = Field(default=None, decimal_places=3, ge=0)
    dimensions: Optional[str] = Field(default=None, max_length=100)  # JSON string
    
    # Status and flags
    is_active: bool = Field(default=True)
    is_taxable: bool = Field(default=True)
    is_trackable: bool = Field(default=True)  # Track inventory
    allow_negative_stock: bool = Field(default=False)
    
    # Metadata
    tags: Optional[str] = Field(default=None, max_length=500)  # JSON array as string
    image_url: Optional[str] = Field(default=None, max_length=500)
    supplier_id: Optional[int] = Field(default=None)
    
    class Config:
        table = True


class ProductCreate(SQLModel):
    """Product creation model"""
    name: str = Field(min_length=1, max_length=200)
    barcode: Optional[str] = Field(default=None, max_length=50)
    sku: Optional[str] = Field(default=None, max_length=50)
    category_id: Optional[int] = None
    price: Decimal = Field(decimal_places=2, ge=0)
    cost: Decimal = Field(decimal_places=2, ge=0)
    discount_percentage: Optional[Decimal] = Field(default=None, decimal_places=2, ge=0, le=100)
    stock_quantity: int = Field(default=0, ge=0)
    min_stock: int = Field(default=0, ge=0)
    max_stock: Optional[int] = Field(default=None, ge=0)
    reorder_point: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, max_length=1000)
    unit: str = Field(default="piece", max_length=20)
    weight: Optional[Decimal] = Field(default=None, decimal_places=3, ge=0)
    dimensions: Optional[str] = Field(default=None, max_length=100)
    is_taxable: bool = Field(default=True)
    is_trackable: bool = Field(default=True)
    allow_negative_stock: bool = Field(default=False)
    tags: Optional[List[str]] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    supplier_id: Optional[int] = None
    
    @validator('price')
    def validate_price(cls, v, values):
        """Validate price is greater than cost"""
        cost = values.get('cost', 0)
        if v < cost:
            raise ValueError('Price must be greater than or equal to cost')
        return v
    
    @validator('max_stock')
    def validate_max_stock(cls, v, values):
        """Validate max_stock is greater than min_stock"""
        if v is not None:
            min_stock = values.get('min_stock', 0)
            if v < min_stock:
                raise ValueError('Max stock must be greater than min stock')
        return v
    
    @validator('barcode')
    def validate_barcode(cls, v):
        """Validate barcode format"""
        if v and not v.isalnum():
            raise ValueError('Barcode must contain only alphanumeric characters')
        return v


class ProductUpdate(SQLModel):
    """Product update model"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    barcode: Optional[str] = Field(default=None, max_length=50)
    sku: Optional[str] = Field(default=None, max_length=50)
    category_id: Optional[int] = None
    price: Optional[Decimal] = Field(default=None, decimal_places=2, ge=0)
    cost: Optional[Decimal] = Field(default=None, decimal_places=2, ge=0)
    discount_percentage: Optional[Decimal] = Field(default=None, decimal_places=2, ge=0, le=100)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    min_stock: Optional[int] = Field(default=None, ge=0)
    max_stock: Optional[int] = Field(default=None, ge=0)
    reorder_point: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, max_length=1000)
    unit: Optional[str] = Field(default=None, max_length=20)
    weight: Optional[Decimal] = Field(default=None, decimal_places=3, ge=0)
    dimensions: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None
    is_taxable: Optional[bool] = None
    is_trackable: Optional[bool] = None
    allow_negative_stock: Optional[bool] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    supplier_id: Optional[int] = None


class ProductResponse(BaseResponse):
    """Product response model"""
    name: str
    barcode: Optional[str]
    sku: Optional[str]
    category_id: Optional[int]
    price: Decimal
    cost: Decimal
    discount_percentage: Optional[Decimal]
    stock_quantity: int
    min_stock: int
    max_stock: Optional[int]
    reorder_point: Optional[int]
    description: Optional[str]
    unit: str
    weight: Optional[Decimal]
    dimensions: Optional[str]
    is_active: bool
    is_taxable: bool
    is_trackable: bool
    allow_negative_stock: bool
    tags: Optional[List[str]]
    image_url: Optional[str]
    supplier_id: Optional[int]
    
    # Computed fields
    profit_margin: Optional[Decimal] = None
    is_low_stock: bool = False
    effective_price: Decimal  # Price after discount


class ProductSearch(SQLModel):
    """Product search parameters"""
    query: Optional[str] = None
    category_id: Optional[int] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    in_stock_only: bool = False
    low_stock_only: bool = False
    active_only: bool = True
    tags: Optional[List[str]] = None


class ProductBulkUpdate(SQLModel):
    """Bulk product update model"""
    product_ids: List[int]
    updates: ProductUpdate
