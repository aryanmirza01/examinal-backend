from datetime import datetime
from typing import Optional, Dict

from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    exam_id: int
    question_text: str
    question_type: str = Field(pattern="^(mcq|short_answer|descriptive)$")
    options: Optional[Dict[str, str]] = None  # {"A":"...","B":"...","C":"...","D":"..."}
    correct_answer: str
    marks: float = Field(default=1.0, gt=0)
    explanation: Optional[str] = None
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    order_index: int = 0


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    options: Optional[Dict[str, str]] = None
    correct_answer: Optional[str] = None
    marks: Optional[float] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    order_index: Optional[int] = None


class QuestionOut(BaseModel):
    id: int
    exam_id: int
    question_text: str
    question_type: str
    options: Optional[Dict[str, str]]
    correct_answer: str
    marks: float
    explanation: Optional[str]
    difficulty: str
    order_index: int
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionStudentView(BaseModel):
    """Same as QuestionOut but hides correct_answer and explanation."""
    id: int
    exam_id: int
    question_text: str
    question_type: str
    options: Optional[Dict[str, str]]
    marks: float
    difficulty: str
    order_index: int

    model_config = {"from_attributes": True}


class GenerateQuestionsRequest(BaseModel):
    course_id: int
    exam_id: int
    num_questions: int = Field(default=5, ge=1, le=50)
    question_type: str = Field(default="mcq", pattern="^(mcq|short_answer|descriptive|mixed)$")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|mixed)$")
    topic: Optional[str] = None