"""
AI Grading Engine — Multi-pass evaluation with NVIDIA Nemotron.

Grading Pipeline:
  1. MCQ: Exact match (instant, 100% accurate)
  2. Short Answer: Keyword extraction + semantic LLM scoring
  3. Descriptive: Multi-pass rubric-based evaluation
     Pass 1: Initial scoring with rubric criteria
     Pass 2: Verification pass — checks for over/under scoring
     Final: Averaged score with confidence calibration

This achieves significantly higher grading accuracy than single-pass.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.submission import ExamSubmission, AnswerResponse
from app.models.question import ExamQuestion
from app.services.rag_pipeline import call_llm

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  GRADING PROMPTS — Optimized for Nemotron accuracy
# ═══════════════════════════════════════════════════════════════

GRADING_SYSTEM = """You are an expert academic exam grader with years of experience.

GRADING PRINCIPLES:
1. Be FAIR — grade on substance, not phrasing
2. Be RIGOROUS — partial credit only for partially correct answers  
3. Be CONSISTENT — same quality answer always gets same score
4. KEY TERMS matter — correct terminology demonstrates understanding
5. WRONG facts get ZERO credit for that portion
6. You MUST return valid JSON only — no explanation outside JSON"""

RUBRIC_GRADING_PROMPT = """Grade this student answer using the rubric below.

═══ QUESTION ═══
{question}

═══ MODEL ANSWER ═══
{correct_answer}

═══ EVALUATION CRITERIA ═══
{rubric}

═══ STUDENT ANSWER ═══
{student_answer}

═══ SCORING RULES ═══
Maximum score: {max_score}
- Full marks: All key concepts present with correct terminology
- 75% marks: Most concepts correct, minor gaps
- 50% marks: Core idea understood, significant gaps
- 25% marks: Some relevant content, major errors
- 0 marks: Completely wrong, irrelevant, or blank

Evaluate step by step:
1. List which rubric criteria the student met
2. List which criteria are missing or wrong
3. Identify any factual errors
4. Calculate the score

Return ONLY this JSON:
{{
  "criteria_met": ["criterion 1", "criterion 2"],
  "criteria_missed": ["criterion 3"],
  "factual_errors": ["error description or empty list"],
  "score": <float 0 to {max_score}>,
  "is_correct": <true if score >= 70% of max>,
  "feedback": "<2-3 sentences: what was good, what was wrong, how to improve>",
  "confidence": <float 0.0 to 1.0>
}}"""

SIMPLE_GRADING_PROMPT = """Grade this student answer by comparing to the model answer.

═══ QUESTION ═══
{question}

═══ MODEL ANSWER ═══
{correct_answer}

═══ STUDENT ANSWER ═══
{student_answer}

═══ SCORING ═══
Maximum score: {max_score}
Grade based on factual correctness, completeness, and understanding.

Return ONLY this JSON:
{{
  "score": <float 0 to {max_score}>,
  "is_correct": <true if score >= 70% of max>,
  "feedback": "<specific feedback: what's correct, what's wrong>",
  "confidence": <float 0.0 to 1.0>
}}"""

VERIFICATION_PROMPT = """You are a grading auditor. Review this grading result for accuracy.

═══ QUESTION ═══
{question}

═══ MODEL ANSWER ═══
{correct_answer}

═══ STUDENT ANSWER ═══
{student_answer}

═══ INITIAL GRADE ═══
Score: {initial_score}/{max_score}
Feedback: {initial_feedback}

═══ YOUR TASK ═══
Check if the initial grade is fair and accurate:
1. Is the score too high? (student got credit for wrong things)
2. Is the score too low? (student had correct content that was missed)
3. Is the feedback accurate?

Return ONLY this JSON:
{{
  "adjusted_score": <float 0 to {max_score}>,
  "adjustment_reason": "<why you changed or kept the score>",
  "confidence": <float 0.0 to 1.0>
}}"""

SHORT_ANSWER_PROMPT = """Grade this short answer question.

═══ QUESTION ═══
{question}

═══ MODEL ANSWER ═══
{correct_answer}

═══ KEY TERMS (must appear for full credit) ═══
{key_terms}

═══ STUDENT ANSWER ═══
{student_answer}

═══ SCORING (max {max_score}) ═══
- All key terms present + correct explanation = full marks
- Most key terms + partial explanation = 70-90%
- Some key terms + vague explanation = 40-60%
- Wrong or irrelevant = 0-20%

