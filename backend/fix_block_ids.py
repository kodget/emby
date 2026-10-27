#!/usr/bin/env python
"""Fix the empty block and sub-block IDs"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Block, SubBlock, Topic, Slide
from django.utils.text import slugify

print("\n" + "="*60)
print("FIXING EMPTY BLOCK AND SUB-BLOCK IDs")
print("="*60 + "\n")

# Find the block with empty ID
broken_block = Block.objects.filter(id='', name='Third Block').first()
if broken_block:
    print(f"Found broken block: '{broken_block.name}' (ID: '{broken_block.id}')")
    
    # Check if 'third-block' already exists
    existing = Block.objects.filter(id='third-block').first()
    if existing:
        print(f"  'third-block' already exists: {existing.name}")
        print(f"  Moving slides to existing block...")
        
        # Move the broken sub-blocks to the existing block
        SubBlock.objects.filter(block=broken_block).update(block=existing)
        
        # Delete the broken block
        broken_block.delete()
        print(f"  ✅ Deleted broken block, moved content to existing")
    else:
        print(f"  Creating new ID: 'third-block'")
        
        # We need to delete and recreate because ID is primary key
        subject = broken_block.subject
        order = broken_block.order
        
        # Get sub-blocks before deleting
        subblocks = list(SubBlock.objects.filter(block=broken_block))
        
        # Delete old block
        broken_block.delete()
        
        # Create new block with proper ID
        new_block = Block.objects.create(
            id='third-block',
            name='Third Block',
            subject=subject,
            order=order
        )
        print(f"  ✅ Created new block: {new_block.id}")
        
        # Update sub-blocks to point to new block
        for subblock in subblocks:
            # Need to handle empty sub-block IDs too
            if not subblock.id or subblock.id == '':
                print(f"\n  Found broken sub-block: '{subblock.name}' (ID: '{subblock.id}')")
                
                # Check if proper ID exists
                proper_id = slugify(subblock.name)
                existing_subblock = SubBlock.objects.filter(id=proper_id, block=new_block).first()
                
                if existing_subblock:
                    print(f"    '{proper_id}' already exists, moving slides...")
                    
                    # Move slides and topics
                    slide_count = Slide.objects.filter(sub_block=subblock).update(sub_block=existing_subblock, block=new_block)
                    topic_count = Topic.objects.filter(sub_block=subblock).update(sub_block=existing_subblock, block=new_block)
                    
                    # Delete broken sub-block
                    subblock.delete()
                    print(f"    ✅ Moved {slide_count} slides and {topic_count} topics")
                    print(f"    ✅ Deleted broken sub-block")
                elif SubBlock.objects.filter(id=proper_id).exists():
                    # Exists in a different block
                    print(f"    '{proper_id}' exists in another block, using 'neuroanatomy-new'...")
                    proper_id = f"{proper_id}-new"
                    
                    # Create new sub-block with modified ID
                    slides = list(Slide.objects.filter(sub_block=subblock))
                    topics = list(Topic.objects.filter(sub_block=subblock))
                    order = subblock.order
                    name = subblock.name
                    
                    # Delete old
                    subblock.delete()
                    
                    # Create new
                    new_subblock = SubBlock.objects.create(
                        id=proper_id,
                        name=name,
                        block=new_block,
                        order=order
                    )
                    
                    # Update slides and topics
                    Slide.objects.filter(id__in=[s.id for s in slides]).update(
                        sub_block=new_subblock,
                        block=new_block
                    )
                    Topic.objects.filter(id__in=[t.id for t in topics]).update(
                        sub_block=new_subblock,
                        block=new_block
                    )
                    
                    print(f"    ✅ Created new sub-block: {new_subblock.id}")
                    print(f"    ✅ Moved {len(slides)} slides and {len(topics)} topics")
                else:
                    # Create new sub-block with proper ID
                    slides = list(Slide.objects.filter(sub_block=subblock))
                    topics = list(Topic.objects.filter(sub_block=subblock))
                    order = subblock.order
                    name = subblock.name
                    
                    # Delete old
                    subblock.delete()
                    
                    # Create new
                    new_subblock = SubBlock.objects.create(
                        id=proper_id,
                        name=name,
                        block=new_block,
                        order=order
                    )
                    
                    # Update slides and topics
                    Slide.objects.filter(id__in=[s.id for s in slides]).update(
                        sub_block=new_subblock,
                        block=new_block
                    )
                    Topic.objects.filter(id__in=[t.id for t in topics]).update(
                        sub_block=new_subblock,
                        block=new_block
                    )
                    
                    print(f"    ✅ Created new sub-block: {new_subblock.id}")
                    print(f"    ✅ Moved {len(slides)} slides and {len(topics)} topics")
else:
    print("No broken block found")

print("\n" + "="*60)
print("VERIFICATION")
print("="*60)

# Verify structure
third_block = Block.objects.filter(name__icontains='third').first()
if third_block:
    print(f"\nThird Block: '{third_block.name}' (ID: '{third_block.id}')")
    subblocks = SubBlock.objects.filter(block=third_block)
    for sb in subblocks:
        print(f"  - {sb.name} (ID: '{sb.id}')")
        topics = Topic.objects.filter(sub_block=sb).count()
        slides = Slide.objects.filter(sub_block=sb).count()
        print(f"    Topics: {topics}, Slides: {slides}")

print("\n✅ All fixed!")
