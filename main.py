"""
Sehat Saathi - Application Entry Point
========================================
Run the FastAPI backend:
    python main.py
    # or
    uvicorn main:app --reload --port 8000
"""
import logging
import uvicorn
from app.api.routes import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if __name__ == "__main__":
    uvicorn.run(
        "app.api.routes:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
