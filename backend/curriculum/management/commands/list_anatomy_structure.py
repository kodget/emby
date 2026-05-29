"""
Management command to list all blocks and sections with their IDs.
This helps identify what needs to be renamed.
Usage: python manage.py list_anatomy_structure
"""

from django.core.management.base import BaseCommand
from curriculum.models import Subject, Block, Topic, Section


class Command(BaseCommand):
    help = 'List all blocks, topics, and sections with their IDs'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('CURRICULUM STRUCTURE'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        # Get all subjects
        subjects = Subject.objects.all().order_by('order')
        
        if not subjects.exists():
            self.stdout.write(self.style.WARNING("No subjects found"))
            return
        
        for subject in subjects:
            self.stdout.write(f"\n📚 SUBJECT: {subject.name} (ID: {subject.id})")
            
            blocks = Block.objects.filter(subject=subject).order_by('order')
            
            if not blocks.exists():
                self.stdout.write(self.style.WARNING(f"  No blocks found for {subject.name}"))
                continue
            
            for block in blocks:
                self.stdout.write(f"\n  📦 BLOCK: {block.name}")
                self.stdout.write(f"     ID: {block.id}")
                self.stdout.write(f"     Order: {block.order}")
                
                # Get topics for this block
                topics = Topic.objects.filter(block=block).order_by('order')
                if topics.exists():
                    self.stdout.write(f"     Topics:")
                    for topic in topics:
                        self.stdout.write(f"       📑 {topic.name} (ID: {topic.id})")
                        
                        # Get sections for this topic
                        topic_sections = Section.objects.filter(topic=topic).order_by('order')
                        if topic_sections.exists():
                            self.stdout.write(f"          Sections:")
                            for section in topic_sections:
                                self.stdout.write(f"            📄 {section.name} (ID: {section.id})")
                
                # Get sections directly under block (no topic)
                block_sections = Section.objects.filter(block=block, topic__isnull=True).order_by('order')
                if block_sections.exists():
                    self.stdout.write(f"     Sections (directly under block):")
                    for section in block_sections:
                        self.stdout.write(f"       📄 {section.name} (ID: {section.id})")
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
        self.stdout.write(self.style.SUCCESS("Use these IDs to update the rename_anatomy_blocks.py command"))
        self.stdout.write(self.style.SUCCESS('='*70))
