"""Persist generation intent for class-owned course slides."""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Slide, SlideDeck, SlideContent, SlideSearchPage


@receiver(post_save, sender=SlideContent)
def index_saved_slide_text(sender, instance, raw=False, using='default', update_fields=None, **kwargs):
    if not raw and (update_fields is None or 'content_data' in update_fields):
        from .search_index import sync_pages
        sync_pages(instance, using)


@receiver(post_delete, sender=SlideContent)
def remove_saved_slide_text(sender, instance, using='default', **kwargs):
    SlideSearchPage.objects.using(using).filter(slide_id=instance.slide_id).delete()


def queue_question_bank(slide, reason: str) -> None:
    from learning.generation_dispatch import request_generation
    if slide and slide.pk and slide.class_group_id:
        request_generation(slide)


@receiver(post_save, sender=Slide)
def trigger_question_generation_on_slide_save(sender, instance, created, **kwargs):
    if created and instance.page_count > 0:
        queue_question_bank(instance, 'slide created')

# SlideDeck is a distinct source model. Matching IDs never establish a relationship.


@receiver(post_delete, sender=SlideDeck)
def remove_deleted_deck_bank_source(sender, instance, **kwargs):
    # Generated questions survive through their SET_NULL source FK for old attempts.
    if instance.curriculum_slide_id:
        Slide.objects.filter(pk=instance.curriculum_slide_id).delete()
