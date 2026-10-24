"""Private storage and short-lived delivery, independent of provider credentials in tests."""
import copy
import logging
import time
import uuid
from pathlib import Path

import cloudinary.uploader
import cloudinary.utils
from rest_framework import serializers

from .class_access import content_admin, member_class
from .models import MediaAsset

logger = logging.getLogger(__name__)
DELIVERY_TTL_SECONDS = 15 * 60


def upload_asset(file, *, class_group, uploaded_by=None, folder='emby/private', resource_type='auto', **options):
    if class_group is None or not class_group.is_active:
        raise ValueError('An active owning class is required for file storage.')
    # Unpredictable identities and no overwrite also protect a successful prior retry.
    options.pop('public_id', None)
    options.pop('type', None)
    options.pop('access_mode', None)
    options.pop('overwrite', None)
    result = cloudinary.uploader.upload(file, folder=f'{folder}/{class_group.pk}',
        public_id=uuid.uuid4().hex, resource_type=resource_type, type='authenticated',
        overwrite=False, **options)
    if (not result.get('public_id') or result.get('type') != 'authenticated'
            or result.get('resource_type') not in {'image', 'video', 'raw'}):
        # Never register or deliver a provider response that did not confirm private storage.
        raise ValueError('Storage did not confirm authenticated delivery.')
    try:
        return MediaAsset.objects.create(class_group=class_group, uploaded_by=uploaded_by,
            public_id=result['public_id'], resource_type=result['resource_type'],
            delivery_type='authenticated', format=result.get('format') or Path(getattr(file, 'name', '')).suffix.lstrip('.').lower(),
            file_size=result.get('bytes') or 0)
    except Exception:
        # This random identity belongs only to this upload. Preserve the original DB exception.
        try:
            cloudinary.uploader.destroy(result['public_id'], resource_type=result['resource_type'],
                                        type='authenticated', invalidate=True)
        except Exception:
            logger.warning('Could not clean up a failed private asset registration.')
        raise


def asset_url(asset):
    if asset.delivery_type != 'authenticated':
        raise ValueError('Public media cannot be delivered as a private asset.')
    # Raw IDs are retained verbatim (including their extension); do not round-trip
    # them through CloudinaryField, which can split the extension off the public ID.
    return cloudinary.utils.private_download_url(asset.public_id,
        asset.format if asset.resource_type != 'raw' else '',
        resource_type=asset.resource_type, type='authenticated',
        expires_at=int(time.time()) + DELIVERY_TTL_SECONDS, attachment=False)


def discard_new_asset(asset):
    """Compensation for an unexposed upload whose content transaction failed."""
    if any(getattr(asset, name).exists() for name in ('slides', 'materials', 'decks', 'pages')):
        raise ValueError('Cannot discard an attached asset.')
    from .models import SlideContent
    for content in SlideContent.objects.values_list('content_data', flat=True).iterator():
        pages = content.get('pages', []) if isinstance(content, dict) else []
        if isinstance(pages, list) and any(isinstance(page, dict) and str(page.get('asset_id')) == str(asset.pk) for page in pages):
            raise ValueError('Cannot discard an asset referenced by cached pages.')
    result = cloudinary.uploader.destroy(asset.public_id, resource_type=asset.resource_type,
                                        type='authenticated', invalidate=True)
    if result.get('result') not in {'ok', 'not found'}:
        raise ValueError('Storage did not confirm asset removal.')
    asset.delete()


def content_file_url(obj):
    if obj.asset_id:
        if obj.asset.class_group_id != obj.class_group_id:
            return ''
        return asset_url(obj.asset)
    # Legacy files are retained for a reviewed migration; this fallback is not a
    # privacy certification. The deployment gate blocks unresolved legacy storage.
    file = getattr(obj, 'file', None) or getattr(obj, 'original_file', None)
    return file.url if file else getattr(obj, 'file_url', '')


def page_payloads(pages, class_group_id):
    """Fresh URL per response; never alter the canonical cached JSON."""
    output = copy.deepcopy(pages)
    ids = set()
    for page in output:
        if page.get('asset_id'):
            try:
                ids.add(uuid.UUID(str(page['asset_id'])))
            except (ValueError, TypeError, AttributeError):
                pass
    assets = {str(a.pk): a for a in MediaAsset.objects.filter(pk__in=ids, class_group_id=class_group_id)}
    for page in output:
        identity = page.pop('asset_id', None)
        if identity:
            asset = assets.get(str(identity))
            page['image_url'] = asset_url(asset) if asset else ''
    return output


class PrivateMediaResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response


class PrivateAssetSerializerMixin:
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request and 'asset_id' in fields:
            qs = MediaAsset.objects.filter(delivery_type='authenticated')
            if not content_admin(request.user):
                group = member_class(request.user)
                qs = qs.filter(class_group=group) if group else qs.none()
            fields['asset_id'].queryset = qs
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        asset = attrs.get('asset')
        request = self.context.get('request')
        if asset and request:
            group_id = self.instance.class_group_id if self.instance else getattr(member_class(request.user), 'pk', None)
            if asset.class_group_id != group_id:
                raise serializers.ValidationError({'asset_id': 'File does not belong to this class.'})
            if self.instance and asset.pk != self.instance.asset_id:
                raise serializers.ValidationError({'asset_id': 'Upload a new content record to replace its source file.'})
        if self.initial_data.get('file_url') and not self.instance and not asset:
            raise serializers.ValidationError({'file_url': 'Upload the file and provide its asset_id.'})
        if asset:
            attrs.update(file=None, file_url='')
            if self.Meta.model.__name__ == 'Material':
                attrs['file_size'] = asset.file_size
            if self.Meta.model.__name__ == 'Slide':
                if asset.format not in {'pdf', 'ppt', 'pptx', 'doc', 'docx'}:
                    raise serializers.ValidationError({'asset_id': 'Select an uploaded document.'})
                attrs['file_type'] = asset.format
        return attrs
