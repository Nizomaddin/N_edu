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
from app.routers.assignments import assign_out, upload_file, BUCKET

router = APIRouter()
bearer_scheme = HTTPBearer()

def sub_out(s, student=None, assignment=None):
    d = dict(s)
    result = {
        "id": d["id"], "assignment_id": d["assignment_id"], "student_id": d["student_id"],
        "file_name": d.get("file_name"), "file_url": d.get("file_url"),
        "comment": d.get("comment",""), "status": d.get("status","pending"),
        "grade": d.get("grade"), "grade_comment": d.get("grade_comment"),
        "graded_at": str(d["graded_at"]) if d.get("graded_at") else None,
        "submitted_at": str(d.get("submitted_at","")),
    }
    if student is not None: result["student"] = user_out(student)
    if assignment is not None: result["assignment"] = assign_out(assignment)
    return result

@router.get("/")
async def list_submissions(
    assignment_id: str = None,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await get_current_user(credentials, conn)
    if user["role"] == "student":
        q = "SELECT * FROM submissions WHERE student_id=$1 ORDER BY submitted_at DESC"
        rows = await conn.fetch(q, user["id"])
    elif user["role"] == "teacher":
        teacher_assigns = await conn.fetch("SELECT id FROM assignments WHERE teacher_id=$1", user["id"])
        ids = [r["id"] for r in teacher_assigns]
        if not ids: return []
        placeholders = ",".join(f"${i+1}" for i in range(len(ids)))
        rows = await conn.fetch(f"SELECT * FROM submissions WHERE assignment_id IN ({placeholders}) ORDER BY submitted_at DESC", *ids)
    else:
        rows = await conn.fetch("SELECT * FROM submissions ORDER BY submitted_at DESC")

    if assignment_id:
        rows = [r for r in rows if r["assignment_id"] == assignment_id]

    result = []
    for s in rows:
        student = await conn.fetchrow("SELECT * FROM users WHERE id=$1", s["student_id"])
        assign = await conn.fetchrow("SELECT * FROM assignments WHERE id=$1", s["assignment_id"])
        result.append(sub_out(s, student, assign))
    return result

@router.post("/", status_code=201)
async def submit_work(
    assignment_id: str = Form(...), comment: str = Form(""),
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await require_role("student")(credentials, conn)
    a = await conn.fetchrow("SELECT * FROM assignments WHERE id=$1", assignment_id)
    if not a: raise HTTPException(404, "Topshiriq topilmadi")
    if a["group_id"] != user["group_id"]: raise HTTPException(403, "Bu topshiriq sizning guruhingiz uchun emas")
    dup = await conn.fetchrow("SELECT id FROM submissions WHERE assignment_id=$1 AND student_id=$2", assignment_id, user["id"])
    if dup: raise HTTPException(400, "Bu topshiriq allaqachon topshirilgan")
    file_name, file_url = await upload_file(file, f"submissions/{user['id']}")
    sid = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO submissions (id,assignment_id,student_id,file_name,file_url,comment,status) VALUES ($1,$2,$3,$4,$5,$6,$7)",
        sid, assignment_id, user["id"], file_name, file_url, comment, "pending"
    )
    row = await conn.fetchrow("SELECT * FROM submissions WHERE id=$1", sid)
    return sub_out(row)

@router.patch("/{submission_id}/grade")
async def grade_submission(
    submission_id: str, body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await require_role("teacher")(credentials, conn)
    s = await conn.fetchrow("SELECT * FROM submissions WHERE id=$1", submission_id)
    if not s: raise HTTPException(404, "Topilmadi")
    a = await conn.fetchrow("SELECT * FROM assignments WHERE id=$1", s["assignment_id"])
    if not a or a["teacher_id"] != user["id"]: raise HTTPException(403, "Bu sizning topshirig'ingiz emas")
    grade = body.get("grade", 0)
    if grade < 0 or grade > a["max_score"]: raise HTTPException(400, f"Baho 0-{a['max_score']} oralig'ida bo'lishi kerak")
    await conn.execute(
        "UPDATE submissions SET grade=$1,grade_comment=$2,status=$3,graded_at=$4 WHERE id=$5",
        grade, body.get("grade_comment",""), body.get("status","graded"), date.today(), submission_id
    )
    row = await conn.fetchrow("SELECT * FROM submissions WHERE id=$1", submission_id)
    return sub_out(row)

@router.get("/{submission_id}")
async def get_submission(
    submission_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn: asyncpg.Connection = Depends(get_db),
):
    user = await get_current_user(credentials, conn)
    s = await conn.fetchrow("SELECT * FROM submissions WHERE id=$1", submission_id)
    if not s: raise HTTPException(404, "Topilmadi")
    if user["role"] == "student" and s["student_id"] != user["id"]: raise HTTPException(403, "Ruxsat yo'q")
    student = await conn.fetchrow("SELECT * FROM users WHERE id=$1", s["student_id"])
    assign = await conn.fetchrow("SELECT * FROM assignments WHERE id=$1", s["assignment_id"])
    return sub_out(s, student, assign)
