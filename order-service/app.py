import time

from fastapi import FastAPI
from fastapi import Depends
from fastapi import HTTPException

from prometheus_fastapi_instrumentator import Instrumentator

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import Base
from database import SessionLocal
from database import engine

from models import Order

from schemas import OrderCreate
from schemas import OrderResponse


def init_db(retries=10, delay=3):
    for attempt in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError:
            time.sleep(delay)

    raise RuntimeError(
        "Database unavailable after startup retries"
    )


init_db()

app = FastAPI(title="Order Service")

Instrumentator().instrument(app).expose(app)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=201
)
def create_order(
    order: OrderCreate,
    db: Session = Depends(get_db)
):
    new_order = Order(
        description=order.description
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return new_order


@app.get(
    "/orders",
    response_model=list[OrderResponse]
)
def list_orders(
    db: Session = Depends(get_db)
):
    return db.query(Order).all()


@app.get(
    "/orders/{order_id}",
    response_model=OrderResponse
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return order