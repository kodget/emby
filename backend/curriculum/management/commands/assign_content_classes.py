"""Explicit, reviewed ownership adoption; never infer history from current membership."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import ClassGroup
from curriculum.models import Subject, Slide, Material, SlideDeck

MODELS = {'subjects': Subject, 'slides': Slide, 'materials': Material, 'decks': SlideDeck}


class Command(BaseCommand):
    help = 'Inventory unassigned content, or validate/apply an explicit JSON ownership manifest.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', help='JSON mapping each content type and record ID to a class primary key.')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm-writes-paused', action='store_true')

    def handle(self, *args, **options):
        if not options['manifest']:
            if options['apply']:
                raise CommandError('--apply requires a manifest.')
            self.stdout.write(json.dumps({name: list(model.objects.filter(class_group__isnull=True)
                                                     .order_by('pk').values_list('pk', flat=True))
                                          for name, model in MODELS.items()}, indent=2))
            return
        if options['apply'] and not options['confirm_writes_paused']:
            raise CommandError('Pause content writes and pass --confirm-writes-paused before applying.')
        try:
            manifest = json.loads(Path(options['manifest']).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            raise CommandError('Could not read the JSON ownership manifest.') from None
        if not isinstance(manifest, dict) or set(manifest) - set(MODELS):
            raise CommandError('Use only subjects, slides, materials and decks mappings.')
        for mapping in manifest.values():
            if not isinstance(mapping, dict) or any(
                not isinstance(pk, str) or not pk or type(group) is not int or group <= 0
                for pk, group in mapping.items()
            ):
                raise CommandError('Map record IDs to positive integer class primary keys.')
        with transaction.atomic():
            group_ids = {group for mapping in manifest.values() for group in mapping.values()}
            groups = set(ClassGroup.objects.select_for_update().filter(pk__in=group_ids, is_active=True)
                         .values_list('pk', flat=True))
            if groups != group_ids:
                raise CommandError('A target class does not exist or is inactive.')
            rows = {}
            for name, model in MODELS.items():
                mapping = manifest.get(name, {})
                rows[name] = {str(obj.pk): obj for obj in model.objects.select_for_update().filter(pk__in=mapping)}
                if set(rows[name]) != set(mapping):
                    raise CommandError(f'Manifest contains an unknown {name} ID.')
                for pk, obj in rows[name].items():
                    if obj.class_group_id not in (None, mapping[pk]):
                        raise CommandError(f'{name} already has a different owner; reassignment is not permitted.')

            def subject_owner(subject):
                return manifest.get('subjects', {}).get(str(subject.pk), subject.class_group_id)

            # Include existing children when assigning a subject so a partial manifest
            # cannot produce contradictory ownership. Unassigned children remain hidden.
            for name, model in (('slides', Slide), ('materials', Material)):
                subjects = manifest.get('subjects', {})
                candidates = model.objects.select_related('subject', 'block__subject',
                    'sub_block__block__subject', 'topic__block__subject', 'topic__sub_block__block__subject')
                from django.db.models import Q
                candidates = candidates.filter(Q(pk__in=manifest.get(name, {})) | Q(subject_id__in=subjects) |
                    Q(block__subject_id__in=subjects) | Q(sub_block__block__subject_id__in=subjects) |
                    Q(topic__block__subject_id__in=subjects) | Q(topic__sub_block__block__subject_id__in=subjects))
                for obj in candidates:
                    owner = manifest.get(name, {}).get(str(obj.pk), obj.class_group_id)
                    if owner is None:
                        continue
                    parents = [obj.subject, obj.block.subject if obj.block else None,
                               obj.sub_block.block.subject if obj.sub_block else None]
                    if obj.topic:
                        parents += [obj.topic.block.subject if obj.topic.block else None,
                                    obj.topic.sub_block.block.subject if obj.topic.sub_block else None]
                    if not any(parents) or any(subject_owner(parent) != owner for parent in parents if parent):
                        raise CommandError('Content ancestry and target class disagree. Repair the explicit mapping first.')
            changed = 0
            if options['apply']:
                for name, records in rows.items():
                    for pk, obj in records.items():
                        if obj.class_group_id is None:
                            changed += MODELS[name].objects.filter(pk=pk, class_group__isnull=True).update(
                                class_group_id=manifest[name][pk])
            self.stdout.write(json.dumps({'mode': 'applied' if options['apply'] else 'dry_run',
                                          'validated_records': sum(len(m) for m in manifest.values()),
                                          'assigned_records': changed}))
