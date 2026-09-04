"""
Sehat Saathi - WhatsApp Webhook (Twilio)
=========================================
Handles incoming WhatsApp messages via Twilio sandbox.
Twilio sends a POST request with form fields: From, Body, etc.
We reply with TwiML.

Setup:
  1. Create a Twilio account → enable WhatsApp Sandbox
  2. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM in .env
  3. Point Twilio webhook → https://<your-domain>/whatsapp/incoming
  4. For local dev: use ngrok → ngrok http 8000
"""
import logging
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import PlainTextResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

# Lazy agent reference (shared with routes.py via module-level singleton)
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from app.agent.mock_agent import MockSehatAgent
        _agent = MockSehatAgent()
    return _agent


def _twiml_response(message: str) -> str:
    """Wrap a text reply in Twilio TwiML XML."""
    # Escape XML special characters
    safe = (
        message
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{safe}</Message>"
        "</Response>"
    )


@router.post("/incoming", response_class=PlainTextResponse)
async def whatsapp_incoming(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    To: str = Form(default=""),
    ProfileName: str = Form(default="User"),
):
    """
    Receive an incoming WhatsApp message from Twilio and reply via TwiML.

    Twilio POSTs form-encoded data; we return TwiML XML.
    The session_id is derived from the sender's phone number so each
    WhatsApp user gets persistent memory.
    """
    # Use phone number as stable session ID
    session_id = From.replace("whatsapp:", "").replace("+", "").strip()
    user_message = Body.strip()

    logger.info("WhatsApp message from %s (%s): %s", From, ProfileName, user_message[:80])

    if not user_message:
        reply = "Namaste 🙏 I am Sehat Saathi, your health awareness assistant. How can I help you today?"
        return PlainTextResponse(_twiml_response(reply), media_type="application/xml")

    try:
        agent = _get_agent()
        result = agent.chat(user_message=user_message, session_id=session_id)
        reply = result.get("response", "Sorry, I could not process your message. Please try again.")

        # WhatsApp has a 1600-char limit per message
        if len(reply) > 1550:
            reply = reply[:1547] + "..."

        logger.info("WhatsApp reply to %s: %s...", From, reply[:80])
        return PlainTextResponse(_twiml_response(reply), media_type="application/xml")

    except Exception as e:
        logger.exception("WhatsApp processing error: %s", e)
        fallback = (
            "I'm sorry, I encountered an error. "
            "For health emergencies, please call 108. "
            "For health queries, call 104 (National Health Helpline)."
        )
        return PlainTextResponse(_twiml_response(fallback), media_type="application/xml")


@router.get("/status", tags=["WhatsApp"])
async def whatsapp_status():
    """Check if Twilio WhatsApp is configured."""
    configured = bool(
        getattr(settings, "twilio_account_sid", None)
        and getattr(settings, "twilio_auth_token", None)
    )
    return {
        "whatsapp_enabled": configured,
        "sandbox_number": getattr(settings, "twilio_whatsapp_from", "Not configured"),
        "webhook_path": "/whatsapp/incoming",
        "note": "Point Twilio sandbox webhook to https://<your-domain>/whatsapp/incoming",
    }
