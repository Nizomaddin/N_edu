from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator


# ───────────── AUTH ─────────────
class LoginRequest(BaseModel):
    login: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ───────────── USER ─────────────
class UserCreate(BaseModel):
    fname:    str
    lname:    str
    login:    str
    password: str
    role:     str          # admin | teacher | student
    subject:  Optional[str] = ""
    group_id: Optional[str] = None

    @field_validator("role")
    @classmethod
    def role_valid(cls, v):
        if v not in ("admin", "teacher", "student"):
            raise ValueError("Rol: admin, teacher yoki student bo'lishi kerak")
        return v

class UserUpdate(BaseModel):
    fname:    Optional[str] = None
    lname:    Optional[str] = None
    password: Optional[str] = None
    subject:  Optional[str] = None
    group_id: Optional[str] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id:         str
    fname:      str
    lname:      str
    login:      str
    role:       str
    subject:    str
    group_id:   Optional[str]
    is_active:  bool
    created_at: datetime

    model_config = {"from_attributes": True}

class UserBulkItem(BaseModel):
    fname:    str
    lname:    str
    login:    str
    password: str
    role:     str
    subject:  Optional[str] = ""
    group_id: Optional[str] = None

class UserBulkCreate(BaseModel):
    users: List[UserBulkItem]


# ───────────── GROUP ─────────────
class GroupCreate(BaseModel):
    name:       str
    dept:       Optional[str] = ""
    teacher_id: Optional[str] = None

class GroupUpdate(BaseModel):
    name:        Optional[str] = None
    dept:        Optional[str] = None
    teacher_id:  Optional[str] = None
    student_ids: Optional[List[str]] = None

class GroupOut(BaseModel):
    id:         str
    name:       str
    dept:       str
    teacher_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

class GroupDetail(GroupOut):
    teacher:  Optional[UserOut]
    students: List[UserOut]
    assignment_count: int


# ───────────── ASSIGNMENT ─────────────
class AssignmentCreate(BaseModel):
    title:       str
    subject:     str
    description: str
    max_score:   int = 100
    due_date:    date
    group_id:    str

class AssignmentOut(BaseModel):
    id:          str
    title:       str
    subject:     str
    description: str
    max_score:   int
    due_date:    date
    teacher_id:  str
    group_id:    str
    file_name:   Optional[str]
    file_url:    Optional[str]
    created_at:  datetime

    model_config = {"from_attributes": True}

class AssignmentDetail(AssignmentOut):
    teacher:          UserOut
    submitted_count:  int
    student_count:    int


# ───────────── SUBMISSION ─────────────
class SubmissionOut(BaseModel):
    id:            str
    assignment_id: str
    student_id:    str
    file_name:     Optional[str]
    file_url:      Optional[str]
    comment:       str
    status:        str
    grade:         Optional[int]
    grade_comment: Optional[str]
    graded_at:     Optional[date]
    submitted_at:  datetime

    model_config = {"from_attributes": True}

class SubmissionDetail(SubmissionOut):
    student:    UserOut
    assignment: AssignmentOut

class GradeRequest(BaseModel):
    grade:         int
    grade_comment: Optional[str] = ""
    status:        str = "graded"


# ───────────── STATS ─────────────
class DashboardStats(BaseModel):
    total_users:    int
    total_teachers: int
    total_students: int
    total_groups:   int
    total_assignments: int
    total_submissions: int

TokenResponse.model_rebuild()
