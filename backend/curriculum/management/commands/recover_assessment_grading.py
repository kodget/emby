from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Recover due saved-assessment grading jobs and expired worker leases.'

    def handle(self, *args, **options):
        from curriculum.assessment_grading import recovery
        result = recovery()
        self.stdout.write(f"Adopted {result['adopted']} submission(s); dispatched {result['published']} grading job(s).")
