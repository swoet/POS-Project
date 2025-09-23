"""
Inventory management endpoints with stock tracking
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
from ....models.inventory import (
    InventoryMovement, InventoryAdjustment, InventoryAlert,
    InventoryMovementCreate, InventoryAdjustmentCreate, InventoryAlertResponse,
    MovementType, AlertType
)
from ....models.product import Product
from ....models.user import User
from ....api.dependencies import (
    get_current_active_user, require_manager_or_admin, get_pagination, 
    PaginationParams, get_request_info
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/movements", response_model=List[dict])
async def get_inventory_movements(
    pagination: PaginationParams = Depends(get_pagination),
    product_id: Optional[int] = None,
    movement_type: Optional[MovementType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get inventory movements with filtering"""
    
    # Build query
    query = select(InventoryMovement, Product.name.label("product_name"), Product.sku)
    query = query.join(Product, InventoryMovement.product_id == Product.id)
    
    conditions = []
    
    if product_id:
        conditions.append(InventoryMovement.product_id == product_id)
    
    if movement_type:
        conditions.append(InventoryMovement.movement_type == movement_type)
    
    if start_date:
        conditions.append(InventoryMovement.created_at >= datetime.combine(start_date, datetime.min.time()))
    
    if end_date:
        conditions.append(InventoryMovement.created_at <= datetime.combine(end_date, datetime.max.time()))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Order by creation date descending
    query = query.order_by(desc(InventoryMovement.created_at))
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    results = db.exec(query).all()
    
    # Build response
    movements = []
    for movement, product_name, sku in results:
        # Get creator name
        creator = db.get(User, movement.created_by) if movement.created_by else None
        creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else "System"
        
        movements.append({
            "id": movement.id,
            "product_id": movement.product_id,
            "product_name": product_name,
            "product_sku": sku,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "reference_id": movement.reference_id,
            "reference_type": movement.reference_type,
            "notes": movement.notes,
            "created_by": movement.created_by,
            "creator_name": creator_name,
            "created_at": movement.created_at
        })
    
    return movements


