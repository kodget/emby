"""Read-only differences between accepted activity and historical counter caches."""
from collections import Counter, defaultdict

from django.db.models import Q, F
from django.utils import timezone

from curriculum.class_access import visible_attempts
from curriculum.models import UserStats, DailyStudySession
from .analytics_evidence import Evidence, minutes
from .events import COMPLETION_RESOURCES
from .models import LearningEvent, WeakArea, XPAward


def report(user):
    evidence = Evidence(user, 7)
    consistency = evidence.consistency()
    stats = UserStats.objects.filter(user=user).first()
    daily = defaultdict(lambda: {'seconds': 0, 'sessions': 0})
    for row in evidence.rows:
        day = timezone.localdate(row['at']).isoformat()
        daily[day]['seconds'] += row['seconds']
        daily[day]['sessions'] += 1
    stored = {row.date.isoformat(): row for row in DailyStudySession.objects.filter(user=user)}
    differences = []
    for day in sorted(daily.keys() | stored.keys()):
        observed = daily[day]
        cached = stored.get(day)
        if (cached.minutes_studied if cached else 0, cached.sessions_count if cached else 0) != (
                observed['seconds'] // 60, observed['sessions']):
            differences.append({'date': day, 'observed_minutes': minutes(observed['seconds']),
                'observed_sessions': observed['sessions'],
                'cached_minutes': cached.minutes_studied if cached else 0,
                'cached_sessions': cached.sessions_count if cached else 0})
    events = LearningEvent.objects.filter(user=user)
    completions = Counter(events.filter(resource_type__in=COMPLETION_RESOURCES).exclude(resource_id='')
                          .values_list('activity', 'resource_type', 'resource_id'))
    weak_keys = Counter(WeakArea.objects.filter(user=user).values_list(
        'scope', 'subject_id', 'block_id', 'sub_block_id', 'topic_id'))
    reward_keys = Counter(XPAward.objects.filter(user=user, event__isnull=False).values_list('event_id', flat=True))
    attempts = visible_attempts(user).filter(status__in=('submitted', 'auto_submitted'),
                                           submitted_at__lte=evidence.now)
    saved_attempts = attempts.exclude(question_snapshots=[])
    return {
        'dry_run': True, 'user_id': user.pk, 'generated_at': evidence.now.isoformat(),
        'timezone': timezone.get_current_timezone_name(),
        'observed': {'study_minutes': minutes(sum(row['seconds'] for row in evidence.rows)),
            'sessions': len(evidence.rows), 'current_streak': consistency['current_streak'],
            'longest_streak': consistency['longest_streak']},
        'cached': {'study_minutes': stats.total_study_minutes, 'current_streak': stats.current_streak,
                   'longest_streak': stats.longest_streak} if stats else None,
        'daily_differences': differences,
        'duplicate_completion_rows': sum(max(0, count-1) for count in completions.values()),
        'duplicate_weak_area_rows': sum(max(0, count-1) for count in weak_keys.values()),
        'legacy_weak_area_rows': WeakArea.objects.filter(user=user, canonical_key__isnull=True).count(),
        'canonical_weak_area_rows': WeakArea.objects.filter(user=user, canonical_key__isnull=False).count(),
        'duplicate_reward_rows': sum(max(0, count-1) for count in reward_keys.values()),
        'invalid_activity_rows': events.filter(Q(correct_count__lt=0) | Q(total_count__lt=0) |
            Q(correct_count__gt=F('total_count')) | Q(duration_seconds__lt=0)).count(),
        'future_activity_rows': events.filter(occurred_at__gt=evidence.now).count(),
        'historical_assessments_without_snapshots': attempts.filter(question_snapshots=[]).count(),
        'saved_assessments_without_completion_event': saved_attempts.exclude(pk__in=events.filter(
            resource_type='QuizAttempt', activity='QUIZ_COMPLETED').values('resource_id')).count(),
        'xp_decisions_unmarked': events.filter(xp_processed=False).count(),
        'notes': [
            'Read-only comparison; no records, points, rewards or caches were changed.',
            'Cache-only activity is unverified, not proof of data loss. Do not invent historical events from these totals.',
            'Unmarked XP decisions include pre-migration rows and are not an instruction to award them.',
            'Unkeyed legacy weak-area duplicates are retained as history; canonical keys protect new writes. Student recommendations use accepted evidence.',
            'Daily comparisons use whole minutes; observed durations retain fractions. Sessions include zero-duration accepted activity.',
        ],
    }
