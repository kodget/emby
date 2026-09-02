import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import QuizAttempt
from django.contrib.auth.models import User
from learning.selection import mark_served, mark_answered
from learning.models import QuestionExposure

user = User.objects.first()
print('Exposures before:', QuestionExposure.objects.filter(user=user).count())

attempts = QuizAttempt.objects.filter(user=user)
for attempt in attempts:
    if attempt.question_ids:
        mark_served(user, attempt.question_ids)
    responses = attempt.responses.filter(question__question_type='mcq')
    for response in responses:
        mark_answered(user, str(response.question_id), response.is_correct)

print('Exposures after:', QuestionExposure.objects.filter(user=user).count())
