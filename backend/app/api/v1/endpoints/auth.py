"""
Authentication endpoints with enhanced security
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
import structlog

from ....core.database import get_db
from ....core.security import security_manager, rate_limit_manager
from ....core.logging import audit_logger
from ....core.cache import cache_manager, CacheKeys
from ....models.user import User, UserLogin, TwoFactorSetup, TwoFactorVerify
from ....models.audit import AuditAction

logger = structlog.get_logger()
router = APIRouter()


@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Enhanced login with rate limiting and security logging"""
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")
    
    # Rate limiting
    if rate_limit_manager.is_rate_limited(f"login:{client_ip}", max_attempts=5, window_minutes=15):
        audit_logger.log_security_event(
            "rate_limit_exceeded",
            ip_address=client_ip,
            details={"endpoint": "/auth/login", "username": form_data.username},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    # Get user
    user = db.exec(select(User).where(User.username == form_data.username)).first()
    
    if not user:
        rate_limit_manager.record_attempt(f"login:{client_ip}")
        audit_logger.log_security_event(
            "login_failed",
            ip_address=client_ip,
            details={"reason": "user_not_found", "username": form_data.username},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        audit_logger.log_security_event(
            "login_blocked",
            user_id=user.id,
            ip_address=client_ip,
            details={"reason": "account_locked"},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked"
        )
    
    # Verify password
    if not security_manager.verify_password(form_data.password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
        
        db.add(user)
        db.commit()
        
        rate_limit_manager.record_attempt(f"login:{client_ip}")
        audit_logger.log_security_event(
            "login_failed",
            user_id=user.id,
            ip_address=client_ip,
            details={"reason": "invalid_password", "attempts": user.failed_login_attempts},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if user is active
    if not user.is_active:
        audit_logger.log_security_event(
            "login_blocked",
            user_id=user.id,
            ip_address=client_ip,
            details={"reason": "account_inactive"},
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Check 2FA if enabled
    if user.otp_enabled:
        # For simplicity, we'll assume OTP is provided in a header or separate field
        # In production, this would be a separate endpoint or field
        otp_code = request.headers.get("x-otp-code")
        if not otp_code or not security_manager.verify_otp(user.otp_secret, otp_code):
            audit_logger.log_security_event(
                "2fa_failed",
                user_id=user.id,
                ip_address=client_ip,
                details={"reason": "invalid_otp"},
                severity="WARNING"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code"
            )
    
    # Successful login - reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    
    # Create tokens
    access_token_expires = timedelta(minutes=30)
    access_token = security_manager.create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "role": user.role,
            "permissions": []  # Add user permissions here
        },
        expires_delta=access_token_expires
    )
    refresh_token = security_manager.create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )
    
    # Cache user data
    await cache_manager.set(
        CacheKeys.user(user.id),
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active
        },
        ttl=1800  # 30 minutes
    )
    
    # Log successful login
    audit_logger.log_user_action(
        user_id=user.id,
        action="login",
        resource="auth",
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "otp_enabled": user.otp_enabled
        }
    }


@router.post("/refresh")
async def refresh_token(
    request: Request,
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """Refresh access token"""
    try:
        token_data = security_manager.verify_token(refresh_token)
        
        # Get user
        user = db.exec(select(User).where(User.username == token_data.username)).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Create new access token
        access_token_expires = timedelta(minutes=30)
        access_token = security_manager.create_access_token(
            data={
                "sub": user.username,
                "user_id": user.id,
                "role": user.role,
                "permissions": []
            },
            expires_delta=access_token_expires
        )
        
        # Create new refresh token
        new_refresh_token = security_manager.create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 1800
        }
        
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    """Logout and blacklist token"""
    try:
        token_data = security_manager.verify_token(token)
        
        # Blacklist the token
        security_manager.blacklist_token(token)
        
        # Clear user cache
        if token_data.user_id:
            await cache_manager.delete(CacheKeys.user(token_data.user_id))
        
        # Log logout
        audit_logger.log_user_action(
            user_id=token_data.user_id,
            action="logout",
            resource="auth",
            ip_address=request.client.host
        )
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error("Logout failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed"
        )


@router.post("/setup-2fa", response_model=TwoFactorSetup)
async def setup_2fa(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Setup 2FA for user"""
    if current_user.otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled"
        )
    
    # Generate OTP secret
    secret = security_manager.generate_otp_secret()
    qr_url = security_manager.get_otp_qr_url(secret, current_user.username)
    
    # Generate backup codes
    backup_codes = [security_manager.generate_secure_token(8) for _ in range(10)]
    
    # Save secret (but don't enable yet)
    current_user.otp_secret = secret
    current_user.backup_codes = ",".join(backup_codes)
    db.add(current_user)
    db.commit()
    
    # Log 2FA setup
    audit_logger.log_security_event(
        "2fa_setup_initiated",
        user_id=current_user.id,
        ip_address=request.client.host,
        severity="INFO"
    )
    
    return TwoFactorSetup(
        secret=secret,
        qr_code_url=qr_url,
        backup_codes=backup_codes
    )


@router.post("/verify-2fa")
async def verify_2fa(
    request: Request,
    verification: TwoFactorVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify and enable 2FA"""
    if not current_user.otp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated"
        )
    
    if not security_manager.verify_otp(current_user.otp_secret, verification.otp_code):
        audit_logger.log_security_event(
            "2fa_verification_failed",
            user_id=current_user.id,
            ip_address=request.client.host,
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code"
        )
    
    # Enable 2FA
    current_user.otp_enabled = True
    db.add(current_user)
    db.commit()
    
    # Log 2FA enabled
    audit_logger.log_security_event(
        "2fa_enabled",
        user_id=current_user.id,
        ip_address=request.client.host,
        severity="INFO"
    )
    
    return {"message": "2FA successfully enabled"}


@router.post("/disable-2fa")
async def disable_2fa(
    request: Request,
    verification: TwoFactorVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disable 2FA"""
    if not current_user.otp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled"
        )
    
    if not security_manager.verify_otp(current_user.otp_secret, verification.otp_code):
        audit_logger.log_security_event(
            "2fa_disable_failed",
            user_id=current_user.id,
            ip_address=request.client.host,
            severity="WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code"
        )
    
    # Disable 2FA
    current_user.otp_enabled = False
    current_user.otp_secret = None
    current_user.backup_codes = None
    db.add(current_user)
    db.commit()
    
    # Log 2FA disabled
    audit_logger.log_security_event(
        "2fa_disabled",
        user_id=current_user.id,
        ip_address=request.client.host,
        severity="INFO"
    )
    
    return {"message": "2FA successfully disabled"}
