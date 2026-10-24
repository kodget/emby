"""Read-only release gate for original/page assets still using public or unknown storage."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from curriculum.models import Slide, Material, SlideDeck, SlidePage, SlideContent, MediaAsset, SpotStation


class Command(BaseCommand):
    help = 'Block release until legacy original and page storage has been explicitly migrated and reviewed.'

    def handle(self, *args, **options):
        unresolved = {}
        for model, fields in ((Slide, ('file', 'file_url')), (Material, ('file', 'file_url')),
                              (SlideDeck, ('original_file', 'converted_pdf', 'converted_pptx')),
                              (SlidePage, ('image', 'image_url'))):
            has_file = Q()
            for field in fields:
                has_file |= Q(**{field + '__isnull': False}) & ~Q(**{field: ''})
            count = model.objects.filter(has_file, asset__isnull=True).count()
            # Old delivery fields must be cleared only after the provider migration is verified.
            count += model.objects.filter(has_file, asset__isnull=False).count()
            unresolved[model.__name__] = count
        private_station = Q(is_shared=False) & (
            Q(subject__class_group__isnull=False) | Q(block__subject__class_group__isnull=False)
        )
        legacy_station_image = (
            Q(image_url__gt='') | Q(original_image_url__gt='')
            | (Q(image__isnull=False) & ~Q(image=''))
        )
        unresolved['private_station_images'] = SpotStation.objects.filter(
            private_station, legacy_station_image
        ).count()
        valid_assets = {str(pk): group for pk, group in MediaAsset.objects.filter(delivery_type='authenticated')
                        .values_list('pk', 'class_group_id')}
        unresolved['cached_pages'] = 0
        for content in SlideContent.objects.select_related('slide').iterator():
            pages = (content.content_data or {}).get('pages', [])
            for page in pages:
                if page.get('image_url') or (page.get('asset_id') and
                        valid_assets.get(str(page['asset_id'])) != content.slide.class_group_id):
                    unresolved['cached_pages'] += 1
        unresolved['invalid_assets'] = MediaAsset.objects.exclude(delivery_type='authenticated').count()
        for model in (Slide, Material, SlideDeck, SlidePage):
            owner = 'deck__class_group_id' if model is SlidePage else 'class_group_id'
            from django.db.models import F
            unresolved[model.__name__ + '_owner_mismatch'] = model.objects.filter(asset__isnull=False).exclude(
                asset__class_group_id=F(owner)).count()
        self.stdout.write(json.dumps(unresolved, sort_keys=True))
        if any(unresolved.values()):
            raise CommandError('Private media adoption is incomplete. Rehearse and verify legacy asset migration before release. No data changed.')
        self.stdout.write('Private media record checks passed. Provider URL revocation must still be verified separately.')
