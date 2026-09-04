"""
Sehat Saathi - Conversation Memory Management
=============================================
Wraps LangChain ConversationBufferMemory with session support.
Each user session gets its own isolated memory object.
"""
import logging
from typing import Dict
from langchain_classic.memory import ConversationBufferMemory

logger = logging.getLogger(__name__)

# In-memory session store: session_id -> ConversationBufferMemory
_session_store: Dict[str, ConversationBufferMemory] = {}


def get_memory(session_id: str, k: int = 10) -> ConversationBufferMemory:
    """
    Retrieve or create a ConversationBufferMemory for the given session.

    Args:
        session_id: Unique identifier for the conversation session.
        k: Not used for ConversationBufferMemory, kept for API parity.

    Returns:
        ConversationBufferMemory instance bound to this session.
    """
    if session_id not in _session_store:
        logger.info("Creating new memory for session: %s", session_id)
        _session_store[session_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            human_prefix="User",
            ai_prefix="Sehat Saathi",
        )
    return _session_store[session_id]


def clear_memory(session_id: str) -> None:
    """Clear the conversation memory for a given session."""
    if session_id in _session_store:
        _session_store[session_id].clear()
        del _session_store[session_id]
        logger.info("Cleared memory for session: %s", session_id)


def list_sessions() -> list[str]:
    """Return all active session IDs."""
    return list(_session_store.keys())
