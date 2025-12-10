from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base
from datetime import datetime, timezone

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    is_important = Column(Boolean, nullable=False, default=False)
    # is_urgent больше не хранится, рассчитывается
    quadrant = Column(String(2), nullable=False)
    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)  # Новое поле

    @property
    def is_urgent(self) -> bool:
        """Рассчитывает срочность на основе дедлайна"""
        if not self.deadline_at:
            return False
        today = datetime.now(timezone.utc)  # Убедитесь, что используется UTC
        days_left = (self.deadline_at - today).days
        return days_left <= 3

    @property
    def days_until_deadline(self) -> int:
        """Возвращает количество дней до дедлайна (отрицательное — если просрочено)"""
        if not self.deadline_at:
            return None
        today = datetime.now(timezone.utc)
        return (self.deadline_at - today).days

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "is_important": self.is_important,
            "is_urgent": self.is_urgent,  # Расчётное поле
            "quadrant": self.quadrant,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "deadline_at": self.deadline_at,
            "days_until_deadline": self.days_until_deadline  # Расчётное поле
        }

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', quadrant='{self.quadrant}')>"