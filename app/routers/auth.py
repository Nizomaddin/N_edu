import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "nedu-nizomaddin-2025-jwt-secret-key-xQ9pL2mK")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

bearer_scheme = HTTPBearer()
router = APIRouter()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token noto'g'ri yoki muddati o'tgan",
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise exc
    except JWTError:
        raise exc

    user = await conn.fetchrow(
        "SELECT * FROM users WHERE id=$1 AND is_active=true", user_id
    )
    if not user:
        raise exc
    return dict(user)


def require_role(*roles: str):
    async def checker(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        conn: asyncpg.Connection = Depends(get_db),
    ):
        user = await get_current_user(credentials, conn)
        if user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amal uchun ruxsat yo'q."
            )
        return user
    return checker


# ── AUTH ROUTES ──────────────────────────────────────────────
@router.post("/login")
async def login(body: dict, conn: asyncpg.Connection = Depends(get_db)):
    login_val = body.get("login", "").strip()
    password = body.get("password", "").strip()

    user = await conn.fetchrow(
        "SELECT * FROM users WHERE login=$1 AND is_active=true", login_val
    )
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol noto'g'ri",
        )

    token = create_token(user["id"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "fname": user["fname"],
            "lname": user["lname"],
            "login": user["login"],
            "role": user["role"],
            "subject": user["subject"] or "",
            "group_id": user["group_id"],
            "is_active": user["is_active"],
            "created_at": str(user["created_at"]),
        }
    }


@router.get("/me")
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await get_current_user(credentials, conn)
    return {
        "id": user["id"],
        "fname": user["fname"],
        "lname": user["lname"],
        "login": user["login"],
        "role": user["role"],
        "subject": user["subject"] or "",
        "group_id": user["group_id"],
        "is_active": user["is_active"],
        "created_at": str(user["created_at"]),
    }