@router.post("/movements")
async def create_inventory_movement(
    movement_data: InventoryMovementCreate,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Create inventory movement (manual adjustment)"""
    
    request_info = await get_request_info(request)
    
    # Get product
    product = db.get(Product, movement_data.product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Create movement
    db_movement = InventoryMovement(
        **movement_data.dict(),
        created_by=current_user.id
    )
    db.add(db_movement)
    
    # Update product stock if it's an adjustment
    if movement_data.movement_type == MovementType.ADJUSTMENT:
        if product.track_inventory:
            product.stock_quantity += movement_data.quantity
            if product.stock_quantity < 0:
                product.stock_quantity = 0
            db.add(product)
    
    db.commit()
    db.refresh(db_movement)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="create",
        resource="inventory_movement",
        resource_id=db_movement.id,
        details={
            "product_id": movement_data.product_id,
            "product_name": product.name,
            "movement_type": movement_data.movement_type,
            "quantity": movement_data.quantity,
            "new_stock": product.stock_quantity if product.track_inventory else None
        },
        **request_info
    )
    
    # Invalidate product cache
    await cache_manager.delete(CacheKeys.product(movement_data.product_id))
    
    return {"message": "Inventory movement created successfully", "id": db_movement.id}


@router.get("/adjustments", response_model=List[dict])
async def get_inventory_adjustments(
    pagination: PaginationParams = Depends(get_pagination),
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get inventory adjustments with filtering"""
    
    # Build query
    query = select(InventoryAdjustment, Product.name.label("product_name"), Product.sku)
    query = query.join(Product, InventoryAdjustment.product_id == Product.id)
    
    conditions = []
    
    if product_id:
        conditions.append(InventoryAdjustment.product_id == product_id)
    
    if start_date:
        conditions.append(InventoryAdjustment.created_at >= datetime.combine(start_date, datetime.min.time()))
    
    if end_date:
        conditions.append(InventoryAdjustment.created_at <= datetime.combine(end_date, datetime.max.time()))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Order by creation date descending
    query = query.order_by(desc(InventoryAdjustment.created_at))
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    results = db.exec(query).all()
    
    # Build response
    adjustments = []
    for adjustment, product_name, sku in results:
        # Get creator name
        creator = db.get(User, adjustment.created_by) if adjustment.created_by else None
        creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else "System"
        
        adjustments.append({
            "id": adjustment.id,
            "product_id": adjustment.product_id,
            "product_name": product_name,
            "product_sku": sku,
            "old_quantity": adjustment.old_quantity,
            "new_quantity": adjustment.new_quantity,
            "adjustment_quantity": adjustment.adjustment_quantity,
            "reason": adjustment.reason,
            "notes": adjustment.notes,
            "created_by": adjustment.created_by,
            "creator_name": creator_name,
            "created_at": adjustment.created_at
        })
    
    return adjustments


@router.post("/adjustments")
async def create_inventory_adjustment(
    adjustment_data: InventoryAdjustmentCreate,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Create inventory adjustment"""
    
    request_info = await get_request_info(request)
    
    # Get product
    product = db.get(Product, adjustment_data.product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    if not product.track_inventory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product does not track inventory"
        )
    
    # Calculate adjustment
    old_quantity = product.stock_quantity
    new_quantity = adjustment_data.new_quantity
    adjustment_quantity = new_quantity - old_quantity
    
    # Create adjustment record
    db_adjustment = InventoryAdjustment(
        product_id=adjustment_data.product_id,
        old_quantity=old_quantity,
        new_quantity=new_quantity,
        adjustment_quantity=adjustment_quantity,
        reason=adjustment_data.reason,
        notes=adjustment_data.notes,
        created_by=current_user.id
    )
    db.add(db_adjustment)
    
    # Update product stock
    product.stock_quantity = new_quantity
    db.add(product)
    
    # Create corresponding inventory movement
    movement = InventoryMovement(
        product_id=adjustment_data.product_id,
        movement_type=MovementType.ADJUSTMENT,
        quantity=adjustment_quantity,
        reference_id=str(db_adjustment.id),
        reference_type="adjustment",
        notes=f"Stock adjustment: {adjustment_data.reason}",
        created_by=current_user.id
    )
    db.add(movement)
    
    db.commit()
    db.refresh(db_adjustment)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="create",
        resource="inventory_adjustment",
        resource_id=db_adjustment.id,
        details={
            "product_id": adjustment_data.product_id,
            "product_name": product.name,
            "old_quantity": old_quantity,
            "new_quantity": new_quantity,
            "adjustment_quantity": adjustment_quantity,
            "reason": adjustment_data.reason
        },
        **request_info
    )
    
    # Invalidate product cache
    await cache_manager.delete(CacheKeys.product(adjustment_data.product_id))
    
    return {"message": "Inventory adjustment created successfully", "id": db_adjustment.id}


@router.get("/alerts", response_model=List[InventoryAlertResponse])
async def get_inventory_alerts(
    pagination: PaginationParams = Depends(get_pagination),
    alert_type: Optional[AlertType] = None,
    resolved: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get inventory alerts"""
    
    # Build query
    query = select(InventoryAlert, Product.name.label("product_name"), Product.sku)
    query = query.join(Product, InventoryAlert.product_id == Product.id)
    
    conditions = []
    
    if alert_type:
        conditions.append(InventoryAlert.alert_type == alert_type)
    
    if resolved is not None:
        conditions.append(InventoryAlert.resolved == resolved)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Order by creation date descending
    query = query.order_by(desc(InventoryAlert.created_at))
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    results = db.exec(query).all()
    
    # Build response
    alerts = []
    for alert, product_name, sku in results:
        alert_dict = alert.dict()
        alert_dict["product_name"] = product_name
        alert_dict["product_sku"] = sku
        alerts.append(InventoryAlertResponse(**alert_dict))
    
    return alerts


@router.put("/alerts/{alert_id}/resolve")
async def resolve_inventory_alert(
    alert_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Resolve inventory alert"""
    
    request_info = await get_request_info(request)
    
    # Get alert
    alert = db.get(InventoryAlert, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    if alert.resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is already resolved"
        )
    
    # Resolve alert
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = current_user.id
    db.add(alert)
    db.commit()
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="resolve",
        resource="inventory_alert",
        resource_id=alert_id,
        details={"alert_type": alert.alert_type},
        **request_info
    )
    
    return {"message": "Alert resolved successfully"}


@router.get("/stock-levels")
async def get_stock_levels(
    pagination: PaginationParams = Depends(get_pagination),
    low_stock_only: bool = False,
    out_of_stock_only: bool = False,
    category_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current stock levels for all products"""
    
    # Build query
    query = select(Product)
    conditions = [Product.is_active == True, Product.track_inventory == True]
    
    if category_id:
        conditions.append(Product.category_id == category_id)
    
    if low_stock_only:
        conditions.append(Product.stock_quantity <= Product.reorder_level)
    
    if out_of_stock_only:
        conditions.append(Product.stock_quantity <= 0)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Order by stock quantity ascending (lowest first)
    query = query.order_by(Product.stock_quantity)
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    products = db.exec(query).all()
    
    # Build response
    stock_levels = []
    for product in products:
        stock_status = "in_stock"
        if product.stock_quantity <= 0:
            stock_status = "out_of_stock"
        elif product.stock_quantity <= product.reorder_level:
            stock_status = "low_stock"
        
        stock_levels.append({
            "product_id": product.id,
            "name": product.name,
            "sku": product.sku,
            "current_stock": product.stock_quantity,
            "reorder_level": product.reorder_level,
            "max_stock": product.max_stock,
            "stock_status": stock_status,
            "days_of_stock": None,  # Could calculate based on average daily sales
            "last_restocked": None  # Could get from last positive inventory movement
        })
    
    return stock_levels


@router.post("/check-alerts")
async def check_inventory_alerts(
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Check and create inventory alerts for low stock and out of stock items"""
    
    # Get products that track inventory
    products = db.exec(
        select(Product).where(
            and_(Product.is_active == True, Product.track_inventory == True)
        )
    ).all()
    
    alerts_created = 0
    
    for product in products:
        alert_type = None
        message = None
        
        # Check for out of stock
        if product.stock_quantity <= 0:
            alert_type = AlertType.OUT_OF_STOCK
            message = f"Product {product.name} is out of stock"
        
        # Check for low stock
        elif product.stock_quantity <= product.reorder_level:
            alert_type = AlertType.LOW_STOCK
            message = f"Product {product.name} is low on stock (Current: {product.stock_quantity}, Reorder Level: {product.reorder_level})"
        
        if alert_type:
            # Check if alert already exists and is unresolved
            existing_alert = db.exec(
                select(InventoryAlert).where(
                    and_(
                        InventoryAlert.product_id == product.id,
                        InventoryAlert.alert_type == alert_type,
                        InventoryAlert.resolved == False
                    )
                )
            ).first()
            
            if not existing_alert:
                # Create new alert
                alert = InventoryAlert(
                    product_id=product.id,
                    alert_type=alert_type,
                    message=message,
                    threshold_value=product.reorder_level if alert_type == AlertType.LOW_STOCK else 0,
                    current_value=product.stock_quantity
                )
                db.add(alert)
                alerts_created += 1
    
    db.commit()
    
    return {
        "message": f"Inventory alerts check completed. {alerts_created} new alerts created.",
        "alerts_created": alerts_created
    }
