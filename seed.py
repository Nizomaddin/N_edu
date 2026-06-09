"""
python seed.py — dastlabki admin va demo ma'lumotlarni yaratadi
To'g'ridan-to'g'ri asyncpg orqali (SQLAlchemy pooler muammosini bypass qiladi)
"""
import asyncio
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

# Parol va ulanish
HOST = "aws-1-ap-south-1.pooler.supabase.com"
PORT = 6543
USER = "postgres.ykyavqikndorzoaglkop"
PASS = os.getenv("DB_PASSWORD", "Nizomaddin2026")
DB   = "postgres"


async def seed():
    import asyncpg

    conn = await asyncpg.connect(
        host=HOST, port=PORT, user=USER, password=PASS, database=DB,
        ssl="require", statement_cache_size=0
    )
    print("✓ Bazaga ulandi!")

    try:
        # Jadvallarni yaratish
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                dept TEXT DEFAULT '',
                teacher_id TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                fname TEXT NOT NULL,
                lname TEXT NOT NULL,
                login TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                subject TEXT DEFAULT '',
                group_id TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                max_score INTEGER DEFAULT 100,
                due_date DATE NOT NULL,
                teacher_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                file_name TEXT,
                file_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                file_name TEXT,
                file_url TEXT,
                comment TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                grade INTEGER,
                grade_comment TEXT,
                graded_at DATE,
                submitted_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("✓ Jadvallar yaratildi!")

        # Admin mavjudmi?
        existing = await conn.fetchrow("SELECT id FROM users WHERE login = 'admin'")
        if existing:
            print("✓ Seed allaqachon bajarilgan.")
            return

        # Bcrypt hash (oddiy usul)
        from passlib.context import CryptContext
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

        admin_id   = str(uuid.uuid4())
        teacher_id = str(uuid.uuid4())
        s1_id = str(uuid.uuid4())
        s2_id = str(uuid.uuid4())
        s3_id = str(uuid.uuid4())
        group_id   = str(uuid.uuid4())

        # Admin
        await conn.execute(
            "INSERT INTO users (id,fname,lname,login,password,role) VALUES ($1,$2,$3,$4,$5,$6)",
            admin_id, "Super", "Admin", "admin", pwd.hash("admin123"), "admin"
        )

        # O'qituvchi
        await conn.execute(
            "INSERT INTO users (id,fname,lname,login,password,role,subject) VALUES ($1,$2,$3,$4,$5,$6,$7)",
            teacher_id, "Ulugbek", "Abdullayev", "teacher1", pwd.hash("teacher123"), "teacher", "Informatika"
        )

        # Guruh
        await conn.execute(
            "INSERT INTO groups (id,name,dept,teacher_id) VALUES ($1,$2,$3,$4)",
            group_id, "CS-21", "Kompyuter fanlari", teacher_id
        )

        # Teacher group_id
        await conn.execute("UPDATE users SET group_id=$1 WHERE id=$2", group_id, teacher_id)

        # Talabalar
        students = [
            (s1_id, "Ali",    "Karimov",  "student1", pwd.hash("student123")),
            (s2_id, "Malika", "Nazarova", "student2", pwd.hash("pass456")),
            (s3_id, "Jasur",  "Yusupov",  "student3", pwd.hash("pass789")),
        ]
        for sid, fname, lname, login, hpass in students:
            await conn.execute(
                "INSERT INTO users (id,fname,lname,login,password,role,group_id) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                sid, fname, lname, login, hpass, "student", group_id
            )

        print("✓ Seed muvaffaqiyatli bajarildi!")
        print("  Admin:      admin / admin123")
        print("  O'qituvchi: teacher1 / teacher123")
        print("  Talaba:     student1 / student123")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())