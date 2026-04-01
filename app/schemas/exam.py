from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class ExamCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: int = Field(default=60, ge=5, le=480)
    total_marks: float = Field(default=100, gt=0)
    passing_marks: float = Field(default=40, ge=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    shuffle_questions: bool = False
    show_results: bool = True
    max_attempts: int = Field(default=1, ge=1, le=10)


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    total_marks: Optional[float] = None
    passing_marks: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    shuffle_questions: Optional[bool] = None
    show_results: Optional[bool] = None
    max_attempts: Optional[int] = None


class ExamOut(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str]
    created_by: int
    duration_minutes: int
    total_marks: float
    passing_marks: float
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    is_published: bool
    shuffle_questions: bool
    show_results: bool
    max_attempts: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ExamAssign(BaseModel):
    student_ids: List[int]