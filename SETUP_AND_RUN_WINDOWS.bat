@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title MedSafe AI Setup and Run
echo.
echo ===============================================
echo        MedSafe AI Setup and Run
echo ===============================================
echo.

rem Check Python launcher and select a supported Python installation.
where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python 3.11 or 3.12 is required.
    echo Install Python from https://www.python.org/downloads/windows/
    echo Enable the Python Launcher during installation, then run this file again.
    pause
    exit /b 1
)

set "PYTHON="
py -3.12 -c "import sys" >nul 2>nul && set "PYTHON=py -3.12"
if not defined PYTHON py -3.11 -c "import sys" >nul 2>nul && set "PYTHON=py -3.11"
if not defined PYTHON py -3 -c "import sys" >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON (
    echo ERROR: No usable Python installation was found.
    pause
    exit /b 1
)

rem Node.js is needed to build the current web interface.
where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: Node.js 20 or later is required.
    echo Install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

rem Use an existing Tesseract installation, including the standard Windows path.
where tesseract >nul 2>nul
if errorlevel 1 if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" set "PATH=%ProgramFiles%\Tesseract-OCR;%PATH%"
where tesseract >nul 2>nul
if errorlevel 1 if exist "%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe" set "PATH=%ProgramFiles(x86)%\Tesseract-OCR;%PATH%"
where tesseract >nul 2>nul
if errorlevel 1 (
    echo Tesseract OCR was not found.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
        pause
        exit /b 1
    )
    echo Attempting to install Tesseract using Windows Package Manager...
    winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo Tesseract installation failed. Install it manually and run this file again.
        pause
        exit /b 1
    )
    if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" set "PATH=%ProgramFiles%\Tesseract-OCR;%PATH%"
)
where tesseract >nul 2>nul
if errorlevel 1 (
    echo ERROR: Tesseract is still unavailable. Restart this window after installation.
    pause
    exit /b 1
)
tesseract --version 2>nul | findstr /i "tesseract" | set /p TESS_VERSION=
echo OCR found: %TESS_VERSION%

rem Create the isolated Python environment once.
if not exist ".venv\Scripts\python.exe" (
    echo Creating the local Python environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create the Python environment.
        pause
        exit /b 1
    )
)

echo Updating the package installer...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

echo Installing application packages...
".venv\Scripts\python.exe" -m pip install -r requirements-product.txt
if errorlevel 1 (
    echo ERROR: Python package installation failed.
    pause
    exit /b 1
)

echo Installing web interface packages...
pushd frontend
call npm install --no-audit --no-fund
if errorlevel 1 (
    popd
    echo ERROR: Web interface package installation failed.
    pause
    exit /b 1
)
call npm run build
if errorlevel 1 (
    popd
    echo ERROR: Web interface build failed.
    pause
    exit /b 1
)
popd

echo.
echo Setup complete.
echo Starting MedSafe AI at http://127.0.0.1:8000
echo Press CTRL+C to stop the application.
echo.
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
set "EXIT_CODE=%errorlevel%"
echo.
echo MedSafe AI stopped with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
