"""
Product management endpoints with enhanced features
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select, and_, or_
from fastapi_cache2.decorator import cache
import structlog

from ....core.database import get_db
from ....core.cache import cache_manager, CacheKeys
from ....core.logging import audit_logger
from ....models.product import Product, ProductCreate, ProductUpdate, ProductResponse, ProductSearch
from ....models.user import User
from ....api.dependencies import get_current_active_user, require_manager_or_admin, get_pagination, PaginationParams

logger = structlog.get_logger()
router = APIRouter()


@router.get("/", response_model=List[ProductResponse])
@cache(expire=300)  # Cache for 5 minutes
async def get_products(
    pagination: PaginationParams = Depends(get_pagination),
    search: Optional[str] = Query(None, description="Search in product name or barcode"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    in_stock_only: bool = Query(False, description="Show only products in stock"),
    low_stock_only: bool = Query(False, description="Show only low stock products"),
    active_only: bool = Query(True, description="Show only active products"),
    db: Session = Depends(get_db)
):
    """Get products with advanced filtering and caching"""
    
    # Build query
    query = select(Product)
    
    # Apply filters
    conditions = []
    
    if active_only:
        conditions.append(Product.is_active == True)
    
    if search:
        search_condition = or_(
            Product.name.ilike(f"%{search}%"),
            Product.barcode.ilike(f"%{search}%"),
            Product.sku.ilike(f"%{search}%")
        )
        conditions.append(search_condition)
    
    if category_id:
        conditions.append(Product.category_id == category_id)
    
    if in_stock_only:
        conditions.append(Product.stock_quantity > 0)
    
    if low_stock_only:
        conditions.append(Product.stock_quantity <= Product.min_stock)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Apply pagination
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    # Execute query
    products = db.exec(query).all()
    
    # Convert to response models with computed fields
    response_products = []
    for product in products:
        product_dict = product.dict()
        
        # Calculate computed fields
        if product.price and product.cost:
            product_dict["profit_margin"] = ((product.price - product.cost) / product.price) * 100
        
        product_dict["is_low_stock"] = product.stock_quantity <= product.min_stock
        
        # Calculate effective price (after discount)
        effective_price = product.price
        if product.discount_percentage:
            effective_price = product.price * (1 - product.discount_percentage / 100)
        product_dict["effective_price"] = effective_price
        
        response_products.append(ProductResponse(**product_dict))
    
    return response_products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Get single product by ID"""
    
    # Try cache first
    cached_product = await cache_manager.get(CacheKeys.product(product_id))
    if cached_product:
        return ProductResponse(**cached_product)
    
    # Get from database
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Calculate computed fields
    product_dict = product.dict()
    if product.price and product.cost:
        product_dict["profit_margin"] = ((product.price - product.cost) / product.price) * 100
    
    product_dict["is_low_stock"] = product.stock_quantity <= product.min_stock
    
    effective_price = product.price
    if product.discount_percentage:
        effective_price = product.price * (1 - product.discount_percentage / 100)
    product_dict["effective_price"] = effective_price
    
    response_product = ProductResponse(**product_dict)
    
    # Cache the result
    await cache_manager.set(
        CacheKeys.product(product_id),
        response_product.dict(),
        ttl=600  # 10 minutes
    )
    
    return response_product


