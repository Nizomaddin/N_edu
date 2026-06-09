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
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")
    except Exception:
        return password


def verify_password(plain: str, hashed: str) -> bool:
    # Plain text (oddiy)
    if plain == hashed:
        return True
    # bcrypt
    if hashed.startswith("$2"):
        try:
            import bcrypt
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False
    return False


def create_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": user_id, "role": role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def user_dict(user):
    return {
        "id": user["id"], "fname": user["fname"], "lname": user["lname"],
        "login": user["login"], "role": user["role"],
        "subject": user.get("subject") or "", "group_id": user.get("group_id"),
        "is_active": user.get("is_active", True), "created_at": str(user.get("created_at", "")),
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    exc = HTTPException(status_code=401, detail="Token noto'g'ri yoki muddati o'tgan")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id: raise exc
    except JWTError:
        raise exc
    user = await conn.fetchrow("SELECT * FROM users WHERE id=$1 AND is_active=true", user_id)
    if not user: raise exc
    return dict(user)


def require_role(*roles: str):
    async def checker(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        conn: asyncpg.Connection = Depends(get_db),
    ):
        user = await get_current_user(credentials, conn)
        if user["role"] not in roles:
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q.")
        return user
    return checker


@router.post("/login")
async def login(body: dict, conn: asyncpg.Connection = Depends(get_db)):
    login_val = (body.get("login") or "").strip()
    password  = (body.get("password") or "").strip()

    if not login_val or not password:
        raise HTTPException(400, "Login va parol kiritilishi shart")

    user = await conn.fetchrow(
        "SELECT id, fname, lname, login, password, role, subject, group_id, is_active, created_at FROM users WHERE login=$1",
        login_val
    )

    if not user:
        raise HTTPException(401, "Login yoki parol noto'g'ri")

    if not user["is_active"]:
        raise HTTPException(401, "Foydalanuvchi bloklangan")

    db_pass = user["password"] or ""

    if not verify_password(password, db_pass):
        raise HTTPException(401, "Login yoki parol noto'g'ri")

    token = create_token(user["id"], user["role"])
    return {"access_token": token, "token_type": "bearer", "user": user_dict(user)}


@router.get("/me")
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await get_current_user(credentials, conn)
    return user_dict(user)
