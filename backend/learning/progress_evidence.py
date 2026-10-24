"""Read-only progress shared by profile, roster and statistics serializers."""
from datetime import timedelta

from django.db.models import F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from curriculum.class_access import scoped_optional_parents, visible
from curriculum.models import (
    Block, DeckReadingProgress, QuizAttempt, QuizQuestion, Slide, SlideDeck,
    SubBlock, Subject, Topic, UserProgress,
)
from .analytics_evidence import Evidence, minutes


def roster_streaks(profiles, *, now=None):
    """Compute class-member streaks from shared queries, without loading full histories."""
    from accounts.models import PlatformRole
    from learning.models import ActivityType, LearningEvent, PracticeAttempt, PracticeMode, PracticeSession
    from learning.practice import playable_stations

    now = now or timezone.now()
    profiles = list(profiles)
    eligible = [
        profile for profile in profiles
        if profile.user.is_active
        and not profile.user.is_superuser
        and profile.platform_role != PlatformRole.ADMIN
        and profile.class_group_id
        and profile.class_group.is_active
        and (profile.class_role != 'class_head' or profile.class_head_verified)
    ]
    streaks = {}
    if eligible:
        user_ids = [profile.user_id for profile in eligible]
        representative = eligible[0].user
        dates_by_user = {user_id: set() for user_id in user_ids}

        events = LearningEvent.objects.filter(
            user_id__in=user_ids,
            occurred_at__lte=now,
            correct_count__gte=0,
            total_count__gte=F('correct_count'),
            duration_seconds__gte=0,
        ).exclude(
            Q(resource_type__in=('QuizAttempt', 'practice_session'))
            | Q(activity__in=(
                ActivityType.QUIZ_COMPLETED,
                ActivityType.STEEPLECHASE_COMPLETED,
                ActivityType.HISTOLOGY_COMPLETED,
            ))
        )
        events = scoped_optional_parents(events, representative, {
            'subject': Subject,
            'block': Block,
            'sub_block': SubBlock,
            'topic': Topic,
        }).filter(
            ~Q(resource_type='standalone_deck')
            | Q(resource_id__in=visible(SlideDeck, representative).values('pk'))
        )
        for user_id, activity_date in events.order_by().annotate(
            activity_date=TruncDate('occurred_at', tzinfo=timezone.get_current_timezone())
        ).values_list('user_id', 'activity_date').distinct():
            dates_by_user[user_id].add(activity_date)

        attempt_rows = QuizAttempt.objects.filter(
            user_id__in=user_ids,
            status__in=('submitted', 'auto_submitted'),
            submitted_at__lte=now,
        )
        formal_ids = attempt_rows.filter(assessment__class_group=eligible[0].class_group).values_list('pk', flat=True)
        snapshot_ids = attempt_rows.filter(snapshot_class=eligible[0].class_group).values_list('pk', flat=True)
        ordinary = scoped_optional_parents(
            attempt_rows.filter(assessment__isnull=True, snapshot_class__isnull=True),
            representative,
            {
                'subject': Subject,
                'block': Block,
                'sub_block': SubBlock,
                'topic': Topic,
                'slide': Slide,
            },
        )
        visible_question_ids = set(visible(QuizQuestion, representative).values_list('pk', flat=True))
        allowed_attempt_ids = [
            attempt_id for attempt_id, question_ids, snapshots in ordinary.values_list(
                'pk', 'question_ids', 'question_snapshots'
            )
            if snapshots and isinstance(question_ids, list)
            and all(isinstance(question_id, str) and question_id in visible_question_ids
                    for question_id in question_ids)
        ]
        foreign_questions = QuizQuestion.objects.exclude(pk__in=visible_question_ids)
        ordinary = ordinary.filter(pk__in=allowed_attempt_ids).exclude(
            responses__question__in=foreign_questions
        )
        attempts = QuizAttempt.objects.filter(user_id__in=user_ids).filter(
            Q(pk__in=formal_ids) | Q(pk__in=snapshot_ids) | Q(pk__in=ordinary)
        ).filter(
            status__in=('submitted', 'auto_submitted'),
            submitted_at__lte=now,
        ).values_list('user_id', 'submitted_at', 'question_snapshots')
        for user_id, submitted_at, snapshots in attempts:
            if snapshots:
                dates_by_user[user_id].add(timezone.localdate(submitted_at))

        allowed_station_ids = set(playable_stations(representative).values_list('pk', flat=True))
        candidate_sessions = PracticeSession.objects.filter(
            user_id__in=user_ids,
            status=PracticeSession.Status.COMPLETED,
            completed_at__lte=now,
            mode__in=PracticeMode.values,
        )
        valid_sessions = {}
        for session_id, user_id, station_ids, completed_at in candidate_sessions.values_list(
            'pk', 'user_id', 'station_ids', 'completed_at'
        ):
            if (isinstance(station_ids, list) and station_ids
                    and all(isinstance(station_id, str) and station_id in allowed_station_ids
                            for station_id in station_ids)
                    and len(set(station_ids)) == len(station_ids)):
                valid_sessions[session_id] = (user_id, set(station_ids), completed_at)
        invalid_sessions = {
            session_id for session_id, station_id in PracticeAttempt.objects.filter(
                session_id__in=valid_sessions
            ).values_list('session_id', 'station_id')
            if station_id not in valid_sessions[session_id][1]
        }
        for session_id, (user_id, _, completed_at) in valid_sessions.items():
            if session_id not in invalid_sessions:
                dates_by_user[user_id].add(timezone.localdate(completed_at))

        today = timezone.localdate(now)
        for user_id, dates in dates_by_user.items():
            latest = max(dates, default=None)
            if latest is None or latest < today - timedelta(days=1):
                streaks[user_id] = 0
                continue
            streak = 1
            while latest - timedelta(days=streak) in dates:
                streak += 1
            streaks[user_id] = streak

    for profile in profiles:
        if profile.user_id not in streaks:
            streaks[profile.user_id] = summary(profile.user)['current_streak']
    return streaks


def summary(user, context=None):
    # Serializer context is request-local, including when serializing a roster.
    cache = context.setdefault('_progress_evidence', {}) if context is not None else {}
    if user.pk not in cache:
        evidence = Evidence(user, 7)
        streak = evidence.consistency()
        completed_slides = set(visible(UserProgress, user).filter(user=user, completed=True).values_list('slide_id', flat=True))
        completed_decks = DeckReadingProgress.objects.filter(user=user,
            current_page__gte=F('deck__page_count'), deck__page_count__gt=0, deck__processing_status='completed',
            deck__in=visible(SlideDeck, user)).values_list('deck_id', 'deck__curriculum_slide_id')
        completed_sources = {f'slide:{pk}' for pk in completed_slides}
        completed_sources.update(f'slide:{slide}' if slide else f'deck:{deck}' for deck, slide in completed_decks)
        cache[user.pk] = {
            'current_streak': streak['current_streak'],
            'longest_streak': streak['longest_streak'],
            'total_study_minutes': minutes(sum(row['seconds'] for row in evidence.rows)),
            'quizzes_taken': sum(row['kind'] in ('practice', 'mock', 'formal') for row in evidence.rows),
            'slides_completed': len(completed_sources),
        }
    return cache[user.pk]
