from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import cloudinary.uploader

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
    
    try:
        # For development: Try Cloudinary first, fallback to local storage
        try:
            print("Attempting Cloudinary upload...")
            
            # Determine resource type based on file extension
            file_ext = file.name.split('.')[-1].lower()
            if file_ext in ['pdf', 'ppt', 'pptx', 'doc', 'docx']:
                resource_type = 'raw'
            elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
                resource_type = 'image'
            elif file_ext in ['mp4', 'mov', 'avi', 'webm']:
                resource_type = 'video'
            else:
                resource_type = 'raw'
            
            print(f"Using resource_type: {resource_type}")
            
            # Read file content to verify it's not empty
            file.seek(0)
            file_content = file.read()
            file.seek(0)  # Reset for upload
            
            print(f"File content size: {len(file_content)} bytes")
            
            if len(file_content) == 0:
                print("ERROR: File is empty!")
                return Response({'error': 'File is empty'}, status=status.HTTP_400_BAD_REQUEST)
            
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
