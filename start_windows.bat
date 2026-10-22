@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Install Python 3.11 or 3.12 and enable the Python launcher.
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: Install Node.js 20 or later to build the redesigned React UI.
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated MedSafe-AI Python environment...
  py -3.11 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-product.txt
if errorlevel 1 exit /b 1
echo.
echo Starting MedSafe-AI: http://127.0.0.1:8000
".venv\Scripts\python.exe" start_product.py
exit /b %errorlevel%
