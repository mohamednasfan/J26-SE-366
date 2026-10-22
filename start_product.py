"""Build the current React interface and start the local MedSafe-AI app.

Run: python start_product.py
Requires Node.js/npm for the first frontend build. There is no silent fallback
to an outdated browser interface.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def ensure_product_frontend():
    dist_index = FRONTEND / "dist" / "index.html"
    candidates = [FRONTEND / "package.json", FRONTEND / "index.html"]
    candidates += [
        p for p in (FRONTEND / "src").rglob("*") if p.suffix in (".jsx", ".js", ".css")
    ]
    recent_source = max((p.stat().st_mtime for p in candidates if p.is_file()), default=0)
    if dist_index.is_file() and dist_index.stat().st_mtime >= recent_source:
        return
    npm = shutil.which("npm.cmd") if os.name == "nt" else shutil.which("npm")
    npm = npm or shutil.which("npm")
    if not npm:
        raise SystemExit(
            "The redesigned React interface must be built before starting. "
            "Install Node.js 20+ from nodejs.org, then run "
            "'cd frontend && npm install && npm run build'."
        )
    print("Building the current MedSafe-AI React interface...", flush=True)
    try:
        if not (FRONTEND / "node_modules").is_dir():
            subprocess.run([npm, "install", "--no-audit", "--no-fund"],
                           cwd=FRONTEND, check=True)
        subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Frontend build failed. Run 'cd frontend && npm install && npm run build' "
            "and inspect the output. The old UI will not be started silently."
        ) from exc
    if not dist_index.is_file():
        raise SystemExit("React build completed without frontend/dist/index.html")


if __name__ == "__main__":
    ensure_product_frontend()
    print("MedSafe-AI running locally at http://127.0.0.1:8000", flush=True)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
