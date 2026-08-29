"""
AI Theory Evaluator Service

Scores theory answers against a marking rubric and returns structured feedback.
Runs on an OpenAI-compatible open-weight model via curriculum.llm (Groq by default),
with automatic model and provider failover. Google Gemini is no longer used.
"""

import json
import logging
from typing import Dict, Any, Optional

from .. import llm

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when every configured LLM provider is rate-limited."""


# Historical name kept so the Celery retry paths in tasks.py keep working unchanged.
Gemini429Exception = RateLimitExceeded


def _get_api_key():
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


class AITheoryEvaluator:
    """
    Service class for evaluating theory question answers using Gemini AI.
    
    Features:
    - Structured scoring based on marking rubrics
    - Detailed feedback generation
    - Score validation and normalization
    - Proper error handling without fake scores
    """

    @staticmethod
    def evaluate(
        question_text,
        student_answer,
        ideal_answer,
        marking_rubric,
        maximum_marks
    ):
        """
        Evaluate a theory question answer using AI.
        
        Args:
            question_text: The question text
            student_answer: The student's answer
            ideal_answer: The ideal/model answer
            marking_rubric: List of scoring criteria with marks
            maximum_marks: Maximum possible marks
        
        Returns:
            dict: {
                'score': float,  # Marks awarded (0 to maximum_marks)
                'feedback': str,  # Detailed feedback for student
                'rubric_breakdown': [  # Score per criterion
                    {
                        'criterion': str,
                        'marks_allocated': int,
                        'marks_awarded': float,
                        'feedback': str
                    }
                ],
                'success': bool
            }
            
            On error returns: {'success': False, 'error': str, 'score': None}
        """
        if not student_answer or not student_answer.strip():
            return {
                'success': True,
                'score': 0.0,
                'feedback': "No answer provided.",
                'rubric_breakdown': []
            }
        
        # Prepare rubric for prompt
        rubric_text = ""
        if marking_rubric and isinstance(marking_rubric, list):
            rubric_text = "\n".join([
                f"- {item.get('criterion', 'Unknown')}: {item.get('marks', 0)} marks"
                for item in marking_rubric
            ])
        else:
            rubric_text = f"Total marks available: {maximum_marks}"
        
        prompt = f"""You are an expert medical examiner evaluating a student's answer to a theory question.

QUESTION:
{question_text}

IDEAL ANSWER:
{ideal_answer}

MARKING RUBRIC:
{rubric_text}

MAXIMUM MARKS: {maximum_marks}

STUDENT'S ANSWER:
{student_answer}

TASK: Evaluate the student's answer objectively and provide:
1. A score out of {maximum_marks} marks
2. Detailed feedback explaining the score
3. Breakdown by rubric criteria (if provided)

CRITICAL REQUIREMENTS:
- Be fair and objective
- Award partial marks for partially correct answers
- Provide constructive feedback
- Use Nigerian medical education standards
- Score must be between 0 and {maximum_marks}

RESPOND ONLY WITH VALID JSON. NO MARKDOWN CODE BLOCKS.

Format:
{{
  "score": 12.5,
  "feedback": "Your answer demonstrates good understanding of...",
  "rubric_breakdown": [
    {{
      "criterion": "Identifies anterior wall",
      "marks_allocated": 3,
      "marks_awarded": 2.5,
      "feedback": "Correctly identified but missing minor detail"
    }}
  ]
}}

Evaluate now."""

        try:
            raw_response = _generate([prompt])
            cleaned_json = _strip_json_fences(raw_response)
            data = json.loads(cleaned_json)
            
            # Extract and validate score
            score = data.get('score', 0)
            try:
                score = float(score)
            except (ValueError, TypeError):
                score = 0.0
            
            # Ensure score is within bounds
            score = max(0.0, min(score, float(maximum_marks)))
            
            # Extract feedback
            feedback = data.get('feedback', '').strip()
            if not feedback:
                feedback = f"Score: {score}/{maximum_marks}"
            
            # Extract rubric breakdown
            rubric_breakdown = data.get('rubric_breakdown', [])
            if not isinstance(rubric_breakdown, list):
                rubric_breakdown = []
            
            # Validate rubric breakdown
            validated_breakdown = []
            for item in rubric_breakdown:
                if isinstance(item, dict):
                    try:
                        validated_breakdown.append({
                            'criterion': str(item.get('criterion', '')).strip(),
                            'marks_allocated': int(item.get('marks_allocated', 0)),
                            'marks_awarded': float(item.get('marks_awarded', 0)),
                            'feedback': str(item.get('feedback', '')).strip()
                        })
                    except (ValueError, TypeError):
                        continue
            
            logger.info(
                f"Theory evaluation complete: {score}/{maximum_marks} marks"
            )
            
            return {
                'success': True,
                'score': score,
                'feedback': feedback,
                'rubric_breakdown': validated_breakdown
            }
            
        except Gemini429Exception:
            logger.warning("Rate limit hit during theory evaluation")
            raise
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in theory evaluation: {e}")
            return {
                'success': False,
                'error': f"Failed to parse AI response: {str(e)}",
                'score': None
            }
            
        except Exception as e:
            logger.error(f"Error in theory evaluation: {e}")
            return {
                'success': False,
                'error': f"Evaluation failed: {str(e)}",
                'score': None
            }


# Singleton instance
theory_evaluator = AITheoryEvaluator()