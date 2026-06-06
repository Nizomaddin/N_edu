import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fname      = Column(String(100), nullable=False)
    lname      = Column(String(100), nullable=False)
    login      = Column(String(50), unique=True, nullable=False, index=True)
    password   = Column(String(255), nullable=False)
    role       = Column(String(20), nullable=False)   # admin | teacher | student
    subject    = Column(String(100), default="")
    group_id   = Column(String, nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    assignments = relationship("Assignment", back_populates="teacher",
                               foreign_keys="Assignment.teacher_id")
    submissions = relationship("Submission", back_populates="student",
                               foreign_keys="Submission.student_id")
