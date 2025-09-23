"""
Sales management endpoints with transaction processing
"""
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlmodel import Session, select, and_, func, desc
import structlog

from ....core.database import get_db
from ....core.logging import audit_logger
from ....core.cache import cache_manager, CacheKeys
from ....models.sale import Sale, SaleItem, SaleCreate, SaleResponse, SaleItemResponse, SaleStatus
from ....models.product import Product
from ....models.user import User
from ....models.inventory import InventoryMovement, MovementType
from ....api.dependencies import (
    get_current_active_user, require_cashier_or_above, get_pagination, 
    PaginationParams, get_request_info
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/", response_model=List[SaleResponse])
async def get_sales(
    pagination: PaginationParams = Depends(get_pagination),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[SaleStatus] = None,
    customer_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get sales with filtering"""
    
    # Build query
    query = select(Sale)
    conditions = []
    
    if start_date:
        conditions.append(Sale.created_at >= datetime.combine(start_date, datetime.min.time()))
    
    if end_date:
        conditions.append(Sale.created_at <= datetime.combine(end_date, datetime.max.time()))
    
    if status:
        conditions.append(Sale.status == status)
    
    if customer_name:
        conditions.append(Sale.customer_name.ilike(f"%{customer_name}%"))
    
    # Non-admin users can only see their own sales
    if current_user.role not in ["admin", "manager"]:
        conditions.append(Sale.cashier_id == current_user.id)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Order by creation date descending
    query = query.order_by(desc(Sale.created_at))
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    sales = db.exec(query).all()
    
    # Build response with items
    response_sales = []
    for sale in sales:
        # Get sale items
        items = db.exec(
            select(SaleItem).where(SaleItem.sale_id == sale.id)
        ).all()
        
        # Get cashier name
        cashier = db.get(User, sale.cashier_id)
        cashier_name = f"{cashier.first_name} {cashier.last_name}".strip() if cashier else "Unknown"
        
        sale_dict = sale.dict()
        sale_dict["cashier_name"] = cashier_name
        sale_dict["items"] = [SaleItemResponse.from_orm(item) for item in items]
        
        response_sales.append(SaleResponse(**sale_dict))
    
    return response_sales


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get single sale by ID"""
    
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found"
        )
    
    # Check permissions
    if current_user.role not in ["admin", "manager"] and sale.cashier_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this sale"
        )
    
    # Get sale items with product details
    items = db.exec(
        select(SaleItem).where(SaleItem.sale_id == sale_id)
    ).all()
    
    # Get cashier name
    cashier = db.get(User, sale.cashier_id)
    cashier_name = f"{cashier.first_name} {cashier.last_name}".strip() if cashier else "Unknown"
    
    # Build response
    sale_dict = sale.dict()
    sale_dict["cashier_name"] = cashier_name
    
    # Add product details to items
    item_responses = []
    for item in items:
        product = db.get(Product, item.product_id)
        item_dict = item.dict()
        item_dict["product_name"] = product.name if product else "Unknown Product"
        item_dict["product_sku"] = product.sku if product else None
        item_responses.append(SaleItemResponse(**item_dict))
    
    sale_dict["items"] = item_responses
    
    return SaleResponse(**sale_dict)


@router.post("/", response_model=SaleResponse)
async def create_sale(
    sale_data: SaleCreate,
    request: Request,
    current_user: User = Depends(require_cashier_or_above),
    db: Session = Depends(get_db)
):
    """Create new sale with inventory updates"""
    
    request_info = await get_request_info(request)
    
    if not sale_data.items or len(sale_data.items) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale must have at least one item"
        )
    
    # Validate products and check inventory
    total_amount = Decimal('0.00')
    validated_items = []
    
    for item in sale_data.items:
        product = db.get(Product, item.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with ID {item.product_id} not found"
            )
        
        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {product.name} is not active"
            )
        
        # Check inventory if tracking is enabled
        if product.track_inventory and product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for {product.name}. Available: {product.stock_quantity}"
            )
        
        # Use current product price if not specified
        unit_price = item.unit_price if item.unit_price else product.price
        line_total = unit_price * item.quantity
        
        validated_items.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "product": product
        })
        
        total_amount += line_total
    
    # Apply discount
    discount_amount = sale_data.discount_amount or Decimal('0.00')
    if discount_amount > total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount amount cannot exceed total amount"
        )
    
    final_amount = total_amount - discount_amount
    
    # Calculate tax
    tax_amount = final_amount * (sale_data.tax_rate or Decimal('0.00')) / 100
    final_total = final_amount + tax_amount
    
    # Create sale
    db_sale = Sale(
        cashier_id=current_user.id,
        customer_name=sale_data.customer_name,
        customer_email=sale_data.customer_email,
        customer_phone=sale_data.customer_phone,
        subtotal=total_amount,
        discount_amount=discount_amount,
        tax_rate=sale_data.tax_rate or Decimal('0.00'),
        tax_amount=tax_amount,
        total_amount=final_total,
        payment_method=sale_data.payment_method,
        notes=sale_data.notes,
        status=SaleStatus.COMPLETED
    )
    
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    
    # Create sale items and update inventory
    for item_data in validated_items:
        # Create sale item
        sale_item = SaleItem(
            sale_id=db_sale.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            line_total=item_data["line_total"]
        )
        db.add(sale_item)
        
        # Update product inventory
        product = item_data["product"]
        if product.track_inventory:
            product.stock_quantity -= item_data["quantity"]
            db.add(product)
            
            # Create inventory movement record
            inventory_movement = InventoryMovement(
                product_id=product.id,
                movement_type=MovementType.SALE,
                quantity=-item_data["quantity"],
                reference_id=str(db_sale.id),
                reference_type="sale",
                notes=f"Sale #{db_sale.id}",
                created_by=current_user.id
            )
            db.add(inventory_movement)
    
    db.commit()
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="create",
        resource="sale",
        resource_id=db_sale.id,
        details={
            "total_amount": float(final_total),
            "items_count": len(validated_items),
            "customer_name": sale_data.customer_name,
            "payment_method": sale_data.payment_method
        },
        **request_info
    )
    
    # Invalidate product caches for updated inventory
    for item_data in validated_items:
        if item_data["product"].track_inventory:
            await cache_manager.delete(CacheKeys.product(item_data["product_id"]))
    
    # Build response
    return await get_sale(db_sale.id, current_user, db)


