"""
Exam‑taking flow: start, autosave, submit, activity events.
"""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.exam import Exam, ExamAssignment
from app.models.submission import ExamSubmission, AnswerResponse
from app.models.question import ExamQuestion
from app.models.activity_log import ActivityLog
from app.schemas.submission import (
    SubmissionStart,
    SubmissionOut,
    SubmissionDetail,
    AnswerResponseOut,
    AutosaveRequest,
    ActivityEvent,
)

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])


@router.post("/start", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
def start_exam(
    payload: SubmissionStart,
    current_user: CurrentUser,
    request: Request,
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == payload.exam_id, Exam.is_published == True).first()  # noqa: E712
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not published")

    # Check assignment
    assigned = (
        db.query(ExamAssignment)
        .filter(ExamAssignment.exam_id == exam.id, ExamAssignment.student_id == current_user.id)
        .first()
    )
    if not assigned and current_user.role == "student":
        raise HTTPException(status_code=403, detail="You are not assigned to this exam")

    # Check max attempts
    existing_count = (
        db.query(ExamSubmission)
        .filter(
            ExamSubmission.exam_id == exam.id,
            ExamSubmission.student_id == current_user.id,
            ExamSubmission.status.in_(["submitted", "graded"]),
        )
        .count()
    )
    if existing_count >= exam.max_attempts:
        raise HTTPException(status_code=400, detail="Maximum attempts reached")

    # Check for in-progress submission
    in_progress = (
        db.query(ExamSubmission)
        .filter(
            ExamSubmission.exam_id == exam.id,
            ExamSubmission.student_id == current_user.id,
            ExamSubmission.status == "in_progress",
        )
        .first()
    )
    if in_progress:
        return in_progress

    submission = ExamSubmission(exam_id=exam.id, student_id=current_user.id)
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Log
    db.add(ActivityLog(
        user_id=current_user.id,
        exam_id=exam.id,
        submission_id=submission.id,
        action_type="exam_started",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))
    db.commit()

    return submission


@router.post("/{submission_id}/autosave")
def autosave_answers(
    submission_id: int,
    payload: AutosaveRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    submission = db.query(ExamSubmission).filter(
        ExamSubmission.id == submission_id,
        ExamSubmission.student_id == current_user.id,
        ExamSubmission.status == "in_progress",
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Active submission not found")

    for ans in payload.answers:
        existing = (
            db.query(AnswerResponse)
            .filter(
                AnswerResponse.submission_id == submission.id,
                AnswerResponse.question_id == ans.question_id,
            )
            .first()
        )
        question = db.query(ExamQuestion).filter(ExamQuestion.id == ans.question_id).first()
        if not question:
            continue
        if existing:
            existing.student_answer = ans.student_answer
        else:
            db.add(AnswerResponse(
                submission_id=submission.id,
                question_id=ans.question_id,
                student_answer=ans.student_answer,
                max_score=question.marks,
            ))
    db.commit()
    return {"status": "saved", "answers_count": len(payload.answers)}


@router.post("/{submission_id}/submit", response_model=SubmissionOut)
def submit_exam(
    submission_id: int,
    payload: AutosaveRequest,
    current_user: CurrentUser,
    request: Request,
    db: Session = Depends(get_db),
):
    submission = db.query(ExamSubmission).filter(
        ExamSubmission.id == submission_id,
        ExamSubmission.student_id == current_user.id,
        ExamSubmission.status == "in_progress",
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Active submission not found")

    # Save final answers
    for ans in payload.answers:
        existing = (
            db.query(AnswerResponse)
            .filter(
                AnswerResponse.submission_id == submission.id,
                AnswerResponse.question_id == ans.question_id,
            )
            .first()
        )
        question = db.query(ExamQuestion).filter(ExamQuestion.id == ans.question_id).first()
        if not question:
            continue
        if existing:
            existing.student_answer = ans.student_answer
        else:
            db.add(AnswerResponse(
                submission_id=submission.id,
                question_id=ans.question_id,
                student_answer=ans.student_answer,
                max_score=question.marks,
            ))

    submission.status = "submitted"
    submission.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(submission)

    # Log
    db.add(ActivityLog(
        user_id=current_user.id,
        exam_id=submission.exam_id,
        submission_id=submission.id,
        action_type="exam_submitted",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))
    db.commit()

    return submission


@router.get("/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    submission = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if current_user.role == "student" and submission.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    answers = db.query(AnswerResponse).filter(AnswerResponse.submission_id == submission.id).all()
    return SubmissionDetail(
        submission=SubmissionOut.model_validate(submission),
        answers=[AnswerResponseOut.model_validate(a) for a in answers],
    )


@router.get("/exam/{exam_id}", response_model=List[SubmissionOut])
def list_exam_submissions(exam_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    q = db.query(ExamSubmission).filter(ExamSubmission.exam_id == exam_id)
    if current_user.role == "student":
        q = q.filter(ExamSubmission.student_id == current_user.id)
    return q.all()


@router.get("/my/all", response_model=List[SubmissionOut])
def my_submissions(current_user: CurrentUser, db: Session = Depends(get_db)):
    return db.query(ExamSubmission).filter(ExamSubmission.student_id == current_user.id).all()


# ── Activity event logging from secure client ──


@router.post("/activity", status_code=status.HTTP_201_CREATED)
def log_activity(
    payload: ActivityEvent,
    current_user: CurrentUser,
    request: Request,
    db: Session = Depends(get_db),
):
    log = ActivityLog(
        user_id=current_user.id,
        exam_id=payload.exam_id,
        submission_id=payload.submission_id,
        action_type=payload.action_type,
        details=payload.details,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(log)
    db.commit()
    return {"status": "logged"}