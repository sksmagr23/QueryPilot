"""Simple entry-point script to start the QueryPilot FastAPI backend server."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("PYTHONPATH", str(BACKEND_DIR))

if __name__ == "__main__":
    print("Starting QueryPilot Backend on http://localhost:8000 ...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(BACKEND_DIR / "app")],
    )
