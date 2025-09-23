"""
Reporting endpoints for analytics and business intelligence
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select, and_, func, desc, text
import structlog

from ....core.database import get_db
from ....core.cache import cache_manager
from ....models.sale import Sale, SaleItem, SaleStatus
from ....models.product import Product
from ....models.category import Category
from ....models.user import User
from ....models.inventory import InventoryMovement, MovementType
from ....api.dependencies import get_current_active_user, require_manager_or_admin

logger = structlog.get_logger()
router = APIRouter()


@router.get("/sales/summary")
async def get_sales_summary(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    group_by: str = Query(default="day", regex="^(day|week|month|year)$"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Get sales summary with grouping options"""
    
    # Default to last 30 days if no dates provided
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Build date grouping expression
    date_formats = {
        "day": "DATE(created_at)",
        "week": "DATE_TRUNC('week', created_at)",
        "month": "DATE_TRUNC('month', created_at)",
        "year": "DATE_TRUNC('year', created_at)"
    }
    
    date_group = date_formats.get(group_by, "DATE(created_at)")
    
    # Execute query
    query = text(f"""
        SELECT 
            {date_group} as period,
            COUNT(*) as total_sales,
            SUM(total_amount) as total_revenue,
            AVG(total_amount) as average_sale,
            SUM(tax_amount) as total_tax,
            COUNT(DISTINCT cashier_id) as active_cashiers
        FROM sales 
        WHERE created_at >= :start_date 
            AND created_at <= :end_date 
            AND status = :status
        GROUP BY {date_group}
        ORDER BY period
    """)
    
    results = db.exec(
        query, 
        {
            "start_date": start_datetime,
            "end_date": end_datetime,
            "status": SaleStatus.COMPLETED
        }
    ).all()
    
    return {
        "period": f"{start_date} to {end_date}",
        "group_by": group_by,
        "data": [
            {
                "period": str(row.period),
                "total_sales": row.total_sales,
                "total_revenue": float(row.total_revenue or 0),
                "average_sale": float(row.average_sale or 0),
                "total_tax": float(row.total_tax or 0),
                "active_cashiers": row.active_cashiers
            }
            for row in results
        ]
    }


@router.get("/products/performance")
async def get_product_performance(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=20, le=100),
    sort_by: str = Query(default="revenue", regex="^(revenue|quantity|profit)$"),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Get product performance metrics"""
    
    # Default to last 30 days
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Build query
    query = select(
        Product.id,
        Product.name,
        Product.sku,
        Product.price,
        Product.cost,
        Category.name.label("category_name"),
        func.sum(SaleItem.quantity).label("quantity_sold"),
        func.sum(SaleItem.line_total).label("revenue"),
        func.count(func.distinct(Sale.id)).label("transactions")
    ).select_from(
        SaleItem
        .join(Product, SaleItem.product_id == Product.id)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .outerjoin(Category, Product.category_id == Category.id)
    ).where(
        and_(
            Sale.created_at >= start_datetime,
            Sale.created_at <= end_datetime,
            Sale.status == SaleStatus.COMPLETED
        )
    ).group_by(
        Product.id, Product.name, Product.sku, Product.price, Product.cost, Category.name
    )
    
    # Apply sorting
    if sort_by == "quantity":
        query = query.order_by(desc(func.sum(SaleItem.quantity)))
    elif sort_by == "profit":
        query = query.order_by(desc(func.sum(SaleItem.line_total) - (func.sum(SaleItem.quantity) * Product.cost)))
    else:  # revenue
        query = query.order_by(desc(func.sum(SaleItem.line_total)))
    
    query = query.limit(limit)
    results = db.exec(query).all()
    
    # Build response
    products = []
    for row in results:
        profit = float(row.revenue or 0) - (float(row.quantity_sold or 0) * float(row.cost or 0))
        margin = (profit / float(row.revenue)) * 100 if row.revenue else 0
        
        products.append({
            "product_id": row.id,
            "name": row.name,
            "sku": row.sku,
            "category": row.category_name,
            "price": float(row.price or 0),
            "cost": float(row.cost or 0),
            "quantity_sold": int(row.quantity_sold or 0),
            "revenue": float(row.revenue or 0),
            "profit": profit,
            "margin_percent": round(margin, 2),
            "transactions": int(row.transactions or 0)
        })
    
    return {
        "period": f"{start_date} to {end_date}",
        "sort_by": sort_by,
        "products": products
    }


@router.get("/categories/performance")
async def get_category_performance(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Get category performance metrics"""
    
    # Default to last 30 days
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get category performance
    query = select(
        Category.id,
        Category.name,
        func.sum(SaleItem.quantity).label("quantity_sold"),
        func.sum(SaleItem.line_total).label("revenue"),
        func.count(func.distinct(Product.id)).label("products_sold"),
        func.count(func.distinct(Sale.id)).label("transactions")
    ).select_from(
        SaleItem
        .join(Product, SaleItem.product_id == Product.id)
        .join(Category, Product.category_id == Category.id)
        .join(Sale, SaleItem.sale_id == Sale.id)
    ).where(
        and_(
            Sale.created_at >= start_datetime,
            Sale.created_at <= end_datetime,
            Sale.status == SaleStatus.COMPLETED
        )
    ).group_by(
        Category.id, Category.name
    ).order_by(desc(func.sum(SaleItem.line_total)))
    
    results = db.exec(query).all()
    
    # Calculate totals for percentages
    total_revenue = sum(float(row.revenue or 0) for row in results)
    total_quantity = sum(int(row.quantity_sold or 0) for row in results)
    
    # Build response
    categories = []
    for row in results:
        revenue = float(row.revenue or 0)
        quantity = int(row.quantity_sold or 0)
        
        categories.append({
            "category_id": row.id,
            "name": row.name,
            "quantity_sold": quantity,
            "revenue": revenue,
            "revenue_percent": round((revenue / total_revenue) * 100, 2) if total_revenue else 0,
            "quantity_percent": round((quantity / total_quantity) * 100, 2) if total_quantity else 0,
            "products_sold": int(row.products_sold or 0),
            "transactions": int(row.transactions or 0),
            "average_transaction": round(revenue / int(row.transactions), 2) if row.transactions else 0
        })
    
    return {
        "period": f"{start_date} to {end_date}",
        "total_revenue": total_revenue,
        "total_quantity": total_quantity,
        "categories": categories
    }


