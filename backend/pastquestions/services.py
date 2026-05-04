"""
Past question processing service.
Extracts text from uploaded past-question files and generates QuizQuestions via Claude.
"""

import io
import requests as http_requests


def _extract_text_from_upload(upload):
    """Return text from a PastQuestionUpload."""
    return upload.file_content


def process_past_question_upload(upload_id):
    """
    Process a PastQuestionUpload: extract text, generate questions, save to QuizQuestion.
    Returns {"created_mcq": int, "created_theory": int, "error": str|None}.
    """
    from .models import PastQuestionUpload
    from curriculum.question_generator import generate_questions_from_past_question_text

    try:
        upload = PastQuestionUpload.objects.get(id=upload_id)
    except PastQuestionUpload.DoesNotExist:
        return {"created_mcq": 0, "created_theory": 0, "error": f"Upload {upload_id} not found"}

    text = _extract_text_from_upload(upload)
    if not text.strip():
        upload.processed = True
        upload.processing_error = "No text content"
        upload.save()
        return {"created_mcq": 0, "created_theory": 0, "error": "No text content"}

    result = generate_questions_from_past_question_text(
        text=text,
        subject=upload.subject,
        block=upload.block,
        topic=upload.topic,
        num_mcq=10,
        num_theory=5,
    )

    upload.processed = True
    upload.processing_error = result.get("error") or ""
    upload.save()

    return result
