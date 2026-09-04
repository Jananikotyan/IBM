"""
Sehat Saathi - FastAPI Routes
==============================
Exposes the Sehat Saathi agent as a REST API.

Endpoints:
  POST /chat          — Main chat endpoint
  GET  /health        — Health check
  POST /clear-memory  — Clear conversation history for a session
  POST /voice         — Voice-to-text + chat (if Watson STT configured)
  GET  /sessions      — List active sessions (dev only)
"""
import logging
import base64
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthCheckResponse,
    ClearMemoryRequest,
    VoiceInputRequest,
)
from app.agent.memory import clear_memory, list_sessions
from app.config import settings
from app.api.whatsapp import router as whatsapp_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sehat Saathi API",
    description=(
        "Multilingual AI Healthcare Awareness Assistant for rural and underserved communities. "
        "Powered by IBM watsonx.ai (Granite) + LangChain."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Streamlit frontend and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WhatsApp router
app.include_router(whatsapp_router)

# Lazy-load agent to avoid startup delay
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        # Always use MockSehatAgent as the base — it handles all tools
        # OLLAMA_MODE enhances the LLM responses inside mock agent
        logger.info("Starting Sehat Saathi agent (mock_mode=%s, ollama_mode=%s)",
                    settings.mock_mode, settings.ollama_mode)
        from app.agent.mock_agent import MockSehatAgent
        _agent = MockSehatAgent()
    return _agent


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """API health check endpoint."""
    return {
        "status": "ok",
        "service": "Sehat Saathi",
        "version": "1.0.0",
        "llm_provider": "IBM watsonx.ai (Granite)" if not settings.mock_mode else "Mock/Demo Mode (no API keys)",
        "mock_mode": settings.mock_mode,
    }


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message to Sehat Saathi.

    The assistant will:
    - Detect the language of your message
    - Check for medical emergencies (red flags)
    - Route to appropriate health tools
    - Respond in your language

    Supports: English, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Punjabi, Malayalam
    """
    try:
        agent = _get_agent()
        result = agent.chat(
            user_message=request.message,
            session_id=request.session_id,
        )

        # Track analytics (non-blocking, best-effort)
        try:
            from app.analytics import track_query
            track_query(
                session_id=request.session_id,
                message=request.message,
                detected_language=result.get("detected_language", "en"),
                category=result.get("category", "general"),
                triage_tier=result.get("triage_tier"),
                is_emergency=result.get("is_emergency", False),
                location=result.get("location"),
            )
        except Exception as analytics_err:
            logger.debug("Analytics tracking skipped: %s", analytics_err)

        return ChatResponse(
            response=result["response"],
            session_id=request.session_id,
            detected_language=result.get("detected_language", "en"),
            is_emergency=result.get("is_emergency", False),
        )
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in /chat: %s", e)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again.",
        )


@app.post("/clear-memory", tags=["Session"])
async def clear_session_memory(request: ClearMemoryRequest):
    """Clear the conversation history for a specific session."""
    clear_memory(request.session_id)
    return {"status": "ok", "message": f"Memory cleared for session: {request.session_id}"}


@app.post("/voice", tags=["Voice"])
async def voice_chat(request: VoiceInputRequest):
    """
    Convert voice input to text, then process as a chat message.
    Requires Watson Speech-to-Text to be configured.
    """
    if not settings.watson_stt_api_key or settings.watson_stt_api_key == "your_stt_api_key_here":
        raise HTTPException(
            status_code=501,
            detail="Voice input is not configured. Please set WATSON_STT_API_KEY.",
        )

    try:
        from ibm_watson import SpeechToTextV1
        from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

        authenticator = IAMAuthenticator(settings.watson_stt_api_key)
        stt = SpeechToTextV1(authenticator=authenticator)
        stt.set_service_url(settings.watson_stt_url)

        audio_data = base64.b64decode(request.audio_base64)
        response = stt.recognize(
            audio=audio_data,
            content_type=request.content_type,
            model="en-IN_NarrowbandModel",
        ).get_result()

        transcripts = response.get("results", [])
        if not transcripts:
            raise HTTPException(status_code=400, detail="Could not transcribe audio.")

        text = transcripts[0]["alternatives"][0]["transcript"].strip()
        logger.info("Transcribed voice input: %s", text)

        # Process as normal chat
        agent = _get_agent()
        result = agent.chat(user_message=text, session_id=request.session_id)

        return {
            "transcribed_text": text,
            "response": result["response"],
            "session_id": request.session_id,
            "detected_language": result.get("detected_language", "en"),
            "is_emergency": result.get("is_emergency", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Voice processing error: %s", e)
        raise HTTPException(status_code=500, detail="Voice processing failed.")


@app.get("/analytics", tags=["Analytics"])
async def get_analytics():
    """Return aggregated usage analytics for the dashboard."""
    try:
        from app.analytics import get_summary
        return get_summary()
    except Exception as e:
        logger.error("Analytics error: %s", e)
        raise HTTPException(status_code=500, detail="Could not load analytics.")


@app.get("/analytics/heatmap", tags=["Analytics"])
async def get_heatmap_data():
    """Return location-tagged query data for the disease heatmap."""
    try:
        from app.analytics import get_disease_heatmap_data
        return {"points": get_disease_heatmap_data()}
    except Exception as e:
        logger.error("Heatmap error: %s", e)
        raise HTTPException(status_code=500, detail="Could not load heatmap data.")


@app.get("/sessions", tags=["System"])
async def get_sessions():
    """List active conversation sessions (development use only)."""
    if settings.app_env == "production":
        raise HTTPException(status_code=403, detail="Not available in production.")
    return {"sessions": list_sessions()}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again.",
            "helpline": "104 (National Health Helpline)",
        },
    )
