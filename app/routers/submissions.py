from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.submission import Submission
from app.models.assignment import Assignment
from app.models.user import User
from app.schemas.schemas import SubmissionOut, SubmissionDetail, GradeRequest, UserOut, AssignmentOut
from app.routers.assignments import upload_to_supabase

router = APIRouter()


# ── GET /submissions ─────────────────────────────────────────
@router.get("/", response_model=list[SubmissionDetail])
async def list_submissions(
    assignment_id: str = None,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    q = select(Submission)

    if current.role == "student":
        q = q.where(Submission.student_id == current.id)
    elif current.role == "teacher":
        # Faqat o'z topshiriqlari uchun
        teacher_assigns = await db.execute(
            select(Assignment.id).where(Assignment.teacher_id == current.id)
        )
        ids = [r[0] for r in teacher_assigns.all()]
        q = q.where(Submission.assignment_id.in_(ids))

    if assignment_id:
        q = q.where(Submission.assignment_id == assignment_id)

    result = await db.execute(q.order_by(Submission.submitted_at.desc()))
    subs = result.scalars().all()

    out = []
    for s in subs:
        student_res = await db.execute(select(User).where(User.id == s.student_id))
        student = student_res.scalar_one_or_none()
        assign_res = await db.execute(select(Assignment).where(Assignment.id == s.assignment_id))
        assign = assign_res.scalar_one_or_none()
        out.append(SubmissionDetail(
            **SubmissionOut.model_validate(s).model_dump(),
            student=UserOut.model_validate(student) if student else None,
            assignment=AssignmentOut.model_validate(assign) if assign else None,
        ))
    return out


# ── POST /submissions ────────────────────────────────────────
@router.post("/", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def submit_work(
    assignment_id: str = Form(...),
    comment: str = Form(""),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_role("student")),
):
    # Topshiriq mavjudligini tekshirish
    assign_res = await db.execute(select(Assignment).where(Assignment.id == assignment_id))
    assignment = assign_res.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi")
    if assignment.group_id != current.group_id:
        raise HTTPException(status_code=403, detail="Bu topshiriq sizning guruhingiz uchun emas")

    # Takror topshirishni oldini olish
    dup = await db.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == current.id,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Bu topshiriq allaqachon topshirilgan")

    # Faylni Supabase ga yuklash
    file_name, file_url = await upload_to_supabase(file, f"submissions/{current.id}")

    sub = Submission(
        assignment_id=assignment_id,
        student_id=current.id,
        file_name=file_name,
        file_url=file_url,
        comment=comment,
        status="pending",
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return SubmissionOut.model_validate(sub)


# ── PATCH /submissions/{id}/grade ────────────────────────────
@router.patch("/{submission_id}/grade", response_model=SubmissionOut)
async def grade_submission(
    submission_id: str,
    body: GradeRequest,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_role("teacher")),
):
    from datetime import date
    res = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = res.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Topshirilgan ish topilmadi")

    # Bu o'qituvchining topshirig'i ekanligini tekshirish
    assign_res = await db.execute(select(Assignment).where(Assignment.id == sub.assignment_id))
    assignment = assign_res.scalar_one_or_none()
    if not assignment or assignment.teacher_id != current.id:
        raise HTTPException(status_code=403, detail="Bu sizning topshirig'ingiz emas")

    if body.grade < 0 or body.grade > assignment.max_score:
        raise HTTPException(status_code=400, detail=f"Baho 0 dan {assignment.max_score} gacha bo'lishi kerak")

    sub.grade         = body.grade
    sub.grade_comment = body.grade_comment
    sub.status        = body.status
    sub.graded_at     = date.today()

    await db.commit()
    await db.refresh(sub)
    return SubmissionOut.model_validate(sub)


# ── GET /submissions/{id} ────────────────────────────────────
@router.get("/{submission_id}", response_model=SubmissionDetail)
async def get_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    res = await db.execute(select(Submission).where(Submission.id == submission_id))
    sub = res.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Topilmadi")

    if current.role == "student" and sub.student_id != current.id:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")

    student_res = await db.execute(select(User).where(User.id == sub.student_id))
    student = student_res.scalar_one_or_none()
    assign_res = await db.execute(select(Assignment).where(Assignment.id == sub.assignment_id))
    assign = assign_res.scalar_one_or_none()

    return SubmissionDetail(
        **SubmissionOut.model_validate(sub).model_dump(),
        student=UserOut.model_validate(student) if student else None,
        assignment=AssignmentOut.model_validate(assign) if assign else None,
    )
