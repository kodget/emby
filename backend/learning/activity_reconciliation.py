"""Opt-in, reviewed repair of derived time/streak caches. Source records stay immutable."""
from collections import defaultdict
from datetime import date
import hashlib
import json
import re

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from curriculum.models import DailyStudySession, UserStats
from .analytics_evidence import Evidence
from .models import ActivityCacheReconciliation

STATS_FIELDS = ('total_study_minutes', 'current_streak', 'longest_streak', 'last_activity_date')


def serializable(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True))


def fingerprint(value):
    return hashlib.sha256(json.dumps(serializable(value), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def totals(evidence):
    daily = defaultdict(lambda: {'seconds': 0, 'sessions_count': 0})
    for row in evidence.rows:
        day = timezone.localdate(row['at']).isoformat()
        daily[day]['seconds'] += row['seconds']
        daily[day]['sessions_count'] += 1
    streak = evidence.consistency()
    stats = dict(total_study_minutes=sum(row['seconds'] for row in evidence.rows) // 60,
                 current_streak=streak['current_streak'], longest_streak=streak['longest_streak'],
                 last_activity_date=max(daily, default=None))
    return stats, {day: dict(minutes_studied=row['seconds'] // 60, sessions_count=row['sessions_count'])
                   for day, row in daily.items()}


def plan(user):
    evidence = Evidence(user, 30)
    stats, daily = totals(evidence)
    cached = UserStats.objects.filter(user=user).values(*STATS_FIELDS).first()
    cached = cached or dict(total_study_minutes=0, current_streak=0, longest_streak=0, last_activity_date=None)
    stored = {row.date.isoformat(): dict(minutes_studied=row.minutes_studied, sessions_count=row.sessions_count)
              for row in DailyStudySession.objects.filter(user=user)}
    days = sorted(daily.keys() | stored.keys())
    empty = dict(minutes_studied=0, sessions_count=0)
    before = serializable(dict(stats=cached, daily={day: stored.get(day, empty) for day in days}))
    after = dict(stats=stats, daily={day: daily.get(day, empty) for day in days})
    content = dict(version=1, user_id=user.pk, timezone=timezone.get_current_timezone_name(),
                   local_date=evidence.today.isoformat(), class_group_id=user.profile.class_group_id,
                   previous_repair_id=ActivityCacheReconciliation.objects.filter(user=user).order_by('-pk')
                       .values_list('pk', flat=True).first(),
                   # Evidence changes invalidate approval even if rounded totals stay equal.
                   evidence_digest=fingerprint(sorted((serializable(row) for row in evidence.rows),
                                                      key=lambda row: json.dumps(row, sort_keys=True))),
                   before=before, after=after)
    return dict(content, fingerprint=fingerprint(content), dry_run=True, changes=before != after)


@transaction.atomic
def apply(user, expected_fingerprint):
    from .events import lock_stats
    if not isinstance(expected_fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', expected_fingerprint):
        raise ValidationError('Supply the exact fingerprint from a reviewed dry run.')
    # Refresh membership before comparing the plan, then use the same lock as activity writers.
    user = type(user).objects.get(pk=user.pk)
    stats = lock_stats(user)
    prior = ActivityCacheReconciliation.objects.filter(user=user, fingerprint=expected_fingerprint).first()
    if prior:
        return dict(applied=False, already_applied=True, receipt_id=prior.pk)
    current = plan(user)
    if current['fingerprint'] != expected_fingerprint:
        raise ValidationError('Activity, membership or caches changed. Review a new dry run before applying.')
    receipt = ActivityCacheReconciliation.objects.create(user=user, fingerprint=expected_fingerprint,
        before=current['before'], after=current['after'])
    for key, value in current['after']['stats'].items():
        setattr(stats, key, date.fromisoformat(value) if key == 'last_activity_date' and value else value)
    stats.save(update_fields=[*STATS_FIELDS, 'updated_at'])
    for day, values in current['after']['daily'].items():
        DailyStudySession.objects.update_or_create(user=user, date=date.fromisoformat(day), defaults=values)
    return dict(applied=True, already_applied=False, receipt_id=receipt.pk, changes=current['changes'])


def refresh_reconciled_time(user, stats, evidence, day):
    """Keep an opted-in account on accepted seconds after subsequent activity."""
    if not ActivityCacheReconciliation.objects.filter(user=user).exists():
        return
    desired, daily = totals(evidence)
    stats.total_study_minutes = desired['total_study_minutes']
    stats.save(update_fields=['total_study_minutes', 'updated_at'])
    # Only the activity's local date can acquire new time in this writer.
    if day is not None:
        DailyStudySession.objects.update_or_create(user=user, date=day,
            defaults=daily.get(day.isoformat(), dict(minutes_studied=0, sessions_count=0)))
