"""
AI Service — Slide-Aware Chat over an OpenAI-compatible open-weight model

CRITICAL ARCHITECTURE:
- The AI is STATELESS: send slide context (text + image) in EVERY request
- Per-slide conversation history managed by the frontend store
- Structured JSON for resources (YouTube, textbooks, MCQs)
- API key lives ONLY on the backend — never exposed to the browser
- Provider-agnostic: all traffic goes through curriculum.llm (Groq / Cerebras / ...)
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

from . import llm

logger = logging.getLogger(__name__)


def _get_api_key() -> str:
    """Deprecated. Retained so old imports keep working; see curriculum.llm."""
    return llm.api_key()


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences the model sometimes wraps JSON in."""
    return llm.strip_fences(text)


def _generate(parts: list, model: Optional[str] = None, return_usage: bool = False) -> Any:
    """
    Core helper: run a completion against the configured open-weight model.

    `parts` keeps the shape the Gemini implementation used — a list where each entry is
    either a prompt string or an inline-image dict — so every existing call site works
    unchanged. Images are dropped with a warning because the open-weight models Emby now
    runs on are text-only; slide text is already included in every prompt by the callers,
    so answers stay grounded in the slide content.

    Returns the model's text, or raises LLMError / LLMNotConfigured.
    """
    texts: list[str] = []
    images: list[dict] = []

    for part in parts:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict) and "data" in part:
            images.append(part)

    prompt = "\n\n".join(t for t in texts if t).strip()
    if not prompt:
        raise llm.LLMError("Refusing to call the model with an empty prompt.")

    # A request carrying a slide image goes to the multimodal model so the tutor can
    # actually see the diagram the student is asking about. If vision is unavailable, or
    # the image request fails, fall back to the text-only path rather than erroring —
    # every caller already includes the slide's extracted text.
    if images and llm.supports_vision():
        image = images[0]
        try:
            return llm.chat_with_image(
                prompt,
                _as_base64(image["data"]),
                mime_type=image.get("mime_type", "image/jpeg"),
                max_tokens=1500,
                return_usage=return_usage,
            )
        except (llm.LLMError, llm.LLMNotConfigured, ValueError) as exc:
            logger.warning("Vision call failed, falling back to slide text: %s", exc)

    return llm.chat(
        [{"role": "user", "content": prompt}],
        model=model,
        temperature=0.4,
        max_tokens=2048,
        return_usage=return_usage,
    )


def _as_base64(data) -> str:
    """Normalise an inline image to a base64 string.

    Callers have historically passed raw bytes or an already-encoded string, so both are
    accepted rather than requiring every call site to change.
    """
    import base64

    if isinstance(data, bytes):
        return base64.b64encode(data).decode()
    return str(data)


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

FORMATTING: 
- Respond in plain text ONLY. 
- Do NOT use markdown formatting (no asterisks `*` or `**` for bold/italics, no `#` for headings).
- Use simple paragraphs and standard text formatting so it is easy to read.
"""

    def chat(
        self,
        user_message: str,
        slide_context: Dict[str, Any],
        slide_image_base64: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        return_usage: bool = False,
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

            if return_usage:
                response_text, tokens = _generate(parts, return_usage=True)
            else:
                response_text = _generate(parts)

            result = {
                "response": response_text,
                "sources": None,
                "youtube": None,
            }
            if return_usage:
                result["total_tokens"] = tokens
            return result

        except Exception as e:
            logger.error(f"LLM chat error: {e}")
            return {
                "response": "I'm having a little trouble right now. Please try again in a moment.",
                "error": str(e),
            }

    def generate_resources(
        self,
        slide_context: Dict[str, Any],
        slide_image_base64: Optional[str] = None,
        return_usage: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate structured study resources for a slide.
        Returns YouTube suggestions, textbook references, and MCQs as JSON.
        """
        empty = {"youtube": [], "textbooks": [], "mcqs": []}

        slide_text = slide_context.get('text', '')
        if slide_text:
            slide_text = slide_text[:8000]
        else:
            slide_text = 'No text available'

        prompt = f"""You are generating study resources for a Nigerian medical student.

SLIDE TITLE: {slide_context.get('title', 'Untitled')}
COURSE: {slide_context.get('course', 'General')}
SLIDE TEXT:
{slide_text}

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

            if return_usage:
                raw, tokens = _generate(parts, return_usage=True)
            else:
                raw = _generate(parts)

            # Extract JSON more safely, handling preambles or fences
            text = raw.strip()
            
            # Find the first { and last } to extract just the JSON object
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                json_str = text[start_idx:end_idx+1]
                resources = json.loads(json_str)
            else:
                resources = {}
            # Ensure all keys exist
            resources.setdefault("youtube", [])
            resources.setdefault("textbooks", [])
            resources.setdefault("mcqs", [])
            if return_usage:
                resources["total_tokens"] = tokens
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


def get_study_recommendations(history=None, weak_topics=None, upcoming=None, user=None) -> Dict[str, Any]:
    """Legacy function used by views.py ai_study_recommendations endpoint."""
    history_str = json.dumps(history) if history else "[]"
    weak_topics_str = ", ".join(weak_topics) if weak_topics else "None"
    upcoming_str = ", ".join(upcoming) if upcoming else "None"
    
    prompt = f"""You are an AI study coach for a Nigerian medical student.
