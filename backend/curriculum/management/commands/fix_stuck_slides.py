"""Requeue generation safely without declaring a bank complete from one question."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Persist retry requests for incomplete question banks without replacing active workers.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--all', action='store_true')

    def handle(self, *args, **options):
        from curriculum.models import Slide
        from learning.generation_dispatch import request_generation
        slides = Slide.objects.filter(class_group__isnull=False)
        if not options['all']:
            slides = slides.filter(generation_status__in=['pending', 'in_progress', 'failed'])
        count = 0
        for slide in slides.iterator():
            if options['dry_run']:
                self.stdout.write(f'{slide.pk}: would inspect generation request')
            else:
                count += int(request_generation(slide, force=options['force']))
        self.stdout.write(f'Saved {count} generation request(s). Active jobs were preserved.')
        if not options['dry_run']:
            from backend.task_dispatch import wait_for_local_tasks
            wait_for_local_tasks()
