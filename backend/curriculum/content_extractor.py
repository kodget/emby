"""Compatibility entry points backed by complete, page-aware document extraction."""
from .services.document_extraction import ExtractionError, extract_document, is_complete, normalize_format


def _pages(source, kind):
    result = extract_document(source, kind)
    if not is_complete(result):
        raise ExtractionError('incomplete', result['text_extraction'])
    return result['pages']


def extract_text_from_pdf(source):
    return _pages(source, 'pdf')


def extract_text_from_pptx(source):
    return _pages(source, 'pptx')


def extract_text_from_docx(source):
    return _pages(source, 'docx')


def extract_text_from_slide(source, file_type):
    kind = normalize_format(file_type)
    try:
        return {'pdf': extract_text_from_pdf, 'pptx': extract_text_from_pptx,
                'docx': extract_text_from_docx}.get(kind, lambda value: _pages(value, kind))(source)
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError('invalid_document') from None


def get_slide_full_text(source, file_type, max_chars=None):
    combined = '\n\n'.join(f"[Page {p['page_number']}]\n{p['text']}" for p in
                           extract_text_from_slide(source, file_type) if p['text'].strip())
    if max_chars is not None and len(combined) > max_chars:
        raise ExtractionError('text_limit')
    return combined
