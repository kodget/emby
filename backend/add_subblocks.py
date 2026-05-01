"""
Add sub-blocks (topics) to specific blocks
Run with: python manage.py shell < add_subblocks.py
"""

from curriculum.models import Block, Topic

# Clear existing topics first
print("Clearing existing topics...")
Topic.objects.all().delete()

print("\nAdding sub-blocks to specific blocks...")

# Define sub-blocks for each block
subblocks_map = {
    'physiology-block-1': [
        ('General Physiology', 1),
        ('Autonomic Nervous System', 2),
        ('Blood and Body Fluids', 3),
        ('Nerve and Muscle Physiology', 4),
    ],
    'physiology-block-2': [
        ('Respiratory Physiology', 1),
        ('GIT', 2),
        ('Cardiovascular Physiology', 3),
        ('Nutrient Metabolism', 4),
    ],
    'physiology-block-3': [
        ('Renal Physiology', 1),
        ('Endocrinology', 2),
        ('Reproductive Physiology', 3),
    ],
    'physiology-block-4': [
        ('Sensory Systems', 1),
        ('Special Senses', 2),
        ('Motor System', 3),
        ('Integration Centres', 4),
    ],
    'gross-anatomy-block-1': [
        ('Upper Limb', 1),
        ('Lower Limb', 2),
    ],
    'gross-anatomy-block-2': [
        ('Thorax', 1),
        ('Abdomen', 2),
        ('Pelvis', 3),
        ('Perineum', 4),
    ],
    'gross-anatomy-block-3': [
        ('Head and Neck', 1),
        ('Neuroanatomy', 2),
    ],
}

# Create topics for each block
for block_id, topics_list in subblocks_map.items():
    try:
        block = Block.objects.get(id=block_id)
        print(f"\n{block.name} ({block_id}):")
        
        for topic_name, order in topics_list:
            topic_id = f"{block_id}-{topic_name.lower().replace(' ', '-').replace('&', 'and')}"
            Topic.objects.create(
                id=topic_id,
                block=block,
                name=topic_name,
                description=f"{topic_name} sub-block",
                order=order
            )
            print(f"  ✓ {topic_name}")
    except Block.DoesNotExist:
        print(f"\n⚠ Block '{block_id}' not found, skipping")

print("\n" + "="*60)
print("SUB-BLOCKS ADDED SUCCESSFULLY!")
print("="*60)
print(f"\nTotal sub-blocks (topics): {Topic.objects.count()}")

# Show summary by block
print("\nSummary:")
for block_id in subblocks_map.keys():
    try:
        block = Block.objects.get(id=block_id)
        count = Topic.objects.filter(block=block).count()
        print(f"  {block.name}: {count} sub-blocks")
    except Block.DoesNotExist:
        pass
