import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Block, Topic

# Gross Anatomy Block 3 sub-blocks
gross_block_3_topics = [
    {'id': 'gross-block-3-head-neck', 'name': 'Head and Neck', 'order': 1},
    {'id': 'gross-block-3-neuroanatomy', 'name': 'Neuroanatomy', 'order': 2},
]

# Physiology Block 1 sub-blocks
physiology_block_1_topics = [
    {'id': 'physiology-block-1-sub-1', 'name': 'Physiology Block 1 Sub-block 1', 'order': 1},
    {'id': 'physiology-block-1-sub-2', 'name': 'Physiology Block 1 Sub-block 2', 'order': 2},
    {'id': 'physiology-block-1-sub-3', 'name': 'Physiology Block 1 Sub-block 3', 'order': 3},
    {'id': 'physiology-block-1-sub-4', 'name': 'Physiology Block 1 Sub-block 4', 'order': 4},
]

# Physiology Block 2 sub-blocks
physiology_block_2_topics = [
    {'id': 'physiology-block-2-sub-1', 'name': 'Physiology Block 2 Sub-block 1', 'order': 1},
    {'id': 'physiology-block-2-sub-2', 'name': 'Physiology Block 2 Sub-block 2', 'order': 2},
    {'id': 'physiology-block-2-sub-3', 'name': 'Physiology Block 2 Sub-block 3', 'order': 3},
    {'id': 'physiology-block-2-sub-4', 'name': 'Physiology Block 2 Sub-block 4', 'order': 4},
]

# Physiology Block 3 sub-blocks
physiology_block_3_topics = [
    {'id': 'physiology-block-3-sub-1', 'name': 'Physiology Block 3 Sub-block 1', 'order': 1},
    {'id': 'physiology-block-3-sub-2', 'name': 'Physiology Block 3 Sub-block 2', 'order': 2},
    {'id': 'physiology-block-3-sub-3', 'name': 'Physiology Block 3 Sub-block 3', 'order': 3},
]

# Physiology Block 4 sub-blocks
physiology_block_4_topics = [
    {'id': 'physiology-block-4-sub-1', 'name': 'Physiology Block 4 Sub-block 1', 'order': 1},
    {'id': 'physiology-block-4-sub-2', 'name': 'Physiology Block 4 Sub-block 2', 'order': 2},
    {'id': 'physiology-block-4-sub-3', 'name': 'Physiology Block 4 Sub-block 3', 'order': 3},
    {'id': 'physiology-block-4-sub-4', 'name': 'Physiology Block 4 Sub-block 4', 'order': 4},
]

# Add topics
def add_topics(block_id, topics_data):
    try:
        block = Block.objects.get(id=block_id)
        for topic_data in topics_data:
            topic, created = Topic.objects.get_or_create(
                id=topic_data['id'],
                defaults={
                    'block': block,
                    'name': topic_data['name'],
                    'order': topic_data['order']
                }
            )
            if created:
                print(f"Created: {topic.name}")
            else:
                print(f"Already exists: {topic.name}")
    except Block.DoesNotExist:
        print(f"Block {block_id} not found!")

print("Adding Gross Anatomy Block 3 sub-blocks...")
add_topics('anatomy-gross-block-3', gross_block_3_topics)

print("\nAdding Physiology Block 1 sub-blocks...")
add_topics('physiology-block-1', physiology_block_1_topics)

print("\nAdding Physiology Block 2 sub-blocks...")
add_topics('physiology-block-2', physiology_block_2_topics)

print("\nAdding Physiology Block 3 sub-blocks...")
add_topics('physiology-block-3', physiology_block_3_topics)

print("\nAdding Physiology Block 4 sub-blocks...")
add_topics('physiology-block-4', physiology_block_4_topics)

print("\nDone! All sub-blocks added.")
