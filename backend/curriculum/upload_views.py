from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import cloudinary.uploader
import logging
from .class_access import upload_class
from .private_media import upload_asset, asset_url

logger = logging.getLogger(__name__)

# PRD §11.4 — restrict uploads to a known allow-list and cap the size.
DOCUMENT_EXTS = {'pdf', 'ppt', 'pptx', 'doc', 'docx'}
IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'}
VIDEO_EXTS = {'mp4', 'mov', 'avi', 'webm'}
ALLOWED_EXTS = DOCUMENT_EXTS | IMAGE_EXTS | VIDEO_EXTS

# Magic-byte signatures used to verify the declared extension matches the bytes.
_MAGIC = {
    'pdf': [b'%PDF'],
    'zip_office': [b'PK\x03\x04'],          # pptx/docx (and svg-in-zip never)
    'ole_office': [b'\xD0\xCF\x11\xE0'],     # legacy ppt/doc
    'png': [b'\x89PNG'],
    'jpg': [b'\xff\xd8\xff'],
    'gif': [b'GIF87a', b'GIF89a'],
    'webp': [b'RIFF'],
    'mp4': [b'\x00\x00\x00'],                 # ftyp box appears after size
}

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


def _ext_of(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def _resource_type_for(ext: str) -> str:
    # Detection is independent of access: every type uses authenticated delivery.
    if ext in DOCUMENT_EXTS:
        return 'auto'
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in VIDEO_EXTS:
        return 'video'
    return 'auto'


def _content_looks_valid(ext: str, head: bytes) -> bool:
    """Light magic-byte check so a renamed executable can't masquerade as a doc."""
    if ext == 'pdf':
        return head.startswith(b'%PDF')
    if ext in ('pptx', 'docx'):
        return head.startswith(b'PK\x03\x04')
    if ext in ('ppt', 'doc'):
        return head.startswith(b'\xD0\xCF\x11\xE0') or head.startswith(b'PK\x03\x04')
    if ext == 'png':
        return head.startswith(b'\x89PNG')
    if ext in ('jpg', 'jpeg'):
        return head.startswith(b'\xff\xd8\xff')
    if ext == 'gif':
        return head.startswith((b'GIF87a', b'GIF89a'))
    if ext == 'webp':
        return head.startswith(b'RIFF')
    # svg is text; videos vary — accept without a strict signature check
    return True


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_file(request):
    """Register a class-owned private asset and return a temporary preview URL."""
    from accounts.permissions import can_upload_slides
    profile = getattr(request.user, "profile", None)
    if profile is None or not can_upload_slides(profile):
        return Response(
            {"error": "Only class heads and material uploaders can upload files."},
            status=status.HTTP_403_FORBIDDEN,
        )
    owning_class = upload_class(request.user)
    
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['file']

    # ---- Validation (PRD §11.4) ----
    file_ext = _ext_of(file.name)
    if file_ext not in ALLOWED_EXTS:
        return Response(
            {'error': f"File type '.{file_ext}' is not allowed.",
             'allowed': sorted(ALLOWED_EXTS)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if file.size and file.size > MAX_UPLOAD_BYTES:
        return Response(
            {'error': f'File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    # Inspect only the signature; never copy a large upload into worker memory.
    file.seek(0)
    file_content = file.read(16)
    file.seek(0)

    if len(file_content) == 0:
        return Response({'error': 'File is empty'}, status=status.HTTP_400_BAD_REQUEST)

    if not _content_looks_valid(file_ext, file_content[:16]):
        return Response(
            {'error': "File content does not match its extension."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resource_type = _resource_type_for(file_ext)

    try:
        asset = upload_asset(
            file, class_group=owning_class, uploaded_by=request.user,
            folder='emby/attachments', resource_type=resource_type, timeout=300,
        )
        
        return Response({
            'url': asset_url(asset),
            'asset_id': str(asset.pk),
            'filename': file.name,
            'size': file.size,
            'format': asset.format,
            'resource_type': asset.resource_type,
        }, status=status.HTTP_201_CREATED, headers={'Cache-Control': 'private, no-store'})
    
    except Exception as e:
        logger.warning('Private upload failed (%s)', type(e).__name__)
        return Response({'error': 'File storage is unavailable. Please try again.'}, status=502)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request):
    """Delete file from Cloudinary"""
    from .class_access import content_admin
    if not content_admin(request.user):
        return Response({'error': 'Delete the class-owned content record instead of an arbitrary storage identifier.'}, status=403)
    from accounts.permissions import can_upload_slides
    profile = getattr(request.user, "profile", None)
    if profile is None or not can_upload_slides(profile):
        return Response(
            {"error": "Only class heads and material uploaders can delete files."},
            status=status.HTTP_403_FORBIDDEN,
        )
    public_id = request.data.get('public_id')
    if not public_id:
        return Response({'error': 'No public_id provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        result = cloudinary.uploader.destroy(public_id)
        if result.get('result') == 'ok':
            return Response({'message': 'File deleted successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
