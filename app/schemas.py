"""Pydantic схемы для валидации данных."""

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Схема для создания пользователя."""

    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(default="", max_length=100)


class UserResponse(BaseModel):
    """Схема ответа с данными пользователя."""

    id: int
    email: str
    name: str

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """Схема ответа с данными заказа."""

    id: int
    title: str
    amount: int

    class Config:
        from_attributes = True


class UserWithOrdersResponse(BaseModel):
    """Схема ответа с пользователем и его заказами."""

    id: int
    email: str
    name: str
    orders: list[OrderResponse]

    class Config:
        from_attributes = True


class EmailVerifyResponse(BaseModel):
    """Схема ответа проверки email."""

    email: str
    valid: bool
