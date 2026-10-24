import json
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import PastQuestionUpload
from .services import process_past_question_upload
from curriculum.class_access import require_visible, scoped_optional_parents
from curriculum.content_permissions import CanWriteUploadedContent
from curriculum.models import Subject, Block, Topic


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([CanWriteUploadedContent])
def upload_past_questions(request):
    """
    Upload past question content for AI processing.
    Body: {content, subject_id, block_id (optional), topic_id (optional), file_name (optional)}
    Generates QuizQuestions and saves them to the curriculum question bank.
    """
    data = request.data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
    elif not isinstance(data, dict):
        try:
            data = json.loads(request.body)
        except Exception:
            return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(data, dict):
        return Response({"error": "Expected an object"}, status=status.HTTP_400_BAD_REQUEST)

    content = data.get("content", "")
    if not isinstance(content, str):
        return Response({"error": "content must be text"}, status=status.HTTP_400_BAD_REQUEST)
    content = content.strip()
    if not content:
        return Response({"error": "content is required"}, status=status.HTTP_400_BAD_REQUEST)

    subject_id = data.get("subject_id")
    block_id = data.get("block_id")
    topic_id = data.get("topic_id")

    if not subject_id:
        return Response({"error": "subject_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    subject = require_visible(Subject, request.user, subject_id)
    block = require_visible(Block, request.user, block_id) if block_id else None
    topic = require_visible(Topic, request.user, topic_id) if topic_id else None
    if topic:
        topic_block = topic.sub_block.block if topic.sub_block_id else topic.block
        if topic_block is None or (topic.block_id and topic.block_id != topic_block.pk):
            raise ValidationError({"topic_id": "This topic needs its hierarchy repaired."})
        if block and block != topic_block:
            raise ValidationError({"topic_id": "This topic does not belong to the selected module."})
        block = topic_block
    if block and block.subject_id != subject.pk:
        raise ValidationError({"block_id": "This module does not belong to the selected course."})

    upload = PastQuestionUpload.objects.create(
        uploaded_by=request.user,
        subject=subject,
        block=block,
        topic=topic,
        file_content=content,
        file_name=data.get("file_name", ""),
    )

    result = process_past_question_upload(upload.id)

    return Response({
        "upload_id": upload.id,
        "created_mcq": result.get("created_mcq", 0),
        "created_theory": result.get("created_theory", 0),
        "error": result.get("error"),
    }, status=status.HTTP_201_CREATED if not result.get("error") else status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_upload_status(request, upload_id):
    """Check processing status of a past question upload."""
    try:
        uploads = scoped_optional_parents(
            PastQuestionUpload.objects.filter(uploaded_by=request.user, subject__isnull=False),
            request.user, {"subject": Subject, "block": Block, "topic": Topic},
        )
        upload = uploads.get(id=upload_id)
    except PastQuestionUpload.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "id": upload.id,
        "file_name": upload.file_name,
        "processed": upload.processed,
        "processing_error": upload.processing_error,
        "uploaded_at": upload.uploaded_at.isoformat(),
    }, status=status.HTTP_200_OK)