@router.put("/{sale_id}/void")
async def void_sale(
    sale_id: int,
    request: Request,
    current_user: User = Depends(require_cashier_or_above),
    db: Session = Depends(get_db)
):
    """Void a sale and restore inventory"""
    
    request_info = await get_request_info(request)
    
    # Get sale
    sale = db.get(Sale, sale_id)
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found"
        )
    
    # Check permissions
    if current_user.role not in ["admin", "manager"] and sale.cashier_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to void this sale"
        )
    
    if sale.status == SaleStatus.VOIDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale is already voided"
        )
    
    # Get sale items
    items = db.exec(
        select(SaleItem).where(SaleItem.sale_id == sale_id)
    ).all()
    
    # Restore inventory for each item
    for item in items:
        product = db.get(Product, item.product_id)
        if product and product.track_inventory:
            product.stock_quantity += item.quantity
            db.add(product)
            
            # Create inventory movement record
            inventory_movement = InventoryMovement(
                product_id=product.id,
                movement_type=MovementType.ADJUSTMENT,
                quantity=item.quantity,
                reference_id=str(sale_id),
                reference_type="sale_void",
                notes=f"Void sale #{sale_id}",
                created_by=current_user.id
            )
            db.add(inventory_movement)
    
    # Update sale status
    sale.status = SaleStatus.VOIDED
    sale.updated_at = datetime.utcnow()
    db.add(sale)
    db.commit()
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="void",
        resource="sale",
        resource_id=sale_id,
        details={
            "original_total": float(sale.total_amount),
            "items_count": len(items)
        },
        **request_info
    )
    
    # Invalidate product caches
    for item in items:
        product = db.get(Product, item.product_id)
        if product and product.track_inventory:
            await cache_manager.delete(CacheKeys.product(item.product_id))
    
    return {"message": "Sale voided successfully"}


@router.get("/summary/daily")
async def get_daily_sales_summary(
    target_date: Optional[date] = Query(default=None, description="Date to get summary for (defaults to today)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get daily sales summary"""
    
    if not target_date:
        target_date = date.today()
    
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    
    # Base query conditions
    conditions = [
        Sale.created_at >= start_datetime,
        Sale.created_at <= end_datetime,
        Sale.status == SaleStatus.COMPLETED
    ]
    
    # Non-admin users can only see their own sales
    if current_user.role not in ["admin", "manager"]:
        conditions.append(Sale.cashier_id == current_user.id)
    
    # Get sales summary
    sales_query = select(
        func.count(Sale.id).label("total_sales"),
        func.sum(Sale.total_amount).label("total_revenue"),
        func.avg(Sale.total_amount).label("average_sale"),
        func.sum(Sale.tax_amount).label("total_tax")
    ).where(and_(*conditions))
    
    result = db.exec(sales_query).first()
    
    # Get payment method breakdown
    payment_breakdown = db.exec(
        select(
            Sale.payment_method,
            func.count(Sale.id).label("count"),
            func.sum(Sale.total_amount).label("total")
        ).where(and_(*conditions))
        .group_by(Sale.payment_method)
    ).all()
    
    # Get top products sold
    top_products = db.exec(
        select(
            Product.name,
            func.sum(SaleItem.quantity).label("quantity_sold"),
            func.sum(SaleItem.line_total).label("revenue")
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(and_(*conditions))
        .group_by(Product.id, Product.name)
        .order_by(desc(func.sum(SaleItem.quantity)))
        .limit(10)
    ).all()
    
    return {
        "date": target_date,
        "summary": {
            "total_sales": result.total_sales or 0,
            "total_revenue": float(result.total_revenue or 0),
            "average_sale": float(result.average_sale or 0),
            "total_tax": float(result.total_tax or 0)
        },
        "payment_methods": [
            {
                "method": pm.payment_method,
                "count": pm.count,
                "total": float(pm.total)
            }
            for pm in payment_breakdown
        ],
        "top_products": [
            {
                "name": tp.name,
                "quantity_sold": tp.quantity_sold,
                "revenue": float(tp.revenue)
            }
            for tp in top_products
        ]
    }
