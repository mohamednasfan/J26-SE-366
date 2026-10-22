@echo off
setlocal
cd /d "%~dp0"
call "%~dp0start_windows.bat"
if errorlevel 1 (
  echo.
  echo Installation or startup failed. Check Python, Node.js and Tesseract.
  pause
  exit /b 1
)
exit /b 0
