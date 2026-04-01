"""
Examinal – AI‑powered assessment platform.
Entry‑point: uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.middleware.activity_logger import ActivityLoggerMiddleware

# ── Import every model so Base.metadata knows them ──
from app.models import (
    user, course, content, exam, question, submission, activity_log,
)

from app.routers import (
    auth, users, courses, content as content_router,
    questions, exams, submissions, grading, analytics, admin,
)
from app.routers.contact import router as contact_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    # ── Startup ──
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.VECTOR_STORE_DIR).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield
    # ── Shutdown ──


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI‑powered end‑to‑end assessment platform",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom middleware ──
app.add_middleware(ActivityLoggerMiddleware)

# ── Routers ──
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(content_router.router)
app.include_router(questions.router)
app.include_router(exams.router)
app.include_router(submissions.router)
app.include_router(grading.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(contact_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}
