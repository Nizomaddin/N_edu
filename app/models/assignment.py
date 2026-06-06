import uuid
from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Assignment(Base):
    __tablename__ = "assignments"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title       = Column(String(200), nullable=False)
    subject     = Column(String(100), nullable=False)
    description = Column(String(2000), nullable=False)
    max_score   = Column(Integer, default=100)
    due_date    = Column(Date, nullable=False)
    teacher_id  = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    group_id    = Column(String, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    file_name   = Column(String(255), nullable=True)
    file_url    = Column(String(500), nullable=True)   # Supabase Storage URL
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    teacher     = relationship("User", back_populates="assignments",
                               foreign_keys=[teacher_id])
    submissions = relationship("Submission", back_populates="assignment",
                               cascade="all, delete-orphan")
