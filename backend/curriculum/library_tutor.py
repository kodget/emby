"""Bounded, class-scoped retrieval over every processed upload in the library."""
import heapq
import re
from .class_access import visible
from .models import SlideContent, SlideDeck, SlidePage


def library_context(user, query, *, slide_filters=None):
    terms = set(re.findall(r"[a-z0-9]{3,}", query.lower())) - {
        'the', 'and', 'for', 'that', 'this', 'with', 'what', 'how', 'explain', 'please',
    }
    candidates, sequence, documents = [], 0, set()

    def consider(kind, pk, title, page, text):
        nonlocal sequence
        if not isinstance(text, str) or not text.strip():
            return
        documents.add((kind, pk))
        for start in range(0, len(text), 1800):
            excerpt = text[start:start + 2200]
            words = set(re.findall(r"[a-z0-9]{3,}", (title + ' ' + excerpt).lower()))
            score = len(terms & words)
            sequence += 1
            entry = (score, -sequence, {'kind': kind, 'id': str(pk), 'title': title,
                                      'page': page, 'text': excerpt})
            if len(candidates) < 12:
                heapq.heappush(candidates, entry)
            elif entry[:2] > candidates[0][:2]:
                heapq.heapreplace(candidates, entry)

    contents = visible(SlideContent, user).select_related('slide').order_by('slide_id')
    if slide_filters:
        contents = contents.filter(**{'slide__' + key: value for key, value in slide_filters.items()})
    for content in contents.iterator():
        data = content.content_data if isinstance(content.content_data, dict) else {}
        pages = data.get('pages', [])
        readable = [p for p in pages if isinstance(p, dict) and (p.get('text') or p.get('extracted_text'))] if isinstance(pages, list) else []
        if readable:
            for index, page in enumerate(readable, 1):
                consider('slide', content.slide_id, content.slide.title,
                         page.get('page_number', page.get('slide_number', index)),
                         page.get('text') or page.get('extracted_text'))
        else:
            consider('slide', content.slide_id, content.slide.title, None, data.get('text', ''))
    pages = SlidePage.objects.filter(deck__in=visible(SlideDeck, user).filter(
        processing_status='completed')).select_related('deck').order_by('deck_id', 'slide_number')
    if slide_filters:
        # Assigned documents are already represented by their curriculum SlideContent.
        pages = pages.none()
    for page in pages.iterator():
        consider('deck', page.deck_id, page.deck.title, page.slide_number, page.extracted_text)
    sources, excerpts = [], []
    for index, (_, _, row) in enumerate(sorted(candidates, reverse=True), 1):
        excerpts.append(f"[{index}] {row['title']}" + (f" — Page {row['page']}" if row['page'] else '') + '\n' + row.pop('text'))
        row['citation'] = index
        sources.append(row)
    return '\n\n'.join(excerpts), sources, len(documents)
