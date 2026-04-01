from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    total_marks: Mapped[float] = mapped_column(Float, default=100.0)
    passing_marks: Mapped[float] = mapped_column(Float, default=40.0)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False)
    show_results: Mapped[bool] = mapped_column(Boolean, default=True)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    course = relationship("Course", back_populates="exams")
    questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan")
    assignments = relationship("ExamAssignment", back_populates="exam", cascade="all, delete-orphan")
    submissions = relationship("ExamSubmission", back_populates="exam", cascade="all, delete-orphan")


class ExamAssignment(Base):
    __tablename__ = "exam_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    exam = relationship("Exam", back_populates="assignments")