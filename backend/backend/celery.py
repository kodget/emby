import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("emby")

# Read CELERY_* settings from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every installed app
app.autodiscover_tasks()


from celery.schedules import crontab

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

app.conf.beat_schedule = {
    "recover-document-indexes": {
        "task": "curriculum.tasks.recover_document_indexes_task",
        "schedule": crontab(minute="*/5"),
    },
    "dispatch-due-notifications": {
        "task": "learning.tasks.dispatch_due_notifications_task",
        "schedule": crontab(minute="*/5"),
    },
    "recover-slide-processing": {
        "task": "curriculum.tasks.recover_slide_processing_task",
        "schedule": crontab(minute="*/5"),
    },
    "recover-standalone-decks": {
        "task": "curriculum.tasks.recover_standalone_decks_task",
        "schedule": crontab(minute="*/5"),
    },
    "recover-assessment-drafts": {
        "task": "curriculum.tasks.recover_assessment_drafts_task",
        "schedule": 300.0,
    },
    "recover-assessment-grading": {
        "task": "curriculum.tasks.recover_assessment_grading_task",
        "schedule": crontab(minute="*/5"),
    },
    "recover-question-generation": {
        "task": "learning.tasks.recover_question_generation_task",
        "schedule": crontab(minute="*/5"),
    },
    "build-notifications-hourly": {
        "task": "learning.tasks.build_all_notifications_task",
        "schedule": crontab(minute=0),  # Top of every hour
    },
    "allocate-daily-credits": {
        "task": "credits.tasks.allocate_daily_credits",
        "schedule": crontab(minute=0, hour=0),  # Midnight every day
    },
    "credit-expiration-cleanup-hourly": {
        "task": "credits.tasks.expiration_cleanup",
        "schedule": crontab(minute=30),  # Hourly at xx:30
    },
}
