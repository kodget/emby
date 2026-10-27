"""Page-complete text extraction. Rendering readiness is separate from text readiness."""
import hashlib
import os
from pathlib import Path
import tempfile

VERSION = 1
FORMATS = {'pdf', 'ppt', 'pptx', 'docx'}
ERRORS = {
    'source_unavailable': 'The original document could not be downloaded. Please retry.',
    'invalid_document': 'The document could not be read. Check the file and retry.',
    'encrypted': 'Unlock the password-protected document before uploading.',
    'unsupported': 'Supported document formats are PDF, PPT, PPTX and DOCX.',
    'ocr_unavailable': 'The text recognition language data is unavailable on the worker.',
    'ocr_failed': 'Text recognition failed on this page. Please retry processing.',
    'unreadable': 'No readable text was found on this non-blank page.',
    'native_failed': 'The text on this page could not be extracted.',
    'incomplete': 'Document text is incomplete. Retry processing before generating study content.',
    'unverified': 'This document needs text processing before generating study content.',
    'text_limit': 'The complete document exceeds the requested text limit.',
}


class ExtractionError(ValueError):
    def __init__(self, code, report=None):
        self.code = code
        self.report = report
        super().__init__(ERRORS[code])


def normalize_format(kind):
    aliases = {
        'application/pdf': 'pdf', 'application/vnd.ms-powerpoint': 'ppt',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    }
    kind = (kind or '').lower().lstrip('.')
    kind = aliases.get(kind, kind)
    if kind not in FORMATS:
        raise ExtractionError('unsupported')
    return kind


def source_bytes(source):
    """Support bytes, local paths and storage URLs without exposing signed URLs in errors."""
    try:
        if isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        elif str(source).lower().startswith(('https://', 'http://')):
            from .slide_conversion_pipeline import _download_from_cloudinary
            data = _download_from_cloudinary(str(source))
        else:
            data = Path(source).read_bytes()
        if not data:
            raise ValueError('empty')
        return data
    except Exception:
        raise ExtractionError('source_unavailable') from None


def ocr_options():
    language = os.environ.get('EMBY_OCR_LANGUAGES', 'eng')
    configured = os.environ.get('TESSDATA_PREFIX')
    candidates = [configured] if configured else [
        '/usr/share/tesseract-ocr/5/tessdata', '/usr/share/tesseract-ocr/4.00/tessdata',
        '/usr/share/tessdata', '/usr/local/share/tessdata',
        r'C:\Program Files\Tesseract-OCR\tessdata',
    ]
    if not configured:
        from django.conf import settings
        if settings.DEBUG:
            candidates.append(str(Path(__file__).resolve().parents[3] / '.test-tessdata'))
    for directory in candidates:
        if directory and all((Path(directory) / f'{lang}.traineddata').is_file()
                             for lang in language.split('+')):
            return {'language': language, 'tessdata': str(directory), 'dpi': 200}
    raise ExtractionError('ocr_unavailable')


def extract_page(page, *, ocr=True):
    result = {'page_number': page.number + 1, 'text': '',
              'extraction_status': 'failed', 'extraction_method': 'native', 'error_code': ''}
    try:
        result['text'] = page.get_text(sort=True).strip()
        # Only images actually painted on this page count, not unused PDF resources.
        has_images = bool(page.get_image_info())
        needs_ocr = has_images or (not result['text'] and bool(page.get_drawings()))
        if not needs_ocr:
            result['extraction_status'] = 'complete' if result['text'] else 'blank'
            return result
        result['extraction_method'] = 'ocr'
        if not ocr:
            result.update(extraction_status='needs_ocr', error_code='incomplete')
            return result
        options = ocr_options()
        textpage = page.get_textpage_ocr(full=not result['text'], **options)
        recognized = page.get_text(textpage=textpage, sort=True).strip()
        if recognized:
            result.update(text=recognized, extraction_status='complete')
        else:
            result['error_code'] = 'unreadable'
    except ExtractionError as exc:
        result['error_code'] = exc.code
    except Exception:
        result['error_code'] = 'ocr_failed' if result['extraction_method'] == 'ocr' else 'native_failed'
    return result


def extraction_summary(pages, source_hash):
    missing = [p['page_number'] for p in pages if p['extraction_status'] not in {'complete', 'blank'}]
    error_counts = {}
    for page in pages:
        error_code = page.get('error_code')
        if error_code:
            error_counts[error_code] = error_counts.get(error_code, 0) + 1
    return {
        'version': VERSION, 'status': 'complete' if pages and not missing else 'partial' if
        any(p['extraction_status'] in {'complete', 'blank'} for p in pages) else 'failed',
        'total_pages': len(pages), 'processed_pages': len(pages) - len(missing),
        'missing_pages': missing, 'error_counts': error_counts,
        'ocr_pages': [p['page_number'] for p in pages if p['extraction_method'] == 'ocr'],
        'character_count': sum(len(p['text']) for p in pages), 'source_sha256': source_hash,
    }


