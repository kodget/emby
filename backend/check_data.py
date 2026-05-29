import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideContent

s = Slide.objects.latest('created_at')
c = SlideContent.objects.get(slide=s)

print(f'Slide ID: {s.id}')
print(f'Slide title: {s.title}')
print(f'Page count: {s.page_count}')
print(f'Is extracted: {c.is_extracted}')
print(f'Total pages in content: {c.content_data.get("total_pages")}')
print(f'Pages array length: {len(c.content_data.get("pages", []))}')

if c.content_data.get("pages"):
    print(f'\nFirst page:')
    print(f'  Page number: {c.content_data["pages"][0]["page_number"]}')
    print(f'  Image URL: {c.content_data["pages"][0]["image_url"]}')
    print(f'  Width: {c.content_data["pages"][0]["width"]}')
    print(f'  Height: {c.content_data["pages"][0]["height"]}')
