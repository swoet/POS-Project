"""
Enhanced security utilities with proper validation and encryption
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import pyotp
import structlog
from fastapi import HTTPException, status
from pydantic import BaseModel, validator

from .config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Use Argon2 for password hashing (more secure than bcrypt)
ph = PasswordHasher()
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None
    permissions: List[str] = []


class SecurityManager:
    """Centralized security management"""
    
    def __init__(self):
        self.settings = get_settings()
        self._blacklisted_tokens: set = set()
    
    def hash_password(self, password: str) -> str:
        """Hash password using Argon2"""
        try:
            return ph.hash(password)
        except Exception as e:
            logger.error("Password hashing failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password processing failed"
            )
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            # Try Argon2 first
            ph.verify(hashed_password, plain_password)
            return True
        except VerifyMismatchError:
            try:
                # Fallback to bcrypt for existing passwords
                return pwd_context.verify(plain_password, hashed_password)
            except Exception:
                return False
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token with enhanced security"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.settings.access_token_expire_minutes
            )
        
        # Add security claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": self.settings.app_name,
            "jti": secrets.token_urlsafe(16),  # JWT ID for blacklisting
        })
        
        try:
            encoded_jwt = jwt.encode(
                to_encode, 
                self.settings.secret_key, 
                algorithm=self.settings.algorithm
            )
            return encoded_jwt
        except Exception as e:
            logger.error("Token creation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(
            days=self.settings.refresh_token_expire_days
        )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": secrets.token_urlsafe(16),
        })
        
        return jwt.encode(
            to_encode,
            self.settings.secret_key,
            algorithm=self.settings.algorithm
        )
    
    def verify_token(self, token: str) -> TokenData:
        """Verify and decode JWT token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.algorithm]
            )
            
            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and jti in self._blacklisted_tokens:
                raise credentials_exception
            
            username: str = payload.get("sub")
            role: str = payload.get("role")
            user_id: int = payload.get("user_id")
            permissions: List[str] = payload.get("permissions", [])
            
            if username is None:
                raise credentials_exception
                
            return TokenData(
                username=username,
                role=role,
                user_id=user_id,
                permissions=permissions
            )
            
        except JWTError as e:
            logger.warning("Token verification failed", error=str(e))
            raise credentials_exception
    
    def blacklist_token(self, token: str) -> None:
        """Add token to blacklist"""
        try:
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.algorithm],
                options={"verify_exp": False}  # Don't verify expiration for blacklisting
            )
            jti = payload.get("jti")
            if jti:
                self._blacklisted_tokens.add(jti)
                logger.info("Token blacklisted", jti=jti)
        except Exception as e:
            logger.error("Token blacklisting failed", error=str(e))
    
    def generate_otp_secret(self) -> str:
        """Generate OTP secret for 2FA"""
        return pyotp.random_base32()
    
    def verify_otp(self, secret: str, token: str) -> bool:
        """Verify OTP token"""
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=1)  # Allow 30s window
        except Exception as e:
            logger.error("OTP verification failed", error=str(e))
            return False
    
    def get_otp_qr_url(self, secret: str, username: str) -> str:
        """Get QR code URL for OTP setup"""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=username,
            issuer_name=self.settings.otp_issuer
        )
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()


# Global security manager instance
security_manager = SecurityManager()


def validate_password_strength(password: str) -> bool:
    """Validate password meets security requirements"""
    if len(password) < 8:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    return all([has_upper, has_lower, has_digit, has_special])


def sanitize_input(input_str: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not input_str:
        return ""
    
    # Remove null bytes and control characters
    sanitized = ''.join(char for char in input_str if ord(char) >= 32 or char in '\t\n\r')
    
    # Limit length
    return sanitized[:max_length]


class RateLimitManager:
    """Rate limiting manager"""
    
    def __init__(self):
        self._attempts: Dict[str, List[datetime]] = {}
        self._blocked: Dict[str, datetime] = {}
    
    def is_rate_limited(self, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Check if identifier is rate limited"""
        now = datetime.utcnow()
        
        # Check if currently blocked
        if identifier in self._blocked:
            if now < self._blocked[identifier]:
                return True
            else:
                del self._blocked[identifier]
        
        # Clean old attempts
        if identifier in self._attempts:
            self._attempts[identifier] = [
                attempt for attempt in self._attempts[identifier]
                if now - attempt < timedelta(minutes=window_minutes)
            ]
        
        # Check attempt count
        attempt_count = len(self._attempts.get(identifier, []))
        if attempt_count >= max_attempts:
            # Block for double the window time
            self._blocked[identifier] = now + timedelta(minutes=window_minutes * 2)
            return True
        
        return False
    
    def record_attempt(self, identifier: str) -> None:
        """Record failed attempt"""
        now = datetime.utcnow()
        if identifier not in self._attempts:
            self._attempts[identifier] = []
        self._attempts[identifier].append(now)


# Global rate limit manager
rate_limit_manager = RateLimitManager()
