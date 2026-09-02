"""Routes for the cross-cutting learning API, mounted at /api/learning/."""

from django.urls import path

from . import views

urlpatterns = [
    # Image-spot practice. `?mode=STEEPLECHASE|HISTOLOGY` selects the pool; both modes
    # share these endpoints because they share the mechanic.
    path("practice/options/", views.practice_options, name="practice-options"),
    path("practice/start/", views.practice_start, name="practice-start"),
    path("practice/history/", views.practice_history, name="practice-history"),
    path(
        "practice/<uuid:session_id>/station/<int:index>/",
        views.practice_station,
        name="practice-station",
    ),
    path("practice/<uuid:session_id>/answer/", views.practice_answer, name="practice-answer"),
    path(
        "practice/<uuid:session_id>/complete/",
        views.practice_complete,
        name="practice-complete",
    ),
    path(
        "practice/<uuid:session_id>/results/",
        views.practice_results,
        name="practice-results",
    ),

    # AI credits
    path("credits/", views.credit_balance, name="credit-balance"),
    path("credits/history/", views.credit_history, name="credit-history"),

    # Learning signals
    path("weak-areas/", views.weak_areas, name="weak-areas"),
    path("xp/", views.xp_summary, name="xp-summary"),

    # Brain Battle — code-based join, server-side scoring
    path("battles/join/", views.battle_join, name="battle-join"),
    path("battles/lookup/<str:code>/", views.battle_lookup, name="battle-lookup"),
    path("battles/<int:battle_id>/question/<int:index>/", views.battle_question, name="battle-question"),
    path("battles/<int:battle_id>/answer/", views.battle_answer, name="battle-answer"),
    path("battles/<int:battle_id>/leaderboard/", views.battle_leaderboard, name="battle-leaderboard"),
    path("battles/<int:battle_id>/finish/", views.battle_finish, name="battle-finish"),

    # Analytics
    path("analytics/", views.analytics_report, name="analytics-report"),

    # Dashboard
    path("dashboard/message/", views.dashboard_message, name="dashboard-message"),
    path("dashboard/snapshot/", views.dashboard_snapshot, name="dashboard-snapshot"),

    # Notifications
    path("notifications/", views.notification_list, name="notification-list"),
    path("notifications/read/", views.notification_read, name="notification-read"),
    path(
        "notifications/preferences/",
        views.notification_preferences,
        name="notification-preferences",
    ),
    path("notifications/subscribe/", views.notification_subscribe, name="notification_subscribe"),
    
    # Gamification
    path("achievements/", views.achievements_list, name="achievements-list"),
    path("badges/", views.user_badges, name="user-badges"),
    path("gamification/profile/", views.gamification_profile, name="gamification-profile"),
]