def extract_document(source, file_type, *, ocr=True):
    """Always return every page, including individual failures; never truncate text."""
    import fitz
    from .document_rendering import office_to_pdf
    kind = normalize_format(file_type)
    data = source_bytes(source)
    try:
        with tempfile.TemporaryDirectory(prefix='emby-extract-') as directory:
            path = Path(directory) / f'original.{kind}'
            path.write_bytes(data)
            pdf = path if kind == 'pdf' else office_to_pdf(path, Path(directory) / 'pdf')
            with fitz.open(pdf) as document:
                if document.needs_pass:
                    raise ExtractionError('encrypted')
                if not len(document):
                    raise ExtractionError('invalid_document')
                pages = [extract_page(page, ocr=ocr) for page in document]
        summary = extraction_summary(pages, hashlib.sha256(data).hexdigest())
        return {'pages': pages, 'text_extraction': summary, 'total_pages': len(pages)}
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError('invalid_document') from None


def is_complete(data):
    """Reject legacy prefix-only blobs and malformed or missing page manifests."""
    summary = data.get('text_extraction') or {}
    pages = data.get('pages') or []
    return bool(summary.get('version') == VERSION and summary.get('status') == 'complete'
                and summary.get('source_sha256') and pages
                and summary.get('total_pages') == len(pages)
                and [p.get('page_number') for p in pages] == list(range(1, len(pages) + 1))
                and all(p.get('extraction_status') in {'complete', 'blank'} for p in pages))


def content_text(data, *, require_complete=False):
    if require_complete and not is_complete(data):
        raise ExtractionError('incomplete' if data.get('text_extraction') else 'unverified', data.get('text_extraction'))
    parts = []
    for number, page in enumerate(data.get('pages') or [], 1):
        text = page.get('text') or page.get('content') or ''
        if not text and not page.get('extraction_status'):
            blocks = page.get('text_blocks') or []
            text = '\n'.join(b if isinstance(b, str) else (b.get('text') or b.get('content') or '') for b in blocks)
        if text.strip():
            parts.append(f"[Page {page.get('page_number', number)}]\n{text.strip()}")
    if parts or data.get('text_extraction'):
        return '\n\n'.join(parts)
    return (data.get('text') or '').strip()


def source_key(slide):
    identity = str(slide.asset_id or slide.file_url or getattr(slide.file, 'public_id', slide.file) or '')
    return hashlib.sha256(f'{slide.file_type}:{identity}'.encode()).hexdigest()


def ensure_slide_extraction(slide):
    """Upgrade old caches from the original. Keep page images and unrelated resources."""
    from django.db import transaction
    from django.utils import timezone
    from curriculum.models import Slide, SlideContent
    from curriculum.private_media import content_file_url
    content, _ = SlideContent.objects.get_or_create(slide=slide)
    data = content.content_data or {}
    key = source_key(slide)
    if is_complete(data) and data['text_extraction'].get('source_key') == key:
        return data
    if content.is_extracted and data.get('pages') and data.get('text_extraction', {}).get('source_key') == key:
        # Rendered documents are indexed once in the background, never scanned again
        # inside a student request (or in a competing question-bank worker).
        from curriculum.document_index import request_index
        from curriculum.models import SlideDeck
        origin = SlideDeck.objects.filter(curriculum_slide=slide, asset_id=slide.asset_id).first()
        request_index(origin or slide, requested=True)
        raise ExtractionError('incomplete', data.get('text_extraction'))
    try:
        result = extract_document(content_file_url(slide), slide.file_type)
    except ExtractionError as exc:
        SlideContent.objects.filter(slide=slide).update(extraction_error=str(exc))
        raise
    except Exception:
        SlideContent.objects.filter(slide=slide).update(extraction_error=ERRORS['source_unavailable'])
        raise ExtractionError('source_unavailable') from None
    result['text_extraction']['source_key'] = key
    with transaction.atomic():
        current_slide = Slide.objects.select_for_update().get(pk=slide.pk)
        if source_key(current_slide) != key:
            raise ExtractionError('source_unavailable')
        content = SlideContent.objects.select_for_update().get(slide=slide)
        data = dict(content.content_data or {})
        old_pages = {p.get('page_number'): p for p in data.get('pages') or []}
        data.update(result)
        data['pages'] = [{**old_pages.get(p['page_number'], {}), **p} for p in result['pages']]
        data['text'] = content_text(result)
        content.content_data = data
        content.extraction_error = '' if is_complete(data) else ERRORS['incomplete']
        content.extracted_at = timezone.now()
        # is_extracted retains its existing meaning: rendered page images are ready.
        content.save(update_fields=['content_data', 'extraction_error', 'extracted_at', 'updated_at'])
    if not is_complete(data):
        raise ExtractionError('incomplete', data['text_extraction'])
    return data
