@echo off
REM Batch script to set environment and start Django dev server with Poppler support

echo Setting up environment...
set "POPPLER_PATH=C:\Release-26.02.0-0\poppler-26.02.0\Library\bin"
set "PATH=%PATH%;%POPPLER_PATH%"

echo Poppler path: %POPPLER_PATH%
pdftoppm -h >nul 2>&1
if errorlevel 1 (
    echo ERROR: Poppler not found at expected location
    echo Expected: %POPPLER_PATH%
    exit /b 1
) else (
    echo ✓ Poppler available
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate venv
    exit /b 1
)

cd backend
echo.
echo Running Django checks...
python manage.py check
if errorlevel 1 (
    echo ERROR: Django check failed
    exit /b 1
)

echo.
echo ✓ Environment ready. Starting Django dev server...
python manage.py runserver 0.0.0.0:8000
