from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)  # mcq | short_answer | descriptive
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"A":"...","B":"...","C":"...","D":"..."}
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[float] = mapped_column(Float, default=1.0)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_passage_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("content_passages.id"), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")  # easy | medium | hard
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    exam = relationship("Exam", back_populates="questions")
    answers = relationship("AnswerResponse", back_populates="question", cascade="all, delete-orphan")