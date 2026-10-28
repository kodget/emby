"""Resumable, class-scoped import of Subject/Block/Sub-block/document folders.

Dry run by default. Originals stay untouched. The manifest contains storage IDs,
never credentials or signed URLs. Reading readiness is checked from real pages.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import threading

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import ClassGroup
from curriculum.models import Subject, Block, SubBlock, Topic, Slide, SlideContent, SlideProcessingStatus, MediaAsset
from curriculum.private_media import upload_asset
from curriculum.slide_processing import reserve, process
from curriculum.slide_uploads import validate_slide_file

STORE_LIMIT = 9 * 1024**2  # Leave headroom below the current provider's 10 MB object limit.
FORMATS = {'pdf', 'ppt', 'pptx', 'docx'}


def fingerprint(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalized(value):
    return re.sub(r'[^\w]', '', value.casefold())


def stable_id(prefix, *parts):
    digest = hashlib.sha256('/'.join(map(str, parts)).encode()).hexdigest()[:24]
    return f'{prefix}_{digest}'


def discover(root):
    entries = []
    for path in sorted(root.glob('*/*/*'), key=lambda p: str(p).casefold()):
        if not path.is_file() or any(p.startswith('.') for p in path.relative_to(root).parts):
            continue
        kind = path.suffix.lower().lstrip('.')
        # A missing extension must not silently drop a valid lecture PDF.
        if kind not in FORMATS:
            with path.open('rb') as stream:
                if not stream.read(8).startswith(b'%PDF-'):
                    raise CommandError(f'Unrecognized document: {path.relative_to(root)}')
            kind, title = 'pdf', path.name
        else:
            title = path.stem
        title = re.sub(r'\s+', ' ', title.replace('_', ' ')).strip().rstrip('.')
        if len(title) > 200:
            raise CommandError(f'Document title exceeds 200 characters: {path.name}')
        entries.append({'path': str(path), 'relative': path.relative_to(root).as_posix(),
                        'block': path.parent.parent.name, 'sub_block': path.parent.name,
                        'title': title, 'kind': kind, 'bytes': path.stat().st_size,
                        'original_sha256': fingerprint(path)})
    if not entries:
        raise CommandError('No documents found at Subject/Block/Sub-block/file depth.')
    return entries


def prepare(entry, cache):
    """Use original bytes when possible; make a smaller PDF copy for large originals."""
    path, kind = Path(entry['path']), entry['kind']
    if path.stat().st_size <= STORE_LIMIT:
        with path.open('rb') as stream:
            validate_slide_file(File(stream, name=f'document.{kind}'))
        return path, kind
    import fitz
    from curriculum.services.document_rendering import office_to_pdf
    folder = cache / entry['original_sha256']
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'upload.pdf'
    if target.is_file() and target.stat().st_size <= STORE_LIMIT:
        with fitz.open(target) as checked:
            if checked.page_count:
                return target, 'pdf'
    source = path if kind == 'pdf' else Path(office_to_pdf(path, folder / 'converted'))
    with fitz.open(source) as original:
        count = original.page_count
        text = [page.get_text() for page in original]
        # Scan PDFs may have enormous page boxes but only 72 DPI images. DPI
        # rewriting does not reliably downsample these; bound image pixels
        # directly while leaving text, vectors and page geometry untouched.
        from PIL import Image
        for edge, quality in ((2800, 90), (2400, 85), (2100, 80)):
            with fitz.open(source) as copy:
                seen = set()
                for page in copy:
                    for info in page.get_images(full=True):
                        xref, mask, width, height = info[:4]
                        if xref in seen or mask or max(width, height) < 600:
                            continue
                        seen.add(xref)
                        with Image.open(BytesIO(copy.extract_image(xref)['image'])) as image:
                            # Keep transparency and monochrome diagrams intact.
                            if image.mode not in {'RGB', 'L'}:
                                continue
                            image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
                            encoded = BytesIO()
                            image.save(encoded, format='JPEG', quality=quality, optimize=True)
                            page.replace_image(xref, stream=encoded.getvalue())
                candidate = folder / f'prepared-{edge}.pdf'
                # replace_image adds a temporary resource entry. Clean unused
                # resources before collecting garbage so images are not doubled.
                copy.save(candidate, garbage=4, clean=True, deflate=True, use_objstms=1)
            with fitz.open(candidate) as check:
                if check.page_count != count or [page.get_text() for page in check] != text:
                    raise ValueError('Prepared PDF did not preserve every page and its text.')
            if candidate.stat().st_size <= STORE_LIMIT:
                candidate.replace(target)
                return target, 'pdf'
    raise ValueError('This document still exceeds the storage limit after preparing a PDF copy.')


def reading_ready(slide):
    content = SlideContent.objects.filter(slide=slide).first()
    pages = (content.content_data or {}).get('pages', []) if content else []
    if not pages or len(pages) != slide.page_count:
        return False
    if [p.get('page_number') for p in pages] != list(range(1, len(pages)+1)):
        return False
    ids = [p.get('asset_id') for p in pages]
    if not all(ids) or len(set(ids)) != len(ids):
        return False
    return MediaAsset.objects.filter(pk__in=ids, class_group_id=slide.class_group_id,
                                    delivery_type='authenticated').count() == len(pages)


class Command(BaseCommand):
    help = 'Import a complete subject folder into an explicit class; dry run unless --apply.'

    def add_arguments(self, parser):
        parser.add_argument('root')
        parser.add_argument('--class-code', required=True)
        parser.add_argument('--owner-email', required=True)
        parser.add_argument('--state-dir', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--prepare-only', action='store_true')
        parser.add_argument('--workers', type=int, default=2)
        parser.add_argument('--limit', type=int)
        parser.add_argument('--only', default='')

    def handle(self, *args, **options):
        root = Path(options['root']).resolve()
        if not root.is_dir():
            raise CommandError('The subject folder does not exist.')
        entries = discover(root)
        if options['only']:
            entries = [e for e in entries if options['only'].casefold() in e['relative'].casefold()]
        if options['limit']:
            entries = entries[:options['limit']]
        state_dir = Path(options['state_dir']).resolve()
        state_dir.mkdir(parents=True, exist_ok=True)
        cache = state_dir / 'prepared'
        if options['prepare_only']:
            for entry in entries:
                path, kind = prepare(entry, cache)
                self.stdout.write(f"PREPARED {entry['relative']} -> {kind}, {path.stat().st_size / 1024**2:.2f} MB")
            return
        group = ClassGroup.objects.get(code=options['class_code'], is_active=True)
        owner = get_user_model().objects.get(email__iexact=options['owner_email'], is_active=True)
        if owner.profile.class_group_id != group.pk:
            raise CommandError('The upload owner must belong to the selected class.')
        from curriculum.class_access import content_admin
        if not (content_admin(owner) or owner.profile.is_class_head or
                owner.profile.class_role == 'material_uploader' or
                'SLIDE_UPLOADER' in owner.profile.class_capabilities):
            raise CommandError('The selected owner cannot upload class materials.')
        subjects = list(Subject.objects.filter(class_group=group, name__iexact=root.name))
        if len(subjects) > 1:
            raise CommandError('Multiple matching subjects exist in this class; resolve them before importing.')
        subject = subjects[0] if subjects else None
        existing = list(Slide.objects.filter(class_group=group).select_related('sub_block__block', 'content'))
        manifest_path = state_dir / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
        if manifest and (manifest.get('root') != str(root) or manifest.get('class_id') != group.pk):
            raise CommandError('This manifest belongs to a different folder or class.')
        manifest.setdefault('root', str(root)); manifest.setdefault('class_id', group.pk)
        records = manifest.setdefault('documents', {})
        for entry in entries:
            saved = records.get(entry['relative'], {})
            if saved and saved.get('original_sha256') != entry['original_sha256']:
                raise CommandError(f"Source changed since import: {entry['relative']}. Review before replacing saved content.")
            candidates = [s for s in existing if normalized(s.title) == normalized(entry['title']) and
                          s.sub_block and normalized(s.sub_block.name).replace('neuroanatomy', 'neuro') == normalized(entry['sub_block']).replace('neuroanatomy', 'neuro')]
            if len(candidates) > 1:
                raise CommandError(f"Multiple existing slides match {entry['relative']}; refusing to guess.")
            entry['slide_id'] = saved.get('slide_id') or (candidates[0].pk if candidates else stable_id('slide_import', group.pk, root.name, entry['relative']))
        self.stdout.write(f"Class: {group.school.name} / {group.set_name}; Subject: {root.name}; Documents: {len(entries)}")
        for entry in entries:
            exists = any(s.pk == entry['slide_id'] for s in existing)
            self.stdout.write(f"{'REUSE' if exists else 'NEW'} {entry['relative']}")
        if not options['apply']:
            self.stdout.write('Dry run only. No database or storage changes made.')
            return
        if not subject:
            subject = Subject.objects.create(id=stable_id('subject', group.pk, root.name), name=root.name, class_group=group)
        parents = {}
        for entry in entries:
            key = (entry['block'], entry['sub_block'])
            if key in parents:
                continue
            # Legacy opaque IDs need not match names. Prefer the populated matching block.
            block = Block.objects.filter(subject=subject, name__iexact=key[0]).annotate(children=Count('sub_blocks')).order_by('-children', 'pk').first()
            order = {'first block': 1, 'second block': 2, 'third block': 3}.get(key[0].casefold())
            if block is None:
                block = Block.objects.create(id=stable_id('block', subject.pk, key[0]), subject=subject, name=key[0], order=order or 0)
            elif order is not None and block.order != order:
                block.order = order
                block.save(update_fields=['order'])
            names = [key[1], 'Neuroanatomy'] if key[1].casefold() == 'neuro' else [key[1]]
            sub = next((s for s in SubBlock.objects.filter(block=block) if s.name.casefold() in [n.casefold() for n in names]), None)
            if sub is None:
                sub = SubBlock.objects.create(id=stable_id('sub', block.pk, key[1]), block=block, name=key[1])
            parents[key] = (block.pk, sub.pk)
        lock = threading.Lock()

        def record(entry, **result):
            with lock:
                records[entry['relative']] = {**records.get(entry['relative'], {}), **entry, **result}
                manifest['updated_at'] = timezone.now().isoformat()
                temporary = manifest_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
                temporary.replace(manifest_path)

        def run(entry):
            connections.close_all()
            try:
                path, kind = prepare(entry, cache)
                digest = fingerprint(path)
                slide = Slide.objects.filter(pk=entry['slide_id'], class_group=group).first()
                if slide is None and Slide.objects.filter(pk=entry['slide_id']).exists():
                    raise ValueError('The saved slide identity belongs to another class.')
                status = SlideProcessingStatus.objects.filter(slide=slide).first() if slide else None
                if status and status.processing_lease_until and status.processing_lease_until > timezone.now():
                    record(entry, status='busy', detail='Another worker owns the current attempt.')
                    return 'busy'
                old = records.get(entry['relative'], {})
                data = getattr(getattr(slide, 'content', None), 'content_data', {}) or {}
                matches = data.get('text_extraction', {}).get('source_sha256') == digest
                asset = slide.asset if slide and slide.asset_id and (matches or old.get('upload_sha256') == digest) else None
                if asset is None:
                    with path.open('rb') as stream:
                        asset = upload_asset(File(stream, name=f"{entry['title']}.{kind}"), class_group=group, uploaded_by=owner,
                                             resource_type='raw', folder='emby/originals', timeout=180)
                block_id, sub_id = parents[(entry['block'], entry['sub_block'])]
                with transaction.atomic():
                    current = Slide.objects.select_for_update().filter(pk=entry['slide_id']).first()
                    current_state = SlideProcessingStatus.objects.filter(slide=current).first() if current else None
                    if current_state and current_state.processing_lease_until and current_state.processing_lease_until > timezone.now():
                        record(entry, status='busy', detail='Another worker started processing this document.')
                        return 'busy'
                    topic = Topic.objects.filter(sub_block_id=sub_id, name__iexact=entry['title']).order_by('pk').first()
                    if topic is None:
                        topic = Topic.objects.create(id=stable_id('topic', group.pk, entry['relative']), name=entry['title'], block_id=block_id, sub_block_id=sub_id)
                    elif topic.block_id != block_id:
                        topic.block_id = block_id; topic.save(update_fields=['block'])
                    slide, _ = Slide.objects.update_or_create(pk=entry['slide_id'], defaults={
                        'class_group': group, 'subject': subject, 'block_id': block_id, 'sub_block_id': sub_id,
                        'topic': topic, 'title': entry['title'], 'asset': asset, 'file': None, 'file_url': '',
                        'file_type': kind, 'uploaded_by': owner})
                    # Manual folder imports prepare reading first. AI features
                    # are requested explicitly by a class member and reused.
                    content, _ = SlideContent.objects.get_or_create(slide=slide)
                    if (content.content_data or {}).get('ai_generation_mode') != 'on_demand':
                        from curriculum.ai_policy import defer_automatic_ai
                        defer_automatic_ai(slide)
                record(entry, status='uploaded', upload_sha256=digest, upload_bytes=path.stat().st_size,
                       prepared_copy=str(path) if path != Path(entry['path']) else None)
                # Existing pages are reusable only when every page has private storage
                # and the rendered source hash matches the file being registered.
                if matches and reading_ready(slide):
                    from curriculum.services.document_extraction import source_key
                    content = slide.content
                    content.content_data['text_extraction']['source_key'] = source_key(slide)
                    content.save(update_fields=['content_data'])
                    result = {'success': True, 'reused_pages': True}
                else:
                    token = reserve(slide.pk, manual=True)
                    if not token:
                        record(entry, status='busy', upload_sha256=digest)
                        return 'busy'
                    result = process(slide.pk, token=token, local_file_path=str(path))
                slide.refresh_from_db()
                ready = reading_ready(slide)
                record(entry, status='ready' if ready else 'failed', upload_sha256=digest,
                       page_count=slide.page_count, detail=result.get('error', ''),
                       reader_path=f'/read/{block_id}/{slide.pk}')
                return 'ready' if ready else 'failed'
            except Exception as exc:
                detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                record(entry, status='failed', detail=detail)
                return 'failed'
            finally:
                connections.close_all()

        counts = {}
        with ThreadPoolExecutor(max_workers=max(1, min(3, options['workers']))) as pool:
            futures = {pool.submit(run, entry): entry for entry in entries}
            for number, future in enumerate(as_completed(futures), 1):
                state = future.result(); counts[state] = counts.get(state, 0)+1
                self.stdout.write(f"[{number}/{len(entries)}] {state.upper()} {futures[future]['relative']}")
                self.stdout.flush()
        self.stdout.write(f'Import results: {counts}. Manifest: {manifest_path}')
        if counts.get('failed') or counts.get('busy'):
            raise CommandError('Some documents need another pass; rerun the same command to resume.')
