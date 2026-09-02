import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import QuizAttempt
from django.contrib.auth.models import User
from learning import events
from learning.models import ActivityType, LearningEvent

user = User.objects.first()
print('Events before:', LearningEvent.objects.count())

attempts = QuizAttempt.objects.filter(user=user)
for attempt in attempts:
    events.record(
        user=user, 
        activity=ActivityType.QUIZ_COMPLETED, 
        subject=getattr(attempt, 'subject', None), 
        correct_count=attempt.mcq_score or 0, 
        total_count=attempt.mcq_total or 10, 
        duration_seconds=120, 
        resource_type='QuizAttempt', 
        resource_id=str(attempt.id), 
        metadata={'exam_type': attempt.exam_type}
    )

print('Events after:', LearningEvent.objects.count())
