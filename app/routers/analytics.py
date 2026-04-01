"""
Analytics and reporting endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import InstructorUser, CurrentUser
from app.schemas.analytics import ExamAnalytics, QuestionAnalytics, StudentPerformance, CourseAnalytics
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/exam/{exam_id}", response_model=ExamAnalytics)
def exam_analytics(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    svc = AnalyticsService(db)
    result = svc.get_exam_analytics(exam_id)
    if not result:
        raise HTTPException(status_code=404, detail="Exam not found")
    return result


@router.get("/exam/{exam_id}/questions", response_model=List[QuestionAnalytics])
def question_analytics(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    svc = AnalyticsService(db)
    return svc.get_question_analytics(exam_id)


@router.get("/student/{student_id}", response_model=StudentPerformance)
def student_performance(student_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    if current_user.role == "student" and current_user.id != student_id:
        raise HTTPException(status_code=403, detail="Access denied")
    svc = AnalyticsService(db)
    result = svc.get_student_performance(student_id)
    if not result:
        raise HTTPException(status_code=404, detail="Student not found")
    return result


@router.get("/course/{course_id}", response_model=CourseAnalytics)
def course_analytics(course_id: int, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    svc = AnalyticsService(db)
    result = svc.get_course_analytics(course_id)
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")
    return result