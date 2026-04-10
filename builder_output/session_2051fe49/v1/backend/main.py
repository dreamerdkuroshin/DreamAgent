"""
DreamAgent-Generated FastAPI Backend
Auto-generated · Do not edit manually.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
from backend.routes import products, orders

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

@app.get("/")
def root():
    return {"status": "DreamStore is running 🚀"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
