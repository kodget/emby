from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Dispatch due saved question-generation requests and recover expired worker leases.'

    def handle(self, *args, **options):
        from learning.generation_dispatch import recover_generation_jobs
        result = recover_generation_jobs()
        self.stdout.write(f"Published {result['published']} saved generation request(s).")
        from backend.task_dispatch import wait_for_local_tasks
        wait_for_local_tasks()
