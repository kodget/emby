"""
Populate curriculum with Anatomy, Physiology, and Biochemistry courses
Run with: python manage.py shell < populate_curriculum.py
"""

from curriculum.models import Subject, Block, Topic

# Clear existing data
print("Clearing existing curriculum...")
Topic.objects.all().delete()
Block.objects.all().delete()
Subject.objects.all().delete()

# Create Subjects
print("\nCreating subjects...")
anatomy = Subject.objects.create(
    id='anatomy',
    name='Anatomy',
    description='Study of body structure',
    order=1
)
print(f"✓ Created: {anatomy.name}")

physiology = Subject.objects.create(
    id='physiology',
    name='Physiology',
    description='Study of body function',
    order=2
)
print(f"✓ Created: {physiology.name}")

biochemistry = Subject.objects.create(
    id='biochemistry',
    name='Medical Biochemistry',
    description='Study of chemical processes in living organisms',
    order=3
)
print(f"✓ Created: {biochemistry.name}")

# ==================== ANATOMY ====================
print("\n\nCreating Anatomy blocks and topics...")

# Anatomy Block 1 - Embryology
anat_b1 = Block.objects.create(
    id='anatomy-block-1',
    subject=anatomy,
    name='First Block - Embryology',
    description='Embryology and early development',
    order=1
)
print(f"✓ {anat_b1.name}")

Topic.objects.create(id='anatomy-block-1-intro-embryology', block=anat_b1, name='Introduction to Embryology', order=1)
Topic.objects.create(id='anatomy-block-1-gametogenesis', block=anat_b1, name='Gametogenesis', order=2)
Topic.objects.create(id='anatomy-block-1-fertilization', block=anat_b1, name='Fertilization', order=3)
Topic.objects.create(id='anatomy-block-1-week1-2', block=anat_b1, name='Week 1-2 Development', order=4)
Topic.objects.create(id='anatomy-block-1-week3', block=anat_b1, name='Week 3 - Gastrulation', order=5)

# Anatomy Block 2 - Gross Anatomy
anat_b2 = Block.objects.create(
    id='anatomy-block-2',
    subject=anatomy,
    name='Second Block - Gross Anatomy',
    description='Macroscopic anatomy of body systems',
    order=2
)
print(f"✓ {anat_b2.name}")

Topic.objects.create(id='anatomy-block-2-upper-limb', block=anat_b2, name='Upper Limb', order=1)
Topic.objects.create(id='anatomy-block-2-lower-limb', block=anat_b2, name='Lower Limb', order=2)
Topic.objects.create(id='anatomy-block-2-thorax', block=anat_b2, name='Thorax', order=3)
Topic.objects.create(id='anatomy-block-2-abdomen', block=anat_b2, name='Abdomen', order=4)

# Anatomy Block 3 - Histology
anat_b3 = Block.objects.create(
    id='anatomy-block-3',
    subject=anatomy,
    name='Third Block - Histology',
    description='Microscopic anatomy and tissue structure',
    order=3
)
print(f"✓ {anat_b3.name}")

Topic.objects.create(id='anatomy-block-3-epithelial', block=anat_b3, name='Epithelial Tissue', order=1)
Topic.objects.create(id='anatomy-block-3-connective', block=anat_b3, name='Connective Tissue', order=2)
Topic.objects.create(id='anatomy-block-3-muscle', block=anat_b3, name='Muscle Tissue', order=3)
Topic.objects.create(id='anatomy-block-3-nervous', block=anat_b3, name='Nervous Tissue', order=4)

# ==================== PHYSIOLOGY ====================
print("\n\nCreating Physiology blocks and topics...")

# Physiology Block 1
phys_b1 = Block.objects.create(
    id='physiology-block-1',
    subject=physiology,
    name='First Block',
    description='Introduction to physiology and basic systems',
    order=1
)
print(f"✓ {phys_b1.name}")

Topic.objects.create(id='physiology-block-1-intro', block=phys_b1, name='Introduction to Physiology', order=1)
Topic.objects.create(id='physiology-block-1-cell', block=phys_b1, name='Cell Physiology', order=2)
Topic.objects.create(id='physiology-block-1-membrane', block=phys_b1, name='Membrane Potential', order=3)
Topic.objects.create(id='physiology-block-1-nerve', block=phys_b1, name='Nerve Physiology', order=4)

# Physiology Block 2
phys_b2 = Block.objects.create(
    id='physiology-block-2',
    subject=physiology,
    name='Second Block',
    description='Cardiovascular and respiratory systems',
    order=2
)
print(f"✓ {phys_b2.name}")

Topic.objects.create(id='physiology-block-2-heart', block=phys_b2, name='Cardiac Physiology', order=1)
Topic.objects.create(id='physiology-block-2-circulation', block=phys_b2, name='Circulation', order=2)
Topic.objects.create(id='physiology-block-2-blood', block=phys_b2, name='Blood Physiology', order=3)
Topic.objects.create(id='physiology-block-2-respiratory', block=phys_b2, name='Respiratory System', order=4)

# Physiology Block 3
phys_b3 = Block.objects.create(
    id='physiology-block-3',
    subject=physiology,
    name='Third Block',
    description='Renal, digestive, and endocrine systems',
    order=3
)
print(f"✓ {phys_b3.name}")

Topic.objects.create(id='physiology-block-3-renal', block=phys_b3, name='Renal Physiology', order=1)
Topic.objects.create(id='physiology-block-3-digestive', block=phys_b3, name='Digestive System', order=2)
Topic.objects.create(id='physiology-block-3-endocrine', block=phys_b3, name='Endocrine System', order=3)
Topic.objects.create(id='physiology-block-3-reproductive', block=phys_b3, name='Reproductive Physiology', order=4)

# ==================== BIOCHEMISTRY ====================
print("\n\nCreating Biochemistry blocks...")

# Biochemistry Block 1
bio_b1 = Block.objects.create(
    id='biochemistry-block-1',
    subject=biochemistry,
    name='First Block - Basic Biochemistry',
    description='Introduction to biochemistry and biomolecules',
    order=1
)
print(f"✓ {bio_b1.name}")

# Biochemistry Block 2
bio_b2 = Block.objects.create(
    id='biochemistry-block-2',
    subject=biochemistry,
    name='Second Block - Metabolism',
    description='Metabolic pathways and energy production',
    order=2
)
print(f"✓ {bio_b2.name}")

# Biochemistry Block 3
bio_b3 = Block.objects.create(
    id='biochemistry-block-3',
    subject=biochemistry,
    name='Third Block - Molecular Biology',
    description='DNA, RNA, and protein synthesis',
    order=3
)
print(f"✓ {bio_b3.name}")

# Summary
print("\n" + "="*50)
print("CURRICULUM CREATED SUCCESSFULLY!")
print("="*50)
print(f"\nSubjects: {Subject.objects.count()}")
print(f"Blocks: {Block.objects.count()}")
print(f"Topics: {Topic.objects.count()}")
print("\n✅ All courses are now available in the app!")
