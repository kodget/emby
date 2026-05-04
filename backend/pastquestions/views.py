from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json

from .models import PastQuestionUpload
from .services import process_past_question_upload


@login_required
@require_http_methods(["POST"])
def upload_past_questions(request):
    """
    Upload past question content for AI processing.
    Body: {content, subject_id, block_id (optional), topic_id (optional), file_name (optional)}
    Generates QuizQuestions and saves them to the curriculum question bank.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    content = data.get("content", "").strip()
    if not content:
        return JsonResponse({"error": "content is required"}, status=400)

    subject_id = data.get("subject_id")
    block_id = data.get("block_id")
    topic_id = data.get("topic_id")

    from curriculum.models import Subject, Block, Topic
    subject = Subject.objects.filter(id=subject_id).first() if subject_id else None
    block = Block.objects.filter(id=block_id).first() if block_id else None
    topic = Topic.objects.filter(id=topic_id).first() if topic_id else None

    upload = PastQuestionUpload.objects.create(
        uploaded_by=request.user,
        subject=subject,
        block=block,
        topic=topic,
        file_content=content,
        file_name=data.get("file_name", ""),
    )

    result = process_past_question_upload(upload.id)

    return JsonResponse({
        "upload_id": upload.id,
        "created_mcq": result.get("created_mcq", 0),
        "created_theory": result.get("created_theory", 0),
        "error": result.get("error"),
    }, status=201 if not result.get("error") else 400)


@login_required
@require_http_methods(["GET"])
def get_upload_status(request, upload_id):
    """Check processing status of a past question upload."""
    try:
        upload = PastQuestionUpload.objects.get(id=upload_id, uploaded_by=request.user)
    except PastQuestionUpload.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    return JsonResponse({
        "id": upload.id,
        "file_name": upload.file_name,
        "processed": upload.processed,
        "processing_error": upload.processing_error,
        "uploaded_at": upload.uploaded_at.isoformat(),
    })
