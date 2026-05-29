@echo off
REM Script to re-render all slides with the improved rendering logic
REM This will fix any slides that are currently showing as blank white pages

echo ==========================================
echo Slide Re-rendering Script
echo ==========================================
echo.
echo This script will re-render all slides that have blank or missing content.
echo The new rendering logic will:
echo   - Use LibreOffice for high-quality PPTX/DOCX conversion
echo   - Properly render text and formatting
echo   - Upload images to Cloudinary
echo.
set /p CONFIRM="Do you want to continue? (y/n): "

if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    exit /b 1
)

echo.
echo Starting re-rendering process...
echo.

REM Navigate to backend directory if not already there
cd /d "%~dp0"

REM Run the management command
python manage.py rerender_slides

echo.
echo ==========================================
echo Re-rendering complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Check the output above for any errors
echo 2. Refresh your browser to see the updated slides
echo 3. If any slides still show blank, you can re-render specific ones with:
echo    python manage.py rerender_slides --slide-id SLIDE_ID
echo.
pause
