"""Schemas Pydantic para validação de requisições e respostas."""

from pydantic import BaseModel


class OrderCreate(BaseModel):
    """Schema para criação de pedido."""
    description: str
    idempotency_key: str


class OrderResponse(BaseModel):
    """Schema de resposta de pedido."""
    id: int
    description: str

    class Config:  # pylint: disable=too-few-public-methods
        """Configuração do Pydantic."""
        from_attributes = True
