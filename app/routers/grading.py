"""
Grading endpoints — auto-grade, batch grade, manual override, confidence review.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import InstructorUser
from app.models.submission import ExamSubmission, AnswerResponse
from app.schemas.submission import SubmissionDetail, SubmissionOut, AnswerResponseOut
from app.services.grading_service import GradingService
from app.config import settings

router = APIRouter(prefix="/api/grading", tags=["Grading"])


@router.post("/auto/{submission_id}", response_model=SubmissionDetail)
def auto_grade(submission_id: int, user: InstructorUser, db: Session = Depends(get_db)):
    submission = db.query(ExamSubmission).filter(ExamSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status not in ("submitted", "graded"):
        raise HTTPException(status_code=400, detail="Submission not yet submitted")

    grading_svc = GradingService(db)
    grading_svc.grade_submission(submission)

    answers = db.query(AnswerResponse).filter(AnswerResponse.submission_id == submission.id).all()
    return SubmissionDetail(
        submission=SubmissionOut.model_validate(submission),
        answers=[AnswerResponseOut.model_validate(a) for a in answers],
    )


@router.post("/auto/exam/{exam_id}")
def auto_grade_all(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):
    submissions = (
        db.query(ExamSubmission)
        .filter(ExamSubmission.exam_id == exam_id, ExamSubmission.status == "submitted")
        .all()
    )
    grading_svc = GradingService(db)
    graded = 0
    failed = 0
    for sub in submissions:
        try:
            grading_svc.grade_submission(sub)
            graded += 1
        except Exception as e:
            failed += 1
    return {
        "graded": graded,
        "failed": failed,
        "total_submitted": len(submissions),
        "grading_mode": settings.GRADING_MODE,
        "llm_model": settings.NVIDIA_LLM_MODEL,
    }


@router.get("/low-confidence/{exam_id}")
def get_low_confidence_answers(
    exam_id: int,
    user: InstructorUser,
    threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """Get answers where AI grading confidence is below threshold — need human review."""
    submissions = (
        db.query(ExamSubmission)
        .filter(ExamSubmission.exam_id == exam_id, ExamSubmission.status == "graded")
        .all()
    )
    sub_ids = [s.id for s in submissions]
    if not sub_ids:
        return []

    low_conf = (
        db.query(AnswerResponse)
        .filter(
            AnswerResponse.submission_id.in_(sub_ids),
            AnswerResponse.confidence_score < threshold,
            AnswerResponse.confidence_score.isnot(None),
        )
        .all()
    )
    return [
        {
            "answer_id": a.id,
            "submission_id": a.submission_id,
            "question_id": a.question_id,
            "student_answer": a.student_answer,
            "current_score": a.score,
            "max_score": a.max_score,
            "confidence": a.confidence_score,
            "ai_feedback": a.ai_feedback,
        }
        for a in low_conf
    ]


@router.patch("/manual/{answer_id}")
def manual_override(
    answer_id: int,
    score: float,
    user: InstructorUser,
    feedback: str | None = None,
    db: Session = Depends(get_db),
):
    answer = db.query(AnswerResponse).filter(AnswerResponse.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    answer.score = min(score, answer.max_score)
    answer.is_correct = score >= (answer.max_score * 0.7)
    answer.confidence_score = 1.0  # Manual = full confidence
    if feedback:
        answer.ai_feedback = f"[Instructor override] {feedback}"
    else:
        answer.ai_feedback = (answer.ai_feedback or "") + " [Score overridden by instructor]"
    db.commit()

    # Recalculate submission totals
    submission = db.query(ExamSubmission).filter(ExamSubmission.id == answer.submission_id).first()
    if submission:
        all_answers = db.query(AnswerResponse).filter(AnswerResponse.submission_id == submission.id).all()
        submission.total_score = round(sum(a.score for a in all_answers), 2)
        submission.max_score = round(sum(a.max_score for a in all_answers), 2)
        submission.percentage = round(
            (submission.total_score / submission.max_score * 100) if submission.max_score else 0, 2
        )
        exam = submission.exam
        passing_pct = (exam.passing_marks / exam.total_marks * 100) if exam and exam.total_marks else 40
        submission.is_passed = submission.percentage >= passing_pct
        db.commit()

    return {"status": "updated", "new_score": answer.score, "confidence": 1.0}


@router.get("/config")
def grading_config(user: InstructorUser):
    """Return current grading configuration."""
    return {
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.NVIDIA_LLM_MODEL,
        "embed_model": settings.NVIDIA_EMBED_MODEL,
        "rerank_model": settings.NVIDIA_RERANK_MODEL,
        "grading_mode": settings.GRADING_MODE,
        "confidence_threshold": settings.GRADING_CONFIDENCE_THRESHOLD,
        "rubric_grading": settings.ENABLE_RUBRIC_GRADING,
        "use_reranker": settings.USE_RERANKER,
    }