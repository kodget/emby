"""Scoped mock exams from eligible saved questions, with immutable review evidence."""
import random
import uuid
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from django.utils import timezone

from learning.bank_sources import eligible_questions
from learning.generation import valid_row
from .class_access import require_visible, visible
from .models import Subject, Block, SubBlock, Slide, Material, QuizQuestion, QuizAttempt


def scope(user, data):
    if data.get('slide') or data.get('topic'):
        raise ValidationError({'error': 'Choose a course, module or submodule for a mock exam.'})
    kind, key = data.get('scope_type'), data.get('scope_id')
    models = {'course': Subject, 'module': Block, 'submodule': SubBlock}
    if not isinstance(kind, str) or kind not in models or not key:
        raise ValidationError({'error': 'Select a course, module or submodule.'})
    selected = require_visible(models[kind], user, key)
    sub = selected if kind == 'submodule' else None
    block = sub.block if sub else selected if kind == 'module' else None
    subject = block.subject if block else selected
    if not subject.class_group_id:
        raise ValidationError({'error': 'Assign the course to a class before starting a mock exam.'})
    for name, obj in [('subject', subject), ('block', block), ('sub_block', sub)]:
        if data.get(name) and (obj is None or str(data[name]) != str(obj.pk)):
            raise ValidationError({'error': 'The selected curriculum parents do not match the scope.'})
    return selected, {'subject': subject, **({'block': block} if block else {}),
                      **({'sub_block': sub} if sub else {})}


def pools(user, parents):
    from .serializers import QuizQuestionSerializer
    from learning.bank_sources import usable_questions
    candidates = usable_questions(user, visible(QuizQuestion, user).filter(**parents))
    result = {difficulty: {'mcq': [], 'theory': []} for difficulty in ('easy', 'medium', 'hard')}
    seen = set()
    for q in candidates:
        snapshot = dict(QuizQuestionSerializer(q).data, bank_key=q.bank_key)
        stem = ' '.join(q.question_text.casefold().split())
        if stem in seen:
            continue
        seen.add(stem)
        source = q.source_slide or q.source_material
        topic = source.topic if source and source.topic_id else None
        label = topic or q.sub_block or q.block or parents['subject']
        label_kind = 'topic' if topic else 'submodule' if q.sub_block else 'module' if q.block else 'course'
        snapshot['coverage_key'] = f'{label_kind}:{label.pk}'
        snapshot['coverage_name'] = label.name
        snapshot['source_key'] = f'slide:{q.source_slide_id}' if q.source_slide_id else (
            f'material:{q.source_material_id}' if q.source_material_id else 'authored')
        result[q.difficulty][q.question_type].append(snapshot)
    return result


def availability(user, data):
    selected, parents = scope(user, data)
    banks = pools(user, parents)
    return {'scope_type': data['scope_type'], 'scope_id': selected.pk, 'name': selected.name,
            'maximum': {'mcq': 100, 'theory': 10, 'minutes': 180},
            'available': {d: {kind: len(rows) for kind, rows in bank.items()} for d, bank in banks.items()}}


def balanced_sample(rows, count):
    """Round-robin topics, then source files within each topic; randomize each round."""
    topics = defaultdict(lambda: defaultdict(list))
    for row in rows:
        topics[row['coverage_key']][row['source_key']].append(row)
    queues = {}
    for key, sources in topics.items():
        queue = []
        for values in sources.values():
            random.shuffle(values)
        while sources:
            source_keys = list(sources)
            random.shuffle(source_keys)
            for source in source_keys:
                queue.append(sources[source].pop())
                if not sources[source]:
                    del sources[source]
        queues[key] = queue
    chosen = []
    while len(chosen) < count:
        keys = list(queues)
        random.shuffle(keys)
        for key in keys:
            chosen.append(queues[key].pop(0))
            if not queues[key]:
                del queues[key]
            if len(chosen) == count:
                break
    return chosen


@transaction.atomic
def create(user, data):
    selected, parents = scope(user, data)
    config = data.get('configuration')
    if not isinstance(config, dict):
        raise ValidationError({'error': 'Configure the question counts and difficulty.'})
    mcqs, theories, difficulty = config.get('mcq_count'), config.get('theory_count'), config.get('difficulty')
    if (type(mcqs) is not int or type(theories) is not int or not 0 <= mcqs <= 100
            or not 0 <= theories <= 10 or mcqs + theories == 0):
        raise ValidationError({'error': 'Choose up to 100 MCQs and 10 written questions, with at least one question.'})
    if difficulty not in ('easy', 'medium', 'hard') or config.get('question_source', 'hierarchy') != 'hierarchy':
        raise ValidationError({'error': 'Choose one difficulty and saved questions from the selected scope.'})
    timed, duration = data.get('is_timed', False), data.get('duration_minutes')
    if type(timed) is not bool or (timed and (type(duration) is not int or not 1 <= duration <= 180)):
        raise ValidationError({'error': 'Timed mocks need a whole-number duration of 1–180 minutes.'})
    if not timed and duration is not None:
        raise ValidationError({'error': 'Untimed mocks must not include a duration.'})
    # Coordinate with bank generation/review, which also locks source slides first.
    list(visible(Slide, user).filter(**parents).select_for_update(of=('self',)).order_by('pk'))
    bank = pools(user, parents)[difficulty]
    available = {kind: len(rows) for kind, rows in bank.items()}
    if mcqs > available['mcq'] or theories > available['theory']:
        raise ValidationError({'error': f"Only {available['mcq']} MCQs and {available['theory']} written questions are available at {difficulty} difficulty.",
                               'available': available, 'code': 'insufficient_questions'})
    snapshots = balanced_sample(bank['mcq'], mcqs) + balanced_sample(bank['theory'], theories)
    return QuizAttempt.objects.create(id=f'mock-{uuid.uuid4().hex}', user=user, exam_type='mock',
        snapshot_class=parents['subject'].class_group, **parents,
        configuration={'scope_type': data['scope_type'], 'scope_id': selected.pk, 'scope_name': selected.name,
                       'mcq_count': mcqs, 'theory_count': theories, 'difficulty': difficulty,
                       'question_source': 'hierarchy', 'sampling_policy': 'topic-source-round-robin-v1'},
        is_timed=timed, duration_minutes=duration, deadline=timezone.now() + timedelta(minutes=duration) if timed else None,
        question_ids=[q['id'] for q in snapshots], question_snapshots=snapshots, mcq_total=mcqs, theory_total=theories)


def review(attempt):
    """Deterministic MCQ topic review, including every unanswered question."""
    responses = {r.snapshot_question_id: r for r in attempt.responses.all()}
    topics = {}
    for q in attempt.question_snapshots:
        if q['question_type'] != 'mcq':
            continue
        row = topics.setdefault(q['coverage_key'], {'topic_name': q['coverage_name'], 'correct': 0, 'total': 0})
        row['total'] += 1
        response = responses.get(q['id'])
        row['correct'] += int(bool(response and response.is_correct))
    return [dict(row, percentage=100 * row['correct'] / row['total']) for row in topics.values()]
