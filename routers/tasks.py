from fastapi import APIRouter, HTTPException, Query, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, date
from models import Task, User
from models.user import UserRole
from schemas import TaskCreate, TaskUpdate, TaskResponse
from database import get_async_session
from dependencies import get_current_user

router = APIRouter(
    tags=["tasks"],
    responses={404: {"description": "Task not found"}},
)

# GET ALL TASKS
@router.get("", response_model=List[TaskResponse])
async def get_all_tasks(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    if current_user.role == UserRole.ADMIN:
        result = await db.execute(select(Task))
    else:
        result = await db.execute(select(Task).where(Task.user_id == current_user.id))
    tasks = result.scalars().all()
    return tasks

# GET TASK BY ID
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    # Проверка доступа: админ — всё видит, пользователь — только своё
    if current_user.role != UserRole.ADMIN and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав для доступа к этой задаче")
    
    return task

# GET TASKS BY QUADRANT
@router.get("/quadrant/{quadrant}", response_model=List[TaskResponse])
async def get_tasks_by_quadrant(
    quadrant: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException(status_code=400, detail="Неверный квадрант")
    
    query = select(Task).where(Task.quadrant == quadrant)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Task.user_id == current_user.id)
    
    result = await db.execute(query)
    return result.scalars().all()

# SEARCH TASKS
@router.get("/search", response_model=List[TaskResponse])
async def search_tasks(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    keyword = f"%{q.lower()}%"
    query = select(Task).where(
        (Task.title.ilike(keyword)) | (Task.description.ilike(keyword))
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(Task.user_id == current_user.id)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    if not tasks:
        raise HTTPException(status_code=404, detail="Ничего не найдено")
    return tasks

# GET TASKS BY STATUS
@router.get("/status/{status}", response_model=List[TaskResponse])
async def get_tasks_by_status(
    status: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    if status not in ["completed", "pending"]:
        raise HTTPException(status_code=400, detail="Неверный статус")
    is_completed = (status == "completed")
    
    query = select(Task).where(Task.completed == is_completed)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Task.user_id == current_user.id)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/today", response_model=List[TaskResponse])
async def get_tasks_due_today(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> List[TaskResponse]:
    today = datetime.utcnow().date()
    query = select(Task).where(
        Task.deadline_at.cast(Date) == today,
        Task.completed == False
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(Task.user_id == current_user.id)
    
    result = await db.execute(query)
    return result.scalars().all()

# CREATE TASK
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    # Определяем квадрант
    if task.is_important and task.is_urgent:
        quadrant = "Q1"
    elif task.is_important and not task.is_urgent:
        quadrant = "Q2"
    elif not task.is_important and task.is_urgent:
        quadrant = "Q3"
    else:
        quadrant = "Q4"

    new_task = Task(
        title=task.title,
        description=task.description,
        is_important=task.is_important,
        is_urgent=task.is_urgent,
        quadrant=quadrant,
        completed=False,
        user_id=current_user.id  # ← привязка к пользователю
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task

# UPDATE TASK
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if current_user.role != UserRole.ADMIN and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав для редактирования этой задачи")

    update_data = task_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    if "is_important" in update_data or "is_urgent" in update_data:
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

# COMPLETE TASK
@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> TaskResponse:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if current_user.role != UserRole.ADMIN and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    task.completed = True
    task.completed_at = datetime.now()
    await db.commit()
    await db.refresh(task)
    return task

# DELETE TASK
@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if current_user.role != UserRole.ADMIN and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Недостаточно прав для удаления")

    await db.delete(task)
    await db.commit()
    return {"message": "Задача удалена", "id": task_id}