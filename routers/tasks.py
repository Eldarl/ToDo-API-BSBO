from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Response, status
from typing import List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select
from schemas import TaskBase, TaskCreate, TaskUpdate, TaskResponse
from models import Task
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_async_session

router = APIRouter(
    prefix="/tasks", 
    tags=["tasks"],
    responses={404: {"description": "Task not found"}},
)

#  Создание задачи ---
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_async_session)) -> TaskResponse:
    # Создаём задачу
    new_task = Task(
        title=task.title,
        description=task.description,
        is_important=task.is_important,
        deadline_at=task.deadline_at,  # Сохраняем дедлайн
        completed=False
    )

    # Рассчитываем квадрант на основе is_important и is_urgent (свойство)
    # Это произойдёт автоматически при обращении к new_task.quadrant
    # Но для надёжности — явно установим:
    if new_task.is_important and new_task.is_urgent:
        new_task.quadrant = "Q1"
    elif new_task.is_important and not new_task.is_urgent:
        new_task.quadrant = "Q2"
    elif not new_task.is_important and new_task.is_urgent:
        new_task.quadrant = "Q3"
    else:
        new_task.quadrant = "Q4"

    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    return new_task

@router.get("", response_model=List[TaskResponse])
async def get_all_tasks(
 # Сессия базы данных (автоматически через Depends
    db: AsyncSession = Depends(get_async_session)) -> List[TaskResponse]: 
    result = await db.execute(select(Task)) # Выполняем SELECT запрос
    tasks = result.scalars().all() # Получаем все объекты # FastAPI автоматически преобразует Task → TaskResponse
    return tasks

@router.get("/quadrant/{quadrant}",
            response_model=List[TaskResponse])
async def get_tasks_by_quadrant(
    quadrant: str,
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException(
            status_code=400,
            detail="Неверный квадрант. Используйте: Q1, Q2, Q3, Q4" # текст, который будет выведен пользователю
        )
    # SELECT * FROM tasks WHERE quadrant = 'Q1'
    result = await db.execute(
        select(Task).where(Task.quadrant == quadrant)
    )
    tasks = result.scalars().all()
    return tasks


@router.get("/search", response_model=List[TaskResponse])
async def search_tasks(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    keyword = f"%{q.lower()}%" # %keyword% для LIKE
    # SELECT * FROM tasks
    # WHERE LOWER(title) LIKE '%keyword%'
    # OR LOWER(description) LIKE '%keyword%'
    result = await db.execute(
        select(Task).where(
            (Task.title.ilike(keyword)) |
            (Task.description.ilike(keyword))
        )
    )
    tasks = result.scalars().all()
    if not tasks:
        raise HTTPException(status_code=404, detail="По данному запросу ничего не найдено")
    return tasks

@router.get("/status/{status}", response_model=List[TaskResponse])
async def get_tasks_by_status(status: str,
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    if status not in ["completed", "pending"]:
        raise HTTPException(status_code=404, detail="Недопустимый статус. Используйте: completed или pending")
 
    is_completed = (status == "completed")
    # SELECT * FROM tasks WHERE completed = True/False
    result = await db.execute(
        select(Task).where(Task.completed == is_completed)
    )

    tasks = result.scalars().all()
    return tasks

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    # SELECT * FROM tasks WHERE id = task_id
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    # Получаем одну задачу или None
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate, db: AsyncSession = Depends(get_async_session)) -> TaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    update_data = task_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    # Пересчитываем квадрант, если изменилась важность или дедлайн (что влияет на is_urgent)
    if "is_important" in update_data or "deadline_at" in update_data:
        if task.is_important and task.is_urgent:
            task.quadrant = "Q1"
        elif task.is_important and not task.is_urgent:
            task.quadrant = "Q2"
        elif not task.is_important and task.is_urgent:
            task.quadrant = "Q3"
        else:
            task.quadrant = "Q4"

    await db.commit()
    await db.refresh(task)

    return task

@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
 )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    # Сохраняем информацию для ответа
    deleted_task_info = {
        "id": task.id,
        "title": task.title
    }
    await db.delete(task) # Помечаем для удаления
    await db.commit() # DELETE FROM tasks WHERE id = task_id
    return {
        "message": "Задача успешно удалена",
        "id": deleted_task_info["id"],
        "title": deleted_task_info["title"]
    }

@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
 task_id: int,
 db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
 )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    task.completed = True
    task.completed_at = datetime.now()

    await db.commit()
    await db.refresh(task)

    return task
