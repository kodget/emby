"""Compare an explicit provider export with registered/reference-bearing assets.

No provider requests or deletion. An unreferenced identity is a review candidate,
never proof that its bytes are disposable.
"""
from datetime import timedelta
import hashlib
import json
import uuid

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import MediaAsset, Slide, Material, SlideDeck, SlidePage, SlideContent


def identity(row):
    return (row['public_id'], row['resource_type'], row['delivery_type'])


def timestamp(value):
    result = parse_datetime(value) if isinstance(value, str) else None
    if result is None or timezone.is_naive(result):
        raise ValueError('Inventory timestamps must include a timezone.')
    return result


def reconcile(document, *, now=None, older_than_hours=24):
    now = now or timezone.now()
    if older_than_hours < 1:
        raise ValueError('The review grace period must be at least one hour.')
    if not isinstance(document, dict) or document.get('version') != 1:
        raise ValueError('Expected a version 1 provider inventory.')
    prefix = document.get('prefix')
    if not isinstance(prefix, str) or not prefix.startswith('emby/') or not prefix.endswith('/'):
        raise ValueError('Inventory prefix must be emby/ or one of its slash-terminated subfolders.')
    if not isinstance(document.get('complete'), bool) or not isinstance(document.get('resources'), list):
        raise ValueError('Inventory must declare complete as a boolean and include resources.')
    exported = timestamp(document.get('exported_at'))
    if exported > now:
        raise ValueError('Inventory export time cannot be in the future.')
    resources = {}
    for row in document['resources']:
        if not isinstance(row, dict) or not isinstance(row.get('public_id'), str) or not row['public_id'].startswith(prefix):
            raise ValueError('Every resource must belong to the explicit inventory prefix.')
        if row.get('resource_type') not in {'image', 'raw', 'video'} or row.get('delivery_type') not in {'authenticated', 'private', 'upload'}:
            raise ValueError('Every resource needs an explicit resource and delivery type.')
        key = identity(row)
        if key in resources:
            raise ValueError('Duplicate provider identity in inventory.')
        created = timestamp(row.get('created_at'))
        if created > exported:
            raise ValueError('Resource creation is later than the inventory export.')
        resources[key] = created

    references = {}
    def refer(asset_id, source):
        if asset_id:
            references.setdefault(str(asset_id), []).append(source)
    for model in (Slide, Material, SlideDeck, SlidePage):
        for pk, asset_id in model.objects.filter(asset__isnull=False).values_list('pk', 'asset_id').iterator():
            refer(asset_id, f'{model.__name__}:{pk}')
    # Page JSON references are authoritative too; FK-only checks miss these images.
    uncertain = []
    for content in SlideContent.objects.all().iterator():
        data = content.content_data
        pages = data.get('pages', []) if isinstance(data, dict) else None
        if not isinstance(pages, list) or any(not isinstance(page, dict) for page in pages):
            uncertain.append(str(content.slide_id)); continue
        for page in pages:
            if page.get('asset_id'):
                try:
                    asset_id = uuid.UUID(str(page['asset_id']))
                except (ValueError, TypeError, AttributeError):
                    uncertain.append(str(content.slide_id)); continue
                refer(asset_id, f'SlideContent:{content.slide_id}')

    registry = {identity(row): row for row in MediaAsset.objects.filter(public_id__startswith=prefix)
                .values('id', 'public_id', 'resource_type', 'delivery_type', 'created_at', 'class_group_id')}
    cutoff = min(now, exported) - timedelta(hours=older_than_hours)
    categories = {name: [] for name in ('referenced', 'registered_unreferenced', 'provider_only',
        'recent_unreferenced', 'missing_at_provider', 'not_in_partial_export', 'created_after_export',
        'non_authenticated', 'uncertain_references')}
    for key in sorted(registry.keys() | resources.keys()):
        row = registry.get(key)
        links = sorted(set(references.get(str(row['id']), []))) if row else []
        entry = dict(zip(('public_id', 'resource_type', 'delivery_type'), key))
        entry.update(asset_id=str(row['id']) if row else None, references=links,
                     class_group_id=row['class_group_id'] if row else None)
        if key[2] != 'authenticated':
            categories['non_authenticated'].append(entry)
        if row and key not in resources:
            category = ('created_after_export' if row['created_at'] > exported else
                        'missing_at_provider' if document['complete'] else 'not_in_partial_export')
        elif links:
            category = 'referenced'
        elif uncertain:
            category = 'uncertain_references'
        elif max(resources[key], row['created_at'] if row else resources[key]) > cutoff:
            category = 'recent_unreferenced'
        else:
            category = 'registered_unreferenced' if row else 'provider_only'
        categories[category].append(entry)
    report = dict(version=1, read_only=True, prefix=prefix, complete=document['complete'],
        exported_at=exported.isoformat(), older_than_hours=older_than_hours,
        malformed_page_references=uncertain, counts={name: len(rows) for name, rows in categories.items()},
        categories=categories,
        warning='Review candidates only. No deletion is authorized; legacy URLs, active uploads and external references require separate review.')
    report['fingerprint'] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    return report
