#!/usr/bin/env python3
"""
ARGUS Unified System Launcher
Starts the FastAPI application serving both the Terminal UI and all Quant APIs.
"""
import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("[!] uvicorn is not installed. Please install requirements:")
        print("    pip install -r backend/requirements.txt")
        sys.exit(1)

    print("=" * 65)
    print("   ARGUS — AI-Powered Quantitative Research Terminal")
    print("   Combined Full-Stack System (UI + Quant Engine + Multi-Agent)")
    print("=" * 65)
    print(" • Web Terminal UI: http://localhost:8000")
    print(" • API Docs:        http://localhost:8000/docs")
    print(" • Health Check:    http://localhost:8000/health")
    print("=" * 65)

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, app_dir=str(backend_dir))
