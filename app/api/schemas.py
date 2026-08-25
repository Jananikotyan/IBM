"""
Sehat Saathi - API Request/Response Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class ChatRequest(BaseModel):
    """Incoming chat message from user."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's message (any language)",
        examples=["Mujhe bukhaar hai", "My baby is 6 weeks old. What vaccines are due?"],
    )
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique session ID for conversation continuity",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Mujhe 2 din se bukhaar hai",
                "session_id": "user-session-abc123",
            }
        }


class ChatResponse(BaseModel):
    """Response from Sehat Saathi assistant."""
    response: str = Field(..., description="Assistant's reply in the user's language")
    session_id: str = Field(..., description="Session ID for follow-up messages")
    detected_language: str = Field(
        default="en",
        description="ISO 639-1 code of detected input language (e.g., 'hi', 'en', 'ta')",
    )
    is_emergency: bool = Field(
        default=False,
        description="True if a life-threatening red flag was detected",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "response": "आपके लक्षणों के आधार पर...",
                "session_id": "user-session-abc123",
                "detected_language": "hi",
                "is_emergency": False,
                "timestamp": "2024-01-01T00:00:00Z",
            }
        }


class HealthCheckResponse(BaseModel):
    """API health check response."""
    status: str = "ok"
    service: str = "Sehat Saathi"
    version: str = "1.0.0"
    llm_provider: str = "IBM watsonx.ai (Granite)"


class ClearMemoryRequest(BaseModel):
    """Request to clear conversation memory for a session."""
    session_id: str


class VoiceInputRequest(BaseModel):
    """Voice-to-text input (for speech interface)."""
    audio_base64: str = Field(..., description="Base64-encoded audio data")
    content_type: str = Field(
        default="audio/wav",
        description="Audio content type (audio/wav, audio/mp3, audio/ogg)",
    )
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
