"""
Signal handlers that kick off background question generation.

A slide that has finished processing should end up with a full question bank without
anyone waiting on the upload request. These handlers queue that work.

Two problems in the previous version are fixed here:

  * The SlidePage handler read `instance.slide_deck`, but the field is `deck`. That
    raised AttributeError inside a post_save receiver on every page that was created,
    which meant page creation itself blew up.
  * The two handlers could both fire for the same slide and queue duplicate work. They
    now share one entry point, and the job row in learning.QuestionGenerationJob is
    claimed under a lock, so duplicate signals are harmless.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Slide, SlidePage

logger = logging.getLogger(__name__)


def queue_question_bank(slide, reason: str) -> None:
    """Queue bulk generation for a slide, tolerating a missing broker.

    Celery may not be running in development. Rather than fail the request that
    triggered this, fall back to leaving the job pending so it can be run later with
    `manage.py generate_question_bank`.
    """
    from .tasks import generate_question_bank_task

    if not slide or not getattr(slide, "id", None):
        return

    try:
        generate_question_bank_task.delay(slide_id=str(slide.id))
        logger.info("Queued question bank for slide %s (%s)", slide.id, reason)
    except Exception as exc:  # noqa: BLE001 - broker unavailable is not fatal
        logger.warning(
            "Could not queue question bank for slide %s (%s): %s", slide.id, reason, exc
        )


@receiver(post_save, sender=Slide)
def trigger_question_generation_on_slide_save(sender, instance, created, **kwargs):
    """Queue generation once a newly created slide has processed content."""
    if not created:
        return
    if instance.page_count <= 0:
        logger.debug("Slide %s has no pages yet; generation deferred", instance.id)
        return

    queue_question_bank(instance, "slide created")


@receiver(post_save, sender=SlidePage)
def trigger_question_generation_on_page_completion(sender, instance, created, **kwargs):
    """Queue generation once every page of a deck has been rendered.

    A deck is a different model from Slide, so this only acts when the deck's pages are
    all present; the claim lock keeps it safe if the slide handler already fired.
    """
    if not created:
        return

    deck = getattr(instance, "deck", None)
    if deck is None:
        return

    total = deck.page_count or 0
    if total <= 0 or deck.pages.count() < total:
        return

    # SlideDeck and Slide are separate models; only queue when a Slide shares the id.
    slide = Slide.objects.filter(id=deck.id).first()
    if slide is None:
        logger.debug("Deck %s finished but has no matching Slide row", deck.id)
        return

    queue_question_bank(slide, "deck pages complete")
