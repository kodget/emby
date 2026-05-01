"""
Slide Rendering System
Converts PDF/PPT/DOCX pages to high-quality images with text coordinates
for selectable text overlay in the frontend
"""

import io
import requests
from pdf2image import convert_from_bytes
from pptx import Presentation
from docx import Document
from PIL import Image, ImageDraw
import cloudinary.uploader
import fitz  # PyMuPDF for better PDF handling with text coordinates


def upload_page_image(image_bytes, slide_id, page_num):
    """Upload rendered page image to Cloudinary"""
    try:
        public_id = f"slides/{slide_id}/page_{page_num}"
        
        result = cloudinary.uploader.upload(
            image_bytes,
            folder="emby/slide_pages",
            public_id=public_id,
            resource_type='image',
            format='jpg',
            quality='auto:best',
            timeout=60
        )
        
        return result['secure_url']
    except Exception as e:
        print(f"Failed to upload page image: {e}")
        return None


def render_pdf_pages(file_url, slide_id):
    """
    Render PDF pages as images with text coordinates
    Uses PyMuPDF (fitz) for accurate text positioning
    """
    try:
        print(f"Downloading PDF from: {file_url}")
        response = requests.get(file_url, timeout=30)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response content length: {len(response.content)}")
        
        if response.status_code != 200:
            print(f"Failed to download PDF: HTTP {response.status_code}")
            return {"total_pages": 0, "pages": []}
        
        if len(response.content) == 0:
            print("Downloaded PDF is empty!")
            return {"total_pages": 0, "pages": []}
        
        pdf_bytes = response.content
        
        # Open PDF with PyMuPDF
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        pages = []
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Render page to image at high DPI (300 for quality)
            zoom = 2  # 2x zoom = ~144 DPI (good balance)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Convert to JPEG bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=90, optimize=True)
            img_byte_arr.seek(0)
            
            # Upload to Cloudinary
            image_url = upload_page_image(img_byte_arr.getvalue(), slide_id, page_num + 1)
            
            if not image_url:
                continue
            
            # Extract text with coordinates
            text_blocks = []
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            # Get bounding box (scaled to match rendered image)
                            bbox = span["bbox"]
                            text_blocks.append({
                                "text": span["text"],
                                "x": bbox[0] * zoom,
                                "y": bbox[1] * zoom,
                                "width": (bbox[2] - bbox[0]) * zoom,
                                "height": (bbox[3] - bbox[1]) * zoom,
                                "font_size": span["size"] * zoom,
                                "font": span.get("font", ""),
                                "color": span.get("color", 0)
                            })
            
            pages.append({
                "page_number": page_num + 1,
                "image_url": image_url,
                "width": pix.width,
                "height": pix.height,
                "text_blocks": text_blocks
            })
        
        pdf_document.close()
        
        return {
            "total_pages": len(pages),
            "pages": pages
        }
    except Exception as e:
        print(f"PDF rendering error: {e}")
        import traceback
        traceback.print_exc()
        return {"total_pages": 0, "pages": []}


def render_pptx_pages(file_url, slide_id):
    """
    Render PowerPoint slides as images
    Note: Text coordinates are approximate for PPTX
    """
    try:
        response = requests.get(file_url, timeout=30)
        pptx_bytes = response.content
        
        prs = Presentation(io.BytesIO(pptx_bytes))
        
        pages = []
        for slide_num, slide in enumerate(prs.slides, 1):
            # Get slide dimensions
            slide_width = prs.slide_width
            slide_height = prs.slide_height
            
            # Create blank image
            scale = 2  # 2x for better quality
            img_width = int(slide_width / 9525 * 96 * scale)  # Convert EMU to pixels
            img_height = int(slide_height / 9525 * 96 * scale)
            
            img = Image.new('RGB', (img_width, img_height), 'white')
            draw = ImageDraw.Draw(img)
            
            # Extract text blocks with approximate positions
            text_blocks = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    # Get shape position (approximate)
                    left = int(shape.left / 9525 * 96 * scale)
                    top = int(shape.top / 9525 * 96 * scale)
                    width = int(shape.width / 9525 * 96 * scale)
                    height = int(shape.height / 9525 * 96 * scale)
                    
                    text_blocks.append({
                        "text": shape.text,
                        "x": left,
                        "y": top,
                        "width": width,
                        "height": height,
                        "font_size": 12,  # Default, can't easily extract from PPTX
                        "font": "",
                        "color": 0
                    })
            
            # For PPTX, we need to use a library like python-pptx-interface or export to PDF first
            # For now, return a placeholder approach
            # TODO: Consider converting PPTX to PDF first, then rendering
            
            # Convert to JPEG bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=90)
            img_byte_arr.seek(0)
            
            # Upload to Cloudinary
            image_url = upload_page_image(img_byte_arr.getvalue(), slide_id, slide_num)
            
            if image_url:
                pages.append({
                    "page_number": slide_num,
                    "image_url": image_url,
                    "width": img_width,
                    "height": img_height,
                    "text_blocks": text_blocks
                })
        
        return {
            "total_pages": len(pages),
            "pages": pages
        }
    except Exception as e:
        print(f"PPTX rendering error: {e}")
        import traceback
        traceback.print_exc()
        return {"total_pages": 0, "pages": []}


def render_slide_pages(file_url, file_type, slide_id):
    """
    Main function to render slides as images with text coordinates
    """
    print(f"Rendering slide {slide_id} from {file_url} (type: {file_type})")
    
    if file_type == 'pdf' or 'pdf' in file_type.lower():
        return render_pdf_pages(file_url, slide_id)
    elif file_type == 'pptx' or 'presentation' in file_type.lower():
        # For PPTX, convert to PDF first for better rendering
        # For now, use direct PPTX rendering
        return render_pptx_pages(file_url, slide_id)
    elif file_type == 'docx' or 'document' in file_type.lower():
        # DOCX is complex - best to convert to PDF first
        # For now, return empty
        print("DOCX rendering not yet implemented - convert to PDF first")
        return {"total_pages": 0, "pages": []}
    else:
        return {"total_pages": 0, "pages": []}
