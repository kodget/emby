import json
import logging
from typing import List, Dict, Any
from google import genai
from google.genai import types
from django.conf import settings
import os

logger = logging.getLogger(__name__)


class Gemini429Exception(Exception):
    """Raised when Gemini API returns 429 rate limit error."""
    pass


def _get_api_key() -> str:
    """Resolve the Gemini API key from Django settings, falling back to env."""
    try:
        from django.conf import settings
        key = getattr(settings, "GEMINI_API_KEY", "") or ""
    except Exception:
        key = ""
    return key or os.getenv("GEMINI_API_KEY", "")


def _get_client():
    """Lazy-initialize the Gemini client."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to your .env to enable AI features."
        )
    return genai.Client(api_key=api_key)


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences the model sometimes wraps JSON in."""
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop the opening fence (``` or ```json) and a trailing fence if present
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _generate(parts: list, model: str = "gemini-3.6-flash") -> str:
    """
    Call Gemini API with text parts.
    Raises Gemini429Exception on rate limit errors.
    """
    client = _get_client()
    try:
        content_parts = []
        for part in parts:
            if isinstance(part, str):
                content_parts.append(types.Part.from_text(text=part))

        response = client.models.generate_content(
            model=model,
            contents=content_parts,
        )
        return response.text or ""
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
            logger.warning(f"Gemini 429 rate limit hit: {e}")
            raise Gemini429Exception(f"Rate limit exceeded: {e}")
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
