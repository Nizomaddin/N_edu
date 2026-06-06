from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.group import Group
from app.models.user import User
from app.models.assignment import Assignment
from app.schemas.schemas import GroupCreate, GroupUpdate, GroupOut, GroupDetail, UserOut

router = APIRouter()
AdminOnly = Depends(require_role("admin"))


@router.get("/", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    result = await db.execute(select(Group).order_by(Group.created_at.desc()))
    return [GroupOut.model_validate(g) for g in result.scalars().all()]


@router.post("/", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    group = Group(name=body.name, dept=body.dept or "", teacher_id=body.teacher_id)
    db.add(group)
    await db.commit()
    await db.refresh(group)

    # O'qituvchini guruhga biriktirish
    if body.teacher_id:
        res = await db.execute(select(User).where(User.id == body.teacher_id))
        teacher = res.scalar_one_or_none()
        if teacher:
            teacher.group_id = group.id
            await db.commit()

    return GroupOut.model_validate(group)


@router.get("/{group_id}", response_model=GroupDetail)
async def get_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    res = await db.execute(select(Group).where(Group.id == group_id))
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")

    teacher = None
    if group.teacher_id:
        tr = await db.execute(select(User).where(User.id == group.teacher_id))
        teacher = tr.scalar_one_or_none()

    students_res = await db.execute(
        select(User).where(User.group_id == group_id, User.role == "student")
    )
    students = students_res.scalars().all()

    assign_count = (await db.execute(
        select(func.count()).select_from(Assignment).where(Assignment.group_id == group_id)
    )).scalar()

    return GroupDetail(
        **GroupOut.model_validate(group).model_dump(),
        teacher=UserOut.model_validate(teacher) if teacher else None,
        students=[UserOut.model_validate(s) for s in students],
        assignment_count=assign_count,
    )


@router.patch("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: str,
    body: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    res = await db.execute(select(Group).where(Group.id == group_id))
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Topilmadi")

    if body.name is not None:       group.name = body.name
    if body.dept is not None:       group.dept = body.dept
    if body.teacher_id is not None:
        # Avvalgi o'qituvchidan guruhni olib, yangisiga berish
        if group.teacher_id and group.teacher_id != body.teacher_id:
            old_t = await db.execute(select(User).where(User.id == group.teacher_id))
            old_teacher = old_t.scalar_one_or_none()
            if old_teacher and old_teacher.group_id == group_id:
                old_teacher.group_id = None
        group.teacher_id = body.teacher_id
        new_t = await db.execute(select(User).where(User.id == body.teacher_id))
        new_teacher = new_t.scalar_one_or_none()
        if new_teacher:
            new_teacher.group_id = group_id

    # Talabalarni yangilash
    if body.student_ids is not None:
        # Avvalgi talabalardan guruhni olib tashlash
        old_students = await db.execute(
            select(User).where(User.group_id == group_id, User.role == "student")
        )
        for s in old_students.scalars().all():
            s.group_id = None

        # Yangi talabalarni biriktirish
        for sid in body.student_ids:
            sr = await db.execute(select(User).where(User.id == sid))
            student = sr.scalar_one_or_none()
            if student:
                student.group_id = group_id

    await db.commit()
    await db.refresh(group)
    return GroupOut.model_validate(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    res = await db.execute(select(Group).where(Group.id == group_id))
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Topilmadi")

    # Foydalanuvchilardan guruhni olib tashlash
    members = await db.execute(select(User).where(User.group_id == group_id))
    for u in members.scalars().all():
        u.group_id = None

    await db.delete(group)
    await db.commit()
