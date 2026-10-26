"""Permission-scoped search of saved content. Never runs extraction or AI."""
import re
from datetime import datetime
from difflib import get_close_matches
from functools import reduce
from operator import and_, or_
from urllib.parse import quote, urlencode

from django.db.models import Case, When, Value, IntegerField, OuterRef, Subquery, Q
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from accounts.models import Announcement, ExamCountdown
from .class_access import visible, member_class
from .models import (Subject, Block, SubBlock, Topic, Slide, SlideDeck, SlidePage,
                     SlideSearchPage, Flashcard, QuizQuestion, Material)

KINDS = ('course', 'topic', 'slide', 'deck', 'flashcard', 'question', 'material', 'announcement', 'exam', 'page')
PAGES = [
    ('Study dashboard', '/dashboard', 'home progress continue learning'),
    ('Class materials', '/courses', 'learn courses subjects modules topics slides notes'),
    ('Uploaded documents', '/decks', 'library files pdf powerpoint slides'),
    ('Flashcards', '/flashcards', 'review spaced repetition cards'),
    ('Practice questions', '/quiz', 'quiz question bank mcq theory revision'),
    ('Mock exams', '/quiz/mock', 'practice exam test'),
    ('Class assessments', '/quiz/assessments', 'formal tests exams'),
    ('My class', '/class', 'classmates roster class head'),
    ('Announcements', '/class/announcements', 'class news updates notices'),
    ('Exam countdowns', '/class/exams', 'exam dates schedule'),
    ('Study plan', '/study-plan', 'schedule planner timetable activities'),
    ('Brain Battle', '/battles', 'multiplayer live quiz kahoot friends'),
    ('Steeplechase', '/steeplechase', 'spotter anatomy timed stations'),
    ('Histology', '/histology', 'microscopy tissue practice'),
    ('Analytics', '/analytics', 'statistics progress performance weak areas'),
    ('Notifications', '/notifications', 'reminders alerts'),
    ('Profile', '/profile', 'account photo name privacy public private'),
    ('Settings', '/settings', 'preferences account notifications privacy'),
    ('AI credits', '/credits', 'balance buy top up credits'),
]


class SearchThrottle(UserRateThrottle):
    rate = '120/min'


def match(terms, fields):
    return reduce(and_, (reduce(or_, (Q(**{field + '__icontains': term}) for field in fields)) for term in terms))


def excerpt(text, terms, length=240):
    text = ' '.join((text or '').split())
    positions = [text.casefold().find(term.casefold()) for term in terms]
    start = max(0, min((p for p in positions if p >= 0), default=0) - 65)
    return ('…' if start else '') + text[start:start + length] + ('…' if len(text) > start + length else '')


def path(*parts):
    return '/' + '/'.join(quote(str(part), safe='') for part in parts if part is not None)


def course_path(obj):
    if isinstance(obj, Subject):
        return '/courses?' + urlencode({'subject': obj.pk})
    if isinstance(obj, Block):
        return path('courses', obj.subject_id, obj.pk)
    if isinstance(obj, SubBlock):
        return path('courses', obj.block.subject_id, obj.block_id, obj.pk)
    block = obj.sub_block.block if obj.sub_block_id else obj.block
    return path('courses', block.subject_id, block.pk, obj.sub_block_id, obj.pk) if block else '/courses'


