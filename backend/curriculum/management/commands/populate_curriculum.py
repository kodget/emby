from django.core.management.base import BaseCommand
from curriculum.models import Subject, Block, Topic, Section


class Command(BaseCommand):
    help = 'Populate curriculum structure with Anatomy, Physiology, and Medical Biochemistry'

    def handle(self, *args, **kwargs):
        self.stdout.write('Populating curriculum structure...')
        
        # Clear existing data
        Section.objects.all().delete()
        Topic.objects.all().delete()
        Block.objects.all().delete()
        Subject.objects.all().delete()
        
        # Create Anatomy
        anatomy = Subject.objects.create(
            id='anatomy',
            name='Anatomy',
            description='Study of body structure',
            order=1
        )
        
        # Gross Anatomy Blocks with Sections
        gross_anatomy_blocks = [
            {
                'id': 'gross-anatomy-block-1',
                'name': 'Gross Anatomy Block 1',
                'order': 1,
                'sections': [
                    {'id': 'upper-limb', 'name': 'Upper Limb', 'order': 1},
                    {'id': 'lower-limb', 'name': 'Lower Limb', 'order': 2},
                ]
            },
            {
                'id': 'gross-anatomy-block-2',
                'name': 'Gross Anatomy Block 2',
                'order': 2,
                'sections': [
                    {'id': 'thorax', 'name': 'Thorax', 'order': 1},
                    {'id': 'abdomen', 'name': 'Abdomen', 'order': 2},
                    {'id': 'pelvis', 'name': 'Pelvis', 'order': 3},
                    {'id': 'perineum', 'name': 'Perineum', 'order': 4},
                ]
            },
            {
                'id': 'gross-anatomy-block-3',
                'name': 'Gross Anatomy Block 3',
                'order': 3,
                'sections': [
                    {'id': 'head-neck', 'name': 'Head and Neck', 'order': 1},
                    {'id': 'neuroanatomy', 'name': 'Neuroanatomy', 'order': 2},
                ]
            },
        ]
        
        for block_data in gross_anatomy_blocks:
            block = Block.objects.create(
                id=block_data['id'],
                subject=anatomy,
                name=block_data['name'],
                order=block_data['order']
            )
            
            for section_data in block_data['sections']:
                Section.objects.create(
                    id=section_data['id'],
                    block=block,
                    name=section_data['name'],
                    order=section_data['order']
                )
        
        # Histology Blocks
        histology_blocks = [
            {'id': 'histology-block-1', 'name': 'Histology Block 1', 'order': 4},
            {'id': 'histology-block-2', 'name': 'Histology Block 2', 'order': 5},
            {'id': 'histology-block-3', 'name': 'Histology Block 3', 'order': 6},
        ]
        
        for block_data in histology_blocks:
            Block.objects.create(
                id=block_data['id'],
                subject=anatomy,
                name=block_data['name'],
                order=block_data['order']
            )
        
        # Embryology Blocks
        embryology_blocks = [
            {'id': 'embryology-block-1', 'name': 'Embryology Block 1', 'order': 7},
            {'id': 'embryology-block-2', 'name': 'Embryology Block 2', 'order': 8},
            {'id': 'embryology-block-3', 'name': 'Embryology Block 3', 'order': 9},
        ]
        
        for block_data in embryology_blocks:
            Block.objects.create(
                id=block_data['id'],
                subject=anatomy,
                name=block_data['name'],
                order=block_data['order']
            )
        
        # Create Physiology
        physiology = Subject.objects.create(
            id='physiology',
            name='Physiology',
            description='Study of body function',
            order=2
        )
        
        # Physiology Blocks with Sections
        physiology_blocks = [
            {
                'id': 'physiology-block-1',
                'name': 'Physiology Block 1',
                'order': 1,
                'sections': [
                    {'id': 'general-physiology', 'name': 'General Physiology', 'order': 1},
                    {'id': 'autonomic-nervous-system', 'name': 'Autonomic Nervous System', 'order': 2},
                    {'id': 'blood-body-fluids', 'name': 'Blood and Body Fluids', 'order': 3},
                    {'id': 'neuromuscular-physiology', 'name': 'Neuromuscular Physiology', 'order': 4},
                ]
            },
            {
                'id': 'physiology-block-2',
                'name': 'Physiology Block 2',
                'order': 2,
                'sections': [
                    {'id': 'respiratory-physiology', 'name': 'Respiratory Physiology', 'order': 1},
                    {'id': 'cardiovascular-physiology', 'name': 'Cardiovascular Physiology', 'order': 2},
                    {'id': 'git-physiology', 'name': 'Physiology of the Gastrointestinal Tract (GIT)', 'order': 3},
                    {'id': 'nutrient-metabolism', 'name': 'Nutrient Metabolism', 'order': 4},
                ]
            },
            {
                'id': 'physiology-block-3',
                'name': 'Physiology Block 3',
                'order': 3,
                'sections': [
                    {'id': 'renal-physiology', 'name': 'Renal Physiology', 'order': 1},
                    {'id': 'endocrinology', 'name': 'Endocrinology', 'order': 2},
                    {'id': 'reproductive-physiology', 'name': 'Reproductive Physiology', 'order': 3},
                ]
            },
            {
                'id': 'physiology-block-4',
                'name': 'Physiology Block 4',
                'order': 4,
                'sections': [
                    {'id': 'sensory-system', 'name': 'Sensory System', 'order': 1},
                    {'id': 'special-senses', 'name': 'Special Senses', 'order': 2},
                    {'id': 'motor-system', 'name': 'Motor System', 'order': 3},
                    {'id': 'integrative-functions', 'name': 'Integrative Functions', 'order': 4},
                ]
            },
        ]
        
        for block_data in physiology_blocks:
            block = Block.objects.create(
                id=block_data['id'],
                subject=physiology,
                name=block_data['name'],
                order=block_data['order']
            )
            
            for section_data in block_data['sections']:
                Section.objects.create(
                    id=section_data['id'],
                    block=block,
                    name=section_data['name'],
                    order=section_data['order']
                )
        
        # Create Medical Biochemistry
        biochemistry = Subject.objects.create(
            id='medical-biochemistry',
            name='Medical Biochemistry',
            description='Study of chemical processes in living organisms',
            order=3
        )
        
        # Biochemistry Blocks
        biochemistry_blocks = [
            {'id': 'biochemistry-block-1', 'name': 'Medical Biochemistry Block 1', 'description': 'Chemistry of the classes of food', 'order': 1},
            {'id': 'biochemistry-block-2', 'name': 'Medical Biochemistry Block 2', 'description': 'Biochemistry of the classes of food', 'order': 2},
            {'id': 'biochemistry-block-3', 'name': 'Medical Biochemistry Block 3', 'description': 'Advanced topics', 'order': 3},
        ]
        
        for block_data in biochemistry_blocks:
            Block.objects.create(
                id=block_data['id'],
                subject=biochemistry,
                name=block_data['name'],
                description=block_data.get('description', ''),
                order=block_data['order']
            )
        
        self.stdout.write(self.style.SUCCESS('Successfully populated curriculum structure!'))
        self.stdout.write(f'Created: 3 subjects, {Block.objects.count()} blocks, {Topic.objects.count()} topics, {Section.objects.count()} sections')
