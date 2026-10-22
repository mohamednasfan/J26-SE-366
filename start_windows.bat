@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements-product.txt || exit /b 1
python -c "import easyocr" >nul 2>&1
if errorlevel 1 (
  echo Installing AI OCR dependencies into the application environment...
  python -m pip install -r requirements-ocr.txt || exit /b 1
)
echo.
echo MedSafe-AI launching at http://127.0.0.1:8000
python start_product.py
