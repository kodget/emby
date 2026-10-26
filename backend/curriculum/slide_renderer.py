"""
Slide Rendering System
Converts PDF/PPTX/DOCX pages to images with text for the reader view.
Results are cached in SlideContent to avoid re-processing on every request.
"""

from PIL import Image


def _upload_page_image(image_bytes, slide_id, page_num):
    from .models import Slide
    from .private_media import upload_asset

    try:
        slide = Slide.objects.select_related('class_group', 'uploaded_by').get(pk=slide_id)
        if not slide.class_group_id:
            raise ValueError('Assign this slide to a class before rendering.')
        asset = upload_asset(
            image_bytes,
            class_group=slide.class_group,
            uploaded_by=slide.uploaded_by,
            folder="emby/slide_pages",
            resource_type='image',
            format='jpg',
            quality='auto:best',
            timeout=60,
        )
        return str(asset.pk)
    except Exception as e:
        print(f"Page storage failed (page {page_num}, {type(e).__name__})")
        return None


def render_slide_pages(file_url, file_type, slide_id):
    """Render every original page, storing the cache only after all uploads succeed."""
    import tempfile
    from pathlib import Path
    from .models import Slide
    from .services.isolated_rendering import render_document_isolated
    from .services.document_extraction import source_key, content_text
    from .services.slide_conversion_pipeline import download_source
    slide = Slide.objects.filter(pk=slide_id, class_group__isnull=False).first()
    if not slide:
        raise ValueError('Assign this slide to a class before rendering.')
    kind = file_type.lower().lstrip('.')
    if kind not in {'pdf', 'ppt', 'pptx', 'docx'}:
        raise ValueError('Unsupported document format.')
    with tempfile.TemporaryDirectory(prefix='emby-render-') as directory:
        source = Path(directory) / f'original.{kind}'
        download_source(file_url, source)
        rendered = render_document_isolated(source, kind, directory)
        pages = []
        for number, image_path in enumerate(rendered['image_paths'], 1):
            asset_id = _upload_page_image(Path(image_path).read_bytes(), slide_id, number)
            if not asset_id:
                raise RuntimeError('A document page could not be stored. Please retry.')
            with Image.open(image_path) as image:
                width, height = image.size
            pages.append({**rendered['pages'][number - 1], 'asset_id': asset_id,
                          'width': width, 'height': height,
                          'text': rendered['page_texts'][number - 1], 'text_blocks': []})
        rendered['text_extraction']['source_key'] = source_key(slide)
        return {'total_pages': len(pages), 'pages': pages, 'text': content_text(rendered),
                'text_extraction': rendered['text_extraction']}
