"""
Parollarni plain text sifatida yozadi - tez test uchun
"""
import asyncio
import asyncpg

DB_URL = "postgresql://postgres.ykyavqikndorzoaglkop:Nizomaddin2026@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"

async def reset():
    conn = await asyncpg.connect(DB_URL, ssl="require", statement_cache_size=0)
    users = [
        ("admin",    "admin123"),
        ("teacher1", "teacher123"),
        ("student1", "student123"),
        ("student2", "pass456"),
        ("student3", "pass789"),
    ]
    for login, password in users:
        await conn.execute("UPDATE users SET password=$1 WHERE login=$2", password, login)
        print(f"✓ {login} -> {password}")
    await conn.close()
    print("Hammasi yangilandi!")

asyncio.run(reset())
