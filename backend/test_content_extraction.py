"""
Test script to check if PDF content extraction is working
Run with: python manage.py shell < test_content_extraction.py
"""

from curriculum.models import Slide
from curriculum.content_extractor import get_slide_full_text

print("=" * 60)
print("TESTING PDF CONTENT EXTRACTION")
print("=" * 60)

# Get all slides
slides = Slide.objects.all()[:5]  # Test first 5 slides

for slide in slides:
    print(f"\n{'='*60}")
    print(f"Slide ID: {slide.id}")
    print(f"Title: {slide.title}")
    print(f"Subject: {slide.subject.name if slide.subject else 'None'}")
    print(f"File Type: {slide.file_type}")
    
    # Check file URL
    file_url = None
    if slide.file:
        file_url = slide.file.url
        print(f"Cloudinary File URL: {file_url}")
    elif slide.file_url:
        file_url = slide.file_url
        print(f"Legacy File URL: {file_url}")
    else:
        print("NO FILE URL FOUND!")
        continue
    
    # Try to extract content
    try:
        content = get_slide_full_text(file_url, slide.file_type or 'pdf')
        print(f"Content Length: {len(content)} characters")
        print(f"Content Preview (first 300 chars):")
        print(content[:300] if content else "EMPTY!")
    except Exception as e:
        print(f"ERROR extracting content: {e}")

print(f"\n{'='*60}")
print("TEST COMPLETE")
print("=" * 60)
