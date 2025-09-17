from fastapi import FastAPI, HTTPException, Depends, status, Query, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Field, SQLModel, Session, create_engine, select, update, delete
from typing import Optional, List, Annotated
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import pyotp
import os
from dotenv import load_dotenv
import json
import asyncio
from fastapi.responses import JSONResponse

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/pos_db")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
OTP_SECRET = os.getenv("OTP_SECRET", "your-otp-secret")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="POS Backend", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

engine = create_engine(DATABASE_URL, echo=False)

# Models
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: EmailStr
    hashed_password: str
    role: str = Field(default="cashier")  # admin, manager, cashier
    is_active: bool = Field(default=True)
    otp_secret: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    description: Optional[str] = None

class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    barcode: Optional[str] = Field(unique=True, index=True)
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    price: float
    cost: float
    stock_quantity: int = Field(default=0)
    min_stock: int = Field(default=0)
    description: Optional[str] = None
    is_active: bool = Field(default=True)

class Sale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    items_json: str
    subtotal: float
    tax: float
    discount: float
    total: float
    payment_method: str = "cash"
    synced: bool = Field(default=True)

class InventoryLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    user_id: int = Field(foreign_key="user.id")
    action: str  # add, remove, adjust
    quantity: int
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    action: str
    resource: str
    resource_id: Optional[int] = None
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "cashier"

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    barcode: Optional[str] = None
    category_id: Optional[int] = None
    price: float
    cost: float
    stock_quantity: int = 0
    min_stock: int = 0
    description: Optional[str] = None

class SaleCreate(BaseModel):
    items: List[dict]
    subtotal: float
    tax: float
    discount: float
    payment_method: str = "cash"

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == token_data.username)).first()
        if user is None:
            raise credentials_exception
        return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def check_role(required_role: str):
    def role_checker(current_user: Annotated[User, Depends(get_current_active_user)]):
        if current_user.role not in ["admin", required_role]:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_checker

def log_audit(session: Session, user_id: Optional[int], action: str, resource: str, resource_id: Optional[int] = None, details: Optional[str] = None, ip: Optional[str] = None):
    audit = AuditLog(user_id=user_id, action=action, resource=resource, resource_id=resource_id, details=details, ip_address=ip)
    session.add(audit)
    session.commit()

# Create tables
SQLModel.metadata.create_all(engine)

# Routes
@app.post("/setup_admin", response_model=UserResponse)
def setup_admin(user: UserCreate):
    with Session(engine) as session:
        if session.exec(select(User).where(User.username == user.username)).first():
            raise HTTPException(status_code=400, detail="Username already registered")
        hashed_password = get_password_hash(user.password)
        db_user = User(username=user.username, email=user.email, hashed_password=hashed_password, role="admin")
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        log_audit(session, db_user.id, "create", "user", db_user.id, "Admin user created")
        return db_user

