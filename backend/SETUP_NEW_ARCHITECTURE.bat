@echo off
echo ========================================
echo Setting Up New Slide Processing Architecture
echo ========================================
echo.

echo Step 1: Clearing cache...
python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache cleared!')"
if %errorlevel% neq 0 (
    echo ERROR: Failed to clear cache
    pause
    exit /b 1
)
echo ✓ Cache cleared
echo.

echo Step 2: Processing all existing slides...
echo This may take 5-30 minutes depending on number of slides...
python manage.py process_slides --all
if %errorlevel% neq 0 (
    echo ERROR: Failed to process slides
    pause
    exit /b 1
)
echo ✓ Slides processed
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Restart your Django server
echo 2. Test the AI panels on any slide
echo 3. Upload a new slide to test automatic processing
echo.
echo The AI panels should now show REAL content!
echo.
pause
