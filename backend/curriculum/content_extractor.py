"""
Slide Content Extraction Utilities
Extracts text and images from PDF, PowerPoint, and Word documents
Uploads images to Cloudinary for rendering
"""

import io
import requests
from PyPDF2 import PdfReader
from pptx import Presentation
from docx import Document
from PIL import Image
import cloudinary.uploader
import base64


def upload_image_to_cloudinary(image_data, slide_id, page_num, image_num):
    """Upload extracted image to Cloudinary"""
    try:
        # Generate unique public_id
        public_id = f"slides/{slide_id}/page_{page_num}_img_{image_num}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            image_data,
            folder="emby/slide_images",
            public_id=public_id,
            resource_type='image'
        )
        
        return result['secure_url']
    except Exception as e:
        print(f"Failed to upload image: {e}")
        return None


def extract_pdf_content(file_url, slide_id):
    """Extract text and images from PDF"""
    try:
        response = requests.get(file_url)
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        pages = []
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            
            # Extract images from PDF page
            images = []
            if '/XObject' in page['/Resources']:
                xObject = page['/Resources']['/XObject'].get_object()
                
                img_count = 0
                for obj in xObject:
                    if xObject[obj]['/Subtype'] == '/Image':
                        try:
                            img_count += 1
                            # Get image data
                            size = (xObject[obj]['/Width'], xObject[obj]['/Height'])
                            data = xObject[obj].get_data()
                            
                            # Upload to Cloudinary
                            img_url = upload_image_to_cloudinary(
                                data, slide_id, page_num, img_count
                            )
                            
                            if img_url:
                                images.append({
                                    'url': img_url,
                                    'width': size[0],
                                    'height': size[1]
                                })
                        except Exception as e:
                            print(f"Failed to extract image: {e}")
                            continue
            
            pages.append({
                'page_number': page_num,
                'content': text,
                'images': images
            })
        
        return {
            'total_pages': len(pages),
            'pages': pages
        }
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return {'total_pages': 0, 'pages': []}


def extract_pptx_content(file_url, slide_id):
    """Extract text and images from PowerPoint"""
    try:
        response = requests.get(file_url)
        pptx_file = io.BytesIO(response.content)
        prs = Presentation(pptx_file)
        
        pages = []
        for slide_num, slide in enumerate(prs.slides, 1):
            text_content = []
            images = []
            
            img_count = 0
            # Extract text and images from shapes
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text_content.append(shape.text)
                
                # Extract images
                if shape.shape_type == 13:  # Picture
                    try:
                        img_count += 1
                        image = shape.image
                        image_bytes = image.blob
                        
                        # Upload to Cloudinary
                        img_url = upload_image_to_cloudinary(
                            image_bytes, slide_id, slide_num, img_count
                        )
                        
                        if img_url:
                            images.append({
                                'url': img_url,
                                'type': image.content_type
                            })
                    except Exception as e:
                        print(f"Failed to extract image: {e}")
                        continue
            
            pages.append({
                'page_number': slide_num,
                'content': '\n'.join(text_content),
                'images': images
            })
        
        return {
            'total_pages': len(pages),
            'pages': pages
        }
    except Exception as e:
        print(f"PPTX extraction error: {e}")
        return {'total_pages': 0, 'pages': []}


def extract_docx_content(file_url, slide_id):
    """Extract text and images from Word document"""
    try:
        response = requests.get(file_url)
        docx_file = io.BytesIO(response.content)
        doc = Document(docx_file)
        
        text_content = []
        images = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text)
        
        # Extract images
        img_count = 0
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                try:
                    img_count += 1
                    image_part = rel.target_part
                    image_bytes = image_part.blob
                    
                    # Upload to Cloudinary
                    img_url = upload_image_to_cloudinary(
                        image_bytes, slide_id, 1, img_count
                    )
                    
                    if img_url:
                        images.append({
                            'url': img_url,
                            'type': image_part.content_type
                        })
                except Exception as e:
                    print(f"Failed to extract image: {e}")
                    continue
        
        pages = [{
            'page_number': 1,
            'content': '\n\n'.join(text_content),
            'images': images
        }]
        
        return {
            'total_pages': len(pages),
            'pages': pages
        }
    except Exception as e:
        print(f"DOCX extraction error: {e}")
        return {'total_pages': 0, 'pages': []}


def extract_slide_content(file_url, file_type, slide_id):
    """Main function to extract content based on file type"""
    if file_type == 'pdf' or 'pdf' in file_type.lower():
        return extract_pdf_content(file_url, slide_id)
    elif file_type == 'pptx' or 'presentation' in file_type.lower():
        return extract_pptx_content(file_url, slide_id)
    elif file_type == 'docx' or 'document' in file_type.lower():
        return extract_docx_content(file_url, slide_id)
    else:
        return {'total_pages': 0, 'pages': []}