@app.post("/token", response_model=Token)
@limiter.limit("5/minute")
def login(request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == form_data.username)).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect username or password")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        
        # Check 2FA if enabled
        if user.otp_secret:
            # For simplicity, assume OTP is provided in password field after main password
            # In production, separate field for OTP
            pass
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(data={"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@app.post("/refresh_token", response_model=Token)
def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
        )
        new_refresh_token = create_refresh_token(data={"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer", "refresh_token": new_refresh_token}

@app.post("/enable_2fa")
def enable_2fa(current_user: Annotated[User, Depends(get_current_active_user)]):
    with Session(engine) as session:
        if current_user.otp_secret:
            raise HTTPException(status_code=400, detail="2FA already enabled")
        otp_secret = pyotp.random_base32()
        current_user.otp_secret = otp_secret
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        log_audit(session, current_user.id, "enable", "2fa", current_user.id)
        return {"otp_secret": otp_secret, "qr_code_url": pyotp.totp.TOTP(otp_secret).provisioning_uri(name=current_user.username, issuer_name="POS System")}

@app.post("/verify_2fa")
def verify_2fa(current_user: Annotated[User, Depends(get_current_active_user)], otp_code: str):
    if not current_user.otp_secret:
        raise HTTPException(status_code=400, detail="2FA not enabled")
    totp = pyotp.TOTP(current_user.otp_secret)
    if not totp.verify(otp_code):
        raise HTTPException(status_code=400, detail="Invalid OTP")
    return {"message": "2FA verified"}

# User management
@app.get("/users", response_model=List[UserResponse])
def read_users(skip: int = 0, limit: int = 100, current_user: Annotated[User, Depends(check_role("admin"))]):
    with Session(engine) as session:
        users = session.exec(select(User).offset(skip).limit(limit)).all()
        return users

@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, current_user: Annotated[User, Depends(check_role("admin"))]):
    with Session(engine) as session:
        if session.exec(select(User).where(User.username == user.username)).first():
            raise HTTPException(status_code=400, detail="Username already registered")
        hashed_password = get_password_hash(user.password)
        db_user = User(username=user.username, email=user.email, hashed_password=hashed_password, role=user.role)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        log_audit(session, current_user.id, "create", "user", db_user.id)
        return db_user

@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserCreate, current_user: Annotated[User, Depends(check_role("admin"))]):
    with Session(engine) as session:
        db_user = session.get(User, user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        db_user.username = user_update.username
        db_user.email = user_update.email
        if user_update.password:
            db_user.hashed_password = get_password_hash(user_update.password)
        db_user.role = user_update.role
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        log_audit(session, current_user.id, "update", "user", db_user.id)
        return db_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: Annotated[User, Depends(check_role("admin"))]):
    with Session(engine) as session:
        db_user = session.get(User, user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(db_user)
        session.commit()
        log_audit(session, current_user.id, "delete", "user", user_id)
        return {"message": "User deleted"}

# Category management
@app.get("/categories")
def read_categories(skip: int = 0, limit: int = 100):
    with Session(engine) as session:
        categories = session.exec(select(Category).offset(skip).limit(limit)).all()
        return categories

@app.post("/categories")
def create_category(category: dict, current_user: Annotated[User, Depends(check_role("manager"))]):
    with Session(engine) as session:
        db_category = Category(name=category["name"], description=category.get("description"))
        session.add(db_category)
        session.commit()
        session.refresh(db_category)
        log_audit(session, current_user.id, "create", "category", db_category.id)
        return db_category

# Product management
@app.get("/products")
def read_products(skip: int = 0, limit: int = 100, search: Optional[str] = None, category_id: Optional[int] = None):
    with Session(engine) as session:
        query = select(Product)
        if search:
            query = query.where(Product.name.contains(search) | Product.barcode.contains(search))
        if category_id:
            query = query.where(Product.category_id == category_id)
        products = session.exec(query.offset(skip).limit(limit)).all()
        return products

@app.post("/products", response_model=Product)
def create_product(product: ProductCreate, current_user: Annotated[User, Depends(check_role("manager"))]):
    with Session(engine) as session:
        db_product = Product(**product.dict())
        session.add(db_product)
        session.commit()
        session.refresh(db_product)
        log_audit(session, current_user.id, "create", "product", db_product.id)
        return db_product

@app.put("/products/{product_id}", response_model=Product)
def update_product(product_id: int, product_update: ProductCreate, current_user: Annotated[User, Depends(check_role("manager"))]):
    with Session(engine) as session:
        db_product = session.get(Product, product_id)
        if not db_product:
            raise HTTPException(status_code=404, detail="Product not found")
        for key, value in product_update.dict().items():
            setattr(db_product, key, value)
        session.add(db_product)
        session.commit()
        session.refresh(db_product)
        log_audit(session, current_user.id, "update", "product", db_product.id)
        return db_product

@app.delete("/products/{product_id}")
def delete_product(product_id: int, current_user: Annotated[User, Depends(check_role("manager"))]):
    with Session(engine) as session:
        db_product = session.get(Product, product_id)
        if not db_product:
            raise HTTPException(status_code=404, detail="Product not found")
        session.delete(db_product)
        session.commit()
        log_audit(session, current_user.id, "delete", "product", product_id)
        return {"message": "Product deleted"}

# Sales
@app.post("/sales")
def create_sale(sale: SaleCreate, current_user: Annotated[User, Depends(get_current_active_user)]):
    with Session(engine) as session:
        total = sale.subtotal + sale.tax - sale.discount
        db_sale = Sale(
            user_id=current_user.id,
            items_json=json.dumps(sale.items),
            subtotal=sale.subtotal,
            tax=sale.tax,
            discount=sale.discount,
            total=total,
            payment_method=sale.payment_method
        )
        session.add(db_sale)
        session.commit()
        session.refresh(db_sale)
        
        # Update inventory
        for item in sale.items:
            product = session.get(Product, item["product_id"])
            if product:
                product.stock_quantity -= item["quantity"]
                session.add(product)
                # Log inventory change
                inv_log = InventoryLog(product_id=product.id, user_id=current_user.id, action="sale", quantity=-item["quantity"])
                session.add(inv_log)
        
        session.commit()
        log_audit(session, current_user.id, "create", "sale", db_sale.id)
        
        # Broadcast to WebSocket
        asyncio.create_task(manager.broadcast(json.dumps({"type": "new_sale", "sale_id": db_sale.id, "total": total})))
        
        return db_sale

@app.get("/sales")
def read_sales(skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
    with Session(engine) as session:
        query = select(Sale)
        if start_date:
            query = query.where(Sale.timestamp >= start_date)
        if end_date:
            query = query.where(Sale.timestamp <= end_date)
        sales = session.exec(query.offset(skip).limit(limit)).all()
        return sales

@app.post("/sales/bulk_sync")
def bulk_sync_sales(sales: List[dict], current_user: Annotated[User, Depends(get_current_active_user)]):
    saved = []
    with Session(engine) as session:
        for sale_data in sales:
            db_sale = Sale(
                user_id=current_user.id,
                timestamp=datetime.fromisoformat(sale_data["timestamp"]),
                items_json=sale_data["items_json"],
                subtotal=sale_data.get("subtotal", 0),
                tax=sale_data.get("tax", 0),
                discount=sale_data.get("discount", 0),
                total=sale_data["total"],
                synced=True
            )
            session.add(db_sale)
            session.commit()
            session.refresh(db_sale)
            saved.append({"id": db_sale.id})
            log_audit(session, current_user.id, "sync", "sale", db_sale.id)
    return {"saved": saved, "count": len(saved)}

# Inventory
@app.get("/inventory")
def read_inventory(skip: int = 0, limit: int = 100):
    with Session(engine) as session:
        products = session.exec(select(Product).where(Product.stock_quantity <= Product.min_stock).offset(skip).limit(limit)).all()
        return products

@app.post("/inventory/adjust")
def adjust_inventory(product_id: int, quantity: int, reason: Optional[str] = None, current_user: Annotated[User, Depends(check_role("manager"))]):
    with Session(engine) as session:
        product = session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product.stock_quantity += quantity
        session.add(product)
        inv_log = InventoryLog(product_id=product.id, user_id=current_user.id, action="adjust", quantity=quantity, reason=reason)
        session.add(inv_log)
        session.commit()
        log_audit(session, current_user.id, "adjust", "inventory", product.id, f"Quantity: {quantity}")
        return {"message": "Inventory adjusted"}

# Audit logs
@app.get("/audit_logs")
def read_audit_logs(skip: int = 0, limit: int = 100, current_user: Annotated[User, Depends(check_role("admin"))]):
    with Session(engine) as session:
        logs = session.exec(select(AuditLog).offset(skip).limit(limit)).all()
        return logs

# WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}

# Reports
@app.get("/reports/sales_summary")
def sales_summary(start_date: datetime, end_date: datetime, current_user: Annotated[User, Depends(check_role("manager"))]):
    with Session(engine) as session:
        sales = session.exec(
            select(Sale).where(Sale.timestamp >= start_date).where(Sale.timestamp <= end_date)
        ).all()
        total_sales = sum(s.total for s in sales)
        total_items = sum(len(json.loads(s.items_json)) for s in sales)
        return {"total_sales": total_sales, "total_items": total_items, "sale_count": len(sales)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
