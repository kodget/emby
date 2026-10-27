"""
Django management command to upload anatomy slides directly to the database.
Usage: python manage.py upload_anatomy_slides
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from pathlib import Path
import os

from curriculum.models import Subject, Block, SubBlock, Slide, Topic
from curriculum.tasks import process_slide_task

User = get_user_model()

ANATOMY_FOLDER = Path(r"c:\Users\USER\emby\anatomy")

class Command(BaseCommand):
    help = 'Upload anatomy slides from the anatomy folder'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🧠 UPLOADING NEUROANATOMY SLIDES"))
        self.stdout.write("="*60 + "\n")

        # Get or create a staff user for ownership
        user = User.objects.filter(is_staff=True).first()
        if not user:
            user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()
        
        if not user:
            self.stdout.write(self.style.ERROR("❌ No user found. Please create a user first."))
            return
        
        self.stdout.write(f"👤 Using user: {user.email or user.username}")
        
        # Get or create an active class group
        from accounts.models import ClassGroup
        class_group = ClassGroup.objects.filter(is_active=True).first()
        if not class_group:
            self.stdout.write(self.style.ERROR("❌ No active class group found. Please create one first."))
            return
        
        self.stdout.write(f"👥 Using class group: {class_group}")

        # Setup structure
        self.stdout.write("\n📋 Setting up course structure...")
        
        subject, created = Subject.objects.get_or_create(
            name="Anatomy",
            defaults={"description": "Human Anatomy", "created_by": user}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Created subject: {subject.name}"))
        else:
            self.stdout.write(f"✅ Using existing subject: {subject.name}")

        # Use EXISTING block structure (the one with proper IDs)
        block = Block.objects.filter(id='first-block').first()
        if not block:
            self.stdout.write(self.style.ERROR("❌ Block 'first-block' not found!"))
            return
        self.stdout.write(f"✅ Using existing block: {block.name} (ID: {block.id})")

        subblock = SubBlock.objects.filter(id='neuroanatomy', block=block).first()
        if not subblock:
            self.stdout.write(self.style.ERROR("❌ Sub-block 'neuroanatomy' not found!"))
            return
        self.stdout.write(f"✅ Using existing sub-block: {subblock.name} (ID: {subblock.id})")

        # Get slides from folder
        neuro_folder = ANATOMY_FOLDER / "Third block" / "Neuro"
        
        if not neuro_folder.exists():
            self.stdout.write(self.style.ERROR(f"❌ Folder not found: {neuro_folder}"))
            return

        # Find all PDF and PPTX files
        slide_files = []
        for ext in ['*.pdf', '*.pptx']:
            slide_files.extend(neuro_folder.glob(ext))
        
        # Filter out unwanted files
        slide_files = [
            f for f in slide_files 
            if not f.name.startswith('.') and not f.name.endswith('.docx.pdf')
        ]
        
        self.stdout.write(f"\n📚 Found {len(slide_files)} slides to upload\n")

        successful = 0
        failed = 0
        skipped = 0

        for i, slide_path in enumerate(slide_files, 1):
            # Clean up title
            title = slide_path.stem
            title = title.replace('_', ' ').replace('  ', ' ').strip()
            
            self.stdout.write(f"\n[{i}/{len(slide_files)}] {title}")
            self.stdout.write("-" * 60)

            # Check if slide already exists
            existing = Slide.objects.filter(
                sub_block=subblock,
                title=title
            ).first()

            if existing:
                self.stdout.write(self.style.WARNING(f"⚠️  Slide already exists (ID: {existing.id}). Skipping..."))
                skipped += 1
                continue

            try:
                # Check file size (skip if over 10MB for Cloudinary limit)
                file_size = slide_path.stat().st_size
                if file_size > 10 * 1024 * 1024:  # 10MB
                    self.stdout.write(self.style.WARNING(f"⚠️  File too large ({file_size / 1024 / 1024:.1f}MB). Skipping..."))
                    skipped += 1
                    continue
                
                # Generate unique IDs
                import uuid
                from django.utils.text import slugify
                slide_id = f"slide_{uuid.uuid4().hex[:12]}"
                
                # Create topic for this slide
                base_slug = slugify(title)[:40]
                topic_id = f"{base_slug}-{uuid.uuid4().hex[:8]}"
                
                topic = Topic.objects.create(
                    id=topic_id,
                    name=title,
                    description=f"Topic for {title}",
                    sub_block=subblock,
                    order=i
                )
                self.stdout.write(f"  ✅ Created topic: {topic.name}")
                
                # Read the file
                with open(slide_path, 'rb') as f:
                    from django.core.files import File
                    from django.core.files.uploadedfile import SimpleUploadedFile
                    
                    file_content = f.read()
                    file_name = slide_path.name
                    file_type = 'pptx' if slide_path.suffix == '.pptx' else 'pdf'
                    
                    uploaded_file = SimpleUploadedFile(
                        name=file_name,
                        content=file_content,
                        content_type='application/pdf' if file_type == 'pdf' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    )
                
                # Create slide record with file
                slide = Slide.objects.create(
                    id=slide_id,
                    title=title,
                    sub_block=subblock,
                    topic=topic,
                    file=uploaded_file,
                    file_type=file_type,
                    uploaded_by=user,
                    class_group=class_group,
                    generation_status='pending'
                )

                self.stdout.write(self.style.SUCCESS(f"✅ Created slide record (ID: {slide.id})"))

                # Trigger async processing
                self.stdout.write("  📤 Queuing for processing...")
                process_slide_task.delay(slide.id)
                
                self.stdout.write(self.style.SUCCESS(f"  ✅ Queued for processing!"))
                successful += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
                failed += 1

        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 UPLOAD SUMMARY"))
        self.stdout.write("="*60)
        self.stdout.write(f"✅ Successful: {successful}")
        self.stdout.write(f"⚠️  Skipped (already exist): {skipped}")
        self.stdout.write(f"❌ Failed: {failed}")
        self.stdout.write(f"📊 Total: {len(slide_files)}")
        self.stdout.write("="*60 + "\n")
        
        self.stdout.write(self.style.SUCCESS("\n✅ All done! Check your Celery worker logs to see processing status."))
        self.stdout.write("🌐 Visit http://localhost:3000 to view the uploaded slides.\n")
