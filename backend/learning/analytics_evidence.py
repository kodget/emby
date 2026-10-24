"""One consistent report window, reconstructed from saved attempts and activity evidence."""
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone
from django.db.models import Q

from curriculum.class_access import scoped_optional_parents, visible_attempts, visible
from curriculum.models import Subject, Block, SubBlock, Topic, SlideDeck
from .models import ActivityType, LearningEvent

OBJECTIVE = {ActivityType.QUIZ_COMPLETED, ActivityType.QUESTION_ANSWERED,
             ActivityType.STEEPLECHASE_COMPLETED, ActivityType.HISTOLOGY_COMPLETED,
             ActivityType.BRAIN_BATTLE_COMPLETED}
LABELS = {ActivityType.QUESTION_ANSWERED: 'Practice questions',
          ActivityType.STEEPLECHASE_COMPLETED: 'Steeplechase',
          ActivityType.HISTOLOGY_COMPLETED: 'Histology',
          ActivityType.BRAIN_BATTLE_COMPLETED: 'Brain Battle',
          ActivityType.FLASHCARD_REVIEWED: 'Flashcards (self-rated)',
          'practice': 'Deck practice', 'mock': 'Mock exams', 'formal': 'Formal assessments'}


def minutes(seconds):
    return round(seconds / 60, 2)


def scope(row):
    for name in ('topic', 'sub_block', 'block', 'subject'):
        node = getattr(row, name, None)
        if node is not None:
            return name.upper(), str(node.pk), node.name
    return None


