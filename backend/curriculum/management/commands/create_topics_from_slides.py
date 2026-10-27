"""
Django management command to create topics from existing slides.
Usage: python manage.py create_topics_from_slides
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify
import uuid

from curriculum.models import Slide, Topic

class Command(BaseCommand):
    help = 'Create topics from existing slides and associate them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subblock',
            type=str,
            help='Filter slides by sub-block name (e.g., "Neuroanatomy")',
        )

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📚 CREATING TOPICS FROM SLIDES"))
        self.stdout.write("="*60 + "\n")

        # Filter slides
        slides = Slide.objects.select_related('sub_block', 'block').all()
        
        if options['subblock']:
            slides = slides.filter(sub_block__name__iexact=options['subblock'])
            self.stdout.write(f"🔍 Filtering by sub-block: {options['subblock']}")
        
        slides = slides.order_by('sub_block', 'title')
        
        if not slides.exists():
            self.stdout.write(self.style.WARNING("⚠️  No slides found."))
            return

        self.stdout.write(f"📋 Found {slides.count()} slides\n")

        created = 0
        updated = 0
        skipped = 0

        for i, slide in enumerate(slides, 1):
            self.stdout.write(f"\n[{i}/{slides.count()}] {slide.title}")
            self.stdout.write("-" * 60)

            # Generate topic ID from slide title
            base_slug = slugify(slide.title)[:40]  # Limit to 40 chars
            topic_id = f"{base_slug}-{uuid.uuid4().hex[:8]}"

            try:
                # Check if slide already has a topic
                if slide.topic:
                    self.stdout.write(self.style.WARNING(f"⚠️  Slide already has topic: {slide.topic.name}"))
                    skipped += 1
                    continue

                # Create topic
                topic = Topic.objects.create(
                    id=topic_id,
                    name=slide.title,
                    description=f"Topic for {slide.title}",
                    sub_block=slide.sub_block,
                    block=slide.block,
                    order=i
                )

                self.stdout.write(self.style.SUCCESS(f"✅ Created topic: {topic.name} (ID: {topic.id})"))

                # Associate slide with topic
                slide.topic = topic
                slide.save(update_fields=['topic'])

                self.stdout.write(self.style.SUCCESS(f"  ✅ Associated slide with topic"))
                created += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
                continue

        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 SUMMARY"))
        self.stdout.write("="*60)
        self.stdout.write(f"✅ Topics created: {created}")
        self.stdout.write(f"⚠️  Skipped (already have topics): {skipped}")
        self.stdout.write(f"📊 Total slides processed: {slides.count()}")
        self.stdout.write("="*60 + "\n")
        
        self.stdout.write(self.style.SUCCESS("\n✅ All done!"))
        self.stdout.write("🌐 Visit http://localhost:3000 to see the topics.\n")
