import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.assignment import Assignment
from app.models.submission import Submission
from app.models.user import User
from app.schemas.schemas import AssignmentCreate, AssignmentOut, AssignmentDetail, UserOut

router = APIRouter()

SUPABASE_URL    = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY    = os.getenv("SUPABASE_SERVICE_KEY", "")
STORAGE_BUCKET  = "assignments"


async def upload_to_supabase(file: UploadFile, folder: str) -> tuple[str, str]:
    """Faylni Supabase Storage ga yuklash, (file_name, public_url) qaytaradi"""
    import httpx, uuid
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    storage_path = f"{folder}/{uuid.uuid4().hex}.{ext}"
    content = await file.read()

    url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": file.content_type or "application/octet-stream",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, content=content, headers=headers)
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"Fayl yuklashda xato: {resp.text}")

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"
    return file.filename, public_url


# ── GET /assignments ─────────────────────────────────────────
@router.get("/", response_model=list[AssignmentOut])
async def list_assignments(
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    q = select(Assignment)
    if current.role == "teacher":
        q = q.where(Assignment.teacher_id == current.id)
    elif current.role == "student":
        q = q.where(Assignment.group_id == current.group_id)
    result = await db.execute(q.order_by(Assignment.created_at.desc()))
    return [AssignmentOut.model_validate(a) for a in result.scalars().all()]


# ── POST /assignments ────────────────────────────────────────
@router.post("/", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    title:       str = Form(...),
    subject:     str = Form(...),
    description: str = Form(...),
    max_score:   int = Form(100),
    due_date:    str = Form(...),
    group_id:    str = Form(...),
    file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_role("teacher")),
):
    from datetime import date
    file_name, file_url = None, None
    if file and file.filename:
        file_name, file_url = await upload_to_supabase(file, f"assignments/{current.id}")

    assignment = Assignment(
        title=title, subject=subject, description=description,
        max_score=max_score, due_date=date.fromisoformat(due_date),
        teacher_id=current.id, group_id=group_id,
        file_name=file_name, file_url=file_url,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return AssignmentOut.model_validate(assignment)


# ── GET /assignments/{id} ────────────────────────────────────
@router.get("/{assignment_id}", response_model=AssignmentDetail)
async def get_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    res = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    a = res.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")

    teacher_res = await db.execute(select(User).where(User.id == a.teacher_id))
    teacher = teacher_res.scalar_one_or_none()

    sub_count = (await db.execute(
        select(func.count()).select_from(Submission).where(Submission.assignment_id == assignment_id)
    )).scalar()

    student_count = (await db.execute(
        select(func.count()).select_from(User)
        .where(User.group_id == a.group_id, User.role == "student")
    )).scalar()

    return AssignmentDetail(
        **AssignmentOut.model_validate(a).model_dump(),
        teacher=UserOut.model_validate(teacher) if teacher else None,
        submitted_count=sub_count,
        student_count=student_count,
    )


# ── DELETE /assignments/{id} ─────────────────────────────────
@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_role("teacher", "admin")),
):
    res = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    a = res.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Topilmadi")
    if current.role == "teacher" and a.teacher_id != current.id:
        raise HTTPException(status_code=403, detail="Bu sizning topshirig'ingiz emas")
    await db.delete(a)
    await db.commit()
