from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import create_tables
from app.routers import auth, users, groups, assignments, submissions


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="EduPortal API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # production da domeningizni yozing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,        prefix="/api/auth",        tags=["Auth"])
app.include_router(users.router,       prefix="/api/users",       tags=["Users"])
app.include_router(groups.router,      prefix="/api/groups",      tags=["Groups"])
app.include_router(assignments.router, prefix="/api/assignments", tags=["Assignments"])
app.include_router(submissions.router, prefix="/api/submissions", tags=["Submissions"])


@app.get("/")
async def root():
    return {"status": "ok", "app": "EduPortal API v1.0"}
