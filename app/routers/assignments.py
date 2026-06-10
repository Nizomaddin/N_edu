import uuid
import os
from datetime import date
import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.database import get_db
from app.routers.auth import get_current_user, require_role
from app.routers.users import user_out

router = APIRouter()
bearer_scheme = HTTPBearer()

SUPABASE_URL   = os.getenv("SUPABASE_URL","")
SUPABASE_KEY   = os.getenv("SUPABASE_SERVICE_KEY","")
BUCKET         = "assignments"

async def upload_file(file: UploadFile, folder: str):
    if not SUPABASE_URL or not SUPABASE_KEY:
        import sys
        print(f"UPLOAD ERROR: SUPABASE_URL={bool(SUPABASE_URL)}, KEY={bool(SUPABASE_KEY)}", file=sys.stderr)
        return None, None
    ext = file.filename.rsplit(".",1)[-1] if "." in file.filename else "bin"
    path = f"{folder}/{uuid.uuid4().hex}.{ext}"
    content = await file.read()
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": file.content_type or "application/octet-stream",
        "x-upsert": "true",
    }
    import sys
    print(f"UPLOADING to: {url[:60]}, size: {len(content)}", file=sys.stderr)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, content=content, headers=headers)
    print(f"UPLOAD RESPONSE: {resp.status_code} {resp.text[:100]}", file=sys.stderr)
    if resp.status_code >= 400:
        return file.filename, None
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"
    return file.filename, public_url

def assign_out(a, teacher=None, submitted_count=None, student_count=None):
    d = dict(a)
    result = {
        "id": d["id"], "title": d["title"], "subject": d["subject"],
        "description": d["description"], "max_score": d["max_score"],
        "due_date": str(d["due_date"]), "teacher_id": d["teacher_id"],
        "group_id": d["group_id"], "file_name": d.get("file_name"),
        "file_url": d.get("file_url"), "created_at": str(d.get("created_at","")),
    }
    if teacher is not None: result["teacher"] = user_out(teacher)
    if submitted_count is not None: result["submitted_count"] = submitted_count
    if student_count is not None: result["student_count"] = student_count
    return result

@router.get("/")
async def list_assignments(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await get_current_user(credentials, conn)
    if user["role"] == "teacher":
        rows = await conn.fetch("SELECT * FROM assignments WHERE teacher_id=$1 ORDER BY created_at DESC", user["id"])
    elif user["role"] == "student":
        rows = await conn.fetch("SELECT * FROM assignments WHERE group_id=$1 ORDER BY created_at DESC", user["group_id"])
    else:
        rows = await conn.fetch("SELECT * FROM assignments ORDER BY created_at DESC")
    return [assign_out(r) for r in rows]

@router.post("/", status_code=201)
async def create_assignment(
    title: str = Form(...), subject: str = Form(...), description: str = Form(...),
    max_score: int = Form(100), due_date: str = Form(...), group_id: str = Form(...),
    file: UploadFile = File(None),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await require_role("teacher")(credentials, conn)
    file_name, file_url = None, None
    if file and file.filename:
        file_name, file_url = await upload_file(file, f"assignments/{user['id']}")
    aid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO assignments (id,title,subject,description,max_score,due_date,teacher_id,group_id,file_name,file_url) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
        aid, title, subject, description, max_score, date.fromisoformat(due_date),
        user["id"], group_id, file_name, file_url
    )
    row = await conn.fetchrow("SELECT * FROM assignments WHERE id=$1", aid)
    return assign_out(row)

@router.get("/{assignment_id}")
async def get_assignment(
    assignment_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    await get_current_user(credentials, conn)
    a = await conn.fetchrow("SELECT * FROM assignments WHERE id=$1", assignment_id)
    if not a: raise HTTPException(404, "Topshiriq topilmadi")
    teacher = await conn.fetchrow("SELECT * FROM users WHERE id=$1", a["teacher_id"])
    sc = await conn.fetchval("SELECT COUNT(*) FROM submissions WHERE assignment_id=$1", assignment_id)
    stc = await conn.fetchval("SELECT COUNT(*) FROM users WHERE group_id=$1 AND role='student'", a["group_id"])
    return assign_out(a, teacher, sc, stc)

@router.delete("/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await require_role("teacher","admin")(credentials, conn)
    a = await conn.fetchrow("SELECT * FROM assignments WHERE id=$1", assignment_id)
    if not a: raise HTTPException(404, "Topilmadi")
    if user["role"] == "teacher" and a["teacher_id"] != user["id"]:
        raise HTTPException(403, "Bu sizning topshirig'ingiz emas")
    await conn.execute("DELETE FROM assignments WHERE id=$1", assignment_id)
