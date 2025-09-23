"""
User management endpoints with enhanced security
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session, select, and_
import structlog

from ....core.database import get_db
from ....core.security import security_manager
from ....core.logging import audit_logger
from ....core.cache import cache_manager, CacheKeys
from ....models.user import (
    User, UserCreate, UserUpdate, UserResponse, UserProfile, 
    PasswordChange, UserRole
)
from ....api.dependencies import (
    get_current_active_user, require_admin, get_pagination, 
    PaginationParams, get_request_info
)

logger = structlog.get_logger()
router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def get_users(
    pagination: PaginationParams = Depends(get_pagination),
    role: Optional[UserRole] = None,
    active_only: bool = True,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get users with filtering (admin only)"""
    
    # Build query
    query = select(User)
    conditions = []
    
    if active_only:
        conditions.append(User.is_active == True)
    
    if role:
        conditions.append(User.role == role)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Apply pagination
    query = query.offset(pagination.skip).limit(pagination.limit)
    
    # Execute query
    users = db.exec(query).all()
    
    return [UserResponse.from_orm(user) for user in users]


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's profile"""
    return UserResponse.from_orm(current_user)


@router.put("/me/profile", response_model=UserResponse)
async def update_current_user_profile(
    profile_update: UserProfile,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    
    request_info = await get_request_info(request)
    update_data = profile_update.dict(exclude_unset=True)
    old_values = {
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "phone": current_user.phone
    }
    
    # Update profile fields
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="update_profile",
        resource="user",
        resource_id=current_user.id,
        details={
            "old_values": old_values,
            "new_values": update_data
        },
        **request_info
    )
    
    # Update cache
    await cache_manager.set(
        CacheKeys.user(current_user.id),
        {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "is_active": current_user.is_active
        },
        ttl=1800
    )
    
    return UserResponse.from_orm(current_user)


@router.put("/me/password")
async def change_password(
    password_change: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    
    request_info = await get_request_info(request)
    
    # Verify current password
    if not security_manager.verify_password(
        password_change.current_password, 
        current_user.hashed_password
    ):
        audit_logger.log_security_event(
            "password_change_failed",
            user_id=current_user.id,
            details={"reason": "invalid_current_password"},
            severity="WARNING",
            **request_info
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    new_hashed_password = security_manager.hash_password(password_change.new_password)
    
    # Update password
    current_user.hashed_password = new_hashed_password
    current_user.password_changed_at = datetime.utcnow()
    current_user.updated_at = datetime.utcnow()
    db.add(current_user)
    db.commit()
    
    # Log security event
    audit_logger.log_security_event(
        "password_changed",
        user_id=current_user.id,
        severity="INFO",
        **request_info
    )
    
    return {"message": "Password changed successfully"}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get user by ID (admin only)"""
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)


@router.post("/", response_model=UserResponse)
async def create_user(
    user_create: UserCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create new user (admin only)"""
    
    request_info = await get_request_info(request)
    
    # Check if username already exists
    existing_user = db.exec(
        select(User).where(User.username == user_create.username)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email already exists
    existing_email = db.exec(
        select(User).where(User.email == user_create.email)
    ).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    # Hash password
    hashed_password = security_manager.hash_password(user_create.password)
    
    # Create user
    user_data = user_create.dict()
    user_data.pop("password")
    user_data["hashed_password"] = hashed_password
    
    db_user = User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="create",
        resource="user",
        resource_id=db_user.id,
        details={
            "created_username": db_user.username,
            "created_role": db_user.role
        },
        **request_info
    )
    
    return UserResponse.from_orm(db_user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user (admin only)"""
    
    request_info = await get_request_info(request)
    
    # Get user
    db_user = db.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check for duplicate username/email if being updated
    update_data = user_update.dict(exclude_unset=True)
    old_values = db_user.dict()
    
    if "username" in update_data:
        existing = db.exec(
            select(User).where(
                and_(User.username == update_data["username"], User.id != user_id)
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
    
    if "email" in update_data:
        existing = db.exec(
            select(User).where(
                and_(User.email == update_data["email"], User.id != user_id)
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Hash password if provided
    if "password" in update_data:
        update_data["hashed_password"] = security_manager.hash_password(update_data["password"])
        update_data.pop("password")
        db_user.password_changed_at = datetime.utcnow()
    
    # Update user
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db_user.updated_at = datetime.utcnow()
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="update",
        resource="user",
        resource_id=user_id,
        details={
            "old_values": old_values,
            "updated_fields": list(update_data.keys()),
            "target_username": db_user.username
        },
        **request_info
    )
    
    # Invalidate user cache
    await cache_manager.delete(CacheKeys.user(user_id))
    
    return UserResponse.from_orm(db_user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Deactivate user (admin only)"""
    
    request_info = await get_request_info(request)
    
    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Get user
    db_user = db.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Soft delete by deactivating
    db_user.is_active = False
    db_user.updated_at = datetime.utcnow()
    db.add(db_user)
    db.commit()
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="delete",
        resource="user",
        resource_id=user_id,
        details={
            "deleted_username": db_user.username,
            "soft_delete": True
        },
        **request_info
    )
    
    # Invalidate user cache
    await cache_manager.delete(CacheKeys.user(user_id))
    
    return {"message": "User deactivated successfully"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate user (admin only)"""
    
    request_info = await get_request_info(request)
    
    # Get user
    db_user = db.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Activate user
    db_user.is_active = True
    db_user.updated_at = datetime.utcnow()
    db.add(db_user)
    db.commit()
    
    # Log audit
    audit_logger.log_user_action(
        user_id=current_user.id,
        action="activate",
        resource="user",
        resource_id=user_id,
        details={"activated_username": db_user.username},
        **request_info
    )
    
    return {"message": "User activated successfully"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reset user password (admin only)"""
    
    request_info = await get_request_info(request)
    
    # Get user
    db_user = db.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate temporary password
    temp_password = security_manager.generate_secure_token(12)
    hashed_password = security_manager.hash_password(temp_password)
    
    # Update password
    db_user.hashed_password = hashed_password
    db_user.password_changed_at = datetime.utcnow()
    db_user.updated_at = datetime.utcnow()
    
    # Force password change on next login (you might want to add this field to User model)
    # db_user.force_password_change = True
    
    db.add(db_user)
    db.commit()
    
    # Log security event
    audit_logger.log_security_event(
        "password_reset_by_admin",
        user_id=db_user.id,
        details={
            "reset_by_admin": current_user.id,
            "target_username": db_user.username
        },
        severity="INFO",
        **request_info
    )
    
    return {
        "message": "Password reset successfully",
        "temporary_password": temp_password,
        "note": "User should change this password on next login"
    }
