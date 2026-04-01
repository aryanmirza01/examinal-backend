"""
Exam CRUD, publish, assign.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser, InstructorUser
from app.models.exam import Exam, ExamAssignment
from app.models.course import Course, CourseEnrollment
from app.schemas.exam import ExamCreate, ExamUpdate, ExamOut, ExamAssign
from app.schemas.question import QuestionStudentView

router = APIRouter(prefix="/api/exams", tags=["Exams"])


@router.post("/", response_model=ExamOut, status_code=status.HTTP_201_CREATED)
def create_exam(payload: ExamCreate, user: InstructorUser, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    exam = Exam(**payload.model_dump(), created_by=user.id)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("/", response_model=List[ExamOut])
def list_exams(
    course_id: int | None = None,
    current_user: CurrentUser = None,  # type: ignore
    db: Session = Depends(get_db),
):
    q = db.query(Exam)
    if current_user.role == "instructor":
        q = q.filter(Exam.created_by == current_user.id)
    elif current_user.role == "student":
        assigned = db.query(ExamAssignment.exam_id).filter(
            ExamAssignment.student_id == current_user.id
        ).subquery()
        q = q.filter(Exam.id.in_(assigned), Exam.is_published == True)  # noqa: E712
    if course_id:
        q = q.filter(Exam.course_id == course_id)
    return q.all()


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.patch("/{exam_id}", response_model=ExamOut)
def update_exam(exam_id: int, payload: ExamUpdate, user: InstructorUser, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your exam")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(exam, k, v)
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/publish", response_model=ExamOut)
def publish_exam(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if not exam.questions:
        raise HTTPException(status_code=400, detail="Add questions before publishing")
    exam.is_published = True
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/unpublish", response_model=ExamOut)
def unpublish_exam(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    exam.is_published = False
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/assign")
def assign_students(exam_id: int, payload: ExamAssign, user: InstructorUser, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    created = 0
    for sid in payload.student_ids:
        existing = (
            db.query(ExamAssignment)
            .filter(ExamAssignment.exam_id == exam_id, ExamAssignment.student_id == sid)
            .first()
        )
        if not existing:
            db.add(ExamAssignment(exam_id=exam_id, student_id=sid))
            created += 1
    db.commit()
    return {"assigned": created, "total_requested": len(payload.student_ids)}


@router.post("/{exam_id}/assign-all")
def assign_all_enrolled(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):
    """Assign all enrolled students of the exam's course."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    enrollments = db.query(CourseEnrollment).filter(CourseEnrollment.course_id == exam.course_id).all()
    created = 0
    for enrollment in enrollments:
        existing = (
            db.query(ExamAssignment)
            .filter(ExamAssignment.exam_id == exam_id, ExamAssignment.student_id == enrollment.student_id)
            .first()
        )
        if not existing:
            db.add(ExamAssignment(exam_id=exam_id, student_id=enrollment.student_id))
            created += 1
    db.commit()
    return {"assigned": created, "total_enrolled": len(enrollments)}


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your exam")
    db.delete(exam)
    db.commit()


@router.get("/{exam_id}/questions-student", response_model=List[QuestionStudentView])
def get_exam_questions_student(exam_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    """Return questions without correct answers (student view)."""
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.is_published == True).first()  # noqa: E712
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not published")
    return exam.questions