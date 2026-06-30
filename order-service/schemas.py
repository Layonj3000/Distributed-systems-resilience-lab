from pydantic import BaseModel


class OrderCreate(BaseModel):
    description: str


class OrderResponse(BaseModel):
    id: int
    description: str

    class Config:
        from_attributes = True