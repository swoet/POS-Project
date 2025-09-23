"""
Category management endpoints with hierarchical support
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, and_, func
import structlog

from ....core.database import get_db
from ....core.logging import audit_logger
from ....core.cache import cache_manager
from ....models.category import Category, CategoryCreate, CategoryUpdate, CategoryResponse, CategoryTree
from ....models.product import Product
from ....models.user import User
from ....api.dependencies import (
    get_current_active_user, require_manager_or_admin, get_pagination, 
    PaginationParams, get_request_info
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    pagination: PaginationParams = Depends(get_pagination),
    active_only: bool = True,
    include_product_count: bool = True,
    db: Session = Depends(get_db)
):
    """Get categories with product counts"""
    
    # Build base query
    query = select(Category)
    
    if active_only:
        query = query.where(Category.is_active == True)
    
    # Order by display_order and name
    query = query.order_by(Category.display_order, Category.name)
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    categories = db.exec(query).all()
    
    # Build response with product counts and parent names
    response_categories = []
    for category in categories:
        category_dict = category.dict()
        
        # Get product count if requested
        if include_product_count:
            product_count = db.exec(
                select(func.count(Product.id)).where(
                    and_(Product.category_id == category.id, Product.is_active == True)
                )
            ).first()
            category_dict["product_count"] = product_count or 0
        
        # Get parent name if has parent
        if category.parent_id:
            parent = db.get(Category, category.parent_id)
            category_dict["parent_name"] = parent.name if parent else None
        
        response_categories.append(CategoryResponse(**category_dict))
    
    return response_categories


@router.get("/tree", response_model=List[CategoryTree])
async def get_category_tree(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get hierarchical category tree"""
    
    # Get all categories
    query = select(Category)
    if active_only:
        query = query.where(Category.is_active == True)
    
    query = query.order_by(Category.display_order, Category.name)
    categories = db.exec(query).all()
    
    # Build category map
    category_map = {cat.id: cat for cat in categories}
    
    # Get product counts for each category
    product_counts = {}
    for category in categories:
        count = db.exec(
            select(func.count(Product.id)).where(
                and_(Product.category_id == category.id, Product.is_active == True)
            )
        ).first()
        product_counts[category.id] = count or 0
    
    # Build tree structure
    def build_tree(parent_id=None):
        tree = []
        for category in categories:
            if category.parent_id == parent_id:
                children = build_tree(category.id)
                tree_node = CategoryTree(
                    id=category.id,
                    name=category.name,
                    children=children,
                    product_count=product_counts.get(category.id, 0)
                )
                tree.append(tree_node)
        return tree
    
    return build_tree()


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """Get single category by ID"""
    
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Build response
    category_dict = category.dict()
    
    # Get product count
    product_count = db.exec(
        select(func.count(Product.id)).where(
            and_(Product.category_id == category.id, Product.is_active == True)
        )
    ).first()
    category_dict["product_count"] = product_count or 0
    
    # Get parent name
    if category.parent_id:
        parent = db.get(Category, category.parent_id)
        category_dict["parent_name"] = parent.name if parent else None
    
    # Get children
    children = db.exec(
        select(Category).where(
            and_(Category.parent_id == category.id, Category.is_active == True)
        ).order_by(Category.display_order, Category.name)
    ).all()
    
    category_dict["children"] = [CategoryResponse.from_orm(child) for child in children]
    
    return CategoryResponse(**category_dict)


@router.post("/", response_model=CategoryResponse)
async def create_category(
    category: CategoryCreate,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Create new category"""
    
    request_info = await get_request_info(request)
    
    # Check for duplicate name
    existing = db.exec(
        select(Category).where(Category.name == category.name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )
    
    # Validate parent exists if specified
    if category.parent_id:
        parent = db.get(Category, category.parent_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found"
            )
        
        # Prevent circular references (basic check)
        if parent.parent_id == category.parent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Circular reference detected"
            )
    
    # Create category
    db_category = Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="create",
        resource="category",
        resource_id=db_category.id,
        details={"name": db_category.name, "parent_id": db_category.parent_id},
        **request_info
    )
    
    # Build response
    category_dict = db_category.dict()
    category_dict["product_count"] = 0
    
    if db_category.parent_id:
        parent = db.get(Category, db_category.parent_id)
        category_dict["parent_name"] = parent.name if parent else None
    
    return CategoryResponse(**category_dict)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Update category"""
    
    request_info = await get_request_info(request)
    
    # Get existing category
    db_category = db.get(Category, category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check for duplicate name if being updated
    update_data = category_update.dict(exclude_unset=True)
    
    if "name" in update_data:
        existing = db.exec(
            select(Category).where(
                and_(Category.name == update_data["name"], Category.id != category_id)
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category with this name already exists"
            )
    
    # Validate parent if being updated
    if "parent_id" in update_data and update_data["parent_id"]:
        if update_data["parent_id"] == category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category cannot be its own parent"
            )
        
        parent = db.get(Category, update_data["parent_id"])
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found"
            )
    
    # Update category
    old_values = db_category.dict()
    
    for field, value in update_data.items():
        setattr(db_category, field, value)
    
    db_category.updated_at = datetime.utcnow()
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="update",
        resource="category",
        resource_id=category_id,
        details={
            "old_values": old_values,
            "new_values": db_category.dict(),
            "updated_fields": list(update_data.keys())
        },
        **request_info
    )
    
    # Build response
    category_dict = db_category.dict()
    
    # Get product count
    product_count = db.exec(
        select(func.count(Product.id)).where(
            and_(Product.category_id == category_id, Product.is_active == True)
        )
    ).first()
    category_dict["product_count"] = product_count or 0
    
    # Get parent name
    if db_category.parent_id:
        parent = db.get(Category, db_category.parent_id)
        category_dict["parent_name"] = parent.name if parent else None
    
    return CategoryResponse(**category_dict)


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    request: Request,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """Delete category (soft delete by setting inactive)"""
    
    request_info = await get_request_info(request)
    
    # Get category
    db_category = db.get(Category, category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Check if category has products
    product_count = db.exec(
        select(func.count(Product.id)).where(
            and_(Product.category_id == category_id, Product.is_active == True)
        )
    ).first()
    
    if product_count and product_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with active products"
        )
    
    # Check if category has children
    children_count = db.exec(
        select(func.count(Category.id)).where(
            and_(Category.parent_id == category_id, Category.is_active == True)
        )
    ).first()
    
    if children_count and children_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with active subcategories"
        )
    
    # Soft delete
    db_category.is_active = False
    db_category.updated_at = datetime.utcnow()
    db.add(db_category)
    db.commit()
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="delete",
        resource="category",
        resource_id=category_id,
        details={"name": db_category.name, "soft_delete": True},
        **request_info
    )
    
    return {"message": "Category deleted successfully"}
