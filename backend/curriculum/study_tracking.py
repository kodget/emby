from django.db import models
from django.contrib.auth.models import User
from datetime import date


class DailyStudySession(models.Model):
    """Track daily study time for weekly charts"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_sessions')
    date = models.DateField(default=date.today)
    minutes_studied = models.IntegerField(default=0)
    sessions_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.minutes_studied}min"
