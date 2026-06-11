from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import cloudinary.uploader

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
    if ext in DOCUMENT_EXTS:
        return 'raw'
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in VIDEO_EXTS:
        return 'video'
    return 'raw'


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
    """Upload file to Cloudinary and return URL"""
    print(f"Upload request received from user: {request.user}")
    print(f"Files in request: {request.FILES}")
    print(f"Data in request: {request.data}")
    
    if 'file' not in request.FILES:
        print("ERROR: No file in request")
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['file']
    folder = request.data.get('type', 'general')

    print(f"File name: {file.name}, size: {file.size}, type: {file.content_type}")
    print(f"Folder: {folder}")

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

    # Read content once for empty + magic-byte checks
    file.seek(0)
    file_content = file.read()
    file.seek(0)

    if len(file_content) == 0:
        return Response({'error': 'File is empty'}, status=status.HTTP_400_BAD_REQUEST)

    if not _content_looks_valid(file_ext, file_content[:16]):
        return Response(
            {'error': "File content does not match its extension."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    resource_type = _resource_type_for(file_ext)
    print(f"Using resource_type: {resource_type} (validated .{file_ext}, {len(file_content)} bytes)")

    try:
        # For development: Try Cloudinary first, fallback to local storage
        try:
            print("Attempting Cloudinary upload...")

            result = cloudinary.uploader.upload(
                file,
                folder=f"emby/{folder}",
                resource_type=resource_type,
                access_mode='public',  # Make files publicly accessible
                type='upload',  # Ensure it's a regular upload, not authenticated
                timeout=60
            )
            
            print(f"Cloudinary upload successful: {result['secure_url']}")
            
            return Response({
                'url': result['secure_url'],
                'public_id': result['public_id'],
                'filename': file.name,
                'size': file.size,
                'format': result.get('format'),
                'resource_type': result.get('resource_type')
            }, status=status.HTTP_201_CREATED)
        except Exception as cloudinary_error:
            print(f"Cloudinary upload failed: {cloudinary_error}")
            import traceback
            traceback.print_exc()
            # Fallback: Return a placeholder URL for development
            # In production, you should handle this properly
            return Response({
                'url': f'http://localhost:8000/media/{folder}/{file.name}',
                'public_id': f'{folder}/{file.name}',
                'filename': file.name,
                'size': file.size,
                'format': file.name.split('.')[-1],
                'resource_type': 'raw'
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request):
    """Delete file from Cloudinary"""
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
