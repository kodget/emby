# AWS S3 File Storage Setup Guide

## Prerequisites
- AWS Account
- AWS CLI installed (optional but recommended)
- Python packages installed from requirements.txt

## Step 1: Install Required Packages

```bash
cd backend
pip install -r requirements.txt
```

Packages added:
- `boto3==1.34.34` - AWS SDK for Python
- `django-storages==1.14.2` - Django storage backends
- `Pillow==10.2.0` - Image processing

## Step 2: Create AWS S3 Bucket

1. Go to AWS S3 Console: https://s3.console.aws.amazon.com
2. Click "Create bucket"
3. Configuration:
   - **Bucket name**: `emby-media-storage` (must be globally unique)
   - **Region**: `us-east-1` (or your preferred region)
   - **Block Public Access**: Uncheck (we'll use signed URLs)
   - **Versioning**: Enable (optional)
4. Click "Create bucket"

### Configure CORS

1. Select your bucket → Permissions → CORS
2. Add this configuration:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedOrigins": ["http://localhost:3000", "http://localhost:3001"],
    "ExposeHeaders": ["ETag"]
  }
]
```

## Step 3: Create IAM User

1. Go to IAM Console: https://console.aws.amazon.com/iam
2. Click "Users" → "Add users"
3. Username: `emby-s3-user`
4. Select "Access key - Programmatic access"
5. Attach policy: `AmazonS3FullAccess` (or use custom policy below)
6. **Save credentials**: Copy Access Key ID and Secret Access Key

### Custom IAM Policy (Recommended)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::emby-media-storage",
        "arn:aws:s3:::emby-media-storage/*"
      ]
    }
  ]
}
```

## Step 4: Configure Environment Variables

Update `backend/.env`:

```env
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_STORAGE_BUCKET_NAME=emby-media-storage
AWS_S3_REGION_NAME=us-east-1
```

**IMPORTANT**: Replace `your_access_key_here` and `your_secret_key_here` with actual credentials from Step 3.

## Step 5: Run Migrations

```bash
python manage.py makemigrations curriculum
python manage.py migrate
```

## Step 6: Test Upload

### Using Django Admin
1. Start server: `python manage.py runserver`
2. Go to http://localhost:8000/admin
3. Create a Slide and upload a file
4. File will be stored in S3 under `slides/` folder

### Using API Endpoint

```bash
curl -X POST http://localhost:8000/api/upload/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@/path/to/file.pdf" \
  -F "type=slides"
```

Response:
```json
{
  "url": "https://emby-media-storage.s3.amazonaws.com/slides/uuid.pdf?signature...",
  "path": "slides/uuid.pdf",
  "filename": "file.pdf",
  "size": 12345
}
```

## File Organization in S3

```
emby-media-storage/
├── slides/          # Slide PDFs/PPTs
├── profiles/        # User profile images
└── media/           # General uploads
```

## API Endpoints

### Upload File
- **POST** `/api/upload/`
- **Headers**: `Authorization: Bearer <token>`
- **Body**: `multipart/form-data`
  - `file`: File to upload
  - `type`: Folder name (slides, profiles, media)
- **Response**: `{ url, path, filename, size }`

### Delete File
- **DELETE** `/api/delete-file/`
- **Headers**: `Authorization: Bearer <token>`
- **Body**: `{ "path": "slides/uuid.pdf" }`
- **Response**: `{ message: "File deleted successfully" }`

## Security Features

1. **Signed URLs**: Files use temporary signed URLs (1 hour expiry)
2. **Authentication**: Upload/delete requires JWT token
3. **No File Overwrite**: Files get unique UUIDs
4. **Private Bucket**: Files not publicly accessible without signed URL

## Cost Estimation

AWS S3 Pricing (us-east-1):
- **Storage**: $0.023 per GB/month
- **PUT requests**: $0.005 per 1,000 requests
- **GET requests**: $0.0004 per 1,000 requests
- **Data transfer out**: $0.09 per GB (first 10TB)

Example: 100GB storage + 10K uploads + 100K downloads = ~$12/month

## Troubleshooting

### Error: "Unable to locate credentials"
- Check `.env` file has correct AWS credentials
- Verify `python-dotenv` is installed
- Restart Django server after updating `.env`

### Error: "Access Denied"
- Verify IAM user has S3 permissions
- Check bucket name matches in `.env`
- Ensure bucket policy allows IAM user access

### Error: "CORS policy blocked"
- Add your frontend URL to bucket CORS configuration
- Include `http://` or `https://` in AllowedOrigins

### Files not uploading
- Check `storages` is in INSTALLED_APPS
- Verify `DEFAULT_FILE_STORAGE` is set in settings.py
- Check Django logs for detailed error messages

## Production Checklist

- [ ] Use environment-specific bucket names
- [ ] Enable S3 bucket versioning
- [ ] Set up CloudFront CDN for faster delivery
- [ ] Configure lifecycle policies for old files
- [ ] Enable S3 access logging
- [ ] Set up CloudWatch alarms for costs
- [ ] Use IAM roles instead of access keys (if on EC2)
- [ ] Enable S3 encryption at rest
- [ ] Configure backup/replication to another region

## Next Steps

1. Update frontend to use upload API
2. Add file type validation
3. Implement file size limits
4. Add image compression for profile pictures
5. Set up CloudFront for CDN delivery
