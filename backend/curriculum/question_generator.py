"""
Auto-generates QuizQuestions from slide content or past-question text.
Calls ai_service.generate_questions_from_text and saves to the DB.
"""

import uuid
from .ai_service import generate_questions_from_text
from .content_extractor import get_slide_full_text


def _make_id():
    return str(uuid.uuid4())[:12]


def generate_questions_from_slide(slide, num_mcq=5, num_theory=3):
    """
    Generate and save QuizQuestion records from a Slide.
    Returns {"created_mcq": int, "created_theory": int, "error": str|None}.
    """
    from .models import QuizQuestion

    file_url = slide.get_file_url
    if not file_url:
        return {"created_mcq": 0, "created_theory": 0, "error": "Slide has no file URL"}

    subject_name = slide.subject.name if slide.subject else "General"
    topic_name = slide.topic.name if slide.topic else ""

    text = get_slide_full_text(file_url, slide.file_type)
    if not text.strip():
        return {"created_mcq": 0, "created_theory": 0, "error": "No text extracted from slide"}

    result = generate_questions_from_text(text, subject_name, topic_name, num_mcq, num_theory)
    if result.get("error"):
        return {"created_mcq": 0, "created_theory": 0, "error": result["error"]}

    created_mcq = 0
    for item in result.get("mcqs", []):
        try:
            QuizQuestion.objects.create(
                id=_make_id(),
                question_type='mcq',
                subject=slide.subject,
                block=slide.block,
                topic=slide.topic,
                question_text=item.get("question", ""),
                option_a=item.get("option_a", ""),
                option_b=item.get("option_b", ""),
                option_c=item.get("option_c", ""),
                option_d=item.get("option_d", ""),
                correct_option=item.get("correct_option", "A").upper(),
                explanation=item.get("explanation", ""),
                source_type='ai_generated',
                source_slide=slide,
            )
            created_mcq += 1
        except Exception as e:
            print(f"Error saving MCQ: {e}")

    created_theory = 0
    for item in result.get("theory", []):
        try:
            QuizQuestion.objects.create(
                id=_make_id(),
                question_type='theory',
                subject=slide.subject,
                block=slide.block,
                topic=slide.topic,
                question_text=item.get("question", ""),
                model_answer=item.get("model_answer", ""),
                source_type='ai_generated',
                source_slide=slide,
            )
            created_theory += 1
        except Exception as e:
            print(f"Error saving theory question: {e}")

    return {"created_mcq": created_mcq, "created_theory": created_theory, "error": None}


def generate_questions_from_past_question_text(text, subject, block=None, topic=None,
                                                source_material=None, num_mcq=10, num_theory=5):
    """
    Generate and save QuizQuestion records from raw past-question text.
    Returns {"created_mcq": int, "created_theory": int, "error": str|None}.
    """
    from .models import QuizQuestion

    if not text.strip():
        return {"created_mcq": 0, "created_theory": 0, "error": "Empty text provided"}

    subject_name = subject.name if subject else "General"
    topic_name = topic.name if topic else ""

    result = generate_questions_from_text(text, subject_name, topic_name, num_mcq, num_theory)
    if result.get("error"):
        return {"created_mcq": 0, "created_theory": 0, "error": result["error"]}

    created_mcq = 0
    for item in result.get("mcqs", []):
        try:
            QuizQuestion.objects.create(
                id=_make_id(),
                question_type='mcq',
                subject=subject,
                block=block,
                topic=topic,
                question_text=item.get("question", ""),
                option_a=item.get("option_a", ""),
                option_b=item.get("option_b", ""),
                option_c=item.get("option_c", ""),
                option_d=item.get("option_d", ""),
                correct_option=item.get("correct_option", "A").upper(),
                explanation=item.get("explanation", ""),
                source_type='past_question',
                source_material=source_material,
            )
            created_mcq += 1
        except Exception as e:
            print(f"Error saving MCQ: {e}")

    created_theory = 0
    for item in result.get("theory", []):
        try:
            QuizQuestion.objects.create(
                id=_make_id(),
                question_type='theory',
                subject=subject,
                block=block,
                topic=topic,
                question_text=item.get("question", ""),
                model_answer=item.get("model_answer", ""),
                source_type='past_question',
                source_material=source_material,
            )
            created_theory += 1
        except Exception as e:
            print(f"Error saving theory question: {e}")

    return {"created_mcq": created_mcq, "created_theory": created_theory, "error": None}
