from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json

from .models import PastQuestionUpload, GeneratedMCQ, GeneratedEssay
from .services import process_past_questions_async


@require_http_methods(["POST"])
def upload_past_questions(request):
    data = json.loads(request.body)

    upload = PastQuestionUpload.objects.create(
        uploaded_by=data["class_rep"],
        block_id=data["block_id"],
        file_content=data["content"]
    )

    # JUST TRIGGER (NOT BLOCKING REQUEST)
    process_past_questions_async(upload.id)

    return JsonResponse({
        "status": "processing",
        "upload_id": upload.id
    })

    
@require_http_methods(["GET"])
def get_questions(request, block_id, topic=None):

    mcqs = GeneratedMCQ.objects.filter(topic_id=topic)[:20]
    essays = GeneratedEssay.objects.filter(topic_id=topic)[:10]

    return JsonResponse({
        "mcqs": list(mcqs.values()),
        "essays": list(essays.values())
    })