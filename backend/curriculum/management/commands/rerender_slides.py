"""
Management command to re-render slides that have blank or missing content.
Usage: python manage.py rerender_slides [--all] [--slide-id SLIDE_ID]
"""

from django.core.management.base import BaseCommand
from curriculum.models import Slide, SlideContent
from curriculum.slide_renderer import render_slide_pages
from django.utils import timezone


class Command(BaseCommand):
    help = 'Re-render slides that have blank or missing content'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Re-render all slides regardless of current state',
        )
        parser.add_argument(
            '--slide-id',
            type=str,
            help='Re-render a specific slide by ID',
        )
        parser.add_argument(
            '--file-type',
            type=str,
            choices=['pdf', 'pptx', 'docx', 'all'],
            default='all',
            help='Only re-render slides of specific file type',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting slide re-rendering...'))
        
        # Build queryset
        if options['slide_id']:
            slides = Slide.objects.filter(id=options['slide_id'])
            if not slides.exists():
                self.stdout.write(self.style.ERROR(f"Slide {options['slide_id']} not found"))
                return
        else:
            slides = Slide.objects.all()
            
            # Filter by file type if specified
            if options['file_type'] != 'all':
                slides = slides.filter(file_type__icontains=options['file_type'])
            
            # If not --all, only get slides with missing or empty content
            if not options['all']:
                # Get slides that either have no content or have empty pages
                slides_to_render = []
                for slide in slides:
                    try:
                        content = SlideContent.objects.get(slide=slide)
                        # Check if content is empty or has no pages
                        if not content.is_extracted or not content.content_data.get('pages'):
                            slides_to_render.append(slide.id)
                    except SlideContent.DoesNotExist:
                        slides_to_render.append(slide.id)
                
                slides = Slide.objects.filter(id__in=slides_to_render)
        
        total = slides.count()
        self.stdout.write(f"Found {total} slides to re-render")
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No slides need re-rendering'))
            return
        
        success_count = 0
        error_count = 0
        
        for idx, slide in enumerate(slides, 1):
            self.stdout.write(f"\n[{idx}/{total}] Processing: {slide.title} ({slide.id})")
            self.stdout.write(f"  File type: {slide.file_type}")
            
            try:
                # Get file URL
                file_url = slide.get_file_url
                if not file_url:
                    self.stdout.write(self.style.ERROR(f"  ✗ No file URL found"))
                    error_count += 1
                    continue
                
                self.stdout.write(f"  File URL: {file_url}")
                
                # Render pages
                self.stdout.write(f"  Rendering pages...")
                content = render_slide_pages(file_url, slide.file_type, slide.id)
                
                if content['total_pages'] == 0:
                    self.stdout.write(self.style.ERROR(f"  ✗ Rendering failed - no pages generated"))
                    error_count += 1
                    continue
                
                # Update page count
                slide.page_count = content['total_pages']
                slide.save(update_fields=['page_count'])
                
                # Store rendered content
                slide_content, _ = SlideContent.objects.get_or_create(slide=slide)
                slide_content.content_data = content
                slide_content.is_extracted = True
                slide_content.extraction_error = ''
                slide_content.extracted_at = timezone.now()
                slide_content.save()
                
                self.stdout.write(self.style.SUCCESS(f"  ✓ Successfully rendered {content['total_pages']} pages"))
                success_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error: {str(e)}"))
                error_count += 1
                import traceback
                traceback.print_exc()
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS(f"Re-rendering complete!"))
        self.stdout.write(f"  Total slides processed: {total}")
        self.stdout.write(self.style.SUCCESS(f"  Successful: {success_count}"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"  Failed: {error_count}"))
        self.stdout.write(self.style.SUCCESS(f"{'='*60}"))
