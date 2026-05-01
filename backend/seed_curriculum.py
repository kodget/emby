"""
Seed script to populate the curriculum database with initial data.
Run this after migrations: python manage.py shell < seed_curriculum.py
"""

from curriculum.models import Subject, Block, Topic
from django.db import transaction

@transaction.atomic
def seed_curriculum():
    print("🌱 Seeding curriculum data...")
    
    # Clear existing data
    Topic.objects.all().delete()
    Block.objects.all().delete()
    Subject.objects.all().delete()
    
    # ==================== ANATOMY ====================
    anatomy = Subject.objects.create(
        id='anatomy',
        name='Anatomy',
        description='Study of the structure of the human body',
        order=1
    )
    print(f"✅ Created subject: {anatomy.name}")
    
    # Anatomy Block 1
    anat_block1 = Block.objects.create(
        id='anatomy-block-1',
        subject=anatomy,
        name='Block 1',
        description='Introduction to Upper Limb',
        order=1
    )
    
    Topic.objects.create(
        id='gross-anatomy',
        block=anat_block1,
        name='Gross Anatomy',
        description='Macroscopic anatomy of the upper limb',
        order=1
    )
    Topic.objects.create(
        id='embryology',
        block=anat_block1,
        name='Embryology',
        description='Development of the upper limb',
        order=2
    )
    Topic.objects.create(
        id='histology',
        block=anat_block1,
        name='Histology',
        description='Microscopic structure of tissues',
        order=3
    )
    print(f"✅ Created {anat_block1.name} with 3 topics")
    
    # Anatomy Block 2
    anat_block2 = Block.objects.create(
        id='anatomy-block-2',
        subject=anatomy,
        name='Block 2',
        description='Lower Limb and Thorax',
        order=2
    )
    
    Topic.objects.create(
        id='gross-anatomy-2',
        block=anat_block2,
        name='Gross Anatomy',
        description='Macroscopic anatomy of lower limb',
        order=1
    )
    Topic.objects.create(
        id='embryology-2',
        block=anat_block2,
        name='Embryology',
        description='Development of lower limb',
        order=2
    )
    Topic.objects.create(
        id='histology-2',
        block=anat_block2,
        name='Histology',
        description='Microscopic structure',
        order=3
    )
    print(f"✅ Created {anat_block2.name} with 3 topics")
    
    # Anatomy Block 3
    anat_block3 = Block.objects.create(
        id='anatomy-block-3',
        subject=anatomy,
        name='Block 3',
        description='Head, Neck and Neuroanatomy',
        order=3
    )
    
    Topic.objects.create(
        id='gross-anatomy-3',
        block=anat_block3,
        name='Gross Anatomy',
        description='Head and neck structures',
        order=1
    )
    Topic.objects.create(
        id='embryology-3',
        block=anat_block3,
        name='Embryology',
        description='Development of head and neck',
        order=2
    )
    Topic.objects.create(
        id='histology-3',
        block=anat_block3,
        name='Histology',
        description='Microscopic structure',
        order=3
    )
    print(f"✅ Created {anat_block3.name} with 3 topics")
    
    # ==================== PHYSIOLOGY ====================
    physiology = Subject.objects.create(
        id='physiology',
        name='Physiology',
        description='Study of the functions of the human body',
        order=2
    )
    print(f"✅ Created subject: {physiology.name}")
    
    # Physiology Block 1
    phys_block1 = Block.objects.create(
        id='physiology-block-1',
        subject=physiology,
        name='Block 1',
        description='General Physiology and Neurophysiology',
        order=1
    )
    
    Topic.objects.create(
        id='general-physiology',
        block=phys_block1,
        name='General Physiology',
        description='Basic physiological principles',
        order=1
    )
    Topic.objects.create(
        id='neurophysiology',
        block=phys_block1,
        name='Neurophysiology',
        description='Function of the nervous system',
        order=2
    )
    print(f"✅ Created {phys_block1.name} with 2 topics")
    
    # Physiology Block 2
    phys_block2 = Block.objects.create(
        id='physiology-block-2',
        subject=physiology,
        name='Block 2',
        description='Cardiovascular and Respiratory Physiology',
        order=2
    )
    
    Topic.objects.create(
        id='cardiovascular',
        block=phys_block2,
        name='Cardiovascular Physiology',
        description='Heart and blood vessel function',
        order=1
    )
    Topic.objects.create(
        id='respiratory',
        block=phys_block2,
        name='Respiratory Physiology',
        description='Lung function and gas exchange',
        order=2
    )
    print(f"✅ Created {phys_block2.name} with 2 topics")
    
    # Physiology Block 3
    phys_block3 = Block.objects.create(
        id='physiology-block-3',
        subject=physiology,
        name='Block 3',
        description='Renal and Gastrointestinal Physiology',
        order=3
    )
    
    Topic.objects.create(
        id='renal',
        block=phys_block3,
        name='Renal Physiology',
        description='Kidney function and fluid balance',
        order=1
    )
    Topic.objects.create(
        id='gastrointestinal',
        block=phys_block3,
        name='Gastrointestinal Physiology',
        description='Digestive system function',
        order=2
    )
    print(f"✅ Created {phys_block3.name} with 2 topics")
    
    # Physiology Block 4
    phys_block4 = Block.objects.create(
        id='physiology-block-4',
        subject=physiology,
        name='Block 4',
        description='Endocrine and Reproductive Physiology',
        order=4
    )
    
    Topic.objects.create(
        id='endocrine',
        block=phys_block4,
        name='Endocrine Physiology',
        description='Hormone function and regulation',
        order=1
    )
    Topic.objects.create(
        id='reproductive',
        block=phys_block4,
        name='Reproductive Physiology',
        description='Reproductive system function',
        order=2
    )
    print(f"✅ Created {phys_block4.name} with 2 topics")
    
    # ==================== BIOCHEMISTRY ====================
    biochemistry = Subject.objects.create(
        id='biochemistry',
        name='Medical Biochemistry',
        description='Study of chemical processes in living organisms',
        order=3
    )
    print(f"✅ Created subject: {biochemistry.name}")
    
    # Biochemistry Block 1 (no topics - slides attach directly to blocks)
    Block.objects.create(
        id='biochemistry-block-1',
        subject=biochemistry,
        name='Block 1',
        description='Biomolecules and Metabolism',
        order=1
    )
    print(f"✅ Created Biochemistry Block 1 (no topics)")
    
    # Biochemistry Block 2
    Block.objects.create(
        id='biochemistry-block-2',
        subject=biochemistry,
        name='Block 2',
        description='Molecular Biology and Genetics',
        order=2
    )
    print(f"✅ Created Biochemistry Block 2 (no topics)")
    
    # Biochemistry Block 3
    Block.objects.create(
        id='biochemistry-block-3',
        subject=biochemistry,
        name='Block 3',
        description='Clinical Biochemistry',
        order=3
    )
    print(f"✅ Created Biochemistry Block 3 (no topics)")
    
    print("\n✨ Curriculum seeding complete!")
    print(f"📊 Summary:")
    print(f"   - Subjects: {Subject.objects.count()}")
    print(f"   - Blocks: {Block.objects.count()}")
    print(f"   - Topics: {Topic.objects.count()}")

if __name__ == '__main__':
    seed_curriculum()
