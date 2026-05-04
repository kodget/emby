"""
AI Learning Support powered by Google Gemini (free tier).
Handles: theory grading, AI tutor chat, study recommendations, question generation.
"""

import json
import re
import google.generativeai as genai
from django.conf import settings


def _model(model_name="gemini-1.5-flash"):
    key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not key:
        raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")
    genai.configure(api_key=key)
    return genai.GenerativeModel(model_name)


def _call(prompt, model_name="gemini-1.5-flash"):
    """Single-turn call, returns response text."""
    model = _model(model_name)
    response = model.generate_content(prompt)
    return response.text.strip()


def _parse_json(raw):
    """Strip markdown fences and parse JSON."""
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# 1. Theory answer grading
# ---------------------------------------------------------------------------
def grade_theory_answer(question_text, model_answer, student_answer, topic_context=""):
    """
    Grade a student's theory answer using Gemini.
    Returns {"score": 0-100, "feedback": str, "key_points_missed": [str]}.
    """
    context_section = f"\nTopic context:\n{topic_context}\n" if topic_context else ""
    prompt = f"""You are a medical school examiner grading a student's theory answer.

Question: {question_text}

Model answer / key points:
{model_answer}
{context_section}
Student's answer:
{student_answer}

Grade the student's answer from 0-100 and provide constructive feedback.
Return ONLY valid JSON with no markdown fences:
{{
  "score": <integer 0-100>,
  "feedback": "<2-3 sentence feedback explaining the grade>",
  "key_points_missed": ["<point 1>", "<point 2>"]
}}"""

    try:
        raw = _call(prompt)
        return _parse_json(raw)
    except json.JSONDecodeError:
        return {"score": 50, "feedback": "Could not parse AI response. Please review manually.", "key_points_missed": []}
    except Exception as e:
        print(f"Theory grading error: {e}")
        return {"score": 0, "feedback": f"AI grading unavailable: {e}", "key_points_missed": []}


# ---------------------------------------------------------------------------
# 2. AI Tutor chat
# ---------------------------------------------------------------------------
def ai_tutor_chat(user_message, slide_text_context="", conversation_history=None):
    """
    AI tutor that answers questions about slide content.
    conversation_history: list of {"role": "user"|"assistant", "content": str}
    Returns {"reply": str}.
    """
    key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not key:
        return {"reply": "AI tutor is not configured. Please set GEMINI_API_KEY."}

    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=(
            "You are Emby, an AI study assistant for medical students. "
            "You help students understand their course material clearly and concisely. "
            "When you have slide context, base your answers on it. "
            "Keep answers focused and practical for medical students."
        ),
    )

    # Build history in Gemini's format
    history = []
    for turn in (conversation_history or [])[-10:]:
        role = "user" if turn["role"] == "user" else "model"
        history.append({"role": role, "parts": [turn["content"]]})

    chat = model.start_chat(history=history)

    content = user_message
    if slide_text_context and not conversation_history:
        content = f"[Slide content for context]\n{slide_text_context[:8000]}\n\n---\n{user_message}"

    try:
        response = chat.send_message(content)
        return {"reply": response.text.strip()}
    except Exception as e:
        print(f"AI tutor error: {e}")
        return {"reply": f"Sorry, I'm unavailable right now: {e}"}


# ---------------------------------------------------------------------------
# 3. Generate MCQ + theory questions from text content
# ---------------------------------------------------------------------------
def generate_questions_from_text(content_text, subject_name, topic_name="", num_mcq=5, num_theory=3):
    """
    Generate quiz questions from provided text (slide content or past questions).
    Returns {"mcqs": [...], "theory": [...]}.
    """
    prompt = f"""You are an expert medical education question writer.
Generate exam questions from the content below.

Subject: {subject_name}
Topic: {topic_name or 'General'}

Content:
{content_text[:12000]}

Generate exactly {num_mcq} MCQ questions and {num_theory} theory/essay questions.

Return ONLY valid JSON with no markdown fences:
{{
  "mcqs": [
    {{
      "question": "<question text>",
      "option_a": "<option A>",
      "option_b": "<option B>",
      "option_c": "<option C>",
      "option_d": "<option D>",
      "correct_option": "A",
      "explanation": "<brief explanation>"
    }}
  ],
  "theory": [
    {{
      "question": "<question text>",
      "model_answer": "<comprehensive model answer>"
    }}
  ]
}}"""

    try:
        raw = _call(prompt, model_name="gemini-1.5-flash")
        data = _parse_json(raw)
        return {
            "mcqs": data.get("mcqs", []),
            "theory": data.get("theory", []),
        }
    except json.JSONDecodeError:
        return {"mcqs": [], "theory": [], "error": "Failed to parse AI response"}
    except Exception as e:
        print(f"Question generation error: {e}")
        return {"mcqs": [], "theory": [], "error": str(e)}


# ---------------------------------------------------------------------------
# 4. Study recommendations
# ---------------------------------------------------------------------------
def get_study_recommendations(user_quiz_history, weak_topics, upcoming_topics):
    """
    Return personalised study recommendations.
    Returns {"recommendations": [str], "focus_areas": [str]}.
    """
    history_summary = "\n".join(
        f"- {q['topic']}: {q['score']}% ({q['quiz_type']})"
        for q in (user_quiz_history or [])[:10]
    )
    weak_str = ", ".join(weak_topics) if weak_topics else "none identified yet"
    upcoming_str = ", ".join(upcoming_topics) if upcoming_topics else "none specified"

    prompt = f"""You are a study coach for a medical student.

Recent quiz performance:
{history_summary or 'No quiz history yet'}

Weak topics: {weak_str}
Upcoming topics: {upcoming_str}

Give 3-5 concise, actionable study recommendations.
Return ONLY valid JSON with no markdown fences:
{{
  "recommendations": ["<rec 1>", "<rec 2>"],
  "focus_areas": ["<topic 1>", "<topic 2>"]
}}"""

    try:
        raw = _call(prompt)
        return _parse_json(raw)
    except Exception as e:
        print(f"Recommendations error: {e}")
        return {"recommendations": [], "focus_areas": [], "error": str(e)}
