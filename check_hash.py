import asyncio
import asyncpg
from passlib.context import CryptContext

DB_URL = "postgresql://postgres.ykyavqikndorzoaglkop:Nizomaddin2026@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"

async def check():
    conn = await asyncpg.connect(DB_URL, ssl="require", statement_cache_size=0)
    row = await conn.fetchrow("SELECT password FROM users WHERE login='admin'")
    db_hash = row['password']
    print("DB hash:", db_hash)
    
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    result = pwd.verify("admin123", db_hash)
    print("Verify result:", result)
    
    # Yangi hash yoz
    new_hash = pwd.hash("admin123")
    print("New hash:", new_hash)
    print("New hash verify:", pwd.verify("admin123", new_hash))
    
    await conn.close()

asyncio.run(check())
