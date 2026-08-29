"""
AI Question Generator — MCQ and theory generation from slide text.

Runs on an OpenAI-compatible open-weight model via curriculum.llm (Groq by default),
with automatic model and provider failover. Google Gemini is no longer used.
"""

import json
import logging
from typing import List, Dict, Any

from django.conf import settings

from .. import llm

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when every configured LLM provider is rate-limited."""


# Historical name kept so the Celery retry paths in tasks.py keep working unchanged.
Gemini429Exception = RateLimitExceeded


def _get_api_key() -> str:
    """Deprecated shim; see curriculum.llm."""
    return llm.api_key()


def _strip_json_fences(text) -> str:
    """Remove markdown code fences the model sometimes wraps JSON in."""
    return llm.strip_fences(text)


def _generate(parts: list, model=None) -> str:
    """
    Run a completion against the configured open-weight model.

    Keeps the original `parts` list signature so every call site is unchanged.
    Raises RateLimitExceeded (aliased as Gemini429Exception for the existing Celery
    retry logic in tasks.py) when every provider in the chain is rate-limited.
    """
    prompt = "\n\n".join(p for p in parts if isinstance(p, str) and p).strip()
    if not prompt:
        raise llm.LLMError("Refusing to call the model with an empty prompt.")

    try:
        return llm.chat(
            [{"role": "user", "content": prompt}],
            model=model,
            temperature=0.5,
            max_tokens=4096,
        )
    except llm.LLMError as e:
        text = str(e).lower()
        if "429" in text or "rate limit" in text or "quota" in text:
            logger.warning("LLM rate limited across all providers: %s", e)
            raise RateLimitExceeded(str(e)) from e
        raise


class AIQuestionGenerator:
    """
    Service class for generating MCQs and theory questions from slide text.
    """
    
    @staticmethod
    def questions_exist_for_slide(slide_id: str) -> bool:
        """Check if questions have already been generated for this slide."""
        from curriculum.models import QuizQuestion
        return QuizQuestion.objects.filter(source_slide_id=slide_id).exists()

    @staticmethod
    def generate_mcqs_from_text(text: str, slide, topic, count: int, difficulty: str) -> List[Dict[str, Any]]:
        """
        Generate multiple-choice questions (MCQs) from text.
        """
        subject_name = slide.subject.name if slide.subject else "General"
        topic_name = topic.name if topic else ""
        source = text.strip()[:15000]
        
        prompt = f"""You are an examiner creating MCQ assessment questions for Nigerian medical students.
        
SUBJECT: {subject_name}
TOPIC: {topic_name}
DIFFICULTY: {difficulty}
SOURCE MATERIAL:
{source}

TASK: Create exactly {count} MCQ questions strictly grounded in the SOURCE MATERIAL above.
All questions must have the difficulty: '{difficulty}'.

Spread the correct answer evenly across A, B, C and D. Do not let one letter dominate,
and never make A correct for every question — students learn the pattern, not the anatomy.
Every distractor must be plausible to someone who half-knows the material.

EXACTLY ONE option must be defensible. Before writing each question, check every
distractor and confirm it is unambiguously wrong. If the source says a structure gives
rise to two things, do not ask "which of these is a branch" and then list both of them —
that question has two right answers and is unusable. Reword the stem so only one option
can be correct, for example by asking which structure is NOT a branch, or by adding a
detail that excludes the other candidates.

RESPOND ONLY WITH VALID JSON. NO MARKDOWN CODE BLOCKS. NO PREAMBLE.

Format:
[
  {{
    "question_text": "Question stem?",
    "option_a": "First option",
    "option_b": "Second option",
    "option_c": "Third option",
    "option_d": "Fourth option",
    "correct_option": "A",
    "explanation": "Why the correct option is right",
    "difficulty": "{difficulty}",
    "maximum_marks": 1
  }}
]
"""
        raw = _generate([prompt])
        data = json.loads(_strip_json_fences(raw))
        if not isinstance(data, list):
            if isinstance(data, dict) and "mcqs" in data:
                data = data["mcqs"]
            else:
                data = [data]
                
        # Validate/clean
        cleaned = []
        for item in data[:count]:
            correct = str(item.get("correct_option", "A")).strip().upper()[:1]
            if correct not in ("A", "B", "C", "D"):
                correct = "A"
            cleaned.append({
                "question_text": item.get("question_text", item.get("question", "")),
                "option_a": item.get("option_a", ""),
                "option_b": item.get("option_b", ""),
                "option_c": item.get("option_c", ""),
                "option_d": item.get("option_d", ""),
                "correct_option": correct,
                "explanation": item.get("explanation", ""),
                "difficulty": item.get("difficulty", difficulty),
                "maximum_marks": int(item.get("maximum_marks", 1))
            })
        return cleaned

    @staticmethod
    def generate_theory_from_text(text: str, slide, topic, count: int, difficulty: str) -> List[Dict[str, Any]]:
        """
        Generate theory (open-ended) questions from text with marking rubrics.
        """
        subject_name = slide.subject.name if slide.subject else "General"
        topic_name = topic.name if topic else ""
        source = text.strip()[:15000]
        
        prompt = f"""You are an examiner creating theory assessment questions for Nigerian medical students.
        
SUBJECT: {subject_name}
TOPIC: {topic_name}
DIFFICULTY: {difficulty}
SOURCE MATERIAL:
{source}

TASK: Create exactly {count} theory questions strictly grounded in the SOURCE MATERIAL above.
All questions must have the difficulty: '{difficulty}'.
Each question must include a marking rubric detailing specific scoring criteria (points) that sum to the maximum marks (typically 10 or 20).

RESPOND ONLY WITH VALID JSON. NO MARKDOWN CODE BLOCKS. NO PREAMBLE.

Format:
[
  {{
    "question_text": "Open-ended question?",
    "ideal_answer": "Concise model answer.",
    "marking_rubric": [
      {{"criterion": "Identifies key factor A", "marks": 5}},
      {{"criterion": "Explains mechanism B", "marks": 5}}
    ],
    "difficulty": "{difficulty}",
    "maximum_marks": 10
  }}
]
"""
        raw = _generate([prompt])
        data = json.loads(_strip_json_fences(raw))
        if not isinstance(data, list):
            if isinstance(data, dict) and "theory" in data:
                data = data["theory"]
            else:
                data = [data]
                
        cleaned = []
        for item in data[:count]:
            rubric = item.get("marking_rubric", [])
            if not isinstance(rubric, list):
                rubric = []
            
            # compute sum of rubric marks or use default
            total_rubric_marks = sum(int(r.get("marks", 0)) for r in rubric if isinstance(r, dict))
            max_marks = int(item.get("maximum_marks", 20))
            if total_rubric_marks > 0:
                max_marks = total_rubric_marks
                
            cleaned.append({
                "question_text": item.get("question_text", item.get("question", "")),
                "ideal_answer": item.get("ideal_answer", item.get("model_answer", "")),
                "marking_rubric": rubric,
                "difficulty": item.get("difficulty", difficulty),
                "maximum_marks": max_marks
            })
        return cleaned


# Global alias for compatibility
question_generator = AIQuestionGenerator
