"""
Add topics to existing blocks
Run with: python manage.py shell < add_topics.py
"""

from curriculum.models import Block, Topic

print("Adding topics to blocks...")

# Get all blocks
blocks = Block.objects.all()

for block in blocks:
    print(f"\nProcessing: {block.name} ({block.id})")
    
    # Check if block already has topics
    existing_topics = Topic.objects.filter(block=block).count()
    if existing_topics > 0:
        print(f"  ✓ Already has {existing_topics} topics, skipping")
        continue
    
    # Add generic topics based on block type
    if 'gross' in block.id.lower() or 'anatomy' in block.name.lower():
        topics_to_add = [
            ('Upper Limb', 1),
            ('Lower Limb', 2),
            ('Thorax', 3),
            ('Abdomen', 4),
            ('Head & Neck', 5),
        ]
    elif 'embryo' in block.id.lower():
        topics_to_add = [
            ('Gametogenesis', 1),
            ('Fertilization', 2),
            ('Early Development', 3),
            ('Organogenesis', 4),
        ]
    elif 'histo' in block.id.lower():
        topics_to_add = [
            ('Epithelial Tissue', 1),
            ('Connective Tissue', 2),
            ('Muscle Tissue', 3),
            ('Nervous Tissue', 4),
        ]
    elif 'physiology' in block.name.lower():
        block_num = block.id.split('-')[-1]
        if block_num == '1':
            topics_to_add = [
                ('General Physiology', 1),
                ('Cell Physiology', 2),
                ('Nerve & Muscle', 3),
            ]
        elif block_num == '2':
            topics_to_add = [
                ('Cardiovascular System', 1),
                ('Respiratory System', 2),
                ('Blood', 3),
            ]
        elif block_num == '3':
            topics_to_add = [
                ('Renal Physiology', 1),
                ('GIT Physiology', 2),
                ('Endocrine System', 3),
            ]
        elif block_num == '4':
            topics_to_add = [
                ('Nervous System', 1),
                ('Special Senses', 2),
                ('Reproductive System', 3),
            ]
        else:
            topics_to_add = []
    else:
        # Biochemistry or other - no topics needed
        print(f"  - No topics needed for this block type")
        continue
    
    # Create topics
    for topic_name, order in topics_to_add:
        topic_id = f"{block.id}-{topic_name.lower().replace(' ', '-').replace('&', 'and')}"
        Topic.objects.create(
            id=topic_id,
            block=block,
            name=topic_name,
            order=order
        )
        print(f"  ✓ Created: {topic_name}")

print("\n" + "="*50)
print("TOPICS ADDED SUCCESSFULLY!")
print("="*50)
print(f"\nTotal topics now: {Topic.objects.count()}")
