"""
backend/builder/generators/fullstack_ecommerce.py
Generates a full-stack ecommerce scaffold:
  - FastAPI backend (main.py, models.py, database.py, routes/)
  - Static frontend (index.html with fetch-based API calls)
  - requirements.txt + README.md
"""

from backend.builder.generators.static_store import generate as _gen_static


def generate(prefs: dict) -> dict:
    features = prefs.get("features", {})
    if isinstance(features, list):
        # Handle cases where features is a list of strings natively
        features_lower = [str(f).lower() for f in features]
        has_auth = "auth" in features_lower
        has_payment = "payment" in features_lower
    else:
        # Default dict fallback
        has_auth = features.get("auth", False)
        has_payment = features.get("payment", False)

    files = {}

    # ── Frontend (static store adapted to call the API) ──────────────────
    static = _gen_static(prefs)
    files["frontend/index.html"] = static["index.html"]

    # ── Backend main.py ───────────────────────────────────────────────────
    files["backend/main.py"] = '''"""
DreamAgent-Generated FastAPI Backend
Auto-generated · Do not edit manually.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
from backend.routes import products, orders
''' + ('''from backend.routes import auth
''' if has_auth else '') + '''
import uvicorn

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DreamStore API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
''' + ('''app.include_router(auth.router, prefix="/api")
''' if has_auth else '') + '''
@app.get("/")
def root():
    return {"status": "DreamStore is running 🚀"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
'''

    # ── Backend database.py ────────────────────────────────────────────────
    files["backend/database.py"] = '''from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./dreamstore.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''

    # ── Backend models.py ──────────────────────────────────────────────────
    files["backend/models.py"] = '''from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
from backend.database import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    image_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)
    total = Column(Float, nullable=False)
    status = Column(String, default="pending")
    customer_email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
''' + ('''
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
''' if has_auth else '')

    # ── Backend routes/products.py ─────────────────────────────────────────
    files["backend/routes/__init__.py"] = ""
    files["backend/routes/products.py"] = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from backend.database import get_db
from backend import models

router = APIRouter(prefix="/products", tags=["products"])

class ProductCreate(BaseModel):
    name: str
    description: str = ""
    price: float
    stock: int = 0
    image_url: str = ""

class ProductOut(ProductCreate):
    id: int
    class Config: from_attributes = True

@router.get("/", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).all()

@router.post("/", response_model=ProductOut)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = models.Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
'''

    # ── Backend routes/orders.py ───────────────────────────────────────────
    files["backend/routes/orders.py"] = '''from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from backend.database import get_db
from backend import models

router = APIRouter(prefix="/orders", tags=["orders"])

class OrderCreate(BaseModel):
    product_id: int
    quantity: int
    customer_email: str

class OrderOut(OrderCreate):
    id: int
    total: float
    status: str
    class Config: from_attributes = True

@router.post("/", response_model=OrderOut)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == order.product_id).first()
    total = (product.price if product else 0) * order.quantity
    db_order = models.Order(**order.model_dump(), total=total)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@router.get("/", response_model=List[OrderOut])
def list_orders(db: Session = Depends(get_db)):
    return db.query(models.Order).all()
'''

    # ── Auth route (conditional) ───────────────────────────────────────────
    if has_auth:
        files["backend/routes/auth.py"] = '''from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from passlib.context import CryptContext
from backend.database import get_db
from backend import models

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    class Config: from_attributes = True

@router.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = pwd_context.hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login")
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Login successful", "user_id": db_user.id}
'''

    # ── requirements.txt ──────────────────────────────────────────────────
    req_lines = [
        "fastapi>=0.111.0",
        "uvicorn[standard]>=0.29.0",
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
    ]
    if has_auth:
        req_lines.append("passlib[bcrypt]>=1.7.4")
    if has_payment:
        req_lines.append("stripe>=8.0.0")

    files["requirements.txt"] = "\n".join(req_lines) + "\n"

    # ── README.md ──────────────────────────────────────────────────────────
    files["README.md"] = f"""# DreamStore — Full-Stack Ecommerce App
> Auto-generated by DreamAgent 🚀

## Project Structure
```
backend/         FastAPI backend
  main.py        Entry point
  database.py    SQLite / SQLAlchemy setup
  models.py      ORM models (Product, Order{', User' if has_auth else ''})
  routes/        API route handlers
frontend/
  index.html     Pretty shopfront (no framework, pure HTML/CSS/JS)
requirements.txt Python dependencies
```

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Run backend
python backend/main.py
# → API docs at http://localhost:8000/docs

# Open frontend
open frontend/index.html
```

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/products | List all products |
| POST | /api/products | Create product |
| GET | /api/products/{{id}} | Get product |
| POST | /api/orders | Place order |
| GET | /api/orders | List orders |
{'| POST | /api/auth/register | Register user |' if has_auth else ''}
{'| POST | /api/auth/login | Login user |' if has_auth else ''}

## Built with DreamAgent
Configure preferences, rebuild, and evolve your app through natural language.
"""

    return files
