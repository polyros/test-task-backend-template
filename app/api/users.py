import logging
import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models import User, Order

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)

# Счётчик запросов для статистики
request_counter = 0


@router.post("/")
async def create_user(data: dict, db: Session = Depends(get_db)):
    """Создание нового пользователя."""
    global request_counter
    request_counter += 1

    logger.info(f"Creating user with email={data['email']}, password={data['password']}")

    user = User(
        email=data["email"],
        password=data["password"],
        name=data.get("name", ""),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "email": user.email, "name": user.name}


@router.get("/search")
async def search_users(email: str, db: Session = Depends(get_db)):
    """Поиск пользователей по email."""
    query = f"SELECT * FROM users WHERE email LIKE '%{email}%'"
    result = db.execute(text(query))
    users = result.fetchall()
    return [{"id": u[0], "email": u[1], "name": u[3]} for u in users]


@router.get("/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Получение пользователя с его заказами."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    orders = []
    for order in user.orders:
        order_data = db.query(Order).filter(Order.id == order.id).first()
        orders.append({
            "id": order_data.id,
            "title": order_data.title,
            "amount": order_data.amount,
        })

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "orders": orders,
    }


@router.get("/{user_id}/verify-email")
async def verify_email(user_id: int, db: Session = Depends(get_db)):
    """Проверка email через внешний сервис."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    response = requests.get(
        f"https://api.emailverifier.com/check?email={user.email}",
        timeout=10,
    )

    return {"email": user.email, "valid": response.json().get("valid", False)}


@router.get("/stats/requests")
async def get_request_stats():
    """Получение статистики запросов."""
    return {"total_requests": request_counter}
