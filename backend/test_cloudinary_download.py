import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide
from curriculum.services.slide_conversion_pipeline import _download_from_cloudinary

# Get the latest slide
slide = Slide.objects.exclude(file_url='').order_by('-created_at').first()
if slide:
    print(f"Slide ID: {slide.id}")
    print(f"File URL: {slide.file_url}")
    print(f"File Type: {slide.file_type}")
    
    try:
        data = _download_from_cloudinary(slide.file_url)
        print(f"Downloaded {len(data)} bytes")
        print(f"First 100 bytes: {data[:100]}")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("No slide found.")
