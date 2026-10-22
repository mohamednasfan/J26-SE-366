#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install -r requirements-product.txt
echo 'MedSafe-AI launching at http://127.0.0.1:8000'
echo 'To install AI OCR: python -m pip install -r requirements-ocr.txt'
python start_product.py
