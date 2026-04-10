from fastapi import APIRouter, Depends
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
