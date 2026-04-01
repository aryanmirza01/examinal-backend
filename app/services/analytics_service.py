"""
Analytics computations for exams, questions, students, courses.
"""

import logging
from typing import Optional, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.question import ExamQuestion
from app.models.submission import ExamSubmission, AnswerResponse
from app.models.course import Course
from app.models.user import User
from app.schemas.analytics import (
    ExamAnalytics,
    QuestionAnalytics,
    StudentPerformance,
    CourseAnalytics,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_exam_analytics(self, exam_id: int) -> Optional[ExamAnalytics]:
        exam = self.db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            return None

        submissions = (
            self.db.query(ExamSubmission).filter(ExamSubmission.exam_id == exam_id).all()
        )
        graded = [s for s in submissions if s.status == "graded"]
        submitted = [s for s in submissions if s.status in ("submitted", "graded")]
        scores = [s.percentage for s in graded if s.percentage is not None]

        # Score distribution buckets
        dist = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for s in scores:
            if s <= 20:
                dist["0-20"] += 1
            elif s <= 40:
                dist["21-40"] += 1
            elif s <= 60:
                dist["41-60"] += 1
            elif s <= 80:
                dist["61-80"] += 1
            else:
                dist["81-100"] += 1

        pass_count = sum(1 for s in graded if s.is_passed)

        return ExamAnalytics(
            exam_id=exam_id,
            exam_title=exam.title,
            total_students=len(submissions),
            submitted_count=len(submitted),
            graded_count=len(graded),
            average_score=round(sum(scores) / len(scores), 2) if scores else None,
            highest_score=max(scores) if scores else None,
            lowest_score=min(scores) if scores else None,
            pass_rate=round(pass_count / len(graded) * 100, 2) if graded else None,
            score_distribution=dist,
        )

    def get_question_analytics(self, exam_id: int) -> List[QuestionAnalytics]:
        questions = (
            self.db.query(ExamQuestion)
            .filter(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.order_index)
            .all()
        )

        analytics = []
        for q in questions:
            answers = self.db.query(AnswerResponse).filter(AnswerResponse.question_id == q.id).all()
            total = len(answers)
            correct = sum(1 for a in answers if a.is_correct)
            avg_score = sum(a.score for a in answers) / total if total else 0

            accuracy = correct / total if total else 0
            if accuracy >= 0.8:
                rating = "easy"
            elif accuracy >= 0.5:
                rating = "medium"
            else:
                rating = "hard"

            analytics.append(QuestionAnalytics(
                question_id=q.id,
                question_text=q.question_text[:200],
                question_type=q.question_type,
                total_attempts=total,
                correct_count=correct,
                accuracy_rate=round(accuracy, 3),
                average_score=round(avg_score, 2),
                difficulty_rating=rating,
            ))

        return analytics

    def get_student_performance(self, student_id: int) -> Optional[StudentPerformance]:
        student = self.db.query(User).filter(User.id == student_id).first()
        if not student:
            return None

        submissions = (
            self.db.query(ExamSubmission)
            .filter(ExamSubmission.student_id == student_id, ExamSubmission.status == "graded")
            .all()
        )
        scores = [s.percentage for s in submissions if s.percentage is not None]

        # Weak areas: questions with low scores
        weak_areas: List[str] = []
        if submissions:
            low_answers = (
                self.db.query(AnswerResponse, ExamQuestion)
                .join(ExamQuestion, AnswerResponse.question_id == ExamQuestion.id)
                .filter(
                    AnswerResponse.submission_id.in_([s.id for s in submissions]),
                    AnswerResponse.is_correct == False,  # noqa: E712
                )
                .limit(10)
                .all()
            )
            seen = set()
            for answer, question in low_answers:
                topic = question.question_text[:80]
                if topic not in seen:
                    weak_areas.append(topic)
                    seen.add(topic)

        return StudentPerformance(
            student_id=student_id,
            student_name=student.full_name,
            exams_taken=len(submissions),
            average_score=round(sum(scores) / len(scores), 2) if scores else 0.0,
            highest_score=max(scores) if scores else 0.0,
            lowest_score=min(scores) if scores else 0.0,
            weak_areas=weak_areas[:5],
        )

    def get_course_analytics(self, course_id: int) -> Optional[CourseAnalytics]:
        course = self.db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return None

        exams = self.db.query(Exam).filter(Exam.course_id == course_id).all()
        exam_summaries = []
        all_scores = []

        for exam in exams:
            ea = self.get_exam_analytics(exam.id)
            if ea:
                exam_summaries.append(ea)
                if ea.average_score is not None:
                    all_scores.append(ea.average_score)

        from app.models.course import CourseEnrollment
        total_students = (
            self.db.query(func.count(CourseEnrollment.id))
            .filter(CourseEnrollment.course_id == course_id)
            .scalar()
        ) or 0

        return CourseAnalytics(
            course_id=course_id,
            course_title=course.title,
            total_exams=len(exams),
            total_students=total_students,
            overall_average=round(sum(all_scores) / len(all_scores), 2) if all_scores else None,
            exam_summaries=exam_summaries,
        )