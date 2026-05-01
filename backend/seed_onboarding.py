"""
Seed onboarding questions
Run with: python manage.py shell -c "exec(open('seed_onboarding.py').read())"
"""

from accounts.models import OnboardingQuestion

# Clear existing questions
OnboardingQuestion.objects.all().delete()

# Create onboarding questions
questions = [
    {
        'question_text': 'What are your primary learning goals?',
        'question_type': 'text',
        'order': 1
    },
    {
        'question_text': 'How many hours per day can you dedicate to studying?',
        'question_type': 'choice',
        'options': ['Less than 1 hour', '1-2 hours', '2-4 hours', 'More than 4 hours'],
        'order': 2
    },
    {
        'question_text': 'What is your preferred learning style?',
        'question_type': 'choice',
        'options': ['Visual (diagrams, videos)', 'Reading/Writing', 'Auditory (lectures)', 'Kinesthetic (hands-on)'],
        'order': 3
    },
    {
        'question_text': 'Which subjects do you find most challenging?',
        'question_type': 'choice',
        'options': ['Anatomy', 'Physiology', 'Biochemistry', 'All equally', 'None'],
        'order': 4
    },
    {
        'question_text': 'Do you prefer studying alone or in groups?',
        'question_type': 'choice',
        'options': ['Alone', 'In small groups', 'In large groups', 'Both alone and groups'],
        'order': 5
    },
]

for q_data in questions:
    OnboardingQuestion.objects.create(**q_data)

print(f"✅ Created {len(questions)} onboarding questions")
