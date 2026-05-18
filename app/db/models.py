from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from app.db.database import Base

class TaskStatus(Base):
    __tablename__ = "task_status"

    id = Column(String, primary_key=True, index=True)
    task_name = Column(String, index=True)
    status = Column(String, default="PENDING")
    result = Column(String, nullable=True)  # JSON string or text
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
