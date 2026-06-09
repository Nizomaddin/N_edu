import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.database import get_db
from app.routers.auth import get_current_user, require_role
from app.routers.users import user_out

router = APIRouter()
bearer_scheme = HTTPBearer()

def group_out(g, teacher=None, students=None, assignment_count=0):
    d = dict(g)
    result = {
        "id": d["id"], "name": d["name"], "dept": d.get("dept",""),
        "teacher_id": d.get("teacher_id"), "created_at": str(d.get("created_at","")),
    }
    if teacher is not None: result["teacher"] = user_out(teacher)
    if students is not None:
        result["students"] = [user_out(s) for s in students]
        result["assignment_count"] = assignment_count
    return result

@router.get("/")
async def list_groups(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await get_current_user(credentials, conn)
    rows = await conn.fetch("SELECT * FROM groups ORDER BY created_at DESC")
    return [group_out(r) for r in rows]

@router.post("/", status_code=201)
async def create_group(
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin")(credentials, conn)
    gid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO groups (id,name,dept,teacher_id) VALUES ($1,$2,$3,$4)",
        gid, body["name"], body.get("dept",""), body.get("teacher_id")
    )
    if body.get("teacher_id"):
        await conn.execute("UPDATE users SET group_id=$1 WHERE id=$2", gid, body["teacher_id"])
    row = await conn.fetchrow("SELECT * FROM groups WHERE id=$1", gid)
    return group_out(row)

@router.get("/{group_id}")
async def get_group(
    group_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await get_current_user(credentials, conn)
    g = await conn.fetchrow("SELECT * FROM groups WHERE id=$1", group_id)
    if not g: raise HTTPException(404, "Guruh topilmadi")
    teacher = None
    if g["teacher_id"]:
        teacher = await conn.fetchrow("SELECT * FROM users WHERE id=$1", g["teacher_id"])
    students = await conn.fetch("SELECT * FROM users WHERE group_id=$1 AND role='student'", group_id)
    ac = await conn.fetchval("SELECT COUNT(*) FROM assignments WHERE group_id=$1", group_id)
    return group_out(g, teacher, students, ac)

@router.patch("/{group_id}")
async def update_group(
    group_id: str,
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin")(credentials, conn)
    g = await conn.fetchrow("SELECT * FROM groups WHERE id=$1", group_id)
    if not g: raise HTTPException(404, "Topilmadi")
    sets, params = [], []
    for field in ["name","dept","teacher_id"]:
        if field in body:
            params.append(body[field]); sets.append(f"{field}=${len(params)}")
    if sets:
        params.append(group_id)
        await conn.execute(f"UPDATE groups SET {','.join(sets)} WHERE id=${len(params)}", *params)
    if "teacher_id" in body and body["teacher_id"]:
        await conn.execute("UPDATE users SET group_id=$1 WHERE id=$2", group_id, body["teacher_id"])
    if "student_ids" in body:
        await conn.execute("UPDATE users SET group_id=NULL WHERE group_id=$1 AND role='student'", group_id)
        for sid in body["student_ids"]:
            await conn.execute("UPDATE users SET group_id=$1 WHERE id=$2", group_id, sid)
    row = await conn.fetchrow("SELECT * FROM groups WHERE id=$1", group_id)
    return group_out(row)

@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await require_role("admin")(credentials, conn)
    await conn.execute("UPDATE users SET group_id=NULL WHERE group_id=$1", group_id)
    await conn.execute("DELETE FROM groups WHERE id=$1", group_id)
