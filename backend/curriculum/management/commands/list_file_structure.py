"""
Management command to list all subjects, blocks, sub-blocks, and topics with their IDs.
Usage: python manage.py list_file_structure
"""

from django.core.management.base import BaseCommand
from curriculum.models import Subject, Block, Topic, Section


class Command(BaseCommand):
    help = 'List all subjects, blocks, sub-blocks, and topics with their IDs'

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
            self.stdout.write(f"\nSUBJECT: {subject.name} (ID: {subject.id})")
            
            blocks = Block.objects.filter(subject=subject).order_by('order')
            
            if not blocks.exists():
                self.stdout.write(self.style.WARNING(f"  No blocks found for {subject.name}"))
                continue
            
            for block in blocks:
                self.stdout.write(f"\n  BLOCK: {block.name}")
                self.stdout.write(f"     ID: {block.id}")
                self.stdout.write(f"     Order: {block.order}")
                
                # Get sub-blocks (topics in DB) for this block
                sub_blocks = Topic.objects.filter(block=block).order_by('order')
                if sub_blocks.exists():
                    self.stdout.write(f"     Sub-blocks:")
                    for sub_block in sub_blocks:
                        self.stdout.write(f"       - {sub_block.name} (ID: {sub_block.id})")
                        
                        # Get topics (sections in DB) for this sub-block
                        topics = Section.objects.filter(topic=sub_block).order_by('order')
                        if topics.exists():
                            self.stdout.write(f"          Topics:")
                            for topic in topics:
                                self.stdout.write(f"            * {topic.name} (ID: {topic.id})")
                
                # Get topics (sections in DB) directly under block (no sub-block)
                direct_topics = Section.objects.filter(block=block, topic__isnull=True).order_by('order')
                if direct_topics.exists():
                    self.stdout.write(f"     Topics (directly under block):")
                    for topic in direct_topics:
                        self.stdout.write(f"       * {topic.name} (ID: {topic.id})")
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
        self.stdout.write(self.style.SUCCESS('='*70))
