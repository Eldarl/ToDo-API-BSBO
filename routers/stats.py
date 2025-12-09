from fastapi import APIRouter, HTTPException, Query
from fastapi import Response, status
from database import tasks_db
from typing import List, Dict, Any
from datetime import datetime

router = APIRouter(
    prefix="/stats", 
    tags=["stats"],
    responses={404: {"description":"Task not found"}},
)

@router.get("")
async def get_tasks_stats() -> dict: 
    return{
        "count": len(tasks_db), #считает кол-во записей в хранилище
        "tasks": tasks_db #выводит все, что есть в хранилище
    }

@router.get("/stats")
async def get_tasks_stats() -> Dict[str, Any]: 
    #Получает статистику по всем задачам.

    total_tasks = len(tasks_db)
    completed_tasks = sum(1 for task in tasks_db if task.get("completed", False))

    # Считаем количество задач по квадрантам
    quadrants = Counter(task["quadrant"] for task in tasks_db)

    # Расчёт среднего времени выполнения (если есть завершённые задачи с датами)
    completed_with_time = [
        task for task in tasks_db
        if task.get("completed") and task.get("completed_at") and task.get("created_at")
    ]
    avg_completion_time_seconds = None
    if completed_with_time:
        total_seconds = sum(
            (task["completed_at"] - task["created_at"]).total_seconds()
            for task in completed_with_time
        )
        avg_completion_time_seconds = round(total_seconds / len(completed_with_time), 2)

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": total_tasks - completed_tasks,
        "quadrant_distribution": dict(quadrants),
        "average_completion_time_seconds": avg_completion_time_seconds,
        "timestamp": datetime.now().isoformat()
    }