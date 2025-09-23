"""
User models with enhanced validation and security
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel
from pydantic import EmailStr, validator
from enum import Enum

from .base import TimestampMixin, BaseResponse


class UserRole(str, Enum):
    """User roles enumeration"""
    ADMIN = "admin"
    MANAGER = "manager"
    CASHIER = "cashier"


class User(SQLModel, TimestampMixin, table=True):
    """User database model"""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, min_length=3, max_length=50)
    email: EmailStr = Field(unique=True, index=True)
    hashed_password: str = Field(min_length=60)  # Argon2 hash length
    role: UserRole = Field(default=UserRole.CASHIER)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    
    # 2FA fields
    otp_secret: Optional[str] = Field(default=None)
    otp_enabled: bool = Field(default=False)
    backup_codes: Optional[str] = Field(default=None)  # JSON string
    
    # Security fields
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None)
    last_login: Optional[datetime] = Field(default=None)
    password_changed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Profile fields
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    
    class Config:
        table = True


class UserCreate(SQLModel):
    """User creation model"""
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.CASHIER
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
        
        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                'Password must contain uppercase, lowercase, digit, and special character'
            )
        
        return v
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v.lower()


class UserUpdate(SQLModel):
    """User update model"""
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    
    @validator('password')
    def validate_password(cls, v):
        if v is None:
            return v
        return UserCreate.validate_password(v)


class UserResponse(BaseResponse):
    """User response model"""
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool
    is_verified: bool
    otp_enabled: bool
    last_login: Optional[datetime]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]


class UserLogin(SQLModel):
    """User login model"""
    username: str
    password: str
    otp_code: Optional[str] = None


class UserProfile(SQLModel):
    """User profile update model"""
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)


class PasswordChange(SQLModel):
    """Password change model"""
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        return UserCreate.validate_password(v)


class TwoFactorSetup(SQLModel):
    """2FA setup response"""
    secret: str
    qr_code_url: str
    backup_codes: List[str]


class TwoFactorVerify(SQLModel):
    """2FA verification model"""
    otp_code: str = Field(min_length=6, max_length=6)
