"""
python seed.py  — dastlabki admin va demo ma'lumotlarni yaratadi
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

# .env ni o'qish
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/eduportal")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def seed():
    from app.core.database import Base
    from app.models.user import User
    from app.models.group import Group
    from app.models import user, group, assignment, submission  # noqa

    # Jadvallarni yaratish
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.core.security import hash_password

    async with SessionLocal() as db:
        # Admin mavjudmi?
        res = await db.execute(select(User).where(User.login == "admin"))
        if res.scalar_one_or_none():
            print("✓ Seed allaqachon bajarilgan.")
            return

        # Admin
        admin = User(fname="Super", lname="Admin", login="admin",
                     password=hash_password("admin123"), role="admin")
        db.add(admin)

        # O'qituvchi
        teacher = User(fname="Ulugbek", lname="Abdullayev", login="teacher1",
                       password=hash_password("teacher123"), role="teacher", subject="Informatika")
        db.add(teacher)

        # Talabalar
        students = [
            User(fname="Ali",    lname="Karimov",  login="student1", password=hash_password("student123"), role="student"),
            User(fname="Malika", lname="Nazarova", login="student2", password=hash_password("pass456"),    role="student"),
            User(fname="Jasur",  lname="Yusupov",  login="student3", password=hash_password("pass789"),    role="student"),
        ]
        for s in students:
            db.add(s)

        await db.flush()  # ID larni olish uchun

        # Guruh
        group_obj = Group(name="CS-21", dept="Kompyuter fanlari", teacher_id=teacher.id)
        db.add(group_obj)
        await db.flush()

        # Guruhga biriktirish
        teacher.group_id = group_obj.id
        for s in students:
            s.group_id = group_obj.id

        await db.commit()
        print("✓ Seed muvaffaqiyatli bajarildi!")
        print("  Admin:     admin / admin123")
        print("  O'qituvchi: teacher1 / teacher123")
        print("  Talaba:    student1 / student123")


if __name__ == "__main__":
    asyncio.run(seed())
