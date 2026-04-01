from typing import Optional, List, Dict

from pydantic import BaseModel


class ExamAnalytics(BaseModel):
    exam_id: int
    exam_title: str
    total_students: int
    submitted_count: int
    graded_count: int
    average_score: Optional[float]
    highest_score: Optional[float]
    lowest_score: Optional[float]
    pass_rate: Optional[float]
    score_distribution: Dict[str, int]


class QuestionAnalytics(BaseModel):
    question_id: int
    question_text: str
    question_type: str
    total_attempts: int
    correct_count: int
    accuracy_rate: float
    average_score: float
    difficulty_rating: str


class StudentPerformance(BaseModel):
    student_id: int
    student_name: str
    exams_taken: int
    average_score: float
    highest_score: float
    lowest_score: float
    weak_areas: List[str]


class CourseAnalytics(BaseModel):
    course_id: int
    course_title: str
    total_exams: int
    total_students: int
    overall_average: Optional[float]
    exam_summaries: List[ExamAnalytics]