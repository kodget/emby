# Slide Rendering Fix - White Blank Pages Issue

## Problem

Slides (especially PPTX and DOCX files) were showing as white blank spaces when rendered in the reader view.

## Root Cause

The slide rendering logic was creating blank white canvases without actually drawing the slide content on them. The text was being extracted but not rendered visually.

## Solution

Updated `backend/curriculum/slide_renderer.py` with improved rendering logic:

### For PPTX Files

1. **Primary Method**: Converts PPTX to PDF using LibreOffice (soffice), then renders the PDF as high-quality images
2. **Fallback Method**: If LibreOffice is unavailable, extracts text and renders it visually with proper formatting

### For DOCX Files

1. **Primary Method**: Converts DOCX to PDF using LibreOffice, then renders as images
2. **Fallback Method**: Extracts text and renders it visually with multi-page support

### For PDF Files

- Uses pdf2image for high-quality rendering at 150 DPI
- Falls back to PyMuPDF if pdf2image is unavailable

## Features of the New Rendering

- ✅ Actual visual rendering instead of blank canvases
- ✅ LibreOffice integration for high-quality conversion (preserves all formatting, images, layouts)
- ✅ Robust fallback with text rendering when LibreOffice isn't available
- ✅ Better text formatting with proper fonts, spacing, and layout
- ✅ Multi-page support for long documents
- ✅ Professional appearance with borders, page numbers, and styling
- ✅ Proper image upload to Cloudinary with secure URLs

## Re-rendering Existing Slides

### Option 1: Re-render All Slides with Blank Content (Recommended)

This will only re-render slides that currently have blank or missing content:

**Linux/Mac:**

```bash
cd backend
chmod +x rerender_all_slides.sh
./rerender_all_slides.sh
```

**Windows:**

```cmd
cd backend
rerender_all_slides.bat
```

**Or directly:**

```bash
cd backend
python manage.py rerender_slides
```

### Option 2: Re-render ALL Slides (Force)

This will re-render every slide regardless of current state:

```bash
cd backend
python manage.py rerender_slides --all
```

### Option 3: Re-render Specific Slide

```bash
cd backend
python manage.py rerender_slides --slide-id <SLIDE_ID>
```

### Option 4: Re-render by File Type

```bash
cd backend
# Only PPTX files
python manage.py rerender_slides --file-type pptx

# Only DOCX files
python manage.py rerender_slides --file-type docx

# Only PDF files
python manage.py rerender_slides --file-type pdf
```

## Requirements

- LibreOffice installed on the server (already confirmed installed)
- Python packages: `pdf2image`, `python-pptx`, `python-docx`, `PyMuPDF`, `Pillow`
- Cloudinary configured for image uploads

## Testing

After re-rendering:

1. Navigate to any course with slides
2. Click on a slide to open the reader view
3. Verify that slides now show actual content instead of blank white pages
4. Check that text is readable and properly formatted
5. Verify that page navigation works correctly

## Future Uploads

All new slides uploaded after this fix will automatically use the improved rendering logic. No manual intervention needed.

## Troubleshooting

### If slides still show blank after re-rendering:

1. Check the Django logs for rendering errors
2. Verify LibreOffice is accessible: `which soffice` or `where soffice`
3. Check Cloudinary credentials are configured correctly
4. Try re-rendering a specific slide with verbose output:
   ```bash
   python manage.py rerender_slides --slide-id <SLIDE_ID>
   ```

### If LibreOffice conversion fails:

The system will automatically fall back to text rendering, which still provides a much better experience than blank pages.

### If Cloudinary upload fails:

Check your Cloudinary configuration in `backend/backend/settings.py`:

- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

## Files Modified

- `backend/curriculum/slide_renderer.py` - Main rendering logic
- `backend/curriculum/management/commands/rerender_slides.py` - Management command (new)
- `backend/rerender_all_slides.sh` - Helper script for Linux/Mac (new)
- `backend/rerender_all_slides.bat` - Helper script for Windows (new)

## Date

2026-05-27
