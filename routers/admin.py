from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models import User, Task
from database import get_async_session
from dependencies import get_current_admin
from typing import List

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users", response_model=List[dict])
async def get_all_users_with_task_count(
    db: AsyncSession = Depends(get_async_session),
    admin: User = Depends(get_current_admin)
):
    result = await db.execute(
        select(User, func.count(Task.id).label("task_count"))
        .outerjoin(Task)
        .group_by(User.id)
    )
    return [
        {
            "id": user.id,
            "nickname": user.nickname,
            "email": user.email,
            "role": user.role.value,
            "task_count": task_count
        }
        for user, task_count in result
    ]