@router.get("/cashiers/performance")
async def get_cashier_performance(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Get cashier performance metrics"""
    
    # Default to last 30 days
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get cashier performance
    query = select(
        User.id,
        User.username,
        User.first_name,
        User.last_name,
        func.count(Sale.id).label("total_sales"),
        func.sum(Sale.total_amount).label("total_revenue"),
        func.avg(Sale.total_amount).label("average_sale"),
        func.sum(Sale.tax_amount).label("total_tax")
    ).select_from(
        Sale.join(User, Sale.cashier_id == User.id)
    ).where(
        and_(
            Sale.created_at >= start_datetime,
            Sale.created_at <= end_datetime,
            Sale.status == SaleStatus.COMPLETED
        )
    ).group_by(
        User.id, User.username, User.first_name, User.last_name
    ).order_by(desc(func.sum(Sale.total_amount)))
    
    results = db.exec(query).all()
    
    # Calculate totals
    total_revenue = sum(float(row.total_revenue or 0) for row in results)
    total_sales = sum(int(row.total_sales or 0) for row in results)
    
    # Build response
    cashiers = []
    for row in results:
        revenue = float(row.total_revenue or 0)
        sales = int(row.total_sales or 0)
        full_name = f"{row.first_name} {row.last_name}".strip()
        
        cashiers.append({
            "cashier_id": row.id,
            "username": row.username,
            "full_name": full_name or row.username,
            "total_sales": sales,
            "total_revenue": revenue,
            "average_sale": float(row.average_sale or 0),
            "total_tax": float(row.total_tax or 0),
            "revenue_percent": round((revenue / total_revenue) * 100, 2) if total_revenue else 0,
            "sales_percent": round((sales / total_sales) * 100, 2) if total_sales else 0
        })
    
    return {
        "period": f"{start_date} to {end_date}",
        "total_revenue": total_revenue,
        "total_sales": total_sales,
        "cashiers": cashiers
    }


@router.get("/inventory/movements")
async def get_inventory_movement_report(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    movement_type: Optional[MovementType] = None,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Get inventory movement report"""
    
    # Default to last 30 days
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Build query
    query = select(
        InventoryMovement.movement_type,
        func.count(InventoryMovement.id).label("movement_count"),
        func.sum(func.abs(InventoryMovement.quantity)).label("total_quantity"),
        func.count(func.distinct(InventoryMovement.product_id)).label("products_affected")
    ).where(
        and_(
            InventoryMovement.created_at >= start_datetime,
            InventoryMovement.created_at <= end_datetime
        )
    )
    
    if movement_type:
        query = query.where(InventoryMovement.movement_type == movement_type)
    
    query = query.group_by(InventoryMovement.movement_type)
    results = db.exec(query).all()
    
    # Get top products with most movements
    top_products_query = select(
        Product.name,
        Product.sku,
        func.count(InventoryMovement.id).label("movement_count"),
        func.sum(func.abs(InventoryMovement.quantity)).label("total_quantity")
    ).select_from(
        InventoryMovement.join(Product, InventoryMovement.product_id == Product.id)
    ).where(
        and_(
            InventoryMovement.created_at >= start_datetime,
            InventoryMovement.created_at <= end_datetime
        )
    ).group_by(
        Product.id, Product.name, Product.sku
    ).order_by(desc(func.count(InventoryMovement.id))).limit(10)
    
    top_products = db.exec(top_products_query).all()
    
    return {
        "period": f"{start_date} to {end_date}",
        "movement_summary": [
            {
                "movement_type": row.movement_type,
                "movement_count": int(row.movement_count or 0),
                "total_quantity": int(row.total_quantity or 0),
                "products_affected": int(row.products_affected or 0)
            }
            for row in results
        ],
        "top_products": [
            {
                "name": row.name,
                "sku": row.sku,
                "movement_count": int(row.movement_count or 0),
                "total_quantity": int(row.total_quantity or 0)
            }
            for row in top_products
        ]
    }


@router.get("/dashboard")
async def get_dashboard_metrics(
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Get key metrics for dashboard"""
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    yesterday_start = datetime.combine(yesterday, datetime.min.time())
    yesterday_end = datetime.combine(yesterday, datetime.max.time())
    
    # Today's sales
    today_sales = db.exec(
        select(
            func.count(Sale.id).label("count"),
            func.sum(Sale.total_amount).label("revenue")
        ).where(
            and_(
                Sale.created_at >= today_start,
                Sale.created_at <= today_end,
                Sale.status == SaleStatus.COMPLETED
            )
        )
    ).first()
    
    # Yesterday's sales for comparison
    yesterday_sales = db.exec(
        select(
            func.count(Sale.id).label("count"),
            func.sum(Sale.total_amount).label("revenue")
        ).where(
            and_(
                Sale.created_at >= yesterday_start,
                Sale.created_at <= yesterday_end,
                Sale.status == SaleStatus.COMPLETED
            )
        )
    ).first()
    
    # Low stock products
    low_stock_count = db.exec(
        select(func.count(Product.id)).where(
            and_(
                Product.is_active == True,
                Product.track_inventory == True,
                Product.stock_quantity <= Product.reorder_level
            )
        )
    ).first()
    
    # Out of stock products
    out_of_stock_count = db.exec(
        select(func.count(Product.id)).where(
            and_(
                Product.is_active == True,
                Product.track_inventory == True,
                Product.stock_quantity <= 0
            )
        )
    ).first()
    
    # Total active products
    total_products = db.exec(
        select(func.count(Product.id)).where(Product.is_active == True)
    ).first()
    
    # Active users
    active_users = db.exec(
        select(func.count(User.id)).where(User.is_active == True)
    ).first()
    
    # Calculate percentage changes
    def calculate_change(current, previous):
        if not previous or previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 2)
    
    today_revenue = float(today_sales.revenue or 0)
    yesterday_revenue = float(yesterday_sales.revenue or 0)
    today_count = int(today_sales.count or 0)
    yesterday_count = int(yesterday_sales.count or 0)
    
    return {
        "today": {
            "sales_count": today_count,
            "revenue": today_revenue,
            "sales_change": calculate_change(today_count, yesterday_count),
            "revenue_change": calculate_change(today_revenue, yesterday_revenue)
        },
        "inventory": {
            "total_products": int(total_products or 0),
            "low_stock": int(low_stock_count or 0),
            "out_of_stock": int(out_of_stock_count or 0)
        },
        "system": {
            "active_users": int(active_users or 0)
        }
    }
