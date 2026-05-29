import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideContent

slide = Slide.objects.order_by('-created_at').first()
print(f'Slide: {slide.title}')
print(f'Page count: {slide.page_count}')

sc = SlideContent.objects.filter(slide=slide).first()
print(f'Has SlideContent: {sc is not None}')

if sc:
    print(f'Is extracted: {sc.is_extracted}')
    print(f'Extraction error: {sc.extraction_error}')
    print(f'Content data keys: {list(sc.content_data.keys()) if sc.content_data else []}')
    if sc.content_data and 'pages' in sc.content_data:
        print(f'Number of pages: {len(sc.content_data["pages"])}')
        if sc.content_data['pages']:
            first_page = sc.content_data['pages'][0]
            print(f'First page keys: {list(first_page.keys())}')
            if 'text' in first_page:
                print(f'First page text length: {len(first_page["text"])}')
