import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import Slide, SlideContent
import cloudinary.uploader
import cloudinary.api

# Get the latest slide
slide = Slide.objects.latest('created_at')
print(f"Fixing slide: {slide.id} - {slide.title}")
print(f"Current URL: {slide.file_url}")

# Extract public_id from URL
# URL format: https://res.cloudinary.com/dom0dtr6h/raw/upload/v1777881321/emby/slides/awtsxk7uvgabzsgjxddl.pdf
parts = slide.file_url.split('/')
public_id = '/'.join(parts[-2:]).replace('.pdf', '')  # emby/slides/awtsxk7uvgabzsgjxddl
print(f"Public ID: {public_id}")

# Update the resource to be public
try:
    result = cloudinary.api.update(
        public_id,
        resource_type='raw',
        access_mode='public'
    )
    print(f"Updated access mode to public")
    print(f"New URL: {result.get('secure_url')}")
    
    # Update slide with new URL
    slide.file_url = result['secure_url']
    slide.save()
    
except Exception as e:
    print(f"Failed to update Cloudinary resource: {e}")
    print("Trying to re-upload...")
    
    # Download the file and re-upload as public
    import requests
    try:
        # Try to download with signed URL
        from cloudinary.utils import cloudinary_url
        signed_url, _ = cloudinary_url(public_id, resource_type='raw', sign_url=True)
        print(f"Trying signed URL: {signed_url}")
        
        resp = requests.get(signed_url, timeout=30)
        if resp.status_code == 200:
            print(f"Downloaded {len(resp.content)} bytes")
            
            # Re-upload as public
            result = cloudinary.uploader.upload(
                resp.content,
                folder="emby/slides",
                resource_type='raw',
                access_mode='public',
                public_id=public_id.split('/')[-1]
            )
            
            print(f"Re-uploaded successfully: {result['secure_url']}")
            slide.file_url = result['secure_url']
            slide.save()
        else:
            print(f"Download failed: HTTP {resp.status_code}")
    except Exception as e2:
        print(f"Re-upload failed: {e2}")

# Now try rendering
print("\n" + "="*50)
print("Attempting to render...")
print("="*50)

from curriculum.slide_renderer import render_slide_pages

result = render_slide_pages(slide.file_url, slide.file_type, slide.id)
print(f"\nRender result:")
print(f"  total_pages: {result['total_pages']}")
print(f"  pages returned: {len(result['pages'])}")

if result['pages']:
    print(f"\nFirst page:")
    print(f"  image_url: {result['pages'][0].get('image_url')}")
    
    # Save to database
    content, _ = SlideContent.objects.get_or_create(slide=slide)
    content.content_data = result
    content.is_extracted = True
    content.save()
    
    slide.page_count = result['total_pages']
    slide.save()
    
    print(f"\nSaved to database. Slide now has {slide.page_count} pages")
else:
    print("\nNo pages rendered!")
