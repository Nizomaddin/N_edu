import uuid
from sqlalchemy import Column, String, DateTime, func
from app.core.database import Base


class Group(Base):
    __tablename__ = "groups"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name       = Column(String(50), nullable=False)
    dept       = Column(String(100), default="")
    teacher_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
