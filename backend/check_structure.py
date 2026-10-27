#!/usr/bin/env python
"""Check the URL structure"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Subject, Block, SubBlock, Topic

# Check Anatomy subject
subject = Subject.objects.filter(name='Anatomy').first()
if not subject:
    print("ERROR: Anatomy subject not found!")
    exit(1)

print(f"\nSubject: {subject.name}")
print(f"  ID: {subject.id}")

# Check blocks
blocks = Block.objects.filter(subject=subject)
print(f"\nBlocks: {blocks.count()}")
for block in blocks:
    print(f"  - {block.name} (ID: {block.id})")
    
    subblocks = SubBlock.objects.filter(block=block)
    for subblock in subblocks:
        print(f"    - {subblock.name} (ID: {subblock.id})")
        
        topics = Topic.objects.filter(sub_block=subblock)
        print(f"      Topics: {topics.count()}")
        if topics.exists():
            topic = topics.first()
            print(f"        Sample: {topic.name[:40]}... (ID: {topic.id})")

print("\n" + "="*60)
print("EXPECTED URL STRUCTURE:")
print("/courses/{subject_id}/{block_id}/{subblock_id}/{topic_id}")
print("\nExample:")
print("/courses/anatomy/first-block/upper-limb/tympanic-cavity")
print("\nOUR STRUCTURE:")
print(f"/courses/{subject.id}/third-block/neuroanatomy/300l-medical...")
print("="*60)
