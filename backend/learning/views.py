"""
Learning API.

Endpoints for the systems that span features: image-spot practice (Steeplechase and
Histology), the AI credit meter, weak areas, XP and notifications.

Everything here is authenticated, scoped to `request.user`, and enforces entitlement
server-side — the frontend displays allowances but never decides them.
"""

from __future__ import annotations

import logging

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from curriculum.models import SpotStation

from . import analytics, battles, credits, dashboard, events, notifications, practice, selection, xp
from .models import (
    AIUsageEvent,
    LearningEvent,
    Notification,
    NotificationPreference,
    PracticeMode,
    PracticeSession,
    WeakArea,
)

logger = logging.getLogger(__name__)


def _mode_from(request, default=PracticeMode.STEEPLECHASE) -> str:
    raw = (request.query_params.get("mode") or request.data.get("mode") or default)
    return str(raw).upper()


# ---------------------------------------------------------------------------
# Practice — Steeplechase and Histology
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def practice_options(request):
    """Everything the setup screen needs: sections, counts and this user's allowance."""
    mode = _mode_from(request)
    if mode not in dict(PracticeMode.choices):
        return Response({"detail": "Unknown mode"}, status=400)

    return Response(
        {
            "mode": mode,
            "seconds_per_station": practice.SECONDS_PER_STATION,
            "sections": practice.available_sections(mode),
            "entitlement": practice.entitlement(request.user, mode),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def practice_start(request):
    """Begin a round. Returns the session and its first station."""
    mode = _mode_from(request)
    sections = request.data.get("sections") or []
    if isinstance(sections, str):
        sections = [sections]
    try:
        count = int(request.data.get("count", practice.FREE_STATIONS_PER_ROUND))
    except (TypeError, ValueError):
        return Response({"detail": "count must be a number"}, status=400)

    try:
        session = practice.start_session(request.user, mode, sections, count)
    except practice.PracticeError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=exc.status)

    first = SpotStation.objects.get(id=session.station_ids[0])
    return Response(
        {
            "session_id": str(session.id),
            "mode": session.mode,
            "total_stations": session.total_stations,
            "seconds_per_station": session.seconds_per_station,
            "station": practice.station_payload(first, 0, session.total_stations),
            "entitlement": practice.entitlement(request.user, mode),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def practice_station(request, session_id, index):
    """Fetch one station by position, without any answer data."""
    session = PracticeSession.objects.filter(id=session_id, user=request.user).first()
    if session is None:
        return Response({"detail": "Session not found"}, status=404)

    try:
        index = int(index)
        station_id = session.station_ids[index]
    except (ValueError, IndexError):
        return Response({"detail": "No station at that position"}, status=404)

    station = SpotStation.objects.filter(id=station_id).first()
    if station is None:
        return Response({"detail": "Station not found"}, status=404)

    return Response(practice.station_payload(station, index, session.total_stations))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def practice_answer(request, session_id):
    """Submit one station's answers and get the reveal."""
    session = PracticeSession.objects.filter(id=session_id, user=request.user).first()
    if session is None:
        return Response({"detail": "Session not found"}, status=404)

    supporting = request.data.get("supporting_choice")
    try:
        supporting = int(supporting) if supporting is not None else None
    except (TypeError, ValueError):
        supporting = None

    tf = request.data.get("true_false_answer")
    if isinstance(tf, str):
        tf = tf.lower() in {"true", "1", "yes"}

    try:
        seconds = int(request.data.get("seconds_taken", 0))
    except (TypeError, ValueError):
        seconds = 0

    try:
        reveal = practice.submit_attempt(
            session,
            str(request.data.get("station_id") or ""),
            main_answer=str(request.data.get("main_answer") or ""),
            supporting_choice=supporting,
            true_false_answer=tf,
            seconds_taken=seconds,
            timed_out=bool(request.data.get("timed_out")),
        )
    except practice.PracticeError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=exc.status)

    return Response(reveal)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def practice_complete(request, session_id):
    """Finish a round and return the full result breakdown."""
    session = PracticeSession.objects.filter(id=session_id, user=request.user).first()
    if session is None:
        return Response({"detail": "Session not found"}, status=404)
    return Response(practice.complete_session(session))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def practice_results(request, session_id):
    session = PracticeSession.objects.filter(id=session_id, user=request.user).first()
    if session is None:
        return Response({"detail": "Session not found"}, status=404)
    return Response(practice.results(session))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def practice_history(request):
    """Recent rounds, for the practice landing screen."""
    mode = _mode_from(request)
    rows = PracticeSession.objects.filter(
        user=request.user, mode=mode, status=PracticeSession.Status.COMPLETED
    ).order_by("-completed_at")[:20]

    return Response(
        [
            {
                "session_id": str(s.id),
                "completed_at": s.completed_at,
                "total_stations": s.total_stations,
                "accuracy_percent": round(s.score * 100),
                "sections": s.sections,
            }
            for s in rows
        ]
    )


# ---------------------------------------------------------------------------
# AI credits
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def credit_balance(request):
    """The authoritative remaining balance, plus what each action costs."""
    return Response(
        {
            **credits.balance(request.user),
            "costs": {k: v for k, v in credits.COSTS.items()},
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def credit_history(request):
    return Response(credits.history(request.user))


# ---------------------------------------------------------------------------
# Weak areas and XP
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weak_areas(request):
    """What this student should revise, newest evidence weighted most."""
    scope = (request.query_params.get("scope") or WeakArea.Scope.TOPIC).upper()
    try:
        limit = min(int(request.query_params.get("limit", 5)), 25)
    except (TypeError, ValueError):
        limit = 5

    weakest = events.weakest(request.user, scope=scope, limit=limit)
    strongest = events.strongest(request.user, scope=scope, limit=limit)

    def serialise(area: WeakArea) -> dict:
        return {
            "id": area.id,
            "scope": area.scope,
            "label": area.label,
            "subject_id": area.subject_id,
            "block_id": area.block_id,
            "sub_block_id": area.sub_block_id,
            "topic_id": area.topic_id,
            "attempted": area.attempted,
            "correct": area.correct,
            "accuracy": round(area.accuracy, 3) if area.accuracy is not None else None,
            "mastery": round(area.mastery, 3),
            "priority": area.priority,
            "last_practised_at": area.last_practised_at,
        }

    return Response(
        {
            "scope": scope,
            "weakest": [serialise(a) for a in weakest],
            "strongest": [serialise(a) for a in strongest],
            # An empty list is a real answer: it means there is not enough evidence yet.
            "has_data": WeakArea.objects.filter(user=request.user, attempted__gt=0).exists(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def xp_summary(request):
    """Total XP plus a recent breakdown, for the profile and analytics screens."""
    try:
        days = min(int(request.query_params.get("days", 30)), 365)
    except (TypeError, ValueError):
        days = 30

    recent = xp.breakdown(request.user, days=days)
    return Response(
        {
            "total_xp": xp.total_xp(request.user),
            "window_days": days,
            "window_total": recent["total"],
            "by_activity": recent["by_activity"],
            "daily_caps": {k: v for k, v in xp.DAILY_CAP.items()},
        }
    )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_list(request):
    """Delivered notifications for the bell menu."""
    qs = Notification.objects.filter(
        user=request.user, scheduled_for__lte=timezone.now()
    ).exclude(status=Notification.Status.CANCELLED)

    if request.query_params.get("unread") == "true":
        qs = qs.filter(read=False)

    rows = list(qs[:50])

    # Serving a notification is the moment it actually reaches the student, so that is
    # when it is marked delivered — rather than assuming delivery at creation time.
    for row in rows:
        notifications.mark_delivered(row)

    return Response(
        {
            "unread_count": Notification.objects.filter(
                user=request.user, read=False, scheduled_for__lte=timezone.now()
            )
            .exclude(status=Notification.Status.CANCELLED)
            .count(),
            "results": [
                {
                    "id": str(n.id),
                    "type": n.type,
                    "title": n.title,
                    "body": n.body,
                    "action_url": n.action_url,
                    "read": n.read,
                    "created_at": n.created_at,
                }
                for n in rows
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read(request):
    """Mark one notification, or all of them, as read."""
    notification_id = request.data.get("id")
    qs = Notification.objects.filter(user=request.user, read=False)
    if notification_id:
        qs = qs.filter(id=notification_id)

    updated = qs.update(read=True, read_at=timezone.now())
    return Response({"marked_read": updated})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == "PATCH":
        allowed = {
            "flashcards_enabled", "planner_enabled", "study_goal_enabled",
            "streak_enabled", "weak_area_enabled", "browser_push_enabled",
            "quiet_hours_start", "quiet_hours_end", "max_per_day",
        }
        for field, value in request.data.items():
            if field in allowed:
                setattr(prefs, field, value)
        prefs.save()

    return Response(
        {
            "flashcards_enabled": prefs.flashcards_enabled,
            "planner_enabled": prefs.planner_enabled,
            "study_goal_enabled": prefs.study_goal_enabled,
            "streak_enabled": prefs.streak_enabled,
            "weak_area_enabled": prefs.weak_area_enabled,
            "browser_push_enabled": prefs.browser_push_enabled,
            "quiet_hours_start": prefs.quiet_hours_start,
            "quiet_hours_end": prefs.quiet_hours_end,
            "max_per_day": prefs.max_per_day,
        }
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_message(request):
    """The personalised greeting, regenerated at most once every six hours."""
    force = request.query_params.get("refresh") == "true"
    return Response(dashboard.get_message(request.user, force=force))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_snapshot(request):
    """The numbers behind the dashboard stat rail, all from real activity."""
    from curriculum.models import FlashcardProgress

    mode_counts = {
        mode: practice.entitlement(request.user, mode)
        for mode, _ in PracticeMode.choices
    }

    return Response(
        {
            "streak": getattr(getattr(request.user, "stats", None), "active_streak", 0) or 0,
            "xp": xp.total_xp(request.user),
            "credits": credits.balance(request.user),
            "cards_due": FlashcardProgress.objects.filter(
                user=request.user, due_date__lte=timezone.now()
            ).count(),
            "practice": mode_counts,
            "question_coverage": selection.coverage(request.user, question_type="mcq"),
        }
    )


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_report(request):
    """Everything the analytics screen renders, computed from recorded activity.

    Free students get real headline figures, activity and per-assessment performance;
    topic-level analysis and bank coverage are the premium half. Nothing is fabricated
    for either tier — where evidence is thin the payload says so.
    """
    try:
        days = min(max(int(request.query_params.get("days", 30)), 7), 365)
    except (TypeError, ValueError):
        days = 30

    profile = getattr(request.user, "profile", None)
    is_premium = bool(profile and profile.is_premium)

    return Response(
        {
            **analytics.full_report(request.user, days, include_detail=is_premium),
            "is_premium": is_premium,
        }
    )


# ---------------------------------------------------------------------------
# Brain Battle
# ---------------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def battle_join(request):
    """Join a battle by its shared code."""
    from curriculum.models import BrainBattle

    try:
        battle, participant, created = battles.join(
            request.user, str(request.data.get("code") or "")
        )
    except battles.BattleError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=exc.status)

    return Response(
        {
            "battle_id": battle.id,
            "code": battle.code,
            "title": battle.title,
            "status": battle.status,
            "total_questions": battle.question_count,
            "seconds_per_question": battle.time_per_question,
            "host": battle.host_id == request.user.id,
            "newly_joined": created,
            "your_score": participant.score,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def battle_lookup(request, code):
    """Check a code before committing to join it."""
    try:
        battle = battles.find_by_code(code)
    except battles.BattleError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=exc.status)

    return Response(
        {
            "code": battle.code,
            "title": battle.title,
            "status": battle.status,
            "total_questions": battle.question_count,
            "seconds_per_question": battle.time_per_question,
            "participants": battle.participants.count(),
            "host_name": (battle.host.get_full_name() or battle.host.username).strip(),
        }
    )


def _participant_battle(request, battle_id):
    """Fetch a battle the caller has actually joined."""
    from curriculum.models import BattleParticipant, BrainBattle

    battle = BrainBattle.objects.filter(id=battle_id).first()
    if battle is None:
        return None, Response({"detail": "Battle not found"}, status=404)
    if not BattleParticipant.objects.filter(battle=battle, user=request.user).exists():
        return None, Response({"detail": "Join this battle first"}, status=403)
    return battle, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def battle_question(request, battle_id, index):
    """One question, with the answer withheld."""
    battle, error = _participant_battle(request, battle_id)
    if error:
        return error
    try:
        return Response(battles.question_payload(battle, int(index)))
    except (battles.BattleError, ValueError) as exc:
        code = getattr(exc, "code", "invalid")
        return Response({"detail": str(exc), "code": code}, status=getattr(exc, "status", 400))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def battle_answer(request, battle_id):
    """Submit an answer. The server decides whether it was right and what it scored."""
    battle, error = _participant_battle(request, battle_id)
    if error:
        return error

    try:
        index = int(request.data.get("index"))
    except (TypeError, ValueError):
        return Response({"detail": "index is required"}, status=400)

    selected = request.data.get("selected_index")
    try:
        selected = int(selected) if selected is not None else None
    except (TypeError, ValueError):
        selected = None

    try:
        seconds = float(request.data.get("seconds_taken", 0) or 0)
    except (TypeError, ValueError):
        seconds = 0.0

    try:
        return Response(
            battles.submit_answer(request.user, battle, index, selected, seconds)
        )
    except battles.BattleError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def battle_leaderboard(request, battle_id):
    battle, error = _participant_battle(request, battle_id)
    if error:
        return error
    return Response({"leaderboard": battles.leaderboard(battle)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def battle_finish(request, battle_id):
    """Close out this participant's run and award XP once."""
    battle, error = _participant_battle(request, battle_id)
    if error:
        return error
    try:
        return Response(battles.finish_for_user(request.user, battle))
    except battles.BattleError as exc:
        return Response({"detail": str(exc), "code": exc.code}, status=exc.status)
# ---------------------------------------------------------------------------
# GAMIFICATION
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def achievements_list(request):
    """List all available achievements and the user's progress."""
    from .models import Achievement, UserAchievement
    achievements = Achievement.objects.filter(is_active=True).select_related("badge")
    user_achs = {ua.achievement_id: ua for ua in UserAchievement.objects.filter(user=request.user)}
    
    data = []
    for ach in achievements:
        ua = user_achs.get(ach.id)
        # Skip hidden achievements unless completed
        if ach.is_hidden and (not ua or not ua.is_completed):
            continue
            
        badge_data = None
        if ach.badge:
            badge_data = {
                "id": ach.badge.id,
                "name": ach.badge.name,
                "icon": ach.badge.icon,
                "rarity": ach.badge.rarity,
                "image_url": ach.badge.image_url,
            }
            
        data.append({
            "id": ach.id,
            "name": ach.name,
            "description": ach.description,
            "category": ach.category,
            "target_metric": ach.target_metric,
            "target_value": ach.target_value,
            "progress": ua.progress if ua else 0,
            "percentage": ua.percentage if ua else 0,
            "is_completed": ua.is_completed if ua else False,
            "completed_at": ua.completed_at.isoformat() if ua and ua.completed_at else None,
            "badge": badge_data
        })
        
    return Response(data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_badges(request):
    """List all badges earned by the user."""
    from .models import UserBadge
    badges = UserBadge.objects.filter(user=request.user).select_related("badge")
    
    data = []
    for ub in badges:
        data.append({
            "id": ub.id,
            "badge_id": ub.badge.id,
            "name": ub.badge.name,
            "description": ub.badge.description,
            "category": ub.badge.category,
            "rarity": ub.badge.rarity,
            "icon": ub.badge.icon,
            "image_url": ub.badge.image_url,
            "earned_at": ub.earned_at.isoformat()
        })
        
    return Response(data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gamification_profile(request):
    """Get a summary of gamification stats for the user's profile."""
    from .models import UserBadge, UserAchievement
    from .xp import total_xp
    
    earned_badges = UserBadge.objects.filter(user=request.user).count()
    completed_achievements = UserAchievement.objects.filter(user=request.user, is_completed=True).count()
    user_xp = total_xp(request.user)
    stats = getattr(request.user, "stats", None)
    current_streak = stats.active_streak if stats else 0
    longest_streak = stats.longest_streak if stats else 0
    
    return Response({
        "xp": user_xp,
        "badges_count": earned_badges,
        "achievements_count": completed_achievements,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
    })

# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_list(request):
    """Return the user's notifications."""
    from .models import Notification
    unread_only = request.GET.get("unread") == "true"
    qs = Notification.objects.filter(user=request.user)
    if unread_only:
        qs = qs.filter(read=False)
    
    qs = qs.order_by("-scheduled_for")[:50]
    
    data = []
    for n in qs:
        data.append({
            "id": n.id,
            "type": n.type,
            "priority": n.priority,
            "title": n.title,
            "body": n.body,
            "action_url": n.action_url,
            "payload": n.payload,
            "read": n.read,
            "scheduled_for": n.scheduled_for.isoformat() if n.scheduled_for else None,
            "created_at": n.created_at.isoformat(),
        })
    return Response(data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read(request):
    """Mark a notification (or all) as read."""
    from .models import Notification
    from django.utils import timezone
    notif_id = request.data.get("id")
    
    qs = Notification.objects.filter(user=request.user, read=False)
    if notif_id:
        qs = qs.filter(id=notif_id)
        
    updated = qs.update(read=True, read_at=timezone.now())
    return Response({"success": True, "updated_count": updated})

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    """Get or update notification preferences."""
    from .models import NotificationPreference
    
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        for field in [
            "academic_enabled", "community_enabled", "system_enabled",
            "flashcards_enabled", "planner_enabled", "study_goal_enabled", "streak_enabled"
        ]:
            if field in request.data:
                setattr(pref, field, bool(request.data[field]))
        pref.save()
        
    return Response({
        "academic_enabled": pref.academic_enabled,
        "community_enabled": pref.community_enabled,
        "system_enabled": pref.system_enabled,
        "flashcards_enabled": pref.flashcards_enabled,
        "planner_enabled": pref.planner_enabled,
        "study_goal_enabled": pref.study_goal_enabled,
        "streak_enabled": pref.streak_enabled,
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_subscribe(request):
    """Subscribe a device for push notifications (web push)."""
    return Response({"success": True})
