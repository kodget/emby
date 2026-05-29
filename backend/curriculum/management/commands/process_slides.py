"""
Management command to process slides through the conversion pipeline

Usage:
    python manage.py process_slides --all
    python manage.py process_slides --slide-id <slide_id>
    python manage.py process_slides --failed-only
"""

from django.core.management.base import BaseCommand
from curriculum.models import Slide, SlideProcessingStatus
from curriculum.services.slide_processor import SlideProcessor
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process slides through conversion pipeline and extract content'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all slides',
        )
        parser.add_argument(
            '--slide-id',
            type=str,
            help='Process specific slide by ID',
        )
        parser.add_argument(
            '--failed-only',
            action='store_true',
            help='Process only slides that previously failed',
        )
        parser.add_argument(
            '--reprocess',
            action='store_true',
            help='Reprocess slides even if already processed',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SLIDE PROCESSING'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Determine which slides to process
        if options['slide_id']:
            slides = Slide.objects.filter(id=options['slide_id'])
            if not slides.exists():
                self.stdout.write(self.style.ERROR(f"Slide {options['slide_id']} not found"))
                return
        elif options['failed_only']:
            # Get slides that failed processing
            failed_statuses = SlideProcessingStatus.objects.filter(
                is_embedded=False
            ).exclude(error_message='')
            slide_ids = [status.slide_id for status in failed_statuses]
            slides = Slide.objects.filter(id__in=slide_ids)
        elif options['all']:
            if options['reprocess']:
                slides = Slide.objects.all()
            else:
                # Skip already processed slides
                processed_ids = SlideProcessingStatus.objects.filter(
                    is_embedded=True
                ).values_list('slide_id', flat=True)
                slides = Slide.objects.exclude(id__in=processed_ids)
        else:
            self.stdout.write(self.style.ERROR('Please specify --all, --slide-id, or --failed-only'))
            return
        
        total = slides.count()
        self.stdout.write(f"Processing {total} slides...\n")
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for idx, slide in enumerate(slides, 1):
            self.stdout.write(f"[{idx}/{total}] Processing: {slide.title}")
            
            # Check if already processed (unless reprocess flag is set)
            if not options['reprocess']:
                status = SlideProcessingStatus.objects.filter(
                    slide=slide,
                    is_embedded=True
                ).first()
                if status:
                    self.stdout.write(self.style.WARNING("  ⊘ Skipped (already processed)"))
                    skipped_count += 1
                    continue
            
            # Process the slide
            result = SlideProcessor.process_slide(slide)
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS("  ✓ Success"))
                self.stdout.write(f"    - Content: {result['content_length']} characters")
                self.stdout.write(f"    - Pages: {result['page_count']}")
                self.stdout.write(f"    - RAG: {'✓' if result['rag_processed'] else '✗'}")
                success_count += 1
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ Failed: {result.get('error', 'Unknown error')}"))
                failed_count += 1
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f"✓ Processed: {success_count}"))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f"⊘ Skipped: {skipped_count}"))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Failed: {failed_count}"))
        self.stdout.write('=' * 60)
