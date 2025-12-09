# Главный файл приложения
from fastapi import FastAPI
from routers import tasks, stats

app = FastAPI(
    title="ToDo лист API",
    description="API для управления задачами с использованием матрицы Эйзенхауэра",
    version="1.0.0",
    contact={
        "name": "Позолотина Лина",
    }
)

app.include_router(tasks.router, prefix="/api/v1")#подключение роутера к приложению
app.include_router(stats.router, prefix="/api/v1")

@app.get("/")
async def root() -> dict:
    return {
        "title": app.title,
        "version": app.version,
        "contact": app.contact,
        "message": "Привет, студент!"
    }

@app.post("/tasks")
async def create_task(task:dict):
    return {"message":"Запись успешно создана!","task": task}