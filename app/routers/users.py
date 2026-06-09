import uuid
from typing import Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.core.database import get_db
from app.routers.auth import get_current_user, require_role, hash_password
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
bearer_scheme = HTTPBearer()

def user_out(u):
    if u is None: return None
    d = dict(u)
    return {
        "id": d["id"], "fname": d["fname"], "lname": d["lname"],
        "login": d["login"], "role": d["role"], "subject": d.get("subject") or "",
        "group_id": d.get("group_id"), "is_active": d.get("is_active", True),
        "created_at": str(d.get("created_at", "")),
    }

@router.get("/stats")
async def stats(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin")(credentials, conn)
    total = await conn.fetchval("SELECT COUNT(*) FROM users")
    teachers = await conn.fetchval("SELECT COUNT(*) FROM users WHERE role='teacher'")
    students = await conn.fetchval("SELECT COUNT(*) FROM users WHERE role='student'")
    groups = await conn.fetchval("SELECT COUNT(*) FROM groups")
    assignments = await conn.fetchval("SELECT COUNT(*) FROM assignments")
    submissions = await conn.fetchval("SELECT COUNT(*) FROM submissions")
    return {"total_users": total, "total_teachers": teachers, "total_students": students,
            "total_groups": groups, "total_assignments": assignments, "total_submissions": submissions}

@router.get("/")
async def list_users(
    role: Optional[str] = Query(None),
    group_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin", "teacher")(credentials, conn)
    q = "SELECT * FROM users WHERE 1=1"
    params = []
    if role: params.append(role); q += f" AND role=${len(params)}"
    if group_id: params.append(group_id); q += f" AND group_id=${len(params)}"
    if search:
        params.append(f"%{search}%")
        q += f" AND (fname ILIKE ${len(params)} OR lname ILIKE ${len(params)} OR login ILIKE ${len(params)})"
    q += " ORDER BY created_at DESC"
    rows = await conn.fetch(q, *params)
    return [user_out(r) for r in rows]

@router.post("/", status_code=201)
async def create_user(
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin")(credentials, conn)
    dup = await conn.fetchrow("SELECT id FROM users WHERE login=$1", body["login"])
    if dup: raise HTTPException(400, f"'{body['login']}' login allaqachon mavjud")
    uid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO users (id,fname,lname,login,password,role,subject,group_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
        uid, body["fname"], body["lname"], body["login"],
        body["password"], body["role"],
        body.get("subject",""), body.get("group_id")
    )
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
    return user_out(row)

@router.post("/bulk", status_code=201)
async def bulk_create(
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin")(credentials, conn)
    added, updated = [], []
    for item in body.get("users", []):
        existing = await conn.fetchrow("SELECT id FROM users WHERE login=$1", item["login"])
        if existing:
            await conn.execute(
                "UPDATE users SET fname=$1,lname=$2,password=$3,subject=$4,group_id=$5 WHERE login=$6",
                item["fname"], item["lname"], item["password"],
                item.get("subject",""), item.get("group_id"), item["login"]
            )
            updated.append(item["login"])
        else:
            uid = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO users (id,fname,lname,login,password,role,subject,group_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                uid, item["fname"], item["lname"], item["login"],
                item["password"], item["role"],
                item.get("subject",""), item.get("group_id")
            )
            added.append(item["login"])
    return {"added": len(added), "updated": len(updated), "logins_added": added, "logins_updated": updated}

@router.get("/{user_id}")
async def get_user(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    current = await get_current_user(credentials, conn)
    if current["role"] != "admin" and current["id"] != user_id:
        raise HTTPException(403, "Ruxsat yo'q")
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    if not row: raise HTTPException(404, "Topilmadi")
    return user_out(row)

@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin")(credentials, conn)
    sets, params = [], []
    for field in ["fname","lname","subject","group_id","is_active"]:
        if field in body:
            params.append(body[field]); sets.append(f"{field}=${len(params)}")
    if "password" in body:
        params.append(body["password"]); sets.append(f"password=${len(params)}")
    if not sets: raise HTTPException(400, "Hech narsa o'zgartirilmadi")
    params.append(user_id)
    await conn.execute(f"UPDATE users SET {','.join(sets)} WHERE id=${len(params)}", *params)
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    return user_out(row)

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    current = await require_role("admin")(credentials, conn)
    if current["id"] == user_id: raise HTTPException(400, "O'zingizni o'chira olmaysiz")
    await conn.execute("DELETE FROM users WHERE id=$1", user_id)
