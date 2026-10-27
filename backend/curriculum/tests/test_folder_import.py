from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
import os
import tempfile
import uuid
from unittest.mock import patch

import fitz
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, SimpleTestCase
from django.utils import timezone

from accounts.models import School, ClassGroup
from curriculum.models import Subject, Block, SubBlock, Slide, SlideContent, SlideProcessingStatus, MediaAsset
from curriculum.management.commands import import_slide_folder as importer


def pdf(path, text='A useful lecture'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 60), text)
        doc.save(path)


class FolderImportTests(TransactionTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'Anatomy'
        pdf(self.root / 'Third block' / 'Neuro' / 'Lecture.pdf')
        pdf(self.root / 'First block' / 'Upper Limb' / 'Palmar spaces- Prof. Mbaka')
        school = School.objects.create(name='Import school')
        self.group = ClassGroup.objects.create(school=school, set_name='Import class', code='135791')
        self.user = get_user_model().objects.create_user('importer', email='importer@example.test', is_staff=True, is_superuser=True)
        self.user.profile.class_group = self.group; self.user.profile.save()
        self.subject = Subject.objects.create(id='anatomy', name='Anatomy', class_group=self.group)
        self.block = Block.objects.create(id='legacy-block', name='Third block', subject=self.subject)
        self.sub = SubBlock.objects.create(id='neuro', name='Neuroanatomy', block=self.block)

    def command(self, **kwargs):
        return call_command('import_slide_folder', str(self.root), class_code=self.group.code,
                            owner_email=self.user.email, state_dir=str(self.base/'state'), workers=1,
                            stdout=StringIO(), **kwargs)

    def upload(self, *args, **kwargs):
        return MediaAsset.objects.create(class_group=self.group, public_id=f'fixture/{uuid.uuid4()}',
                                         resource_type='raw', format='pdf')

    def process(self, slide_id, *, token, local_file_path):
        slide = Slide.objects.get(pk=slide_id)
        page = MediaAsset.objects.create(class_group=self.group, public_id=f'page/{uuid.uuid4()}', resource_type='image')
        SlideContent.objects.update_or_create(slide=slide, defaults={'is_extracted': True, 'content_data': {
            'pages': [{'page_number': 1, 'asset_id': str(page.pk), 'text': 'Study material'}],
            'text_extraction': {'source_sha256': importer.fingerprint(local_file_path)}}})
        Slide.objects.filter(pk=slide.pk).update(page_count=1)
        SlideProcessingStatus.objects.filter(slide=slide).update(status='indexing', processing_lease_until=None)
        return {'success': True}

    def test_dry_run_does_not_create_content_or_upload(self):
        with patch.object(importer, 'upload_asset') as upload:
            self.command()
        upload.assert_not_called()
        self.assertEqual(Slide.objects.count(), 0)
        self.assertEqual(Block.objects.count(), 1)

    def test_full_hierarchy_private_pages_and_resume_without_duplicates(self):
        with patch.object(importer, 'upload_asset', side_effect=self.upload) as upload, patch.object(importer, 'process', side_effect=self.process) as render:
            self.command(apply=True)
            self.command(apply=True)
        self.assertEqual(upload.call_count, 2)
        self.assertEqual(render.call_count, 2)
        self.assertEqual(Slide.objects.count(), 2)
        self.assertEqual(Block.objects.count(), 2)
        self.block.refresh_from_db()
        self.assertEqual(self.block.order, 3)
        for slide in Slide.objects.all():
            self.assertEqual(slide.subject, self.subject)
            self.assertEqual(slide.topic.block, slide.block)
            self.assertEqual(slide.topic.sub_block, slide.sub_block)
            self.assertTrue(importer.reading_ready(slide))

    def test_active_processing_is_not_overwritten(self):
        slide = Slide.objects.create(id='old', title='Lecture', class_group=self.group, sub_block=self.sub)
        SlideProcessingStatus.objects.create(slide=slide, processing_lease_until=timezone.now()+timedelta(minutes=5))
        with patch.object(importer, 'upload_asset') as upload:
            with self.assertRaises(CommandError):
                self.command(apply=True, only='Neuro')
        upload.assert_not_called()
        slide.refresh_from_db(); self.assertIsNone(slide.asset_id)

    def test_owner_cannot_import_into_another_class(self):
        self.user.profile.class_group = None; self.user.profile.save()
        with self.assertRaises(CommandError):
            self.command(apply=True)
        self.assertFalse(Slide.objects.exists())

    def test_completed_label_does_not_make_missing_pages_ready(self):
        slide = Slide.objects.create(id='missing', title='Missing', class_group=self.group, page_count=4, generation_status='completed')
        SlideContent.objects.create(slide=slide, is_extracted=True, content_data={'pages': []})
        self.assertFalse(importer.reading_ready(slide))

    def test_verification_includes_failed_imports_instead_of_silently_skipping_them(self):
        manifest = self.base / 'manifest.json'
        manifest.write_text(json.dumps({'class_id': self.group.pk, 'documents': {
            'Third block/Neuro/Unfinished.pdf': {'status': 'failed', 'slide_id': 'unfinished'}
        }}))
        with self.assertRaises(CommandError):
            call_command('verify_slide_import', str(manifest), owner_email=self.user.email, stdout=StringIO())
        report = json.loads(manifest.with_name('verification.json').read_text())
        self.assertEqual(len(report), 1)
        self.assertFalse(report[0]['verified'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser)


class FolderDiscoveryTests(SimpleTestCase):
    def test_large_poster_scan_is_reduced_without_losing_pages_or_text(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'Subject'
            path = root / 'Block' / 'Sub-block' / 'Scan.pdf'
            path.parent.mkdir(parents=True)
            scan = Path(directory) / 'scan.png'
            Image.frombytes('RGB', (1800, 2600), os.urandom(1800*2600*3)).save(scan)
            with fitz.open() as doc:
                page = doc.new_page(width=2140, height=3102)
                page.insert_image(page.rect, filename=str(scan))
                page.insert_text((30, 50), 'Preserve the lecture text')
                doc.save(path)
            before = importer.fingerprint(path)
            with patch.object(importer, 'STORE_LIMIT', 3 * 1024**2):
                prepared, kind = importer.prepare(importer.discover(root)[0], Path(directory)/'cache')
            self.assertEqual(kind, 'pdf')
            self.assertLessEqual(prepared.stat().st_size, 3 * 1024**2)
            self.assertEqual(importer.fingerprint(path), before)
            with fitz.open(prepared) as checked:
                self.assertEqual(len(checked), 1)
                self.assertIn('Preserve the lecture text', checked[0].get_text())

    def test_missing_pdf_extension_is_detected_without_changing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'Subject'
            path = root / 'Block' / 'Sub-block' / 'Lecture. Lecturer'
            pdf(path)
            before = path.read_bytes()
            entries = importer.discover(root)
            prepared, kind = importer.prepare(entries[0], Path(directory)/'cache')
            self.assertEqual(kind, 'pdf'); self.assertEqual(prepared, path)
            self.assertEqual(path.read_bytes(), before)

    def test_unknown_file_is_reported_instead_of_silently_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'Block' / 'Sub-block' / 'Broken.file'
            path.parent.mkdir(parents=True); path.write_bytes(b'broken')
            with self.assertRaises(CommandError): importer.discover(root)