@router.post("/", response_model=ProductResponse)
async def create_product(
    product: ProductCreate,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Create new product"""
    
    # Check for duplicate barcode/SKU
    if product.barcode:
        existing = db.exec(select(Product).where(Product.barcode == product.barcode)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product with this barcode already exists"
            )
    
    if product.sku:
        existing = db.exec(select(Product).where(Product.sku == product.sku)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product with this SKU already exists"
            )
    
    # Create product
    product_data = product.dict()
    
    # Convert tags list to JSON string if provided
    if product.tags:
        import json
        product_data["tags"] = json.dumps(product.tags)
    
    db_product = Product(**product_data)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="create",
        resource="product",
        resource_id=db_product.id,
        details={"name": db_product.name, "barcode": db_product.barcode}
    )
    
    # Invalidate related caches
    if product.category_id:
        await cache_manager.delete(CacheKeys.products_by_category(product.category_id))
    
    # Return response
    product_dict = db_product.dict()
    if db_product.price and db_product.cost:
        product_dict["profit_margin"] = ((db_product.price - db_product.cost) / db_product.price) * 100
    
    product_dict["is_low_stock"] = db_product.stock_quantity <= db_product.min_stock
    product_dict["effective_price"] = db_product.price
    
    return ProductResponse(**product_dict)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Update product"""
    
    # Get existing product
    db_product = db.get(Product, product_id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check for duplicate barcode/SKU if being updated
    update_data = product_update.dict(exclude_unset=True)
    
    if "barcode" in update_data and update_data["barcode"]:
        existing = db.exec(
            select(Product).where(
                and_(Product.barcode == update_data["barcode"], Product.id != product_id)
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product with this barcode already exists"
            )
    
    if "sku" in update_data and update_data["sku"]:
        existing = db.exec(
            select(Product).where(
                and_(Product.sku == update_data["sku"], Product.id != product_id)
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product with this SKU already exists"
            )
    
    # Convert tags list to JSON string if provided
    if "tags" in update_data and update_data["tags"]:
        import json
        update_data["tags"] = json.dumps(update_data["tags"])
    
    # Update product
    old_values = db_product.dict()
    
    for field, value in update_data.items():
        setattr(db_product, field, value)
    
    db_product.updated_at = datetime.utcnow()
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="update",
        resource="product",
        resource_id=db_product.id,
        details={
            "old_values": old_values,
            "new_values": db_product.dict(),
            "updated_fields": list(update_data.keys())
        }
    )
    
    # Invalidate caches
    await cache_manager.delete(CacheKeys.product(product_id))
    if db_product.category_id:
        await cache_manager.delete(CacheKeys.products_by_category(db_product.category_id))
    
    # Return response
    product_dict = db_product.dict()
    if db_product.price and db_product.cost:
        product_dict["profit_margin"] = ((db_product.price - db_product.cost) / db_product.price) * 100
    
    product_dict["is_low_stock"] = db_product.stock_quantity <= db_product.min_stock
    
    effective_price = db_product.price
    if db_product.discount_percentage:
        effective_price = db_product.price * (1 - db_product.discount_percentage / 100)
    product_dict["effective_price"] = effective_price
    
    return ProductResponse(**product_dict)


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Delete product (soft delete by setting inactive)"""
    
    # Get product
    db_product = db.get(Product, product_id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Soft delete by setting inactive
    db_product.is_active = False
    db_product.updated_at = datetime.utcnow()
    db.add(db_product)
    db.commit()
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="delete",
        resource="product",
        resource_id=product_id,
        details={"name": db_product.name, "soft_delete": True}
    )
    
    # Invalidate caches
    await cache_manager.delete(CacheKeys.product(product_id))
    if db_product.category_id:
        await cache_manager.delete(CacheKeys.products_by_category(db_product.category_id))
    
    return {"message": "Product deleted successfully"}


@router.get("/barcode/{barcode}", response_model=ProductResponse)
async def get_product_by_barcode(
    barcode: str,
    db: Session = Depends(get_db)
):
    """Get product by barcode for POS scanning"""
    
    product = db.exec(
        select(Product).where(
            and_(Product.barcode == barcode, Product.is_active == True)
        )
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Calculate computed fields
    product_dict = product.dict()
    if product.price and product.cost:
        product_dict["profit_margin"] = ((product.price - product.cost) / product.price) * 100
    
    product_dict["is_low_stock"] = product.stock_quantity <= product.min_stock
    
    effective_price = product.price
    if product.discount_percentage:
        effective_price = product.price * (1 - product.discount_percentage / 100)
    product_dict["effective_price"] = effective_price
    
    return ProductResponse(**product_dict)


@router.get("/low-stock/", response_model=List[ProductResponse])
async def get_low_stock_products(
    pagination: PaginationParams = Depends(get_pagination),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get products with low stock"""
    
    # Try cache first
    cache_key = CacheKeys.inventory_low_stock()
    cached_products = await cache_manager.get(cache_key)
    if cached_products:
        return [ProductResponse(**p) for p in cached_products]
    
    # Query low stock products
    products = db.exec(
        select(Product).where(
            and_(
                Product.stock_quantity <= Product.min_stock,
                Product.is_active == True,
                Product.is_trackable == True
            )
        ).offset(pagination.skip).limit(pagination.limit)
    ).all()
    
    # Convert to response models
    response_products = []
    for product in products:
        product_dict = product.dict()
        if product.price and product.cost:
            product_dict["profit_margin"] = ((product.price - product.cost) / product.price) * 100
        
        product_dict["is_low_stock"] = True
        product_dict["effective_price"] = product.price
        
        response_products.append(ProductResponse(**product_dict))
    
    # Cache results
    await cache_manager.set(
        cache_key,
        [p.dict() for p in response_products],
        ttl=300  # 5 minutes
    )
    
    return response_products
