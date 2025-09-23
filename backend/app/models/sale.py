"""
Sale models with comprehensive transaction tracking
"""
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from sqlmodel import Field, SQLModel
from pydantic import validator
from enum import Enum

from .base import TimestampMixin, BaseResponse


class PaymentMethod(str, Enum):
    """Payment method enumeration"""
    CASH = "cash"
    CARD = "card"
    DIGITAL = "digital"
    CREDIT = "credit"
    GIFT_CARD = "gift_card"


class SaleStatus(str, Enum):
    """Sale status enumeration"""
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class SaleItem(SQLModel):
    """Individual sale item model"""
    product_id: int
    name: str = Field(max_length=200)
    barcode: Optional[str] = None
    price: Decimal = Field(decimal_places=2, ge=0)
    quantity: int = Field(ge=1)
    discount: Decimal = Field(default=0, decimal_places=2, ge=0)
    tax_rate: Decimal = Field(default=0, decimal_places=4, ge=0, le=1)
    total: Decimal = Field(decimal_places=2, ge=0)
    
    @validator('total')
    def calculate_total(cls, v, values):
        """Calculate item total"""
        price = values.get('price', 0)
        quantity = values.get('quantity', 1)
        discount = values.get('discount', 0)
        tax_rate = values.get('tax_rate', 0)
        
        subtotal = (price * quantity) - discount
        tax = subtotal * tax_rate
        return subtotal + tax


class Sale(SQLModel, TimestampMixin, table=True):
    """Sale database model"""
    id: Optional[int] = Field(default=None, primary_key=True)
    receipt_number: str = Field(unique=True, index=True, max_length=50)
    user_id: int = Field(foreign_key="user.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id", index=True)
    
    # Sale details
    items_json: str = Field()  # JSON string of SaleItem list
    subtotal: Decimal = Field(decimal_places=2, ge=0)
    tax_amount: Decimal = Field(decimal_places=2, ge=0)
    discount_amount: Decimal = Field(default=0, decimal_places=2, ge=0)
    total_amount: Decimal = Field(decimal_places=2, ge=0)
    
    # Payment
    payment_method: PaymentMethod = Field(default=PaymentMethod.CASH)
    amount_paid: Decimal = Field(decimal_places=2, ge=0)
    change_given: Decimal = Field(default=0, decimal_places=2, ge=0)
    
    # Status and metadata
    status: SaleStatus = Field(default=SaleStatus.COMPLETED)
    notes: Optional[str] = Field(default=None, max_length=1000)
    
    # Sync and audit
    synced: bool = Field(default=True)
    pos_terminal_id: Optional[str] = Field(default=None, max_length=50)
    
    # Refund tracking
    refunded_amount: Decimal = Field(default=0, decimal_places=2, ge=0)
    refund_reason: Optional[str] = Field(default=None, max_length=500)
    refunded_at: Optional[datetime] = None
    refunded_by: Optional[int] = Field(default=None, foreign_key="user.id")
    
    class Config:
        table = True


class SaleCreate(SQLModel):
    """Sale creation model"""
    items: List[SaleItem]
    customer_id: Optional[int] = None
    payment_method: PaymentMethod = PaymentMethod.CASH
    amount_paid: Decimal = Field(decimal_places=2, ge=0)
    discount_amount: Decimal = Field(default=0, decimal_places=2, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    pos_terminal_id: Optional[str] = Field(default=None, max_length=50)
    
    @validator('items')
    def validate_items(cls, v):
        """Validate sale items"""
        if not v:
            raise ValueError('Sale must have at least one item')
        return v
    
    @validator('amount_paid')
    def validate_payment(cls, v, values):
        """Validate payment amount"""
        items = values.get('items', [])
        discount = values.get('discount_amount', 0)
        
        if items:
            total = sum(item.total for item in items) - discount
            if v < total:
                raise ValueError('Amount paid must be greater than or equal to total')
        
        return v


class SaleUpdate(SQLModel):
    """Sale update model"""
    status: Optional[SaleStatus] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    customer_id: Optional[int] = None


class SaleResponse(BaseResponse):
    """Sale response model"""
    receipt_number: str
    user_id: int
    customer_id: Optional[int]
    items: List[SaleItem]
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    payment_method: PaymentMethod
    amount_paid: Decimal
    change_given: Decimal
    status: SaleStatus
    notes: Optional[str]
    synced: bool
    pos_terminal_id: Optional[str]
    refunded_amount: Decimal
    refund_reason: Optional[str]
    refunded_at: Optional[datetime]
    
    # Computed fields
    user_name: Optional[str] = None
    customer_name: Optional[str] = None
    item_count: int = 0


class SaleRefund(SQLModel):
    """Sale refund model"""
    refund_amount: Decimal = Field(decimal_places=2, gt=0)
    reason: str = Field(min_length=1, max_length=500)
    items_to_refund: Optional[List[int]] = None  # Product IDs to refund


class SalesReport(SQLModel):
    """Sales report model"""
    start_date: datetime
    end_date: datetime
    total_sales: Decimal
    total_transactions: int
    average_transaction: Decimal
    payment_methods: dict
    top_products: List[dict]
    hourly_breakdown: List[dict]
    daily_breakdown: List[dict]


class SaleSearch(SQLModel):
    """Sale search parameters"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_id: Optional[int] = None
    customer_id: Optional[int] = None
    payment_method: Optional[PaymentMethod] = None
    status: Optional[SaleStatus] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    receipt_number: Optional[str] = None
