from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
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