@never_cache
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([SearchThrottle])
def search(request):
    query = ' '.join(request.query_params.get('q', '').split())
    kind = request.query_params.get('type', 'all')
    subject = request.query_params.get('subject', '')
    sort = request.query_params.get('sort', 'relevance')
    try:
        offset = int(request.query_params.get('offset', 0))
        limit = int(request.query_params.get('limit', 20))
        if not 0 <= offset <= 1000 or not 1 <= limit <= 40:
            raise ValueError
    except (ValueError, TypeError):
        return Response({'detail': 'Use an offset from 0 to 1000 and a limit from 1 to 40.'}, status=400)
    terms = re.findall(r'[^\W_]+', query, re.UNICODE)
    if len(query) > 160 or len(terms) > 8 or kind not in ('all', *KINDS) or sort not in ('relevance', 'recent'):
        return Response({'detail': 'Use up to 160 characters and eight search words with valid filters.'}, status=400)
    subjects = list(visible(Subject, request.user).values('id', 'name'))
    counts = dict.fromkeys(KINDS, 0)
    base = {'query': query, 'counts': counts, 'subjects': subjects, 'results': [], 'total': 0, 'next_offset': None, 'suggestions': []}
    if len(query) < 2 or not terms or (subject and subject not in {s['id'] for s in subjects}):
        return Response(base)
    results = []

    def add(qs, category, title_field, body_fields, url, *, subject_filter=None, page=False, label=None):
        if subject:
            if subject_filter is None:
                return
            qs = qs.filter(subject_filter)
        qs = qs.filter(match(terms, [title_field, *body_fields])).annotate(search_rank=Case(
            When(**{title_field + '__iexact': query}, then=Value(100)),
            When(**{title_field + '__istartswith': query}, then=Value(80)),
            When(**{title_field + '__icontains': query}, then=Value(60)),
            default=Value(20), output_field=IntegerField()))
        counts[category] += qs.count()
        if kind not in ('all', category):
            return
        ordering = ['-created_at', 'pk'] if sort == 'recent' else ['-search_rank', '-created_at', 'pk']
        for obj in qs.order_by(*ordering)[:offset + limit]:
            title = getattr(obj, title_field)
            body = []
            for field in body_fields:
                value = obj
                for attr in field.split('__'):
                    value = getattr(value, attr, None)
                    if value is None:
                        break
                if isinstance(value, str):
                    body.append(value)
            # Snippets contain text only. No file URLs, answers, credentials or HTML.
            best = max(body, key=lambda value: sum(t.casefold() in value.casefold() for t in terms), default='')
            page_number = getattr(obj, 'match_page', None) if page else None
            href = url(obj)
            if page_number:
                href += ('&' if '?' in href else '?') + urlencode({'page': page_number})
            results.append({'id': f'{category}:{obj._meta.model_name}:{obj.pk}', 'type': category,
                'title': title, 'excerpt': excerpt(best, terms), 'url': href,
                'label': label(obj) if label else category.capitalize(), 'page': page_number,
                'created_at': obj.created_at.isoformat(), '_rank': obj.search_rank})

    user = request.user
    add(visible(Subject, user), 'course', 'name', ['description'], course_path, subject_filter=Q(pk=subject), label=lambda _: 'Subject')
    add(visible(Block, user).select_related('subject'), 'course', 'name', ['description', 'subject__name'], course_path,
        subject_filter=Q(subject_id=subject), label=lambda o: f'Module · {o.subject.name}')
    add(visible(SubBlock, user).select_related('block__subject'), 'course', 'name', ['description', 'block__name'], course_path,
        subject_filter=Q(block__subject_id=subject), label=lambda o: f'Submodule · {o.block.subject.name}')
    add(visible(Topic, user).select_related('block__subject', 'sub_block__block__subject'), 'topic', 'name', ['description'], course_path,
        subject_filter=Q(block__subject_id=subject) | Q(sub_block__block__subject_id=subject))

    pages = SlideSearchPage.objects.filter(slide_id=OuterRef('pk')).filter(
        match(terms, ['text', 'slide__title'])).order_by('page_number')
    slides = visible(Slide, user).filter(standalone_deck__isnull=True).select_related('subject').annotate(
        match_text=Subquery(pages.values('text')[:1]), match_page=Subquery(pages.values('page_number')[:1]))
    add(slides, 'slide', 'title', ['match_text', 'subject__name'],
        lambda o: path('read', o.topic_id or o.sub_block_id or o.block_id or o.subject_id or 'library', o.pk),
        subject_filter=Q(subject_id=subject) | Q(block__subject_id=subject) | Q(topic__block__subject_id=subject) |
            Q(topic__sub_block__block__subject_id=subject), page=True, label=lambda o: f'Slides · {o.subject.name}' if o.subject else 'Slides')
    deck_pages = SlidePage.objects.filter(deck_id=OuterRef('pk')).filter(
        match(terms, ['extracted_text', 'deck__title'])).order_by('slide_number')
    decks = visible(SlideDeck, user).filter(Q(curriculum_slide__isnull=True) |
        Q(curriculum_slide__in=visible(Slide, user))).annotate(
        match_text=Subquery(deck_pages.values('extracted_text')[:1]), match_page=Subquery(deck_pages.values('slide_number')[:1]))
    add(decks, 'deck', 'title', ['match_text'], lambda o: path('decks', o.pk),
        subject_filter=Q(curriculum_slide__subject_id=subject), page=True, label=lambda _: 'Uploaded document')
    add(visible(Flashcard, user).filter(user=user).select_related('subject'), 'flashcard', 'front', ['back', 'explanation'],
        lambda o: '/flashcards/manage?' + urlencode({'card': o.pk}), subject_filter=Q(subject_id=subject), label=lambda _: 'Your flashcard')
    from learning.bank_sources import eligible_questions
    questions = eligible_questions(visible(QuizQuestion, user).filter(match(terms, ['question_text', 'subject__name'])).filter(needs_review=False).filter(
        ~Q(source_type='ai_generated') | ~Q(bank_key='')).filter(
        Q(source_slide__isnull=True) | Q(source_slide__in=visible(Slide, user))).filter(
        Q(source_material__isnull=True) | Q(source_material__in=visible(Material, user))))
    add(questions.select_related('subject'), 'question', 'question_text', ['subject__name'],
        lambda o: '/quiz?' + urlencode({'subject': o.subject_id, **({'slide': o.source_slide_id} if o.source_slide_id else {})}),
        subject_filter=Q(subject_id=subject), label=lambda o: f'{"MCQ" if o.question_type == "mcq" else "Written question"} · {o.difficulty} · Practice source')
    add(visible(Material, user).select_related('block'), 'material', 'title', ['description'],
        lambda o: (path('courses', o.subject_id, o.block_id, o.sub_block_id, o.topic_id) + '#material-' + quote(str(o.pk), safe='')),
        subject_filter=Q(subject_id=subject), label=lambda o: o.get_material_type_display())
    group = member_class(user)
    if group:
        add(Announcement.objects.filter(class_group=group), 'announcement', 'title', ['content'],
            lambda o: '/class/announcements#announcement-' + str(o.pk))
        add(ExamCountdown.objects.filter(class_group=group), 'exam', 'title', ['description', 'subject'],
            lambda o: '/class/exams#exam-' + str(o.pk), label=lambda o: 'Exam · ' + str(o.exam_date))

    if not subject:
        for title, url, keywords in PAGES:
            if not all(term.casefold() in (title + ' ' + keywords).casefold() for term in terms):
                continue
            counts['page'] += 1
            if kind in ('all', 'page'):
                results.append({'id': 'page:' + url, 'type': 'page', 'title': title, 'excerpt': '', 'url': url,
                    'label': 'Page or tool', 'page': None, 'created_at': None, '_rank': 90 if title.casefold() == query.casefold() else 10})
    results.sort(key=lambda r: ((-r['_rank'],) if sort == 'relevance' else ()) +
                 (-(datetime.fromisoformat(r['created_at']).timestamp() if r['created_at'] else 0), r['id']))
    total = sum(counts.values()) if kind == 'all' else counts[kind]
    selected = results[offset:offset + limit]
    for row in selected:
        row.pop('_rank')
    if total == 0 and not subject and len(terms) <= 3:
        # Suggestions are best effort over bounded, authorized titles only.
        vocabulary = set()
        for model, field in ((Subject, 'name'), (Topic, 'name'), (Slide, 'title'), (SlideDeck, 'title')):
            for title in visible(model, user).order_by('-created_at').values_list(field, flat=True)[:200]:
                vocabulary.update(word.casefold() for word in re.findall(r'[^\W_]{3,}', title, re.UNICODE))
        corrected = [get_close_matches(term.casefold(), sorted(vocabulary), n=1, cutoff=0.78) for term in terms]
        suggestion = ' '.join(words[0] if words else term for words, term in zip(corrected, terms))
        if suggestion.casefold() != query.casefold():
            base['suggestions'] = [suggestion]
    response = Response({**base, 'results': selected, 'total': total,
        'next_offset': offset + limit if offset + limit < total and offset + limit <= 1000 else None})
    response['Cache-Control'] = 'private, no-store'
    return response