Respond ONLY with valid JSON. No markdown. No explanation.
Format:
{{
  "recommendations": [
    {{
      "type": "quiz_weak", 
      "title": "Review Anatomy", 
      "description": "Your scores in Upper Limb anatomy were low. Review the slides.", 
      "action_label": "Review Slides", 
      "action_url": "/dashboard/curriculum"
    }}
  ],
  "focus_areas": ["area 1", "area 2"]
}}
Allowed types: "flashcard", "quiz_missed", "quiz_weak", "mixed".
Action URLs can be "/dashboard/curriculum", "/dashboard/flashcards", or "/steeplechase".

Student Context:
- Recent Quiz History: {history_str}
- Weak Topics: {weak_topics_str}
- Upcoming Topics: {upcoming_str}

Provide 3 specific study recommendations and 2 focus areas tailored to this student's context."""

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
            "recommendations": [
                {
                    "type": "mixed",
                    "title": "Review Recent Material",
                    "description": "Go over the latest slides to reinforce your memory.",
                    "action_label": "Go to Curriculum",
                    "action_url": "/dashboard/curriculum"
                },
                {
                    "type": "quiz_weak",
                    "title": "Practice MCQs",
                    "description": "Test yourself on recent topics to identify weak points.",
                    "action_label": "Take a Quiz",
                    "action_url": "/dashboard/quizzes"
                }
            ],
            "focus_areas": ["Anatomy", "Physiology"],
        }


