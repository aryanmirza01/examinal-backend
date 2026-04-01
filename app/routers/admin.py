"""
Admin‑only endpoints: audit logs, stats, DB health.
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import AdminUser
from app.models.user import User
from app.models.course import Course
from app.models.exam import Exam
from app.models.submission import ExamSubmission
from app.models.activity_log import ActivityLog

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/stats")
def platform_stats(_admin: AdminUser, db: Session = Depends(get_db)):  # type: ignore
    return {
        "total_users": db.query(func.count(User.id)).scalar(),
        "total_instructors": db.query(func.count(User.id)).filter(User.role == "instructor").scalar(),
        "total_students": db.query(func.count(User.id)).filter(User.role == "student").scalar(),
        "total_courses": db.query(func.count(Course.id)).scalar(),
        "total_exams": db.query(func.count(Exam.id)).scalar(),
        "total_submissions": db.query(func.count(ExamSubmission.id)).scalar(),
        "published_exams": db.query(func.count(Exam.id)).filter(Exam.is_published == True).scalar(),  # noqa
    }


@router.get("/activity-logs")
def get_activity_logs(
    user_id: int | None = None,
    exam_id: int | None = None,
    action_type: str | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    _admin: AdminUser = None,  # type: ignore
    db: Session = Depends(get_db),
):
    q = db.query(ActivityLog).order_by(ActivityLog.created_at.desc())
    if user_id:
        q = q.filter(ActivityLog.user_id == user_id)
    if exam_id:
        q = q.filter(ActivityLog.exam_id == exam_id)
    if action_type:
        q = q.filter(ActivityLog.action_type == action_type)
    logs = q.offset(skip).limit(limit).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "exam_id": l.exam_id,
            "submission_id": l.submission_id,
            "action_type": l.action_type,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


@router.get("/exam/{exam_id}/integrity")
def exam_integrity_report(exam_id: int, _admin: AdminUser, db: Session = Depends(get_db)):  # type: ignore
    """Suspicious activity summary for an exam."""
    suspicious_actions = ["tab_switch", "copy_attempt", "paste_attempt", "focus_lost"]
    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.exam_id == exam_id, ActivityLog.action_type.in_(suspicious_actions))
        .all()
    )
    # Group by user
    user_flags: dict = {}
    for log in logs:
        uid = log.user_id
        if uid not in user_flags:
            user_flags[uid] = {"user_id": uid, "events": []}
        user_flags[uid]["events"].append({
            "action": log.action_type,
            "time": log.created_at.isoformat() if log.created_at else None,
            "details": log.details,
        })

    return {
        "exam_id": exam_id,
        "total_flags": len(logs),
        "flagged_students": list(user_flags.values()),
    }