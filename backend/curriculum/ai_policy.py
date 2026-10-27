"""Per-document AI policy, stored alongside content without changing file data."""
from django.db import transaction

ON_DEMAND = 'on_demand'
DEFERRED_MESSAGE = 'AI content will be generated when requested.'


def on_demand(source):
    from .models import Slide, SlideContent
    if isinstance(source, Slide):
        data = SlideContent.objects.filter(slide=source).values_list('content_data', flat=True).first() or {}
    else:
        data = getattr(source, 'text_extraction', {}) or {}
    return data.get('ai_generation_mode') == ON_DEMAND


@transaction.atomic
def defer_automatic_ai(slide):
    """Fence unfinished automatic work; preserve all pages and generated results.

    Existing failure-budget fields also stop older deployed workers from resuming
    these requests before the on-demand code is deployed. Explicit requests in
    the updated code reset this particular deferral, not genuine failures.
    """
    from .models import Slide, SlideContent, DocumentIndexJob
    from .document_index import MAX_FAILURES
    from learning.models import QuestionGenerationJob
    slide = Slide.objects.select_for_update().get(pk=slide.pk)
    content, _ = SlideContent.objects.get_or_create(slide=slide)
    content.content_data = {**(content.content_data or {}), 'ai_generation_mode': ON_DEMAND}
    content.save(update_fields=['content_data'])
    DocumentIndexJob.objects.filter(slide=slide).exclude(status='complete').update(
        status='failed', error_code=ON_DEMAND, attempts=MAX_FAILURES,
        lease_token=None, lease_expires_at=None, next_attempt_at=None)
    QuestionGenerationJob.objects.filter(slide=slide).exclude(status='completed').update(
        status='failed', error=DEFERRED_MESSAGE, attempts=QuestionGenerationJob.MAX_ATTEMPTS,
        lease_token=None, lease_expires_at=None, next_attempt_at=None)
    if not QuestionGenerationJob.objects.filter(slide=slide, status='completed').exists():
        Slide.objects.filter(pk=slide.pk).update(generation_status='pending')
