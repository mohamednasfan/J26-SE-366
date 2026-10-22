@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Install Python 3.10 or 3.11 from python.org and enable the Python launcher.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" setup_and_verify_models.py --install
if errorlevel 1 goto :failed
echo.
echo OCR verification passed. Starting http://127.0.0.1:8000
".venv\Scripts\python.exe" start_product.py
if errorlevel 1 goto :failed
exit /b 0
:failed
echo.
echo Setup failed. See runtime_data\ocr_model_smoke_test.json for details.
pause
exit /b 1
