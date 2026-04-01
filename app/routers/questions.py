"""
Question CRUD + AI generation.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import InstructorUser
from app.models.question import ExamQuestion
from app.models.exam import Exam
from app.schemas.question import (
    QuestionCreate,
    QuestionUpdate,
    QuestionOut,
    GenerateQuestionsRequest,
)
from app.services.question_generator import QuestionGeneratorService

router = APIRouter(prefix="/api/questions", tags=["Questions"])


@router.post("/", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionCreate, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    exam = db.query(Exam).filter(Exam.id == payload.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    question = ExamQuestion(**payload.model_dump())
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.get("/exam/{exam_id}", response_model=List[QuestionOut])
def list_questions(exam_id: int, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    return (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam_id)
        .order_by(ExamQuestion.order_index)
        .all()
    )


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    q = db.query(ExamQuestion).filter(ExamQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


@router.patch("/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionUpdate, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    q = db.query(ExamQuestion).filter(ExamQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(q, k, v)
    db.commit()
    db.refresh(q)
    return q


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, user: InstructorUser, db: Session = Depends(get_db)):  # type: ignore
    q = db.query(ExamQuestion).filter(ExamQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()


@router.post("/generate", response_model=List[QuestionOut])
def generate_questions(
    payload: GenerateQuestionsRequest,
    user: InstructorUser,  # type: ignore
    db: Session = Depends(get_db),
):
    """Use RAG + LLM to generate questions from course content."""
    exam = db.query(Exam).filter(Exam.id == payload.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    try:
        gen_service = QuestionGeneratorService(db)
        questions = gen_service.generate(
            course_id=payload.course_id,
            exam_id=payload.exam_id,
            num_questions=payload.num_questions,
            question_type=payload.question_type,
            difficulty=payload.difficulty,
            topic=payload.topic,
        )
        return questions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")