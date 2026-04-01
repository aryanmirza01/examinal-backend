from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    instructor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    instructor = relationship("User", back_populates="courses_created")
    enrollments = relationship("CourseEnrollment", back_populates="course", cascade="all, delete-orphan")
    documents = relationship("ContentDocument", back_populates="course", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="course", cascade="all, delete-orphan")


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    course = relationship("Course", back_populates="enrollments")
    student = relationship("User", back_populates="enrollments")