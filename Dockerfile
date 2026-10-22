# Multi-stage build: independent React assets + loopback-oriented research API
FROM node:22-alpine AS web
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MEDSAFE_DATA_DIR=/var/lib/medsafe
WORKDIR /opt/medsafe
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libglib2.0-0 libgl1 \
  && rm -rf /var/lib/apt/lists/*
COPY requirements-product.txt ./
RUN pip install --no-cache-dir -r requirements-product.txt
COPY . ./
COPY --from=web /build/frontend/dist ./frontend/dist
RUN useradd --create-home --uid 10001 medsafe && mkdir -p /var/lib/medsafe \
  && chown -R medsafe:medsafe /var/lib/medsafe /opt/medsafe
USER medsafe
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" || exit 1
CMD ["python","-m","uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000"]
