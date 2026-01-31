from fastapi import FastAPI

from app.database import Base, engine
from app.api.users import router as users_router

# Создание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="User Management API",
    description="API для управления пользователями",
    version="0.1.0",
)

app.include_router(users_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
