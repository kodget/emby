import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide
from curriculum.services.slide_conversion_pipeline import SlideConversionPipeline
import shutil

# Get the latest slide
slide = Slide.objects.exclude(file_url='').order_by('-created_at').first()
if slide:
    print(f"Slide ID: {slide.id}")
    
    # Run the pipeline locally to see output
    result = SlideConversionPipeline.process_slide(
        cloudinary_url=slide.file_url,
        slide_id=slide.id,
        original_file_type=slide.file_type
    )
    
    if result['success']:
        print(f"Pipeline succeeded. Page count: {result['page_count']}")
        print(f"Images are in: {result['temp_dir']}")
        
        # Copy the first image and the PDF to a known location
        output_dir = os.path.join(os.getcwd(), 'test_output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Copy pdf
        pdf_dir = os.path.join(result['temp_dir'], 'pdf')
        if os.path.exists(pdf_dir):
            for f in os.listdir(pdf_dir):
                if f.endswith('.pdf'):
                    shutil.copy(os.path.join(pdf_dir, f), os.path.join(output_dir, 'test.pdf'))
                    print(f"Copied PDF to {output_dir}/test.pdf")
                    
        # Copy first image
        if result['image_paths']:
            shutil.copy(result['image_paths'][0], os.path.join(output_dir, 'test_page_1.jpg'))
            print(f"Copied first page image to {output_dir}/test_page_1.jpg")
            
    else:
        print(f"Pipeline failed: {result['error']}")
else:
    print("No slide found.")
