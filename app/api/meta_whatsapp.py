"""
Sehat Saathi - Meta WhatsApp Cloud API Webhook
===============================================
Handles incoming WhatsApp messages via Meta's official Cloud API (100% free).
No Twilio needed. No credit card needed.

How it works:
  1. Meta sends a POST to /meta-whatsapp/incoming when user messages your bot
  2. We call the Meta Graph API to send a reply back
  3. For verification, Meta sends a GET with hub.challenge — we echo it back

Setup (see README or docs for full guide):
  1. Go to https://developers.facebook.com → Create App → Business
  2. Add "WhatsApp" product to your app
  3. Copy Phone Number ID, Token → paste into .env
  4. Set WHATSAPP_VERIFY_TOKEN to any secret string you choose
  5. Point webhook → https://<ngrok-url>/meta-whatsapp/incoming
  6. Subscribe to "messages" webhook field

Free tier: 1,000 conversations/month free forever.
"""
from __future__ import annotations

import logging
import threading
import httpx

from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse, JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meta-whatsapp", tags=["Meta WhatsApp"])

# ---------------------------------------------------------------------------
# Meta Graph API helpers
# ---------------------------------------------------------------------------

META_API_URL = "https://graph.facebook.com/v19.0"


def _send_whatsapp_message(to: str, text: str) -> bool:
    """Send a text reply via Meta WhatsApp Cloud API. Returns True on success."""
    if not settings.meta_whatsapp_token or not settings.meta_phone_number_id:
        logger.warning("Meta WhatsApp not configured — skipping send.")
        return False

    # WhatsApp has a ~4096-char limit; truncate at word boundary to be safe
    if len(text) > 4000:
        truncated = text[:3990]
        last_space = truncated.rfind(" ")
        text = (truncated[:last_space] if last_space > 0 else truncated) + "…\n\n📞 Call 104 for more info."

    url = f"{META_API_URL}/{settings.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            logger.info("Message sent to %s — status %s", to, resp.status_code)
            return True
    except httpx.HTTPStatusError as e:
        logger.error("Meta API HTTP error sending to %s: %s — %s", to, e.response.status_code, e.response.text)
        return False
    except Exception as e:
        logger.exception("Meta API error sending to %s: %s", to, e)
        return False


# ---------------------------------------------------------------------------
# Lazy agent
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
# Webhook verification (GET) — Meta calls this once when you register the URL
# ---------------------------------------------------------------------------

@router.get("/incoming")
async def verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    """
    Meta webhook verification handshake.
    Meta sends hub.challenge — we echo it back if the token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_whatsapp_verify_token:
        logger.info("Meta WhatsApp webhook verified successfully.")
        return PlainTextResponse(hub_challenge)

    logger.warning(
        "Webhook verification failed. mode=%s token_match=%s",
        hub_mode,
        hub_verify_token == settings.meta_whatsapp_verify_token,
    )
    return PlainTextResponse("Verification failed", status_code=403)


# ---------------------------------------------------------------------------
# Incoming messages (POST) — Meta calls this for every user message
# ---------------------------------------------------------------------------

@router.post("/incoming")
async def receive_message(request: Request):
    """
    Receive an incoming WhatsApp message from Meta Cloud API and reply.

    Meta sends a JSON payload with nested message objects.
    We extract the text, run it through the Sehat Saathi agent, and reply.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "ok"}, status_code=200)  # Always 200 to Meta

    # Always return 200 immediately so Meta doesn't retry
    # (process in-band since FastAPI handles async fine here)

    try:
        entry = body.get("entry", [])
        if not entry:
            return JSONResponse({"status": "ok"})

        changes = entry[0].get("changes", [])
        if not changes:
            return JSONResponse({"status": "ok"})

        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            # Could be a status update (delivered/read) — ignore silently
            return JSONResponse({"status": "ok"})

        msg = messages[0]
        msg_type = msg.get("type", "")
        sender = msg.get("from", "")  # Phone number e.g. "919876543210"

        if msg_type != "text":
            # Handle non-text gracefully
            _send_whatsapp_message(
                sender,
                "Namaste 🙏 I can read text messages. Please type your health question in any Indian language."
            )
            return JSONResponse({"status": "ok"})

        user_text = msg.get("text", {}).get("body", "").strip()
        if not user_text:
            return JSONResponse({"status": "ok"})

        logger.info("Meta WhatsApp from %s: %s", sender, user_text[:80])

        # Use phone number as stable session ID (gives persistent memory per user)
        session_id = f"wa_{sender}"

        agent = _get_agent()
        result = agent.chat(user_message=user_text, session_id=session_id)
        reply = result.get("response", "Sorry, I could not process your message. Please try again.")

        _send_whatsapp_message(sender, reply)

    except Exception as e:
        logger.exception("Meta WhatsApp processing error: %s", e)
        # Don't crash — Meta expects 200 always

    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------

@router.get("/status", tags=["Meta WhatsApp"])
async def meta_whatsapp_status():
    """Check if Meta WhatsApp Cloud API is configured."""
    token_set = bool(settings.meta_whatsapp_token)
    phone_id_set = bool(settings.meta_phone_number_id)
    verify_token_set = bool(settings.meta_whatsapp_verify_token)
    configured = token_set and phone_id_set and verify_token_set
    return {
        "meta_whatsapp_enabled": configured,
        "token_configured": token_set,
        "phone_number_id_configured": phone_id_set,
        "verify_token_configured": verify_token_set,
        "webhook_path": "/meta-whatsapp/incoming",
        "note": "Point Meta webhook to https://<your-ngrok-url>/meta-whatsapp/incoming",
    }
