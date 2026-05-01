# Cloudinary File Storage Setup Guide

## Why Cloudinary?
- **Free tier**: 25GB storage + 25GB bandwidth/month
- **No credit card required** for free tier
- **Easier setup** than AWS (3 steps vs 10+ steps)
- **Built-in CDN** for fast delivery worldwide
- **Image optimization** automatic
- **Video support** included

## Step 1: Create Cloudinary Account

1. Go to https://cloudinary.com/users/register_free
2. Sign up with email or Google
3. Verify your email
4. **That's it!** No credit card needed

## Step 2: Get Your Credentials

1. After login, go to Dashboard: https://console.cloudinary.com
2. You'll see your credentials:
   - **Cloud Name**: e.g., `dxyz123abc`
   - **API Key**: e.g., `123456789012345`
   - **API Secret**: e.g., `abcdefghijklmnopqrstuvwxyz123`
3. Copy these values

## Step 3: Configure Environment Variables

Update `backend/.env`:

```env
# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

Replace with your actual credentials from Step 2.

## Step 4: Install Package

```bash
cd backend
pip install -r requirements.txt
```

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
4. File will be stored in Cloudinary under `emby/slides/` folder

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
  "url": "https://res.cloudinary.com/your_cloud/raw/upload/v123/emby/slides/file.pdf",
  "public_id": "emby/slides/file",
  "filename": "file.pdf",
  "size": 12345,
  "format": "pdf",
  "resource_type": "raw"
}
```

## File Organization in Cloudinary

```
emby/
├── slides/          # Slide PDFs/PPTs
├── profiles/        # User profile images
└── general/         # General uploads
```

## API Endpoints

### Upload File
- **POST** `/api/upload/`
- **Headers**: `Authorization: Bearer <token>`
- **Body**: `multipart/form-data`
  - `file`: File to upload
  - `type`: Folder name (slides, profiles, general)
- **Response**: `{ url, public_id, filename, size, format, resource_type }`

### Delete File
- **DELETE** `/api/delete-file/`
- **Headers**: `Authorization: Bearer <token>`
- **Body**: `{ "public_id": "emby/slides/file" }`
- **Response**: `{ message: "File deleted successfully" }`

## Supported File Types

- **Images**: JPG, PNG, GIF, WebP, SVG, etc.
- **Videos**: MP4, WebM, MOV, etc.
- **Documents**: PDF, DOCX, PPTX, etc.
- **Raw files**: Any file type

## Free Tier Limits

- **Storage**: 25 GB
- **Bandwidth**: 25 GB/month
- **Transformations**: 25,000/month
- **Admin API calls**: 500/hour

For most educational apps, this is more than enough!

## Features Included

1. **Automatic CDN**: Files delivered from nearest server
2. **Image optimization**: Automatic format conversion (WebP)
3. **Responsive images**: Generate different sizes on-the-fly
4. **Video transcoding**: Convert videos to web-friendly formats
5. **Secure URLs**: Optional signed URLs for private content
6. **Backup**: Automatic backups included

## Cloudinary Dashboard

Access at: https://console.cloudinary.com

- View all uploaded files
- Manage folders
- See usage statistics
- Configure settings
- Generate transformations

## Troubleshooting

### Error: "Invalid cloud_name"
- Check `.env` file has correct CLOUDINARY_CLOUD_NAME
- Verify no extra spaces in credentials
- Restart Django server after updating `.env`

### Error: "Invalid signature"
- Check CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET
- Ensure credentials match your Cloudinary dashboard
- Verify no typos in `.env` file

### Files not uploading
- Check `cloudinary` is in INSTALLED_APPS
- Verify cloudinary.config() is called in settings.py
- Check Django logs for detailed error messages

### Upload size limit
- Default limit: 10MB for free tier
- Can be increased in Cloudinary settings
- Or compress files before upload

## Production Checklist

- [ ] Use environment variables for credentials
- [ ] Enable signed URLs for private content
- [ ] Set up folder structure for organization
- [ ] Configure upload presets for consistency
- [ ] Enable automatic backups
- [ ] Set up usage alerts
- [ ] Consider paid plan if exceeding free tier

## Upgrade Options

If you need more:
- **Plus Plan**: $89/month - 100GB storage, 100GB bandwidth
- **Advanced Plan**: $224/month - 500GB storage, 500GB bandwidth
- **Custom**: Contact sales for enterprise needs

## Comparison: Cloudinary vs AWS S3

| Feature | Cloudinary Free | AWS S3 |
|---------|----------------|--------|
| Setup Time | 5 minutes | 30+ minutes |
| Credit Card | Not required | Required |
| Free Storage | 25GB | 5GB (12 months) |
| Free Bandwidth | 25GB/month | 15GB (12 months) |
| CDN | Included | Extra cost |
| Image Optimization | Automatic | Manual setup |
| Learning Curve | Easy | Complex |

## Next Steps

1. Sign up at https://cloudinary.com
2. Copy credentials to `.env`
3. Run migrations
4. Test upload via admin or API
5. Update frontend to use upload API
