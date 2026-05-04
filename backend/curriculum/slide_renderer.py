"""
Slide Rendering System
Converts PDF/PPTX/DOCX pages to images with text for the reader view.
Results are cached in SlideContent to avoid re-processing on every request.
"""

import io
import requests
import fitz  # PyMuPDF
import cloudinary.uploader
from PIL import Image


def _upload_page_image(image_bytes, slide_id, page_num):
    try:
        result = cloudinary.uploader.upload(
            image_bytes,
            folder="emby/slide_pages",
            public_id=f"slides/{slide_id}/page_{page_num}",
            resource_type='image',
            format='jpg',
            quality='auto:best',
            timeout=60,
        )
        return result['secure_url']
    except Exception as e:
        print(f"Cloudinary upload failed (page {page_num}): {e}")
        return None


def _render_pdf_from_bytes(pdf_bytes, slide_id):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = 2  # ~144 DPI — good balance of quality vs size
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=88, optimize=True)

        image_url = _upload_page_image(buf.getvalue(), slide_id, page_num + 1)
        if not image_url:
            continue

        text_blocks = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span["bbox"]
                    text_blocks.append({
                        "text": span["text"],
                        "x": bbox[0] * zoom,
                        "y": bbox[1] * zoom,
                        "width": (bbox[2] - bbox[0]) * zoom,
                        "height": (bbox[3] - bbox[1]) * zoom,
                        "font_size": span["size"] * zoom,
                    })

        pages.append({
            "page_number": page_num + 1,
            "image_url": image_url,
            "width": pix.width,
            "height": pix.height,
            "text_blocks": text_blocks,
        })
    doc.close()
    return pages


def _render_pptx_from_bytes(pptx_bytes, slide_id):
    """
    Render PPTX by converting each slide to PDF via python-pptx then rendering.
    Falls back to text-only extraction if conversion fails.
    """
    from pptx import Presentation
    from pptx.util import Pt

    prs = Presentation(io.BytesIO(pptx_bytes))
    pages = []

    for slide_num, slide in enumerate(prs.slides, 1):
        slide_w = int(prs.slide_width / 9525 * 96 * 2)   # EMU → px at 2x
        slide_h = int(prs.slide_height / 9525 * 96 * 2)

        canvas = Image.new('RGB', (slide_w, slide_h), 'white')

        text_blocks = []
        for shape in slide.shapes:
            if not hasattr(shape, "text") or not shape.text.strip():
                continue
            left = int(shape.left / 9525 * 96 * 2)
            top = int(shape.top / 9525 * 96 * 2)
            width = int(shape.width / 9525 * 96 * 2)
            height = int(shape.height / 9525 * 96 * 2)
            text_blocks.append({
                "text": shape.text,
                "x": left, "y": top,
                "width": width, "height": height,
                "font_size": 24,
            })

        buf = io.BytesIO()
        canvas.save(buf, format='JPEG', quality=88)
        image_url = _upload_page_image(buf.getvalue(), slide_id, slide_num)
        if not image_url:
            continue

        pages.append({
            "page_number": slide_num,
            "image_url": image_url,
            "width": slide_w,
            "height": slide_h,
            "text_blocks": text_blocks,
        })

    return pages


def _render_docx_from_bytes(docx_bytes, slide_id):
    """
    Extract DOCX as a single page of text.
    Real image rendering requires LibreOffice; for now we return text blocks only.
    """
    from docx import Document

    doc = Document(io.BytesIO(docx_bytes))
    lines = [p.text for p in doc.paragraphs if p.text.strip()]

    # Build a simple white image with text blocks at estimated positions
    line_height = 28
    img_width, img_height = 1200, max(800, len(lines) * line_height + 80)
    canvas = Image.new('RGB', (img_width, img_height), 'white')

    text_blocks = []
    for i, line in enumerate(lines):
        text_blocks.append({
            "text": line,
            "x": 40, "y": 40 + i * line_height,
            "width": img_width - 80, "height": line_height,
            "font_size": 16,
        })

    buf = io.BytesIO()
    canvas.save(buf, format='JPEG', quality=88)
    image_url = _upload_page_image(buf.getvalue(), slide_id, 1)

    if not image_url:
        return []

    return [{
        "page_number": 1,
        "image_url": image_url,
        "width": img_width,
        "height": img_height,
        "text_blocks": text_blocks,
    }]


def render_slide_pages(file_url, file_type, slide_id):
    """
    Download the file and render all pages.
    Returns {"total_pages": N, "pages": [...]} for the SlideContent cache.
    """
    print(f"Rendering {slide_id} ({file_type}) from {file_url}")
    try:
        resp = requests.get(file_url, timeout=30)
        if resp.status_code != 200 or not resp.content:
            print(f"Download failed: HTTP {resp.status_code}")
            return {"total_pages": 0, "pages": []}
        file_bytes = resp.content
    except Exception as e:
        print(f"Download error: {e}")
        return {"total_pages": 0, "pages": []}

    ft = file_type.lower()
    try:
        if 'pdf' in ft:
            pages = _render_pdf_from_bytes(file_bytes, slide_id)
        elif 'pptx' in ft or 'presentation' in ft or 'ppt' in ft:
            pages = _render_pptx_from_bytes(file_bytes, slide_id)
        elif 'docx' in ft or 'document' in ft or 'doc' in ft:
            pages = _render_docx_from_bytes(file_bytes, slide_id)
        else:
            print(f"Unsupported file type: {file_type}")
            pages = []
    except Exception as e:
        import traceback
        print(f"Rendering error for {slide_id}: {e}")
        traceback.print_exc()
        pages = []

    return {"total_pages": len(pages), "pages": pages}
