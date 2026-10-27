"""Check imported reader responses and real storage delivery without printing signed URLs."""
import copy
import json
from pathlib import Path

import requests
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ClassRole, PlatformRole
from curriculum.models import Slide
from curriculum.views import get_slide_content
from curriculum.management.commands.import_slide_folder import reading_ready


class Command(BaseCommand):
    help = 'Verify page counts, class-scoped reader responses and first/last image delivery.'

    def add_arguments(self, parser):
        parser.add_argument('manifest')
        parser.add_argument('--owner-email', required=True)
        parser.add_argument('--limit', type=int)
        parser.add_argument('--media', action='store_true')
        parser.add_argument('--only', default='')

    def handle(self, *args, **options):
        manifest_path = Path(options['manifest']).resolve()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        user = get_user_model().objects.get(email__iexact=options['owner_email'])
        if user.profile.class_group_id != manifest['class_id']:
            raise CommandError('The verification user must belong to this class.')
        # Verify ordinary class-member visibility. These copies are never saved.
        student = copy.copy(user)
        student.is_staff = student.is_superuser = False
        student._state = copy.copy(user._state)
        student._state.fields_cache = dict(user._state.fields_cache)
        profile = copy.copy(user.profile)
        profile.platform_role = PlatformRole.USER; profile.class_role = ClassRole.STUDENT
        profile.class_capabilities = []; profile.class_head_verified = False
        student._state.fields_cache['profile'] = profile
        entries = list(manifest['documents'].items())
        if options['only']:
            entries = [(path, row) for path, row in entries if options['only'].casefold() in path.casefold()]
        if options['limit']:
            entries = entries[:options['limit']]
        results = []
        for path, entry in entries:
            if entry.get('status') != 'ready':
                results.append({'document': path, 'slide_id': entry.get('slide_id'),
                                'verified': False, 'import_status': entry.get('status')})
                self.stdout.write(f"FAILED {path}: import is not ready")
                continue
            slide = Slide.objects.get(pk=entry['slide_id'], class_group_id=manifest['class_id'])
            request = APIRequestFactory().get(f'/api/slides/{slide.pk}/content/')
            force_authenticate(request, user=student)
            response = get_slide_content(request, slide.pk)
            pages = response.data.get('pages', [])
            valid = response.status_code == 200 and reading_ready(slide) and len(pages) == slide.page_count
            media = []
            if valid and options['media']:
                for index in sorted({0, len(pages)-1}):
                    try:
                        with requests.get(pages[index]['image_url'], stream=True, timeout=(15, 45)) as result:
                            signature = next(result.iter_content(32), b'')
                            good = result.status_code == 200 and signature.startswith((b'\xff\xd8', b'\x89PNG', b'RIFF'))
                            media.append({'page': index+1, 'http': result.status_code, 'image': good})
                            valid = valid and good
                    except requests.RequestException:
                        media.append({'page': index+1, 'image': False}); valid = False
            results.append({'document': path, 'slide_id': slide.pk, 'reader_path': entry['reader_path'],
                            'pages': len(pages), 'reader_http': response.status_code, 'verified': valid, 'media': media})
            self.stdout.write(f"{'VERIFIED' if valid else 'FAILED'} {path}: {len(pages)} pages")
            self.stdout.flush()
        report = manifest_path.with_name('verification.json')
        report.write_text(json.dumps(results, indent=2), encoding='utf-8')
        self.stdout.write(f'{sum(r["verified"] for r in results)}/{len(results)} verified. Report: {report}')
        if not entries or not all(r['verified'] for r in results):
            raise CommandError('One or more documents could not be verified.')
