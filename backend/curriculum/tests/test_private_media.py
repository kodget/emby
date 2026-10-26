from io import StringIO
from unittest.mock import patch, Mock
from urllib.parse import urlsplit, parse_qs

import requests
from contextlib import redirect_stdout
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import School, ClassGroup, ClassRole
from curriculum.models import Subject, Block, Slide, SlideContent, MediaAsset, Material, SlideDeck, SpotStation
from curriculum.private_media import upload_asset, asset_url, page_payloads, content_file_url
from curriculum.services.slide_conversion_pipeline import _download_from_cloudinary
from curriculum import views, upload_views


class PrivateMediaTests(TestCase):
    def setUp(self):
        school = School.objects.create(name='Private files')
        self.group = ClassGroup.objects.create(school=school, set_name='Year 1', code='567891')
        self.foreign = ClassGroup.objects.create(school=school, set_name='Year 2', code='567892')
        self.user = User.objects.create_user('private-uploader')
        self.user.profile.class_group = self.group
        self.user.profile.class_role = ClassRole.MATERIAL_UPLOADER
        self.user.profile.save()
        self.subject = Subject.objects.create(id='course', name='Course', class_group=self.group)
        self.block = Block.objects.create(id='module', name='Module', subject=self.subject)
        self.factory = APIRequestFactory()

    def asset(self, **kwargs):
        values = dict(class_group=self.group, uploaded_by=self.user, public_id='original/lecture.pdf',
                      resource_type='raw', format='pdf', delivery_type='authenticated')
        values.update(kwargs)
        return MediaAsset.objects.create(**values)

    def request(self, handler, *, method='get', data=None, action=None, multipart=False, **kwargs):
        request = getattr(self.factory, method)('/api/test/', data or {}, format='multipart' if multipart else 'json')
        force_authenticate(request, self.user)
        if action:
            handler = handler.as_view({method: action})
        return handler(request, **kwargs)

    def provider_result(self):
        return {'public_id': 'private/new.pdf', 'type': 'authenticated', 'resource_type': 'raw', 'bytes': 16}

    @patch('cloudinary.uploader.upload')
    def test_private_upload_preserves_identity_and_never_stores_delivery_url(self, upload):
        upload.return_value = self.provider_result()
        asset = upload_asset(SimpleUploadedFile('lecture.pdf', b'%PDF-1.7'), class_group=self.group, uploaded_by=self.user)
        self.assertEqual(upload.call_args.kwargs['type'], 'authenticated')
        self.assertFalse(upload.call_args.kwargs['overwrite'])
        self.assertNotIn('access_mode', upload.call_args.kwargs)
        asset.refresh_from_db()
        self.assertEqual(asset.public_id, 'private/new.pdf')
        self.assertEqual(asset.format, 'pdf')
        self.assertEqual(asset.class_group, self.group)

    @patch('cloudinary.uploader.upload')
    def test_public_provider_response_is_rejected(self, upload):
        upload.return_value = {**self.provider_result(), 'type': 'upload'}
        with self.assertRaisesRegex(ValueError, 'authenticated'):
            upload_asset(b'document', class_group=self.group)
        self.assertFalse(MediaAsset.objects.exists())

    @patch('cloudinary.uploader.upload')
    def test_classless_upload_never_calls_storage(self, upload):
        with self.assertRaises(ValueError):
            upload_asset(b'document', class_group=None)
        upload.assert_not_called()

    @patch('curriculum.private_media.time.time', return_value=1000)
    def test_raw_signed_url_expires_and_preserves_original_public_id(self, _):
        asset = self.asset()
        asset.refresh_from_db()
        url = urlsplit(asset_url(asset))
        params = parse_qs(url.query)
        self.assertTrue(url.path.endswith('/raw/download'))
        self.assertEqual(params['public_id'], ['original/lecture.pdf'])
        self.assertEqual(params['type'], ['authenticated'])
        self.assertEqual(params['expires_at'], ['1900'])
        self.assertTrue(params['signature'])
        self.assertNotIn('test-secret', url.query)

    def test_cached_pages_get_fresh_links_without_mutating_stored_json(self):
        asset = self.asset(resource_type='image', format='jpg')
        pages = [{'page_number': 1, 'asset_id': str(asset.pk), 'text': 'Source'}]
        with patch('curriculum.private_media.time.time', return_value=1000):
            first = page_payloads(pages, self.group.pk)
        with patch('curriculum.private_media.time.time', return_value=2000):
            second = page_payloads(pages, self.group.pk)
        self.assertNotEqual(first[0]['image_url'], second[0]['image_url'])
        self.assertNotIn('image_url', pages[0])
        self.assertEqual(first[0]['text'], 'Source')

    @patch('cloudinary.utils.private_download_url')
    def test_foreign_or_missing_page_assets_never_get_signed(self, sign):
        asset = self.asset(class_group=self.foreign)
        pages = [{'asset_id': str(asset.pk)}, {'asset_id': 'malformed'}]
        self.assertEqual([p['image_url'] for p in page_payloads(pages, self.group.pk)], ['', ''])
        sign.assert_not_called()

    @patch('cloudinary.utils.private_download_url')
    def test_foreign_slide_asset_cannot_bypass_class_with_bad_metadata(self, sign):
        slide = Slide.objects.create(id='bad', class_group=self.group, asset=self.asset(class_group=self.foreign))
        self.assertEqual(content_file_url(slide), '')
        sign.assert_not_called()

    def test_content_endpoint_resolves_pages_and_disables_response_caching(self):
        slide = Slide.objects.create(id='slide', class_group=self.group, subject=self.subject, block=self.block)
        asset = self.asset()
        SlideContent.objects.create(slide=slide, is_extracted=True,
            content_data={'pages': [{'page_number': 1, 'asset_id': str(asset.pk)}]})
        response = self.request(views.get_slide_content, slide_id=slide.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn('expires_at=', response.data['pages'][0]['image_url'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertNotIn('image_url', SlideContent.objects.get(slide=slide).content_data['pages'][0])

    def test_material_attachment_uses_registered_asset_not_client_url(self):
        asset = self.asset()
        response = self.request(views.MaterialViewSet, action='create', method='post', data={
            'title': 'Notes', 'material_type': 'pdf', 'subject': self.subject.pk, 'block': self.block.pk,
            'asset_id': str(asset.pk), 'file_url': 'https://other.test/forged.pdf'})
        self.assertEqual(response.status_code, 201, response.data)
        material = Material.objects.get(pk=response.data['id'])
        self.assertEqual(material.asset, asset)
        self.assertEqual(material.file_url, '')
        self.assertNotIn('other.test', response.data['file_url'])

    def test_foreign_asset_and_unregistered_url_cannot_be_attached(self):
        foreign = self.asset(class_group=self.foreign)
        for extra in ({'asset_id': str(foreign.pk)}, {'file_url': 'https://other.test/private.pdf'}):
            response = self.request(views.MaterialViewSet, action='create', method='post', data={
                'title': 'Invalid', 'material_type': 'pdf', 'subject': self.subject.pk, 'block': self.block.pk, **extra})
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Material.objects.exists())

    @patch('cloudinary.uploader.upload')
    def test_generic_upload_returns_private_registry_id(self, upload):
        upload.return_value = self.provider_result()
        response = self.request(upload_views.upload_file, method='post', multipart=True,
            data={'file': SimpleUploadedFile('notes.pdf', b'%PDF-1.7\ncontent'), 'type': '../../foreign'})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(MediaAsset.objects.filter(pk=response.data['asset_id'], class_group=self.group).exists())
        self.assertNotIn('foreign', upload.call_args.kwargs['folder'])
        self.assertIn('expires_at=', response.data['url'])

    @patch('curriculum.slide_uploads.dispatch_standalone_deck_processing')
    @patch('cloudinary.uploader.upload')
    def test_standalone_deck_uses_private_original(self, upload, process):
        upload.return_value = self.provider_result()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.request(views.SlideDeckViewSet, action='create', method='post', multipart=True,
                data={'file': SimpleUploadedFile('notes.pdf', b'%PDF-1.7\ncontent'), 'title': 'Deck'})
        self.assertEqual(response.status_code, 201, response.data)
        deck = SlideDeck.objects.get(pk=response.data['id'])
        self.assertTrue(deck.asset_id)
        self.assertFalse(deck.original_file)
        process.assert_called_once_with(deck.pk)

    @patch.dict('sys.modules', {'curriculum.services.converter': Mock()})
    @patch('requests.get', side_effect=requests.RequestException('https://test/?signature=secret'))
    def test_deck_processing_failure_does_not_store_or_log_delivery_tokens(self, get):
        deck = SlideDeck.objects.create(id='failure', title='Private deck', file_type='pdf',
                                       file_size=16, class_group=self.group, uploaded_by=self.user, asset=self.asset())
        with self.assertLogs('curriculum.deck_processing', level='ERROR') as captured:
            views.SlideDeckViewSet()._process_deck_async(deck)
        deck.refresh_from_db()
        self.assertEqual(deck.processing_status, 'failed')
        self.assertNotIn('secret', deck.processing_error)
        self.assertNotIn('secret', str(captured.output))

    @patch('curriculum.deck_processing.upload_asset', side_effect=RuntimeError('storage unavailable'))
    @patch('requests.get', return_value=Mock(status_code=200, iter_content=Mock(return_value=[b'%PDF-test'])))
    def test_failed_page_storage_cannot_mark_a_deck_complete(self, get, upload):
        converter = Mock()
        converter.SlideConverter.convert_document.return_value = (True, {
            'slide_images': ['rendered-page.jpg'], 'page_count': 1, 'pages': [{'text': 'Page'}],
        })
        deck = SlideDeck.objects.create(id='page-failure', title='Private deck', file_type='pdf',
                                       file_size=16, class_group=self.group, uploaded_by=self.user, asset=self.asset())
        with patch.dict('sys.modules', {'curriculum.services.converter': converter}), \
                patch('PIL.Image.open') as image, self.assertLogs('curriculum.deck_processing'):
            image.return_value.__enter__.return_value.size = (640, 480)
            views.SlideDeckViewSet()._process_deck_async(deck)
        deck.refresh_from_db()
        self.assertEqual(deck.processing_status, 'failed')
        self.assertFalse(deck.pages.exists())
        upload.assert_called_once()

    @patch('cloudinary.utils.cloudinary_url')
    @patch('requests.get')
    def test_failed_private_download_never_falls_back_to_public_storage(self, get, sign):
        get.return_value = Mock(status_code=401)
        with self.assertRaises(IOError) as caught:
            _download_from_cloudinary('https://api.cloudinary.com/v1_1/test/raw/download?signature=secret')
        sign.assert_not_called()
        self.assertEqual(get.call_count, 1)
        self.assertNotIn('secret', str(caught.exception))

    @patch('requests.get', side_effect=requests.RequestException('https://test/?signature=secret'))
    def test_network_errors_do_not_expose_signed_urls(self, get):
        with self.assertRaises(IOError) as caught:
            _download_from_cloudinary('https://api.cloudinary.com/v1_1/test/raw/download?signature=secret')
        self.assertNotIn('secret', str(caught.exception))

    @patch('curriculum.content_extractor.extract_text_from_pdf',
           side_effect=requests.RequestException('https://test/?signature=secret'))
    def test_text_extraction_failures_do_not_log_private_delivery_tokens(self, extract):
        from curriculum.content_extractor import extract_text_from_slide
        from curriculum.services.document_extraction import ExtractionError
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(ExtractionError) as caught:
            extract_text_from_slide('https://test/?signature=secret', 'pdf')
        self.assertNotIn('secret', str(caught.exception))
        self.assertNotIn('secret', output.getvalue())

    def test_storage_release_gate_blocks_legacy_urls_without_mutating_them(self):
        slide = Slide.objects.create(id='legacy', class_group=self.group, file_url='https://legacy.test/file.pdf')
        with self.assertRaises(CommandError):
            call_command('check_private_media', stdout=StringIO())
        slide.refresh_from_db()
        self.assertEqual(slide.file_url, 'https://legacy.test/file.pdf')

    def test_storage_release_gate_blocks_private_station_images_without_mutating_them(self):
        station = SpotStation.objects.create(
            id='legacy-private-station', subject=self.subject, prompt='Identify the structure',
            accepted_answers=['nerve'], image_url='https://legacy.test/station.jpg',
        )
        with self.assertRaises(CommandError):
            call_command('check_private_media', stdout=StringIO())
        station.refresh_from_db()
        self.assertEqual(station.image_url, 'https://legacy.test/station.jpg')

    def test_storage_release_gate_accepts_private_records_and_blocks_foreign_cache(self):
        slide = Slide.objects.create(id='private', class_group=self.group, asset=self.asset())
        SpotStation.objects.create(
            id='shared-catalogue-station', is_shared=True, prompt='Identify the structure',
            accepted_answers=['nerve'], image_url='https://legacy.test/shared-station.jpg',
        )
        call_command('check_private_media', stdout=StringIO())
        foreign = self.asset(class_group=self.foreign, public_id='foreign/page')
        SlideContent.objects.create(slide=slide, content_data={'pages': [{'asset_id': str(foreign.pk)}]})
        with self.assertRaises(CommandError):
            call_command('check_private_media', stdout=StringIO())