Return ONLY this JSON:
{{
  "key_terms_found": ["term1", "term2"],
  "key_terms_missing": ["term3"],
  "score": <float 0 to {max_score}>,
  "is_correct": <true if score >= 70% of max>,
  "feedback": "<specific feedback>",
  "confidence": <float 0.0 to 1.0>
}}"""


class GradingService:
    def __init__(self, db: Session):
        self.db = db
        self.mode = settings.GRADING_MODE
        self.confidence_threshold = settings.GRADING_CONFIDENCE_THRESHOLD

    def grade_submission(self, submission: ExamSubmission):
        """Grade all answers in a submission."""
        answers = (
            self.db.query(AnswerResponse)
            .filter(AnswerResponse.submission_id == submission.id)
            .all()
        )

        total_score = 0.0
        total_max = 0.0
        low_confidence_count = 0

        for answer in answers:
            question = (
                self.db.query(ExamQuestion)
                .filter(ExamQuestion.id == answer.question_id)
                .first()
            )
            if not question:
                continue

            answer.max_score = question.marks
            total_max += question.marks

            if not answer.student_answer or not answer.student_answer.strip():
                answer.score = 0.0
                answer.is_correct = False
                answer.ai_feedback = "No answer provided."
                answer.confidence_score = 1.0
                continue

            # ── Grade by type ──
            if question.question_type == "mcq":
                self._grade_mcq(answer, question)
            elif question.question_type == "short_answer":
                self._grade_short_answer(answer, question)
            else:
                self._grade_descriptive(answer, question)

            total_score += answer.score

            if answer.confidence_score is not None and answer.confidence_score < self.confidence_threshold:
                low_confidence_count += 1

        # ── Update submission ──
        submission.total_score = round(total_score, 2)
        submission.max_score = round(total_max, 2)
        submission.percentage = round((total_score / total_max * 100), 2) if total_max > 0 else 0
        exam = submission.exam
        passing_pct = (exam.passing_marks / exam.total_marks * 100) if exam and exam.total_marks else 40
        submission.is_passed = submission.percentage >= passing_pct
        submission.status = "graded"
        submission.graded_at = datetime.now(timezone.utc)

        self.db.commit()

        logger.info(
            "Graded submission %d: %.1f/%.1f (%.1f%%) — %d low-confidence answers",
            submission.id, total_score, total_max,
            submission.percentage or 0, low_confidence_count,
        )

    # ═══════════════════════════════════════════════════════════
    #  MCQ — Exact match (100% accurate, no LLM needed)
    # ═══════════════════════════════════════════════════════════

    def _grade_mcq(self, answer: AnswerResponse, question: ExamQuestion):
        student = answer.student_answer.strip().upper()
        correct = question.correct_answer.strip().upper()

        is_correct = student == correct
        answer.is_correct = is_correct
        answer.score = question.marks if is_correct else 0.0
        answer.confidence_score = 1.0

        if is_correct:
            answer.ai_feedback = "Correct!"
        else:
            answer.ai_feedback = f"Incorrect. The correct answer is {correct}."

        if question.explanation:
            answer.ai_feedback += f" {question.explanation}"

    # ═══════════════════════════════════════════════════════════
    #  SHORT ANSWER — Key term matching + LLM evaluation
    # ═══════════════════════════════════════════════════════════

    def _grade_short_answer(self, answer: AnswerResponse, question: ExamQuestion):
        # Extract key terms from explanation if available
        key_terms = self._extract_key_terms(question)

        try:
            prompt = SHORT_ANSWER_PROMPT.format(
                question=question.question_text,
                correct_answer=question.correct_answer,
                key_terms=", ".join(key_terms) if key_terms else "Not specified — compare to model answer",
                student_answer=answer.student_answer,
                max_score=question.marks,
            )
            raw = call_llm(prompt, GRADING_SYSTEM, temperature=0.1)
            result = self._parse_grade(raw, question.marks)

            answer.score = result["score"]
            answer.is_correct = result["is_correct"]
            answer.confidence_score = result["confidence"]

            # Build detailed feedback
            feedback_parts = [result["feedback"]]
            if result.get("key_terms_found"):
                feedback_parts.append(f"Key terms found: {', '.join(result['key_terms_found'])}")
            if result.get("key_terms_missing"):
                feedback_parts.append(f"Missing: {', '.join(result['key_terms_missing'])}")
            answer.ai_feedback = " | ".join(feedback_parts)

        except Exception as e:
            logger.error("Short answer grading failed for answer %d: %s", answer.id, e)
            self._fallback_grade(answer, question)

    # ═══════════════════════════════════════════════════════════
    #  DESCRIPTIVE — Multi-pass rubric evaluation
    # ═══════════════════════════════════════════════════════════

    def _grade_descriptive(self, answer: AnswerResponse, question: ExamQuestion):
        if self.mode == "multi_pass":
            self._grade_descriptive_multi_pass(answer, question)
        else:
            self._grade_descriptive_single(answer, question)

    def _grade_descriptive_single(self, answer: AnswerResponse, question: ExamQuestion):
        """Single-pass grading — faster but less accurate."""
        try:
            rubric = self._extract_rubric(question)

            if rubric and settings.ENABLE_RUBRIC_GRADING:
                prompt = RUBRIC_GRADING_PROMPT.format(
                    question=question.question_text,
                    correct_answer=question.correct_answer,
                    rubric=rubric,
                    student_answer=answer.student_answer,
                    max_score=question.marks,
                )
            else:
                prompt = SIMPLE_GRADING_PROMPT.format(
                    question=question.question_text,
                    correct_answer=question.correct_answer,
                    student_answer=answer.student_answer,
                    max_score=question.marks,
                )

            raw = call_llm(prompt, GRADING_SYSTEM, temperature=0.1)
            result = self._parse_grade(raw, question.marks)

            answer.score = result["score"]
            answer.is_correct = result["is_correct"]
            answer.ai_feedback = result["feedback"]
            answer.confidence_score = result["confidence"]

        except Exception as e:
            logger.error("Descriptive grading failed for answer %d: %s", answer.id, e)
            self._fallback_grade(answer, question)

    def _grade_descriptive_multi_pass(self, answer: AnswerResponse, question: ExamQuestion):
        """
        Multi-pass grading for maximum accuracy:
          Pass 1: Initial rubric-based scoring
          Pass 2: Verification — check for over/under scoring
          Final:  Weighted average with confidence calibration
        """
        try:
            rubric = self._extract_rubric(question)

            # ── PASS 1: Initial grading ──
            if rubric and settings.ENABLE_RUBRIC_GRADING:
                prompt1 = RUBRIC_GRADING_PROMPT.format(
                    question=question.question_text,
                    correct_answer=question.correct_answer,
                    rubric=rubric,
                    student_answer=answer.student_answer,
                    max_score=question.marks,
                )
            else:
                prompt1 = SIMPLE_GRADING_PROMPT.format(
                    question=question.question_text,
                    correct_answer=question.correct_answer,
                    student_answer=answer.student_answer,
                    max_score=question.marks,
                )

            raw1 = call_llm(prompt1, GRADING_SYSTEM, temperature=0.1)
            result1 = self._parse_grade(raw1, question.marks)

            # ── PASS 2: Verification ──
            prompt2 = VERIFICATION_PROMPT.format(
                question=question.question_text,
                correct_answer=question.correct_answer,
                student_answer=answer.student_answer,
                initial_score=result1["score"],
                max_score=question.marks,
                initial_feedback=result1["feedback"],
            )

            raw2 = call_llm(prompt2, GRADING_SYSTEM, temperature=0.1)
            result2 = self._parse_verification(raw2, question.marks)

            # ── COMBINE: Weighted average ──
            pass1_score = result1["score"]
            pass2_score = result2["adjusted_score"]
            pass1_conf = result1["confidence"]
            pass2_conf = result2["confidence"]

            # Weight by confidence
            total_conf = pass1_conf + pass2_conf
            if total_conf > 0:
                final_score = (pass1_score * pass1_conf + pass2_score * pass2_conf) / total_conf
            else:
                final_score = (pass1_score + pass2_score) / 2

            final_score = round(min(final_score, question.marks), 2)
            final_confidence = round((pass1_conf + pass2_conf) / 2, 3)

            answer.score = final_score
            answer.is_correct = final_score >= (question.marks * 0.7)
            answer.confidence_score = final_confidence

            # Build comprehensive feedback
            feedback_parts = [result1["feedback"]]
            if abs(pass1_score - pass2_score) > 0.5:
                feedback_parts.append(
                    f"[Verification adjusted score from {pass1_score} to {pass2_score}: "
                    f"{result2.get('adjustment_reason', 'refinement')}]"
                )
            if final_confidence < self.confidence_threshold:
                feedback_parts.append("[⚠ Low confidence — instructor review recommended]")

            answer.ai_feedback = " ".join(feedback_parts)

            logger.debug(
                "Multi-pass grade: P1=%.2f (conf=%.2f) P2=%.2f (conf=%.2f) → Final=%.2f",
                pass1_score, pass1_conf, pass2_score, pass2_conf, final_score,
            )

        except Exception as e:
            logger.error("Multi-pass grading failed for answer %d: %s", answer.id, e)
            # Try single pass as fallback
            try:
                self._grade_descriptive_single(answer, question)
            except Exception:
                self._fallback_grade(answer, question)

    # ═══════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════

    def _extract_rubric(self, question: ExamQuestion) -> str:
        """Extract rubric criteria from question explanation."""
        if not question.explanation:
            return ""
        explanation = question.explanation
        rubric_parts = []
        if "Rubric:" in explanation:
            rubric_section = explanation.split("Rubric:")[1].strip()
            rubric_parts.append(rubric_section)
        elif "Key terms:" in explanation:
            terms_section = explanation.split("Key terms:")[1].strip()
            rubric_parts.append(f"Must include these key terms: {terms_section}")
        if not rubric_parts:
            rubric_parts.append(f"Compare against model answer. Explanation: {explanation}")
        return "\n".join(rubric_parts)

    def _extract_key_terms(self, question: ExamQuestion) -> List[str]:
        """Extract key terms from explanation."""
        if not question.explanation:
            return []
        if "Key terms:" in question.explanation:
            terms_str = question.explanation.split("Key terms:")[1].strip()
            return [t.strip() for t in terms_str.split(",") if t.strip()]
        return []

    def _fallback_grade(self, answer: AnswerResponse, question: ExamQuestion):
        """Keyword overlap scoring when LLM is unavailable."""
        student_words = set(answer.student_answer.lower().split())
        correct_words = set(question.correct_answer.lower().split())
        # Remove common stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                      "to", "for", "of", "and", "or", "but", "it", "this", "that", "with"}
        student_words -= stop_words
        correct_words -= stop_words

        if not correct_words:
            answer.score = 0.0
            answer.is_correct = False
            answer.ai_feedback = "Could not auto-grade. Manual review required."
            answer.confidence_score = 0.0
            return

        overlap = len(student_words & correct_words) / len(correct_words)
        answer.score = round(overlap * question.marks, 2)
        answer.is_correct = overlap >= 0.7
        answer.confidence_score = 0.2
        answer.ai_feedback = (
            f"Fallback scoring by keyword overlap ({overlap:.0%}). "
            f"Matched: {', '.join(student_words & correct_words) or 'none'}. "
            f"⚠ Manual review strongly recommended."
        )

    @staticmethod
    def _parse_grade(text: str, max_score: float) -> dict:
        """Parse grading JSON from LLM output."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(text[start: end + 1])
                return {
                    "score": min(float(data.get("score", 0)), max_score),
                    "is_correct": bool(data.get("is_correct", False)),
                    "feedback": str(data.get("feedback", "")),
                    "confidence": min(float(data.get("confidence", 0.5)), 1.0),
                    "key_terms_found": data.get("key_terms_found", []),
                    "key_terms_missing": data.get("key_terms_missing", []),
                    "criteria_met": data.get("criteria_met", []),
                    "criteria_missed": data.get("criteria_missed", []),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return {
            "score": 0.0,
            "is_correct": False,
            "feedback": "Grading response could not be parsed. Manual review needed.",
            "confidence": 0.0,
        }

    @staticmethod
    def _parse_verification(text: str, max_score: float) -> dict:
        """Parse verification pass JSON."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(text[start: end + 1])
                return {
                    "adjusted_score": min(float(data.get("adjusted_score", 0)), max_score),
                    "adjustment_reason": str(data.get("adjustment_reason", "")),
                    "confidence": min(float(data.get("confidence", 0.5)), 1.0),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return {
            "adjusted_score": 0.0,
            "adjustment_reason": "Could not parse verification",
            "confidence": 0.0,
        }