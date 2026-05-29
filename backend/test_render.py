import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideContent

# Get the latest slide
slide = Slide.objects.latest('created_at')
print(f"Testing slide: {slide.id} - {slide.title}")
print(f"File URL: {slide.file_url}")
print(f"File type: {slide.file_type}")
print(f"Page count: {slide.page_count}")

# Check if content exists
try:
    content = SlideContent.objects.get(slide=slide)
    print(f"\nSlideContent exists:")
    print(f"  is_extracted: {content.is_extracted}")
    print(f"  extraction_error: {content.extraction_error}")
    print(f"  total_pages: {content.content_data.get('total_pages', 0)}")
    
    pages = content.content_data.get('pages', [])
    print(f"  pages in data: {len(pages)}")
    
    if pages:
        print(f"\nFirst page:")
        print(f"  page_number: {pages[0].get('page_number')}")
        print(f"  image_url: {pages[0].get('image_url', 'MISSING')}")
        print(f"  width: {pages[0].get('width')}")
        print(f"  height: {pages[0].get('height')}")
except SlideContent.DoesNotExist:
    print("\nNo SlideContent found - rendering never happened")

# Try rendering now
print("\n" + "="*50)
print("Attempting to render now...")
print("="*50)

from curriculum.slide_renderer import render_slide_pages

result = render_slide_pages(slide.file_url, slide.file_type, slide.id)
print(f"\nRender result:")
print(f"  total_pages: {result['total_pages']}")
print(f"  pages returned: {len(result['pages'])}")

if result['pages']:
    print(f"\nFirst page from render:")
    print(f"  page_number: {result['pages'][0].get('page_number')}")
    print(f"  image_url: {result['pages'][0].get('image_url', 'MISSING')}")
