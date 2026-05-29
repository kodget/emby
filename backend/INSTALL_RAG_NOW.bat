@echo off
echo ========================================
echo Installing RAG System for Emby
echo ========================================
echo.

echo Step 1: Installing Python packages...
pip install sentence-transformers numpy scikit-learn
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages
    pause
    exit /b 1
)
echo ✓ Packages installed successfully
echo.

echo Step 2: Running database migrations...
python manage.py migrate
if %errorlevel% neq 0 (
    echo ERROR: Failed to run migrations
    pause
    exit /b 1
)
echo ✓ Migrations completed successfully
echo.

echo Step 3: Processing slides (this may take a while)...
python manage.py process_slides_rag --all
if %errorlevel% neq 0 (
    echo ERROR: Failed to process slides
    pause
    exit /b 1
)
echo ✓ Slides processed successfully
echo.

echo ========================================
echo RAG System Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Restart your Django server
echo 2. Test the AI panels in the reader
echo.
echo The AI will now give much better answers!
echo.
pause