def generate_questions_from_text(
    text: str,
    subject_name: str = "General",
    topic_name: str = "",
    num_mcq: int = 5,
    num_theory: int = 3,
    return_usage: bool = False,
) -> Dict[str, Any]:
    """
    Generate MCQ and theory questions from arbitrary source text (slide content
    or past-question text) using Gemini.

    Returns:
        {
          "mcqs": [
            {"question", "option_a", "option_b", "option_c", "option_d",
             "correct_option" (A-D), "explanation"}
          ],
          "theory": [{"question", "model_answer"}],
          "error": str | None,
        }
    """
    empty = {"mcqs": [], "theory": [], "error": None}

    if not text or not text.strip():
        return {**empty, "error": "No source text provided"}

    # Keep the prompt bounded — long decks blow past context limits
    source = text.strip()[:15000]
    topic_line = f"TOPIC: {topic_name}\n" if topic_name else ""

    prompt = f"""You are an examiner creating assessment questions for Nigerian medical students.

SUBJECT: {subject_name}
{topic_line}SOURCE MATERIAL:
{source}

TASK: Create exam questions strictly grounded in the SOURCE MATERIAL above.

RESPOND ONLY WITH VALID JSON. NO MARKDOWN. NO PREAMBLE.

Format:
{{
  "mcqs": [
    {{
      "question": "Question stem?",
      "option_a": "First option",
      "option_b": "Second option",
      "option_c": "Third option",
      "option_d": "Fourth option",
      "correct_option": "A",
      "explanation": "Why the correct option is right"
    }}
  ],
  "theory": [
    {{"question": "Open-ended question?", "model_answer": "A concise model answer."}}
  ]
}}

Generate exactly {num_mcq} MCQs (each with 4 options and one correct answer A-D)
and {num_theory} theory questions. Ensure every MCQ has a single unambiguous correct option."""

    raw = ""
    try:
        if return_usage:
            raw, tokens = _generate([prompt], return_usage=True)
        else:
            raw = _generate([prompt])
        data = json.loads(_strip_json_fences(raw))

        mcqs = data.get("mcqs", []) if isinstance(data, dict) else []
        theory = data.get("theory", []) if isinstance(data, dict) else []

        # Normalise correct_option to an uppercase A-D letter
        cleaned_mcqs = []
        for m in mcqs:
            if not isinstance(m, dict):
                continue
            correct = str(m.get("correct_option", "A")).strip().upper()[:1]
            if correct not in ("A", "B", "C", "D"):
                correct = "A"
            cleaned_mcqs.append({
                "question": m.get("question", ""),
                "option_a": m.get("option_a", ""),
                "option_b": m.get("option_b", ""),
                "option_c": m.get("option_c", ""),
                "option_d": m.get("option_d", ""),
                "correct_option": correct,
                "explanation": m.get("explanation", ""),
            })

        cleaned_theory = [
            {"question": t.get("question", ""), "model_answer": t.get("model_answer", "")}
            for t in theory if isinstance(t, dict)
        ]

        res = {"mcqs": cleaned_mcqs, "theory": cleaned_theory, "error": None}
        if return_usage:
            res["total_tokens"] = tokens
        return res

    except json.JSONDecodeError as e:
        logger.error(f"generate_questions_from_text JSON parse error: {e}; raw={raw[:300]}")
        return {**empty, "error": "AI returned malformed JSON"}
    except Exception as e:
        logger.error(f"generate_questions_from_text error: {e}")
        return {**empty, "error": str(e)}


def grade_theory_answer(
    question_text: str, model_answer: str, student_answer: str, return_usage: bool = False
) -> Dict[str, Any]:
    """Legacy function used by views.py quiz answer endpoint."""
    prompt = f"""Grade this medical student's theory answer. Respond ONLY with valid JSON.
Question: {question_text}
Model Answer: {model_answer}
Student Answer: {student_answer}
Format: {{"score": 7, "feedback": "Good explanation of..."}}
Score out of 10."""

    try:
        if return_usage:
            raw, tokens = _generate([prompt], return_usage=True)
        else:
            raw = _generate([prompt])
            
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        res = json.loads(text)
        if return_usage:
            res["total_tokens"] = tokens
        return res
    except Exception as e:
        logger.error(f"grade_theory_answer error: {e}")
        return {"score": 0, "feedback": "Grading unavailable. Please review the model answer."}


def generate_battle_questions(topic: str, num_questions: int = 10, difficulty: str = "mixed", return_usage: bool = False) -> Any:
    """Generates multiple choice questions for a Brain Battle or Friend Challenge."""
    prompt = f"""Generate {num_questions} quiz questions for medical students about the topic: '{topic}'.
Target Difficulty Level: {difficulty.upper()} (ensure the cognitive complexity matches this level).
Mix standard 4-option multiple choice questions and True/False questions randomly.
Respond ONLY with valid JSON in this exact structure:
[
  {{
    "question": "What is...?",
    "options": ["A", "B", "C", "D"], // Use ["True", "False"] for true/false questions
    "correct_index": 0,
    "explanation": "Because..."
  }}
]"""

    try:
        if return_usage:
            raw, tokens = _generate([prompt], return_usage=True)
        else:
            raw = _generate([prompt])
            
        text = _strip_json_fences(raw)
        res = json.loads(text)
        if return_usage:
            return res, tokens
        return res
    except Exception as e:
        logger.error(f"generate_battle_questions error: {e}")
        return []
