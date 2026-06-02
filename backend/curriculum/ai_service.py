"""
AI Service — Slide-Aware Chat with Google Gemini (google-genai SDK)

CRITICAL ARCHITECTURE:
- The AI is STATELESS: send slide context (text + image) in EVERY request
- Per-slide conversation history managed by the frontend store
- Structured JSON for resources (YouTube, textbooks, MCQs)
- API key lives ONLY on the backend — never exposed to the browser
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def _get_client():
    """Lazy-initialize the Gemini client."""
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def _generate(parts: list, model: str = "gemini-2.0-flash") -> str:
    """
    Core helper: call Gemini with a list of parts (text and/or images).
    Returns the text response, or raises on failure.
    """
    client = _get_client()
    from google.genai import types

    content_parts = []
    for part in parts:
        if isinstance(part, str):
            content_parts.append(types.Part.from_text(text=part))
        elif isinstance(part, dict) and "data" in part:
            # Inline image
            content_parts.append(
                types.Part.from_bytes(
                    data=part["data"] if isinstance(part["data"], bytes) else bytes.fromhex(part["data"]) if all(c in "0123456789abcdefABCDEF" for c in part["data"][:10]) else __import__("base64").b64decode(part["data"]),
                    mime_type=part.get("mime_type", "image/jpeg"),
                )
            )

    response = client.models.generate_content(
        model=model,
        contents=content_parts,
    )
    return response.text or ""


class SlideAwareAI:
    """
    Slide-aware AI tutor.

    RULES:
    1. AI has NO memory — send context every request
    2. Include slide text + slide image in every chat call
    3. Send full per-slide conversation history each time
    4. Structured JSON for resource generation
    """

    def build_system_prompt(self, slide_context: Dict[str, Any]) -> str:
        return f"""You are Emby, a warm and encouraging AI study assistant for Nigerian medical students.

CURRENT CONTEXT:
- Slide {slide_context.get('slide_index', 1)} of {slide_context.get('total_slides', 1)}
- Title: {slide_context.get('title', 'Untitled')}
- Course: {slide_context.get('course', 'General')}

SLIDE CONTENT:
{slide_context.get('text', 'No text extracted from this slide.')}

YOUR ROLE:
1. Help the student understand THIS slide's content
2. Explain complex medical terms simply
3. Give clinical context relevant to Nigerian medical education
4. Refer to the slide image if the student asks about diagrams or charts
5. Generate MCQs or summaries when asked

