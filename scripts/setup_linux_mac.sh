#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -r requirements-ocr.txt
python3 scripts/setup_models.py --download-only
(python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm install && npm run dev) &
echo "Backend: http://127.0.0.1:8000"
echo "Frontend: http://127.0.0.1:5173"
