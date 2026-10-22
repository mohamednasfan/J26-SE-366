@echo off
setlocal
cd /d "%~dp0.."
python -m pip install -r requirements-ocr.txt
python scripts\setup_models.py --download-only
start "MedSafe backend" cmd /c "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
cd frontend
if not exist node_modules npm install
start "MedSafe frontend" cmd /c "npm run dev"
echo Backend: http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173
