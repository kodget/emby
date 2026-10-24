from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from curriculum.media_inventory import reconcile
from curriculum.models import MediaAsset, SlideContent
from curriculum.tests.test_bank_recovery import BankFixture


class MediaInventoryTests(BankFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()
        self.old = self.now-timedelta(days=3)
        self.document = dict(version=1, prefix='emby/', complete=True,
                             exported_at=self.now.isoformat(), resources=[])

    def provider(self, name, **changes):
        row = dict(public_id=f'emby/{name}', resource_type='image', delivery_type='authenticated',
                   created_at=self.old.isoformat())
        row.update(changes); self.document['resources'].append(row)
        return row

    def asset(self, name, **changes):
        asset = MediaAsset.objects.create(class_group=self.user.profile.class_group,
            public_id=f'emby/{name}', resource_type='image', **changes)
        MediaAsset.objects.filter(pk=asset.pk).update(created_at=self.old)
        return asset

    def report(self):
        return reconcile(self.document, now=self.now)

    def test_foreign_keys_and_json_page_assets_are_retained_as_referenced(self):
        original, page = self.asset('original'), self.asset('page')
        self.slide.asset = original; self.slide.save()
        SlideContent.objects.filter(slide=self.slide).update(content_data={'pages': [{'asset_id': str(page.pk)}]})
        self.provider('original'); self.provider('page')
        report = self.report()
        self.assertEqual(report['counts']['referenced'], 2)
        self.assertEqual(report['counts']['registered_unreferenced'], 0)
        self.assertIn(f'SlideContent:{self.slide.pk}', report['categories']['referenced'][1]['references'])

    def test_registered_and_unregistered_old_assets_are_distinct_from_recent_uploads(self):
        self.asset('unused'); self.provider('unused'); self.provider('not-registered')
        self.provider('new', created_at=(self.now-timedelta(minutes=5)).isoformat())
        report = self.report()
        self.assertEqual(report['counts']['registered_unreferenced'], 1)
        self.assertEqual(report['counts']['provider_only'], 1)
        self.assertEqual(report['counts']['recent_unreferenced'], 1)

    def test_partial_export_does_not_claim_missing_files_and_new_registrations_are_separate(self):
        self.asset('absent')
        self.assertEqual(self.report()['counts']['missing_at_provider'], 1)
        self.document['complete'] = False
        self.assertEqual(self.report()['counts']['missing_at_provider'], 0)
        self.assertEqual(self.report()['counts']['not_in_partial_export'], 1)
        asset = self.asset('after-export')
        MediaAsset.objects.filter(pk=asset.pk).update(created_at=self.now+timedelta(seconds=1))
        self.assertEqual(self.report()['counts']['created_after_export'], 1)

    def test_provider_identity_includes_resource_and_delivery_type(self):
        self.asset('same')
        self.provider('same', delivery_type='upload')
        self.provider('same', resource_type='raw')
        report = self.report()
        self.assertEqual(report['counts']['missing_at_provider'], 1)
        self.assertEqual(report['counts']['provider_only'], 2)
        self.assertEqual(report['counts']['non_authenticated'], 1)

    def test_malformed_page_references_prevent_unused_classification(self):
        self.asset('unused'); self.provider('unused')
        for pages in ({'not': 'an array'}, [{'asset_id': 'bad-id'}], ['bad page']):
            with self.subTest(pages=pages):
                SlideContent.objects.filter(slide=self.slide).update(content_data={'pages': pages})
                report = self.report()
                self.assertEqual(report['counts']['registered_unreferenced'], 0)
                self.assertEqual(report['counts']['uncertain_references'], 1)
                self.assertTrue(report['malformed_page_references'])

    def test_report_has_no_writes_provider_calls_or_secret_urls_and_has_stable_fingerprint(self):
        self.asset('unused'); self.provider('unused')
        self.document['resources'][0]['secure_url'] = 'https://storage.invalid/?signature=secret'
        with CaptureQueriesContext(connection) as queries, patch('cloudinary.uploader.destroy') as destroy, \
                patch('cloudinary.uploader.upload') as upload:
            report = self.report()
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE')) for q in queries))
        destroy.assert_not_called(); upload.assert_not_called()
        self.assertNotIn('secret', json.dumps(report))
        self.assertEqual(self.report()['fingerprint'], report['fingerprint'])
        self.slide.asset = MediaAsset.objects.get(); self.slide.save()
        self.assertNotEqual(self.report()['fingerprint'], report['fingerprint'])

    def test_bad_scope_dates_duplicate_identities_and_grace_period_fail_closed(self):
        self.provider('one')
        for change in ({'prefix': ''}, {'prefix': 'unrelated/'}, {'complete': 'true'},
                       {'exported_at': '2026-10-20'}, {'resources': [self.document['resources'][0]]*2},
                       {'resources': [{**self.document['resources'][0], 'public_id': 'other/x'}]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                reconcile({**self.document, **change}, now=self.now)
        with self.assertRaises(ValueError): reconcile(self.document, now=self.now, older_than_hours=0)

    def test_command_reads_explicit_file_and_has_no_apply_mode(self):
        self.provider('one')
        with tempfile.TemporaryDirectory(prefix='emby-inventory-') as folder:
            path = Path(folder)/'inventory.json'; path.write_text(json.dumps(self.document), encoding='utf-8')
            output = StringIO()
            call_command('reconcile_media_inventory', inventory=str(path), stdout=output)
            self.assertTrue(json.loads(output.getvalue())['read_only'])
            path.write_text('{', encoding='utf-8')
            with self.assertRaises(CommandError):
                call_command('reconcile_media_inventory', inventory=str(path), stdout=StringIO())
        self.assertFalse(MediaAsset.objects.exists())
