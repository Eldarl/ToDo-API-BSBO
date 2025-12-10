from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from models import Task, User
from models.user import UserRole
from database import get_async_session
from dependencies import get_current_user


router = APIRouter(
    prefix="/stats",
    tags=["statistics"]
)

@router.get("/", response_model=dict)
async def get_tasks_stats(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> dict:
    query = select(Task)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Task.user_id == current_user.id)

    result = await db.execute(query)
    tasks = result.scalars().all()

    total_tasks = len(tasks)
    by_quadrant = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    by_status = {"completed": 0, "pending": 0}

    for task in tasks:
        by_quadrant[task.quadrant] = by_quadrant.get(task.quadrant, 0) + 1
        if task.completed:
            by_status["completed"] += 1
        else:
            by_status["pending"] += 1

    return {
        "total_tasks": total_tasks,
        "by_quadrant": by_quadrant,
        "by_status": by_status
    }

@router.get("/deadlines", response_model=dict)
async def get_pending_tasks_with_deadlines(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> dict:
    query = select(Task).where(Task.completed == False, Task.deadline_at.isnot(None))
    if current_user.role != UserRole.ADMIN:
        query = query.where(Task.user_id == current_user.id)

    result = await db.execute(query)
    tasks = result.scalars().all()

    pending_with_deadlines = []
    for task in tasks:
        days_left = (task.deadline_at - task.created_at).days if task.deadline_at and task.created_at else None
        pending_with_deadlines.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "deadline_at": task.deadline_at,
            "days_until_deadline": (task.deadline_at - task.created_at).days if task.deadline_at else None
        })

    return {
        "total_pending_with_deadlines": len(pending_with_deadlines),
        "tasks": pending_with_deadlines
    }