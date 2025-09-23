"""
Inventory models for tracking stock movements and adjustments
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from sqlmodel import Field, SQLModel
from enum import Enum

from .base import TimestampMixin, BaseResponse


class InventoryAction(str, Enum):
    """Inventory action types"""
    SALE = "sale"
    PURCHASE = "purchase"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    DAMAGE = "damage"
    THEFT = "theft"
    TRANSFER = "transfer"
    RECOUNT = "recount"


class InventoryLog(SQLModel, TimestampMixin, table=True):
    """Inventory movement log"""
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    
    # Movement details
    action: InventoryAction
    quantity_before: int = Field(ge=0)
    quantity_change: int  # Can be negative
    quantity_after: int = Field(ge=0)
    
    # Cost tracking
    unit_cost: Optional[Decimal] = Field(default=None, decimal_places=2, ge=0)
    total_cost: Optional[Decimal] = Field(default=None, decimal_places=2)
    
    # Reference information
    reference_type: Optional[str] = Field(default=None, max_length=50)  # sale, purchase_order, etc.
    reference_id: Optional[int] = None
    
    # Details
    reason: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)
    
    # Location tracking
    location: Optional[str] = Field(default=None, max_length=100)
    
    class Config:
        table = True


class InventoryAdjustment(SQLModel):
    """Inventory adjustment model"""
    product_id: int
    quantity_change: int
    reason: str = Field(min_length=1, max_length=500)
    unit_cost: Optional[Decimal] = Field(default=None, decimal_places=2, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    location: Optional[str] = Field(default=None, max_length=100)


class BulkInventoryAdjustment(SQLModel):
    """Bulk inventory adjustment model"""
    adjustments: list[InventoryAdjustment]
    reason: str = Field(min_length=1, max_length=500)


class InventoryCount(SQLModel):
    """Physical inventory count model"""
    product_id: int
    counted_quantity: int = Field(ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class InventoryCountSession(SQLModel, TimestampMixin, table=True):
    """Inventory count session tracking"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    location: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default="in_progress", max_length=20)  # in_progress, completed, cancelled
    notes: Optional[str] = Field(default=None, max_length=1000)
    completed_at: Optional[datetime] = None
    
    class Config:
        table = True


class InventoryAlert(SQLModel, TimestampMixin, table=True):
    """Inventory alerts for low stock, etc."""
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    alert_type: str = Field(max_length=50)  # low_stock, out_of_stock, overstock
    message: str = Field(max_length=500)
    is_acknowledged: bool = Field(default=False)
    acknowledged_by: Optional[int] = Field(default=None, foreign_key="user.id")
    acknowledged_at: Optional[datetime] = None
    
    class Config:
        table = True


class InventoryReport(SQLModel):
    """Inventory report model"""
    total_products: int
    total_value: Decimal
    low_stock_items: int
    out_of_stock_items: int
    overstock_items: int
    top_movers: list[dict]
    slow_movers: list[dict]
    category_breakdown: list[dict]