TONE: Warm, encouraging, like a helpful senior colleague. If something is confusing, say so ("Totally normal to find this tricky at first...").
"""

    def chat(
        self,
        user_message: str,
        slide_context: Dict[str, Any],
        slide_image_base64: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Send a chat message with full slide context.

        Args:
            user_message: The student's question
            slide_context: dict with slide_index, total_slides, title, text, course
            slide_image_base64: raw base64 string of the current slide image
            conversation_history: [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            {"response": "...", "sources": [...], "youtube": {...}}
        """
        try:
            system_prompt = self.build_system_prompt(slide_context)

            # Build history string to prepend
            history_text = ""
            if conversation_history:
                for msg in conversation_history[-6:]:  # Last 6 exchanges to keep context bounded
                    role = "Student" if msg.get("role") == "user" else "Emby"
                    history_text += f"{role}: {msg.get('content', '')}\n"

            full_prompt = f"{system_prompt}\n\nPrevious conversation:\n{history_text}\nStudent: {user_message}\nEmby:"

            parts: list = []

            # Include slide image for vision understanding
            if slide_image_base64:
                parts.append({"data": slide_image_base64, "mime_type": "image/jpeg"})

            parts.append(full_prompt)

            response_text = _generate(parts)

            return {
                "response": response_text,
                "sources": None,
                "youtube": None,
            }

        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            return {
                "response": "I'm having a little trouble right now. Please try again in a moment.",
                "error": str(e),
            }

    def generate_resources(
        self,
        slide_context: Dict[str, Any],
        slide_image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured study resources for a slide.
        Returns YouTube suggestions, textbook references, and MCQs as JSON.
        """
        empty = {"youtube": [], "textbooks": [], "mcqs": []}

        prompt = f"""You are generating study resources for a Nigerian medical student.

SLIDE TITLE: {slide_context.get('title', 'Untitled')}
COURSE: {slide_context.get('course', 'General')}
SLIDE TEXT:
{slide_context.get('text', 'No text available')}

TASK: Generate a JSON object with study resources for THIS specific slide.

RESPOND ONLY WITH VALID JSON. NO MARKDOWN CODE BLOCKS. NO PREAMBLE.

Format:
{{
  "youtube": [
    {{"title": "Descriptive video title", "query": "youtube search query", "reason": "why this helps"}}
  ],
  "textbooks": [
    {{"title": "Textbook Name", "author": "Author Name", "chapter": "Relevant Chapter", "reason": "why relevant"}}
  ],
  "mcqs": [
    {{"question": "Question text?", "options": ["A) option", "B) option", "C) option", "D) option"], "correct": 0, "explanation": "why correct"}}
  ]
}}

Generate: 3 YouTube suggestions, 2 textbook recommendations, 5 MCQs based on this slide."""

        try:
            parts: list = []
            if slide_image_base64:
                parts.append({"data": slide_image_base64, "mime_type": "image/jpeg"})
            parts.append(prompt)

            raw = _generate(parts)

            # Strip markdown fences if present
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first and last fence lines
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            resources = json.loads(text)
            # Ensure all keys exist
            resources.setdefault("youtube", [])
            resources.setdefault("textbooks", [])
            resources.setdefault("mcqs", [])
            return resources

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in generate_resources: {e}")
            logger.error(f"Raw response: {raw[:500] if 'raw' in dir() else 'N/A'}")
            return empty
        except Exception as e:
            logger.error(f"generate_resources error: {e}")
            return {**empty, "error": str(e)}


# ── Singleton instance ─────────────────────────────────────────────────────
slide_ai = SlideAwareAI()

# Legacy alias — views.py imports `ai_service`
ai_service = slide_ai


# ── Legacy functions imported by views.py ─────────────────────────────────

def ai_tutor_chat(
    message: str,
    slide_id: Optional[str] = None,
    history: Optional[List[Dict]] = None,
) -> str:
    """Legacy chat function used by views.py ai_tutor endpoint."""
    from .models import Slide, SlideContent

    slide_text = ""
    slide_title = "General"

    if slide_id:
        try:
            slide = Slide.objects.get(id=slide_id)
            slide_title = slide.title
            try:
                content = SlideContent.objects.get(slide=slide)
                if content.content_data:
                    slide_text = content.content_data.get("text", "")
            except Exception:
                pass
        except Exception:
            pass

    result = slide_ai.chat(
        user_message=message,
        slide_context={"title": slide_title, "text": slide_text, "course": "General"},
        conversation_history=history or [],
    )
    return result.get("response", "I couldn't process that request.")


def suggest_related_videos(slide_id: str) -> List[Dict[str, Any]]:
    """Legacy function used by views.py suggest_videos endpoint."""
    from .models import Slide, SlideContent

    slide_text = ""
    slide_title = "General"

    try:
        slide = Slide.objects.get(id=slide_id)
        slide_title = slide.title
        try:
            content = SlideContent.objects.get(slide=slide)
            if content.content_data:
                slide_text = content.content_data.get("text", "")
        except Exception:
            pass
    except Exception:
        pass

    resources = slide_ai.generate_resources(
        slide_context={"title": slide_title, "text": slide_text}
    )
    return resources.get("youtube", [])


def get_study_recommendations(user=None) -> Dict[str, Any]:
    """Legacy function used by views.py ai_study_recommendations endpoint."""
    prompt = """You are an AI study coach for a Nigerian medical student.
Respond ONLY with valid JSON. No markdown. No explanation.
Format:
{"recommendations": ["rec 1", "rec 2", "rec 3", "rec 4", "rec 5"], "focus_areas": ["area 1", "area 2"]}
Provide 5 specific study recommendations and 2 focus areas."""

    try:
        raw = _generate([prompt])
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)
    except Exception as e:
        logger.error(f"get_study_recommendations error: {e}")
        return {
            "recommendations": ["Review recent slides", "Practice MCQs daily", "Use spaced repetition"],
            "focus_areas": ["Anatomy", "Physiology"],
        }


def grade_theory_answer(
    question_text: str, model_answer: str, student_answer: str
) -> Dict[str, Any]:
    """Legacy function used by views.py quiz answer endpoint."""
    prompt = f"""Grade this medical student's theory answer. Respond ONLY with valid JSON.
Question: {question_text}
Model Answer: {model_answer}
Student Answer: {student_answer}
Format: {{"score": 7, "feedback": "Good explanation of..."}}
Score out of 10."""

    try:
        raw = _generate([prompt])
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)
    except Exception as e:
        logger.error(f"grade_theory_answer error: {e}")
        return {"score": 0, "feedback": "Grading unavailable. Please review the model answer."}
