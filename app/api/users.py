"""API endpoints для работы с пользователями."""

import logging
from hashlib import sha256

import bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    EmailVerifyResponse,
    UserCreate,
    UserResponse,
    UserWithOrdersResponse,
)

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, db: Session = Depends(get_db)):
    """Создание нового пользователя."""
    logger.info("Creating user with email=%s", data.email)

    # Хешируем пароль (bcrypt ограничен 72 байтами, используем SHA256 для длинных)
    password_bytes = data.password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = sha256(password_bytes).digest()
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    user = User(
        email=data.email,
        password=hashed_password,
        name=data.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.get("/search", response_model=list[UserResponse])
async def search_users(email: str, db: Session = Depends(get_db)):
    """Поиск пользователей по email."""
    # Используем ORM вместо raw SQL для защиты от SQL injection
    users = db.query(User).filter(User.email.ilike(f"%{email}%")).all()
    return users


@router.get("/{user_id}", response_model=UserWithOrdersResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Получение пользователя с его заказами."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Используем данные из relationship напрямую (без N+1)
    return user


@router.get("/{user_id}/verify-email", response_model=EmailVerifyResponse)
async def verify_email(user_id: int, db: Session = Depends(get_db)):
    """Проверка email через внешний сервис."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Используем async HTTP клиент вместо sync requests
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.emailverifier.com/check?email={user.email}",
                timeout=10.0,
            )
            valid = response.json().get("valid", False)
        except httpx.RequestError:
            valid = False

    return EmailVerifyResponse(email=user.email, valid=valid)
