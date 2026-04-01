from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExamSubmission(Base):
    __tablename__ = "exam_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="in_progress")  # in_progress | submitted | graded
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    exam = relationship("Exam", back_populates="submissions")
    student = relationship("User", back_populates="submissions")
    answers = relationship("AnswerResponse", back_populates="submission", cascade="all, delete-orphan")


class AnswerResponse(Base):
    __tablename__ = "answer_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(Integer, ForeignKey("exam_submissions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("exam_questions.id"), nullable=False)
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=1.0)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    submission = relationship("ExamSubmission", back_populates="answers")
    question = relationship("ExamQuestion", back_populates="answers")