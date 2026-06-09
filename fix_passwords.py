import asyncio
import asyncpg
import bcrypt

DB_URL = "postgresql://postgres.ykyavqikndorzoaglkop:Nizomaddin2026@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"

async def fix():
    conn = await asyncpg.connect(DB_URL, ssl="require", statement_cache_size=0)
    users = [
        ("admin",    "admin123"),
        ("teacher1", "teacher123"),
        ("student1", "student123"),
        ("student2", "pass456"),
        ("student3", "pass789"),
    ]
    for login, password in users:
        h = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await conn.execute("UPDATE users SET password=$1 WHERE login=$2", h, login)
        # Verify
        row = await conn.fetchrow("SELECT password FROM users WHERE login=$1", login)
        ok = bcrypt.checkpw(password.encode("utf-8"), row['password'].encode("utf-8"))
        print(f"{'✓' if ok else '✗'} {login}: {h[:25]}...")
    await conn.close()
    print("Hammasi yangilandi!")

asyncio.run(fix())
