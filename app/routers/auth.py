import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg
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
    """Parolni hash qilish"""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")
    except Exception:
        return password


def verify_password(plain: str, hashed: str) -> bool:
    """Parolni tekshirish - bcrypt va plain text ikkalasini qo'llab-quvvatlaydi"""
    # Avval bcrypt bilan tekshir
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        try:
            import bcrypt
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception as e:
            # bcrypt ishlamasa, plain text tekshir
            pass
    # Plain text tekshirish (fallback)
    return plain == hashed


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


def user_dict(user):
    return {
        "id": user["id"],
        "fname": user["fname"],
        "lname": user["lname"],
        "login": user["login"],
        "role": user["role"],
        "subject": user.get("subject") or "",
        "group_id": user.get("group_id"),
        "is_active": user.get("is_active", True),
        "created_at": str(user.get("created_at", "")),
    }


# ── AUTH ROUTES ──────────────────────────────────────────────
@router.post("/login")
async def login(body: dict, conn: asyncpg.Connection = Depends(get_db)):
    login_val = body.get("login", "").strip()
    password  = body.get("password", "").strip()

    user = await conn.fetchrow(
        "SELECT * FROM users WHERE login=$1 AND is_active=true", login_val
    )
    if not user:
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri")

    db_pass = user["password"]

    # Debug uchun log
    import sys
    print(f"LOGIN: {login_val}, DB_PASS_START: {db_pass[:10]}, IS_BCRYPT: {db_pass.startswith('$2')}", file=sys.stderr)

    if not verify_password(password, db_pass):
        # Oxirgi urinish: plain text saqlanganmi?
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri")

    token = create_token(user["id"], user["role"])
    return {"access_token": token, "token_type": "bearer", "user": user_dict(user)}


@router.get("/me")
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await get_current_user(credentials, conn)
    return user_dict(user)