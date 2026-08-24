"""
AI Theory Evaluator Service

Evaluates theory question answers using Google Gemini AI.
Provides structured feedback and scoring based on marking rubrics.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Gemini429Exception(Exception):
    """Raised when Gemini API returns 429 rate limit error."""
    pass


def _get_api_key():
    """Get Gemini API key from settings or environment."""
    try:
        from django.conf import settings
        key = getattr(settings, "GEMINI_API_KEY", "") or ""
    except Exception:
        key = ""
    return key or os.getenv("GEMINI_API_KEY", "")


def _get_client():
    """Initialize Gemini client."""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to your .env file."
        )
    from google import genai
    return genai.Client(api_key=api_key)


def _strip_json_fences(text):
    """Remove markdown code fences from JSON responses."""
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _generate(parts, model="gemini-3.6-flash"):
    """
    Call Gemini API with text parts.
    Raises Gemini429Exception on rate limit errors.
    """
    client = _get_client()
    from google.genai import types
    
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