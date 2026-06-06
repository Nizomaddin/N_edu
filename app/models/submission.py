import uuid
from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    assignment_id = Column(String, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id    = Column(String, ForeignKey("users.id",       ondelete="CASCADE"), nullable=False)
    file_name     = Column(String(255), nullable=True)
    file_url      = Column(String(500), nullable=True)   # Supabase Storage URL
    comment       = Column(String(1000), default="")
    status        = Column(String(20), default="pending")  # pending | graded | done | late
    grade         = Column(Integer, nullable=True)
    grade_comment = Column(String(500), nullable=True)
    graded_at     = Column(Date, nullable=True)
    submitted_at  = Column(DateTime(timezone=True), server_default=func.now())

    assignment    = relationship("Assignment", back_populates="submissions")
    student       = relationship("User", back_populates="submissions",
                                 foreign_keys=[student_id])
