"""
Sehat Saathi - Telegram Bot Integration
=========================================
100% free. No credit card. No website account.
Just the Telegram app on your phone.

How it works (polling mode):
  - Bot connects to Telegram servers and polls for new messages
  - No webhook / no ngrok needed
  - Works perfectly on localhost

Setup (5 minutes):
  1. Open Telegram → search @BotFather → /newbot
  2. Give your bot a name and username
  3. Copy the token → paste TELEGRAM_BOT_TOKEN in .env
  4. Run: python -m app.api.telegram_bot
     (or it auto-starts when backend starts if TELEGRAM_BOT_TOKEN is set)
"""
from __future__ import annotations

import logging
import threading
import time
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot"

# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

def _tg(method: str, **kwargs) -> dict:
    """Call a Telegram Bot API method. Returns parsed JSON."""
    url = f"{TELEGRAM_API}{settings.telegram_bot_token}/{method}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=kwargs)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("Telegram API error %s: %s — %s", method, e.response.status_code, e.response.text[:200])
        return {}
    except Exception as e:
        logger.exception("Telegram API error %s: %s", method, e)
        return {}


def send_message(chat_id: int | str, text: str, parse_mode: str = "") -> bool:
    """Send a text message to a Telegram chat."""
    # Telegram limit is 4096 chars; truncate at word boundary
    if len(text) > 4000:
        truncated = text[:3990]
        last_space = truncated.rfind(" ")
        text = (truncated[:last_space] if last_space > 0 else truncated) + "…\n\n📞 Call 104 for more info."

    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    result = _tg("sendMessage", **payload)
    return bool(result.get("ok"))


def send_typing(chat_id: int | str) -> None:
    """Show 'typing…' indicator in the chat."""
    _tg("sendChatAction", chat_id=chat_id, action="typing")


# ---------------------------------------------------------------------------
# Agent (lazy singleton)
# ---------------------------------------------------------------------------

_agent = None
_agent_lock = threading.Lock()


def _get_agent():
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                from app.agent.mock_agent import MockSehatAgent
                _agent = MockSehatAgent()
    return _agent


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

HELP_TEXT = """🏥 *Sehat Saathi — Your Health Assistant*

I can help you with:
• 🤒 Symptom checking
• 💉 Vaccination schedules
• 🏥 Nearby health facilities
• 🌡️ Health awareness information

Just type your question in *any Indian language*:
Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Punjabi, Malayalam, or English.

*Example questions:*
• बुखार और सिरदर्द है
• நான் தலைவலியால் அவதிப்படுகிறேன்
• Nearest hospital in Delhi 110001
• Child vaccination schedule

*Commands:*
/start — Welcome message
/help  — Show this help
/clear — Clear conversation history
"""

WELCOME_TEXT = """🙏 *Namaste! I am Sehat Saathi*

आपका स्वास्थ्य सहायक — Your Health Companion

I provide free health awareness information for rural and underserved communities across India.

Type your health question in *any language* — Hindi, Tamil, Telugu, Bengali, Marathi, or English.

Type /help to see what I can do."""


def handle_update(update: dict) -> None:
    """Process a single Telegram update (message)."""
    message = update.get("message", {})
    if not message:
        return  # Ignore non-message updates (edited messages, etc.)

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    first_name = message.get("from", {}).get("first_name", "User")

    if not chat_id or not text:
        return

    logger.info("Telegram from %s (chat %s): %s", first_name, chat_id, text[:80])

    # Handle bot commands
    if text.startswith("/start"):
        send_message(chat_id, WELCOME_TEXT, parse_mode="Markdown")
        return

    if text.startswith("/help"):
        send_message(chat_id, HELP_TEXT, parse_mode="Markdown")
        return

    if text.startswith("/clear"):
        try:
            from app.agent.memory import clear_memory
            clear_memory(str(chat_id))
        except Exception:
            pass
        send_message(chat_id, "✅ Conversation history cleared. Start fresh!")
        return

    # Show typing indicator
    send_typing(chat_id)

    # Use chat_id as stable session ID (persistent memory per user)
    session_id = f"tg_{chat_id}"

    try:
        agent = _get_agent()
        result = agent.chat(user_message=text, session_id=session_id)
        reply = result.get("response", "Sorry, I could not process your message. Please try again.")
        send_message(chat_id, reply)

    except Exception as e:
        logger.exception("Error handling Telegram message: %s", e)
        send_message(
            chat_id,
            "I'm sorry, I encountered an error. "
            "For health emergencies please call 108. "
            "For health queries call 104 (National Health Helpline)."
        )


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------

def run_polling(stop_event: threading.Event | None = None) -> None:
    """
    Long-poll Telegram for updates and process them.
    Runs forever until stop_event is set (or KeyboardInterrupt).
    """
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return

    logger.info("Starting Telegram bot polling…")

    # Verify token works
    me = _tg("getMe")
    if not me.get("ok"):
        logger.error("Invalid TELEGRAM_BOT_TOKEN — bot will not start.")
        return

    bot_name = me.get("result", {}).get("username", "unknown")
    logger.info("Telegram bot started: @%s", bot_name)
    print(f"\n✅ Telegram bot running: https://t.me/{bot_name}\n   Send a message to start chatting!\n")

    offset = 0
    while not (stop_event and stop_event.is_set()):
        try:
            data = _tg("getUpdates", offset=offset, timeout=25, allowed_updates=["message"])
            if not data.get("ok"):
                time.sleep(5)
                continue

            updates = data.get("result", [])
            for update in updates:
                update_id = update.get("update_id", 0)
                offset = update_id + 1  # Acknowledge this update
                try:
                    handle_update(update)
                except Exception as e:
                    logger.exception("Error processing update %s: %s", update_id, e)

        except KeyboardInterrupt:
            logger.info("Telegram polling stopped.")
            break
        except Exception as e:
            logger.exception("Polling error: %s", e)
            time.sleep(5)  # Back off on error


def start_bot_thread() -> threading.Thread | None:
    """
    Start the Telegram bot in a background thread.
    Called automatically from main.py if TELEGRAM_BOT_TOKEN is set.
    Returns the thread (or None if token not configured).
    """
    if not settings.telegram_bot_token:
        return None

    stop_event = threading.Event()
    thread = threading.Thread(
        target=run_polling,
        args=(stop_event,),
        name="telegram-bot",
        daemon=True,  # Dies when main process exits
    )
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Run directly: python -m app.api.telegram_bot
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    # Add project root to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_polling()
