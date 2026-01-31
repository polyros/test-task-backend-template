"""Тесты для API пользователей."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# Тестовая БД в памяти
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override dependency для тестов."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Создание таблиц перед каждым тестом."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """TestClient для запросов."""
    return TestClient(app)


def test_create_user(client):
    """Тест создания пользователя с валидными данными."""
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "password": "securepassword123",
            "name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert "password" not in data  # Пароль не должен возвращаться


def test_create_user_invalid_email(client):
    """Тест ошибки при невалидном email."""
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "not-an-email",
            "password": "securepassword123",
            "name": "Test User",
        },
    )
    assert response.status_code == 422  # Validation error


def test_get_user_not_found(client):
    """Тест 404 при запросе несуществующего пользователя."""
    response = client.get("/api/v1/users/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_search_users_sql_injection(client):
    """Тест защиты от SQL injection."""
    # Создаём тестового пользователя
    client.post(
        "/api/v1/users/",
        json={
            "email": "victim@example.com",
            "password": "password123",
            "name": "Victim",
        },
    )

    # Пытаемся выполнить SQL injection
    response = client.get("/api/v1/users/search?email=' OR '1'='1")
    assert response.status_code == 200

    # При SQL injection вернулись бы все пользователи
    # При правильной защите - только те, что содержат строку поиска
    data = response.json()
    # Не должно быть пользователя victim, т.к. его email не содержит "' OR '1'='1"
    emails = [u["email"] for u in data]
    assert "victim@example.com" not in emails
