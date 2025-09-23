"""
FastAPI dependencies for authentication, authorization, and common functionality
"""
from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
import structlog

from ..core.database import get_db
from ..core.security import security_manager
from ..core.cache import cache_manager, CacheKeys
from ..models.user import User, UserRole

logger = structlog.get_logger()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify token
        token_data = security_manager.verify_token(token)
        
        # Try to get user from cache first
        cached_user = await cache_manager.get(CacheKeys.user(token_data.user_id))
        if cached_user and cached_user.get("is_active"):
            # Get full user from database
            user = db.get(User, token_data.user_id)
            if user and user.is_active:
                return user
        
        # Get user from database
        user = db.exec(
            select(User).where(User.username == token_data.username)
        ).first()
        
        if user is None or not user.is_active:
            raise credentials_exception
            
        # Cache user data
        await cache_manager.set(
            CacheKeys.user(user.id),
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active
            },
            ttl=1800
        )
        
        return user
        
    except Exception as e:
        logger.error("User authentication failed", error=str(e))
        raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_role(required_roles: List[UserRole]):
    """Dependency to require specific user roles"""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in [UserRole.ADMIN] + required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Require admin role"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_manager_or_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Require manager or admin role"""
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required"
        )
    return current_user


async def get_request_info(request: Request) -> dict:
    """Extract request information for logging"""
    return {
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent", ""),
        "endpoint": str(request.url.path),
        "method": request.method
    }


class PaginationParams:
    """Pagination parameters"""
    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
        max_limit: int = 1000
    ):
        if limit > max_limit:
            limit = max_limit
        if skip < 0:
            skip = 0
        
        self.skip = skip
        self.limit = limit


def get_pagination(
    skip: int = 0,
    limit: int = 100
) -> PaginationParams:
    """Get pagination parameters"""
    return PaginationParams(skip=skip, limit=limit)
