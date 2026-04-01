from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel


class AnswerSubmit(BaseModel):
    question_id: int
    student_answer: str


class AutosaveRequest(BaseModel):
    answers: List[AnswerSubmit]


class SubmissionStart(BaseModel):
    exam_id: int


class SubmissionOut(BaseModel):
    id: int
    exam_id: int
    student_id: int
    started_at: datetime
    submitted_at: Optional[datetime]
    status: str
    total_score: Optional[float]
    max_score: Optional[float]
    percentage: Optional[float]
    is_passed: Optional[bool]
    graded_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AnswerResponseOut(BaseModel):
    id: int
    submission_id: int
    question_id: int
    student_answer: Optional[str]
    is_correct: Optional[bool]
    score: float
    max_score: float
    ai_feedback: Optional[str]
    confidence_score: Optional[float]

    model_config = {"from_attributes": True}


class SubmissionDetail(BaseModel):
    submission: SubmissionOut
    answers: List[AnswerResponseOut]


class ActivityEvent(BaseModel):
    exam_id: int
    submission_id: int
    action_type: str  # tab_switch | copy_attempt | paste_attempt | right_click | focus_lost | focus_gained
    details: Optional[Dict] = None