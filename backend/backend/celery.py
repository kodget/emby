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
