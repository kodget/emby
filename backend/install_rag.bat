@echo off
echo ========================================
echo Installing RAG System Dependencies
echo ========================================
echo.

echo Installing sentence-transformers...
pip install sentence-transformers

echo Installing numpy...
pip install numpy

echo Installing scikit-learn...
pip install scikit-learn

echo.
echo ========================================
echo Running Database Migrations...
echo ========================================
python manage.py migrate

echo.
echo ========================================
echo RAG System Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Process your slides: python manage.py process_slides_rag --all
echo 2. Restart Django server: python manage.py runserver
echo 3. Test AI panels in the browser
echo.
pause
