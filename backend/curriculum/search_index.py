"""Maintain a small, synchronous projection of text already read by the pipeline."""
from django.db import transaction


def page_texts(data):
    if not isinstance(data, dict):
        return []
    pages = data.get('pages')
    rows = {}
    for index, page in enumerate(pages if isinstance(pages, list) else [], 1):
        if not isinstance(page, dict):
            continue
        number = page.get('page_number', page.get('slide_number', index))
        text = page.get('text') or page.get('extracted_text') or page.get('content')
        if type(number) is int and number > 0 and isinstance(text, str) and text.strip():
            rows[number] = text.strip()
    if not rows and isinstance(data.get('text'), str) and data['text'].strip():
        rows[1] = data['text'].strip()
    return sorted(rows.items())


def sync_pages(content, using='default'):
    from .models import SlideSearchPage, SlideContent
    with transaction.atomic(using=using):
        # Serialize concurrent saves and project the latest committed version.
        content = SlideContent.objects.using(using).select_for_update().filter(pk=content.pk).first()
        if content is None:
            return
        SlideSearchPage.objects.using(using).filter(slide_id=content.slide_id).delete()
        SlideSearchPage.objects.using(using).bulk_create([
            SlideSearchPage(slide_id=content.slide_id, page_number=number, text=text)
            for number, text in page_texts(content.content_data)
        ], batch_size=200)
