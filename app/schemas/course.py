from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    code: str = Field(min_length=2, max_length=30)


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class CourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    code: str
    instructor_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrollmentCreate(BaseModel):
    """Accept student_id OR username OR email — backend resolves the student."""
    student_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None


class EnrollmentOut(BaseModel):
    id: int
    course_id: int
    student_id: int
    enrolled_at: datetime
    # Include student details so frontend can display names
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    student_username: Optional[str] = None

    model_config = {"from_attributes": True}