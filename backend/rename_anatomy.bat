@echo off
REM Script to rename anatomy and physiology blocks and sections

echo ==========================================
echo Blocks and Sections Renaming
echo ==========================================
echo.
echo This script will rename blocks and sections for:
echo   - Anatomy (Blocks 1, 2, 3)
echo   - Physiology (Blocks 1, 2, 3, 4)
echo.
echo ANATOMY CHANGES:
echo   Block 1: "Anatomy Block 1" --^> "Upper and Lower Limb"
echo     - Subblock 1 --^> Upper Limb
echo     - Subblock 2 --^> Lower Limb
echo.
echo   Block 2: "Anatomy Block 2" --^> "TAPP"
echo     - Subblock 1 --^> Thorax
echo     - Subblock 2 --^> Abdomen
echo     - Subblock 3 --^> Pelvis
echo     - Subblock 4 --^> Perineum
echo.
echo   Block 3: "Anatomy Block 3" --^> "Head and Neck and Neuroanatomy"
echo     - Subblock 1 --^> Head and Neck
echo     - Subblock 2 --^> Neuroanatomy
echo.
echo PHYSIOLOGY CHANGES:
echo   Block 1: --^> "Physiology Block 1"
echo     - Subblock 1 --^> General Physiology
echo     - Subblock 2 --^> Autoregulation
echo     - Subblock 3 --^> Blood and Body Fluids
echo     - Subblock 4 --^> Neuromuscular Physiology
echo.
echo   Block 2: --^> "Physiology Block 2"
echo     - Subblock 1 --^> Respiratory Physiology
echo     - Subblock 2 --^> Cardiovascular Physiology
echo     - Subblock 3 --^> Gastrointestinal Physiology
echo     - Subblock 4 --^> Nutrient Metabolism
echo.
echo   Block 3: --^> "Physiology Block 3"
echo     - Subblock 1 --^> Renal Physiology
echo     - Subblock 2 --^> Endocrinology
echo     - Subblock 3 --^> Reproductive Physiology
echo.
echo   Block 4: --^> "Physiology Block 4"
echo     - Subblock 1 --^> Sensory System
echo     - Subblock 2 --^> Special Senses
echo     - Subblock 3 --^> Motor System
echo     - Subblock 4 --^> Integrating Centre
echo.
echo NOTE: Histology and Embryology blocks remain unchanged
echo.
set /p CONFIRM="Do you want to continue? (y/n): "

if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    exit /b 1
)

echo.
echo ==========================================
echo Step 1: Listing current structure...
echo ==========================================
echo.

cd /d "%~dp0"
python manage.py list_anatomy_structure

echo.
echo ==========================================
echo Step 2: Applying renames...
echo ==========================================
echo.

python manage.py rename_anatomy_blocks

echo.
echo ==========================================
echo Step 3: Verifying changes...
echo ==========================================
echo.

python manage.py list_anatomy_structure

echo.
echo ==========================================
echo Done!
echo ==========================================
echo.
echo Next steps:
echo 1. Refresh your browser
echo 2. Clear browser cache if needed (Ctrl+Shift+R)
echo 3. Check the courses page to see new names
echo.
pause
