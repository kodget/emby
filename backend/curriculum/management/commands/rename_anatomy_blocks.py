"""
Management command to rename anatomy and physiology blocks and sections.
Usage: python manage.py rename_anatomy_blocks
"""

from django.core.management.base import BaseCommand
from curriculum.models import Block, Section


class Command(BaseCommand):
    help = 'Rename anatomy and physiology blocks and sections to new names'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting blocks and sections renaming...'))
        
        updates = []
        errors = []
        
        # Block renamings
        block_renames = {
            # Anatomy Blocks
            'anatomy-block-1': 'Upper and Lower Limb',
            'anatomy-block-2': 'TAPP',
            'anatomy-block-3': 'Head and Neck and Neuroanatomy',
            
            # Physiology Blocks
            'physiology-block-1': 'Physiology Block 1',
            'physiology-block-2': 'Physiology Block 2',
            'physiology-block-3': 'Physiology Block 3',
            'physiology-block-4': 'Physiology Block 4',
        }
        
        # Section renamings
        section_renames = {
            # ===== ANATOMY SECTIONS =====
            
            # Anatomy Block 1 sections
            'anatomy-block-1-subblock-1': 'Upper Limb',
            'upper-limb': 'Upper Limb',
            'anatomy-block-1-subblock-2': 'Lower Limb',
            'lower-limb': 'Lower Limb',
            
            # Anatomy Block 2 sections
            'anatomy-block-2-subblock-1': 'Thorax',
            'thorax': 'Thorax',
            'anatomy-block-2-subblock-2': 'Abdomen',
            'abdomen': 'Abdomen',
            'anatomy-block-2-subblock-3': 'Pelvis',
            'pelvis': 'Pelvis',
            'anatomy-block-2-subblock-4': 'Perineum',
            'perineum': 'Perineum',
            
            # Anatomy Block 3 sections
            'anatomy-block-3-subblock-1': 'Head and Neck',
            'head-and-neck': 'Head and Neck',
            'anatomy-block-3-subblock-2': 'Neuroanatomy',
            'neuroanatomy': 'Neuroanatomy',
            
            # ===== PHYSIOLOGY SECTIONS =====
            
            # Physiology Block 1 sections
            'physiology-block-1-subblock-1': 'General Physiology',
            'general-physiology': 'General Physiology',
            'physiology-block-1-subblock-2': 'Autoregulation',
            'autoregulation': 'Autoregulation',
            'physiology-block-1-subblock-3': 'Blood and Body Fluids',
            'blood-and-body-fluids': 'Blood and Body Fluids',
            'physiology-block-1-subblock-4': 'Neuromuscular Physiology',
            'neuromuscular-physiology': 'Neuromuscular Physiology',
            
            # Physiology Block 2 sections
            'physiology-block-2-subblock-1': 'Respiratory Physiology',
            'respiratory-physiology': 'Respiratory Physiology',
            'physiology-block-2-subblock-2': 'Cardiovascular Physiology',
            'cardiovascular-physiology': 'Cardiovascular Physiology',
            'physiology-block-2-subblock-3': 'Gastrointestinal Physiology',
            'gastrointestinal-physiology': 'Gastrointestinal Physiology',
            'physiology-block-2-subblock-4': 'Nutrient Metabolism',
            'nutrient-metabolism': 'Nutrient Metabolism',
            
            # Physiology Block 3 sections
            'physiology-block-3-subblock-1': 'Renal Physiology',
            'renal-physiology': 'Renal Physiology',
            'physiology-block-3-subblock-2': 'Endocrinology',
            'endocrinology': 'Endocrinology',
            'physiology-block-3-subblock-3': 'Reproductive Physiology',
            'reproductive-physiology': 'Reproductive Physiology',
            
            # Physiology Block 4 sections
            'physiology-block-4-subblock-1': 'Sensory System',
            'sensory-system': 'Sensory System',
            'physiology-block-4-subblock-2': 'Special Senses',
            'special-senses': 'Special Senses',
            'physiology-block-4-subblock-3': 'Motor System',
            'motor-system': 'Motor System',
            'physiology-block-4-subblock-4': 'Integrating Centre',
            'integrating-centre': 'Integrating Centre',
        }
        
        # Update blocks
        self.stdout.write('\n=== Updating Blocks ===')
        for block_id, new_name in block_renames.items():
            try:
                block = Block.objects.get(id=block_id)
                old_name = block.name
                block.name = new_name
                block.save()
                updates.append(f"Block: '{old_name}' → '{new_name}' (ID: {block_id})")
                self.stdout.write(self.style.SUCCESS(f"✓ Updated block: {block_id} → {new_name}"))
            except Block.DoesNotExist:
                errors.append(f"Block not found: {block_id}")
                self.stdout.write(self.style.WARNING(f"✗ Block not found: {block_id}"))
        
        # Update sections
        self.stdout.write('\n=== Updating Sections ===')
        for section_id, new_name in section_renames.items():
            try:
                section = Section.objects.get(id=section_id)
                old_name = section.name
                section.name = new_name
                section.save()
                updates.append(f"Section: '{old_name}' → '{new_name}' (ID: {section_id})")
                self.stdout.write(self.style.SUCCESS(f"✓ Updated section: {section_id} → {new_name}"))
            except Section.DoesNotExist:
                # Not an error, just means this ID doesn't exist
                self.stdout.write(self.style.WARNING(f"  Section not found: {section_id} (may not exist)"))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS(f"Renaming complete!"))
        self.stdout.write(f"  Total updates: {len(updates)}")
        if errors:
            self.stdout.write(self.style.ERROR(f"  Errors: {len(errors)}"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"    - {error}"))
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS("Changes applied:"))
        for update in updates:
            self.stdout.write(f"  • {update}")
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS("✓ All done! Refresh your browser to see the changes."))
