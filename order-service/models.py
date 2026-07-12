"""Modelos ORM do SQLAlchemy."""

from sqlalchemy import Column, Integer, String

from database import Base  # pylint: disable=import-error


class Order(Base):  # pylint: disable=too-few-public-methods
    """Modelo de pedido no banco de dados."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
