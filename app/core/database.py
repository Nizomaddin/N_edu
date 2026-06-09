import os
import asyncpg
from typing import AsyncGenerator

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.ykyavqikndorzoaglkop:Nizomaddin2026@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
)

# URL dan postgresql+asyncpg:// ni postgresql:// ga o'tkazish
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


async def get_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Har bir request uchun yangi ulanish"""
    conn = await asyncpg.connect(
        DATABASE_URL,
        ssl="require",
        statement_cache_size=0,
    )
    try:
        yield conn
    finally:
        await conn.close()


async def get_db():
    """FastAPI Depends uchun"""
    async for conn in get_conn():
        yield conn
