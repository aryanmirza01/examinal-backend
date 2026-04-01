"""
RAG + LLM question generation with robust JSON parsing.
"""

import json
import logging
import re
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.question import ExamQuestion
from app.services.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert exam question generator for academic assessments.

STRICT RULES:
1. Use ONLY the provided course context.
2. Every question must be answerable from the context.
3. Return ONLY a valid JSON array — no markdown fences, no extra text.
4. Keep model answers CONCISE — max 3 sentences for short answer, max 5 sentences for descriptive.
5. Each question must have ONE clear correct answer."""

MCQ_PROMPT = """Generate exactly {num} MCQ questions from the context.
Difficulty: {difficulty}
{topic_line}

Each question: 4 options (A,B,C,D), one correct answer, brief explanation.

Return JSON array:
[{{"question_text":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"correct_answer":"A","explanation":"...","difficulty":"{difficulty}"}}]"""

SHORT_ANSWER_PROMPT = """Generate exactly {num} short-answer questions from the context.
Difficulty: {difficulty}
{topic_line}

Keep model answers to 1-2 sentences maximum.

Return JSON array:
[{{"question_text":"...","correct_answer":"1-2 sentence answer","explanation":"Why this is correct","difficulty":"{difficulty}"}}]"""

DESCRIPTIVE_PROMPT = """Generate exactly {num} essay questions from the context.
Difficulty: {difficulty}
{topic_line}

Keep model answers to 3-5 sentences maximum. Be concise.

Return JSON array:
[{{"question_text":"...","correct_answer":"3-5 sentence model answer","explanation":"Key evaluation points","difficulty":"{difficulty}"}}]"""


class QuestionGeneratorService:
    def __init__(self, db: Session):
        self.db = db
        self.rag = RAGPipeline()

    def generate(
        self,
        course_id: int,
        exam_id: int,
        num_questions: int = 5,
        question_type: str = "mcq",
        difficulty: str = "medium",
        topic: Optional[str] = None,
    ) -> List[ExamQuestion]:

        topic_line = f"Focus on: {topic}" if topic else ""
        search_query = topic or "key concepts important topics"

        passages = self.rag.retrieve_context(course_id, search_query, top_k=10)
        if not passages:
            raise ValueError("No indexed content found. Upload and index course files first.")

        if question_type == "mixed":
            mcq_n = max(1, num_questions // 3)
            short_n = max(1, num_questions // 3)
            desc_n = num_questions - mcq_n - short_n
            questions = []
            if mcq_n > 0:
                questions += self._gen_type(passages, "mcq", mcq_n, difficulty, topic_line, exam_id)
            if short_n > 0:
                questions += self._gen_type(passages, "short_answer", short_n, difficulty, topic_line, exam_id)
            if desc_n > 0:
                questions += self._gen_type(passages, "descriptive", desc_n, difficulty, topic_line, exam_id)
            return questions
        else:
            return self._gen_type(passages, question_type, num_questions, difficulty, topic_line, exam_id)

    def _gen_type(self, passages, qtype, num, difficulty, topic_line, exam_id) -> List[ExamQuestion]:
        templates = {
            "mcq": MCQ_PROMPT,
            "short_answer": SHORT_ANSWER_PROMPT,
            "descriptive": DESCRIPTIVE_PROMPT,
        }
        template = templates.get(qtype, MCQ_PROMPT)
        user_prompt = template.format(num=num, difficulty=difficulty, topic_line=topic_line)

        # Use higher max_tokens for descriptive to avoid truncation
        token_limits = {
            "mcq": 4096,
            "short_answer": 4096,
            "descriptive": 8192,
        }

        raw = self.rag.generate_with_context(
            passages, user_prompt, SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=token_limits.get(qtype, 4096),
        )

        questions_data = self._parse_json(raw)
        if not questions_data:
            # Retry once with explicit JSON instruction
            retry_prompt = user_prompt + "\n\nIMPORTANT: Return ONLY the JSON array. No markdown. No ```json. Just the raw [ ... ] array."
            raw = self.rag.generate_with_context(
                passages, retry_prompt, SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=token_limits.get(qtype, 4096),
            )
            questions_data = self._parse_json(raw)

        if not questions_data:
            raise ValueError(f"Failed to parse LLM response for {qtype} questions. The AI response was not valid JSON.")

        max_idx = (
            self.db.query(func.max(ExamQuestion.order_index))
            .filter(ExamQuestion.exam_id == exam_id)
            .scalar()
        ) or 0

        marks_map = {"mcq": 1.0, "short_answer": 3.0, "descriptive": 5.0}
        created: List[ExamQuestion] = []

        for i, qd in enumerate(questions_data[:num]):
            if not isinstance(qd, dict):
                continue
            question_text = qd.get("question_text", "").strip()
            correct_answer = qd.get("correct_answer", "").strip()
            if not question_text or not correct_answer:
                continue

            q = ExamQuestion(
                exam_id=exam_id,
                question_text=question_text,
                question_type=qtype,
                options=qd.get("options"),
                correct_answer=correct_answer,
                marks=marks_map.get(qtype, 1.0),
                explanation=qd.get("explanation", ""),
                difficulty=qd.get("difficulty", difficulty),
                order_index=max_idx + i + 1,
            )
            self.db.add(q)
            created.append(q)

        self.db.commit()
        for q in created:
            self.db.refresh(q)

        logger.info("Generated %d %s questions for exam %d", len(created), qtype, exam_id)
        return created

    @staticmethod
    def _parse_json(text: str) -> list:
        """
        Robust JSON extraction from LLM output.
        Handles: markdown fences, truncated JSON, mixed text.
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # Step 1: Remove markdown code fences
        text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # Step 2: Try direct parse
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass

        # Step 3: Find JSON array in text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            json_str = text[start: end + 1]
            try:
                data = json.loads(json_str)
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        # Step 4: Try to fix truncated JSON (response cut off mid-object)
        if start != -1:
            json_str = text[start:]

            # If array is not closed, try to close it
            if "]" not in json_str:
                # Find the last complete object (ends with })
                last_brace = json_str.rfind("}")
                if last_brace != -1:
                    json_str = json_str[:last_brace + 1] + "]"
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, list):
                            logger.warning("Recovered %d items from truncated JSON", len(data))
                            return data
                    except json.JSONDecodeError:
                        pass

            # Try removing the last incomplete object
            # Find all complete objects by splitting on },{
            try:
                # Remove outer brackets
                inner = json_str.strip()
                if inner.startswith("["):
                    inner = inner[1:]
                if inner.endswith("]"):
                    inner = inner[:-1]

                # Split into potential objects
                objects = []
                depth = 0
                current = ""
                for char in inner:
                    current += char
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            # Try parsing this object
                            obj_str = current.strip().strip(",").strip()
                            try:
                                obj = json.loads(obj_str)
                                objects.append(obj)
                            except json.JSONDecodeError:
                                pass
                            current = ""

                if objects:
                    logger.warning("Recovered %d items by parsing individual objects", len(objects))
                    return objects
            except Exception:
                pass

        # Step 5: Try to find individual JSON objects
        objects = []
        for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
            try:
                obj = json.loads(match.group())
                if "question_text" in obj:
                    objects.append(obj)
            except json.JSONDecodeError:
                continue

        if objects:
            logger.warning("Recovered %d questions by regex extraction", len(objects))
            return objects

        logger.error("JSON parse completely failed. Response preview: %s", text[:500])
        return []