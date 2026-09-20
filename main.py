"""
Sehat Saathi - Application Entry Point
========================================
Run the FastAPI backend:
    python main.py
    # or
    uvicorn main:app --reload --port 8000

The Telegram bot (if TELEGRAM_BOT_TOKEN is set) starts automatically
in a background thread alongside the FastAPI server.
"""
import logging
import os
import uvicorn
from app.api.routes import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if __name__ == "__main__":
    # Start Telegram bot in background thread if token is configured
    from app.api.telegram_bot import start_bot_thread
    start_bot_thread()

    app_env = os.getenv("APP_ENV", "development")
    uvicorn.run(
        "app.api.routes:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=app_env != "production",
        log_level="info",
    )
