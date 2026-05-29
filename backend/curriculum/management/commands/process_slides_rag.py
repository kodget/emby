"""
Management command to process slides for RAG system
Chunks PDFs and generates embeddings
"""

from django.core.management.base import BaseCommand
from curriculum.models import Slide
from curriculum.rag_service import rag_service


class Command(BaseCommand):
    help = 'Process slides for RAG system (chunking and embeddings)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slide-id',
            type=str,
            help='Process a specific slide by ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all slides',
        )
        parser.add_argument(
            '--reprocess',
            action='store_true',
            help='Reprocess slides even if already processed',
        )

    def handle(self, *args, **options):
        slide_id = options.get('slide_id')
        process_all = options.get('all')
        reprocess = options.get('reprocess')

        if slide_id:
            # Process specific slide
            try:
                slide = Slide.objects.get(id=slide_id)
                self.stdout.write(f"Processing slide: {slide.title}")
                
                if reprocess:
                    # Delete existing processing status to force reprocess
                    slide.processing_status.delete() if hasattr(slide, 'processing_status') else None
                
                success = rag_service.process_slide(slide)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f"✓ Successfully processed {slide.title}"))
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Failed to process {slide.title}"))
                    
            except Slide.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Slide with ID '{slide_id}' not found"))
                
        elif process_all:
            # Process all slides
            slides = Slide.objects.all()
            total = slides.count()
            
            self.stdout.write(f"Processing {total} slides...")
            
            success_count = 0
            failed_count = 0
            skipped_count = 0
            
            for i, slide in enumerate(slides, 1):
                self.stdout.write(f"[{i}/{total}] Processing: {slide.title}")
                
                # Skip if already processed and not reprocessing
                if not reprocess and hasattr(slide, 'processing_status') and slide.processing_status.is_embedded:
                    self.stdout.write(self.style.WARNING(f"  ⊘ Skipped (already processed)"))
                    skipped_count += 1
                    continue
                
                if reprocess and hasattr(slide, 'processing_status'):
                    slide.processing_status.delete()
                
                success = rag_service.process_slide(slide)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Success"))
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR(f"  ✗ Failed"))
                    failed_count += 1
            
            self.stdout.write("\n" + "="*50)
            self.stdout.write(self.style.SUCCESS(f"✓ Processed: {success_count}"))
            self.stdout.write(self.style.WARNING(f"⊘ Skipped: {skipped_count}"))
            self.stdout.write(self.style.ERROR(f"✗ Failed: {failed_count}"))
            self.stdout.write("="*50)
            
        else:
            self.stdout.write(self.style.ERROR("Please specify --slide-id or --all"))
