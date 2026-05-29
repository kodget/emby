"""
Management command to delete all slides from the database
"""
from django.core.management.base import BaseCommand
from curriculum.models import Slide, SlideContent, SlideChunk, SlideProcessingStatus


class Command(BaseCommand):
    help = 'Delete all slides and related data from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all slides',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will delete ALL slides and related data from the database.\n'
                    'Run with --confirm to proceed.'
                )
            )
            return

        self.stdout.write('Deleting all slides and related data...')

        # Count before deletion
        slide_count = Slide.objects.count()
        content_count = SlideContent.objects.count()
        chunk_count = SlideChunk.objects.count()
        status_count = SlideProcessingStatus.objects.count()

        self.stdout.write(f'Found:')
        self.stdout.write(f'  - {slide_count} slides')
        self.stdout.write(f'  - {content_count} slide contents')
        self.stdout.write(f'  - {chunk_count} slide chunks')
        self.stdout.write(f'  - {status_count} processing statuses')

        # Delete all related data
        SlideChunk.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {chunk_count} slide chunks'))

        SlideProcessingStatus.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {status_count} processing statuses'))

        SlideContent.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {content_count} slide contents'))

        Slide.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {slide_count} slides'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully deleted all slides and related data!'
            )
        )
