"""Local page rendering shared by both readers and the worker."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import hashlib
import logging
import math
import sys

logger = logging.getLogger(__name__)

RENDER_ERRORS = {
    'office_unavailable': 'PowerPoint and Word conversion is unavailable on the server. Ask the administrator to enable LibreOffice, or upload a PDF exported from the original document.',
    'office_timeout': 'The document took too long to convert. Try exporting it as a PDF and uploading that file.',
    'office_failed': 'The document could not be converted. Check that it opens correctly, or export it as a PDF and upload that file.',
    'render_failed': 'The document could not be rendered. Check the original file and retry.',
    'render_memory': 'The server has insufficient memory to render this document safely. Your original is saved. Processing will retry; if this repeats, the server needs more memory.',
    'render_timeout': 'Rendering exceeded the time limit. Your original is saved. Retry processing or upload a PDF exported from the original.',
}


class DocumentRenderingError(RuntimeError):
    """Only predefined, safe messages cross the processing/status boundary."""
    def __init__(self, code):
        self.code = code if code in RENDER_ERRORS else 'render_failed'
        super().__init__(RENDER_ERRORS[self.code])


def rendering_failure(exc):
    if isinstance(exc, DocumentRenderingError):
        return exc.code, str(exc)
    from .document_extraction import ExtractionError
    if isinstance(exc, ExtractionError):
        return exc.code, str(exc)
    return 'render_failed', RENDER_ERRORS['render_failed']


def office_executable():
    executable = shutil.which('soffice') or shutil.which('libreoffice')
    if executable:
        return executable
    for candidate in (r'C:\Program Files\LibreOffice\program\soffice.exe',
                      r'C:\Program Files (x86)\LibreOffice\program\soffice.exe'):
        if Path(candidate).is_file():
            return candidate
    raise DocumentRenderingError('office_unavailable')


def office_to_pdf(source, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # An isolated profile prevents concurrent jobs from attaching to an existing GUI process.
    try:
        with tempfile.TemporaryDirectory(prefix='emby-office-') as profile:
            result = subprocess.run([
                office_executable(), f'-env:UserInstallation={Path(profile).resolve().as_uri()}',
                '--headless', '--convert-to', 'pdf', '--outdir', str(output), str(Path(source).resolve()),
            ], capture_output=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired:
        raise DocumentRenderingError('office_timeout') from None
    except OSError:
        raise DocumentRenderingError('office_unavailable') from None
    pdf = output / (Path(source).stem + '.pdf')
    if result.returncode or not pdf.is_file() or pdf.stat().st_size == 0:
        # Converter output can include filenames/document text. Log only safe diagnostics.
        logger.warning('Office conversion failed: exit_code=%s pdf_created=%s', result.returncode, pdf.is_file())
        raise DocumentRenderingError('office_failed')
    return str(pdf)


def render_document(source, file_type, output, *, ocr=False, progress=None, memory_mb=None):
    """Return ordered page images and text. Never substitute text-only fake slides."""
    import fitz
    from .document_extraction import extract_page, extraction_summary
    kind = file_type.lower().lstrip('.')
    if kind not in {'pdf', 'ppt', 'pptx', 'docx'}:
        raise ValueError('Supported formats: PDF, PPT, PPTX and DOCX.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pdf = str(source) if kind == 'pdf' else office_to_pdf(source, output / 'pdf')
    if memory_mb is not None and sys.platform.startswith('linux'):
        # Limit additional native allocations after imports and Office conversion.
        # RSS is also monitored by the parent, including converter descendants.
        import resource
        stat = Path('/proc/self/statm').read_text().split()
        page_size = os.sysconf('SC_PAGE_SIZE')
        virtual, resident = (int(value) * page_size for value in stat[:2])
        ceiling = virtual + max(16 * 1024**2, memory_mb * 1024**2 - resident)
        resource.setrlimit(resource.RLIMIT_AS, (ceiling, ceiling))
    images, texts, pages = [], [], []
    with fitz.open(pdf) as document:
        if document.needs_pass:
            raise ValueError('Password-protected documents must be unlocked before uploading.')
        if len(document) == 0:
            raise ValueError('The document has no readable pages.')
        for index, page in enumerate(document, 1):
            path = output / f'page_{index:04d}.jpg'
            # Compressed file size says little about raster memory. A giant page
            # must never allocate a giant bitmap, even when the PDF is only 1 MB.
            width, height = page.rect.width, page.rect.height
            scale = min(150 / 72, 1920 / max(width, height), math.sqrt(2_000_000 / (width * height)))
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
            pixmap.save(str(path), jpg_quality=85)
            del pixmap
            images.append(str(path))
            extracted = extract_page(page, ocr=ocr)
            pages.append(extracted)
            texts.append(extracted['text'])
            # MuPDF otherwise retains decoded images across pages (up to 256 MB).
            fitz.TOOLS.store_shrink(100)
            if progress:
                progress('rendering', index, len(document))
    with Path(source).open('rb') as stream:
        fingerprint = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'pdf_path': pdf, 'image_paths': images, 'page_texts': texts, 'page_count': len(images),
            'pages': pages, 'text_extraction': extraction_summary(pages, fingerprint)}


def cleanup_render(result):
    """Delete only a render directory created by this module's callers."""
    directory = result.get('temp_dir') if result else None
    if not directory:
        return
    path = Path(directory).resolve()
    if path.parent != Path(tempfile.gettempdir()).resolve() or not path.name.startswith('emby-render-'):
        raise ValueError('Refusing to clean a directory outside the render workspace.')
    shutil.rmtree(path, ignore_errors=True)
