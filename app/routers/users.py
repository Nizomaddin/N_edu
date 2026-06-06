from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user, require_role, hash_password
from app.models.user import User
from app.schemas.schemas import UserCreate, UserUpdate, UserOut, UserBulkCreate, DashboardStats

router = APIRouter()

AdminOnly    = Depends(require_role("admin"))
AdminTeacher = Depends(require_role("admin", "teacher"))


# ── GET /users ──────────────────────────────────────────────
@router.get("/", response_model=list[UserOut])
async def list_users(
    role:     Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    search:   Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    q = select(User)
    if role:     q = q.where(User.role == role)
    if group_id: q = q.where(User.group_id == group_id)
    if search:
        like = f"%{search}%"
        q = q.where((User.fname.ilike(like)) | (User.lname.ilike(like)) | (User.login.ilike(like)))
    result = await db.execute(q.order_by(User.created_at.desc()))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


# ── POST /users ─────────────────────────────────────────────
@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    dup = await db.execute(select(User).where(User.login == body.login))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"'{body.login}' login allaqachon mavjud")

    user = User(
        fname=body.fname, lname=body.lname,
        login=body.login, password=hash_password(body.password),
        role=body.role, subject=body.subject or "",
        group_id=body.group_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


# ── POST /users/bulk ─────────────────────────────────────────
@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_create_users(
    body: UserBulkCreate,
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    """Excel import uchun — bir nechta foydalanuvchi bir vaqtda"""
    added, updated, skipped = [], [], []

    for item in body.users:
        dup = await db.execute(select(User).where(User.login == item.login))
        existing = dup.scalar_one_or_none()

        if existing:
            existing.fname    = item.fname
            existing.lname    = item.lname
            existing.password = hash_password(item.password)
            if item.subject:  existing.subject  = item.subject
            if item.group_id: existing.group_id = item.group_id
            updated.append(item.login)
        else:
            user = User(
                fname=item.fname, lname=item.lname,
                login=item.login, password=hash_password(item.password),
                role=item.role, subject=item.subject or "",
                group_id=item.group_id,
            )
            db.add(user)
            added.append(item.login)

    await db.commit()
    return {"added": len(added), "updated": len(updated), "logins_added": added, "logins_updated": updated}


# ── GET /users/stats ─────────────────────────────────────────
@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db), _=AdminOnly):
    from app.models.group import Group
    from app.models.assignment import Assignment
    from app.models.submission import Submission

    async def count(model, **filters):
        q = select(func.count()).select_from(model)
        for col, val in filters.items():
            q = q.where(getattr(model, col) == val)
        return (await db.execute(q)).scalar()

    return DashboardStats(
        total_users       = await count(User),
        total_teachers    = await count(User, role="teacher"),
        total_students    = await count(User, role="student"),
        total_groups      = await count(Group),
        total_assignments = await count(Assignment),
        total_submissions = await count(Submission),
    )


# ── GET /users/{id} ──────────────────────────────────────────
@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    # Foydalanuvchi o'zini yoki admin barchani ko'ra oladi
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return UserOut.model_validate(user)


# ── PATCH /users/{id} ────────────────────────────────────────
@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")

    if body.fname:     user.fname    = body.fname
    if body.lname:     user.lname    = body.lname
    if body.password:  user.password = hash_password(body.password)
    if body.subject is not None:  user.subject  = body.subject
    if body.group_id  is not None: user.group_id = body.group_id
    if body.is_active is not None: user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


# ── DELETE /users/{id} ───────────────────────────────────────
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_role("admin")),
):
    if current.id == user_id:
        raise HTTPException(status_code=400, detail="O'zingizni o'chira olmaysiz")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    await db.delete(user)
    await db.commit()
