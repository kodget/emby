from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Recover private assessment drafting jobs after queue or worker interruptions.'

    def handle(self, *args, **options):
        from curriculum.assessment_drafts import recovery
        self.stdout.write(f'Dispatched {recovery()} drafting job(s).')
