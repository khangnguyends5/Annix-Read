"""Annix Read — local development entry point.

    python run.py            # runs at http://127.0.0.1:8000

Honours HOST / PORT from .env. For production, run uvicorn directly:

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
import os
import sys
from dotenv import load_dotenv
import uvicorn

# Force UTF-8 stdout on Windows so server logs with emoji don't crash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
