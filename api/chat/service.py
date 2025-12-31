"""Chat service for managing chat sessions."""

import time
import uuid
from typing import List

from api.llm import call_llm
from api.logger import root_logger

from .models import ChatSession, ChatSessionCreate

log = root_logger.debug


class ChatSessionService:
    """Service for managing chat sessions."""

    def __init__(self):
        """Initialize service."""
        self._sessions: dict[str, ChatSession] = {}

    def create_session(self, session_data: ChatSessionCreate) -> ChatSession:
        """
        Create a new chat session.

        Args:
            session_data: Session creation data

        Returns:
            Created ChatSession
        """
        session_id = str(uuid.uuid4())
        now = int(time.time() * 1000)

        session = ChatSession(
            id=session_id,
            topic=session_data.topic,
            created_at=now,
            updated_at=now,
            message_count=0,
            conceptTreeId=session_data.conceptTreeId,
        )

        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            ChatSession or None if not found
        """
        return self._sessions.get(session_id)

    def update_session(self, session_id: str, updates: dict) -> ChatSession | None:
        """
        Update session.

        Args:
            session_id: Session identifier
            updates: Fields to update

        Returns:
            Updated ChatSession or None if not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.updated_at = int(time.time() * 1000)
        return session

    def increment_message_count(self, session_id: str) -> ChatSession | None:
        """
        Increment message count for session.

        Args:
            session_id: Session identifier

        Returns:
            Updated ChatSession or None if not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        session.message_count += 1
        session.updated_at = int(time.time() * 1000)
        return session

    def get_all_sessions(self) -> list[ChatSession]:
        """
        Get all sessions.

        Returns:
            List of all ChatSessions
        """
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


async def generate_starters() -> List[str]:
    """
    Generates conversation starters for the symbiosis project using LLM.

    Returns:
        List of 3 conversation starter questions/phrases
    """
    prompt = """
    You are an expert in symbiosis and biosphere research. Generate 3 engaging conversation starters
    for a platform about symbiosis and ecosystem improvement. Each starter should be:
    - In Russian language
    - Concise (under 100 characters)
    - Thought-provoking and relevant to symbiosis/biosphere topics
    - Varied in approach (some questions, some statements)

    Output ONLY a JSON array of strings, e.g. ["question 1", "statement 2", "question 3"].
    """
    try:
        response = await call_llm(prompt)
        # Extract JSON from response
        import re
        import json

        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            # Ensure result is a list of strings
            if isinstance(result, list) and all(isinstance(item, str) for item in result):
                return result[:3]  # Return max 3 starters
        return ["что такое симбиоз?", "давай исследовать экосистему!", "как улучшить биосферу?"]
    except Exception as e:
        log(f"⚠️ Starters generation failed: {e}")
        return ["что такое симбиоз?", "давай исследовать экосистему!", "как улучшить биосферу?"]


# Global instance
chat_session_service = ChatSessionService()