class Evidence:
    def __init__(self, user, days, now=None):
        self.user = user
        self.now = now or timezone.now()
        self.today = timezone.localdate(self.now)
        self.first = self.today - timedelta(days=days - 1)
        self.start = timezone.make_aware(datetime.combine(self.first, time.min))
        self.days = days
        self.rows = []
        self.excluded_historical = 0
        self.pending_written = 0
        self.historical_image_rounds = 0
        self._load(user)
        self.window = [r for r in self.rows if self.start <= r['at'] <= self.now]

    def _load(self, user):
        parents = {'subject': Subject, 'block': Block, 'sub_block': SubBlock, 'topic': Topic}
        events = scoped_optional_parents(LearningEvent.objects.filter(user=user, occurred_at__lte=self.now),
                                         user, parents).select_related(*parents).order_by('occurred_at', 'created_at', 'pk')
        events = events.filter(~Q(resource_type='standalone_deck') |
                               Q(resource_id__in=visible(SlideDeck, user).values('pk')))
        seen = set()
        for event in events:
            # The attempt itself is authoritative, including when an old event is missing or duplicated.
            if (event.resource_type in ('QuizAttempt', 'practice_session') or event.activity in (
                    ActivityType.QUIZ_COMPLETED, ActivityType.STEEPLECHASE_COMPLETED, ActivityType.HISTOLOGY_COMPLETED)):
                continue
            if not (0 <= event.correct_count <= event.total_count and event.duration_seconds >= 0):
                continue
            if event.resource_id and event.resource_type in ('practice_session', 'brain_battle', 'schedule_item'):
                key = (event.activity, event.resource_type, event.resource_id)
                if key in seen:
                    continue
                seen.add(key)
            objective = event.activity in OBJECTIVE
            self.rows.append(dict(at=event.occurred_at, activity=event.activity, kind=event.activity,
                attempted=event.total_count if objective else 0, correct=event.correct_count if objective else 0,
                seconds=0 if event.activity == ActivityType.PLANNER_TASK_COMPLETED else event.duration_seconds,
                nodes=[(scope(event), event.correct_count, event.total_count)] if objective else []))
        attempts = visible_attempts(user).select_related('subject', 'block', 'sub_block', 'topic').prefetch_related('responses')
        for attempt in attempts:
            if not attempt.question_snapshots:
                if attempt.submitted_at and self.start <= attempt.submitted_at <= self.now:
                    self.excluded_historical += 1
                continue
            if attempt.status not in ('submitted', 'auto_submitted') or not attempt.submitted_at or attempt.submitted_at > self.now:
                continue
            responses = {r.snapshot_question_id or r.question_id: r for r in attempt.responses.all()}
            mcqs = [q for q in attempt.question_snapshots if q.get('question_type') == 'mcq']
            correct = 0
            nodes = []
            for question in mcqs:
                answer = responses.get(question['id'])
                right = int(bool(answer and answer.selected_option == question.get('correct_option')))
                correct += right
                # Mock snapshots preserve their original coverage labels after source deletion.
                node = scope(attempt)
                if question.get('coverage_key') and question.get('coverage_name'):
                    kind, _, key = question['coverage_key'].partition(':')
                    level = {'topic': 'TOPIC', 'submodule': 'SUB_BLOCK', 'module': 'BLOCK', 'course': 'SUBJECT'}.get(kind)
                    if level:
                        node = (level, key, question['coverage_name'])
                nodes.append((node, right, 1))
            end = min(attempt.submitted_at, attempt.deadline) if attempt.deadline else attempt.submitted_at
            seconds = max(0, int((end - attempt.started_at).total_seconds()))
            self.rows.append(dict(at=attempt.submitted_at, activity=ActivityType.QUIZ_COMPLETED,
                                  kind=attempt.exam_type, attempted=len(mcqs), correct=correct, seconds=seconds, nodes=nodes))
            if attempt.theory_grading_pending and self.start <= attempt.submitted_at <= self.now:
                self.pending_written += 1

        from .practice import visible_sessions
        from .practice_evidence import counts
        from .models import PracticeMode, PracticeSession
        sessions = visible_sessions(user).filter(status=PracticeSession.Status.COMPLETED,
            completed_at__lte=self.now, mode__in=PracticeMode.values).prefetch_related('attempts')
        for session in sessions:
            saved = counts(session)
            if saved is None and session.completed_at >= self.start:
                self.historical_image_rounds += 1
            activity = (ActivityType.STEEPLECHASE_COMPLETED if session.mode == PracticeMode.STEEPLECHASE
                        else ActivityType.HISTOLOGY_COMPLETED)
            seconds = saved['seconds'] if saved else sum(max(0, min(a.seconds_taken, 90))
                                                       for a in session.attempts.all())
            self.rows.append(dict(at=session.completed_at, activity=activity, kind=activity,
                attempted=saved['total'] if saved else 0, correct=saved['correct'] if saved else 0,
                seconds=seconds, nodes=[], image_mode=session.mode,
                stations=len(session.station_ids), verified=saved is not None,
                timed_out=saved['timed_out'] if saved else sum(a.timed_out for a in session.attempts.all())))

    def practice_summary(self):
        from .models import PracticeMode
        out = {}
        for mode in PracticeMode.values:
            rows = [r for r in self.window if r.get('image_mode') == mode]
            total = sum(r['attempted'] for r in rows)
            out[mode] = dict(rounds=len(rows), stations=sum(r['stations'] for r in rows),
                average_accuracy=round(sum(r['correct'] for r in rows) / total, 3) if total else None,
                timed_out=sum(r['timed_out'] for r in rows), scored_items=total,
                historical_rounds_excluded_from_accuracy=sum(not r['verified'] for r in rows))
        return out

    def overview(self):
        attempted = sum(r['attempted'] for r in self.window)
        correct = sum(r['correct'] for r in self.window)
        return dict(window_days=self.days, has_data=bool(self.window), attempted=attempted, correct=correct,
                    incorrect=attempted-correct, accuracy=round(correct/attempted, 3) if attempted else None,
                    sessions=len(self.window), study_minutes=minutes(sum(r['seconds'] for r in self.window)))

    def improvement(self):
        midpoint = self.start + (self.now-self.start)/2
        halves = [[r for r in self.window if (r['at'] < midpoint) == earlier] for earlier in (True, False)]
        counts = [sum(r['attempted'] for r in rows) for rows in halves]
        accuracies = [sum(r['correct'] for r in rows)/count if count >= 10 else None for rows, count in zip(halves, counts)]
        first, last = accuracies
        change = last-first if first is not None and last is not None else None
        return dict(direction='insufficient_data' if change is None else 'up' if change > .02 else 'down' if change < -.02 else 'flat',
                    earlier_accuracy=round(first, 3) if first is not None else None,
                    recent_accuracy=round(last, 3) if last is not None else None,
                    earlier_items=counts[0], recent_items=counts[1], change=round(change, 3) if change is not None else None,
                    note='At least 10 scored objective items in each half of this period are needed to compare results. Different question sets can affect the comparison.')

    def daily(self):
        grouped = defaultdict(lambda: [0, 0])
        for row in self.window:
            values = grouped[timezone.localdate(row['at'])]
            values[0] += row['seconds']; values[1] += 1
        return [dict(date=(self.first+timedelta(days=i)).isoformat(),
                     minutes=minutes(grouped[self.first+timedelta(days=i)][0]),
                     sessions=grouped[self.first+timedelta(days=i)][1]) for i in range(self.days)]

    def consistency(self):
        dates = sorted({timezone.localdate(r['at']) for r in self.rows})
        longest = run = 0
        previous = None
        for day in dates:
            run = run + 1 if previous and day == previous+timedelta(days=1) else 1
            longest = max(longest, run); previous = day
        current = run if dates and dates[-1] >= self.today-timedelta(days=1) else 0
        active = sum(day >= self.first for day in dates)
        total = minutes(sum(r['seconds'] for r in self.window))
        return dict(active_days=active, window_days=self.days, active_rate=round(active/self.days, 3),
                    current_streak=current, longest_streak=longest, total_minutes=total,
                    average_minutes_per_active_day=round(total/active, 2) if active else 0)

    def by_assessment(self):
        grouped = {}
        for row in self.window:
            if row['kind'] not in LABELS:
                continue
            group = grouped.setdefault(row['kind'], dict(activity=row['kind'], label=LABELS[row['kind']],
                                                        attempted=0, correct=0, sessions=0, seconds=0))
            for key in ('attempted', 'correct', 'seconds'):
                group[key] += row[key]
            group['sessions'] += 1
        return [dict(activity=g['activity'], label=g['label'], attempted=g['attempted'], correct=g['correct'],
                     sessions=g['sessions'], minutes=minutes(g['seconds']),
                     accuracy=round(g['correct']/g['attempted'], 3) if g['attempted'] else None)
                for g in sorted(grouped.values(), key=lambda g: (-g['attempted'], g['activity']))]

    def _scope_nodes(self, requested):
        """Roll finer evidence up only through currently authorized ancestors."""
        models = {'TOPIC': Topic, 'SUB_BLOCK': SubBlock, 'BLOCK': Block, 'SUBJECT': Subject}
        related = {'TOPIC': ('block__subject', 'sub_block__block__subject'),
                   'SUB_BLOCK': ('block__subject',), 'BLOCK': ('subject',), 'SUBJECT': ()}
        nodes = {node for row in self.window for node, _, _ in row['nodes'] if node}
        mapped = {node: node for node in nodes if node[0] == requested}
        by_identity = defaultdict(list)
        for node in nodes:
            by_identity[node[:2]].append(node)
        levels = tuple(models)
        for level, model in models.items():
            # Evidence can roll up to ancestors, never down into an untested child.
            if requested in models and levels.index(level) >= levels.index(requested):
                continue
            keys = [node[1] for node in nodes if node[0] == level]
            if not keys:
                continue
            rows = visible(model, self.user).filter(pk__in=keys).select_related(*related[level])
            for row in rows:
                sub = row if level == 'SUB_BLOCK' else row.sub_block if level == 'TOPIC' else None
                block = row if level == 'BLOCK' else sub.block if sub else row.block if level == 'TOPIC' else None
                subject = row if level == 'SUBJECT' else block.subject if block else None
                ancestor = {'SUB_BLOCK': sub, 'BLOCK': block, 'SUBJECT': subject}.get(requested)
                if ancestor is not None:
                    for node in by_identity.get((level, str(row.pk)), ()):
                        mapped[node] = (requested, str(ancestor.pk), ancestor.name)
        return mapped

    def topics(self, limit=8, scope=None):
        mapped = self._scope_nodes(scope) if scope else None
        grouped = {}
        for row in sorted(self.window, key=lambda r: r['at']):
            for node, correct, total in row['nodes']:
                if not node or not total:
                    continue
                if mapped is not None:
                    node = mapped.get(node)
                    if node is None:
                        continue
                level, pk, label = node
                group = grouped.setdefault((level, pk), dict(id=f'{level}:{pk}', scope=level, label=label, correct=0, attempted=0))
                group['correct'] += correct; group['attempted'] += total; group['last_practised_at'] = row['at']
        scope_level = scope or next((s for s in ('TOPIC', 'SUB_BLOCK', 'BLOCK', 'SUBJECT')
                            if any(g['scope'] == s and g['attempted'] >= 3 for g in grouped.values())), None)
        rows = [dict(g, accuracy=round(g['correct']/g['attempted'], 3),
                     mastery=g['correct']/g['attempted'], priority=1-g['correct']/g['attempted'])
                for g in grouped.values() if g['scope'] == scope_level and g['attempted'] >= 3]
        return dict(scope=scope_level, tracked_nodes=len(rows),
                    weakest=sorted([r for r in rows if r['mastery'] < .75], key=lambda r: (-r['priority'], r['id']))[:limit],
                    strongest=sorted([r for r in rows if r['mastery'] >= .75], key=lambda r: (-r['mastery'], r['id']))[:limit])
