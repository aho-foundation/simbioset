"""Chat service for managing chat sessions."""

import json
import random
import time
import uuid
import fcntl
from pathlib import Path
from typing import List, Set

from api.llm import call_llm
from api.logger import root_logger

from .models import ChatSession, ChatSessionCreate

log = root_logger.debug

# Кеш стартеров
_STARTERS_CACHE_FILE = Path("data/starters_cache.json")
_STARTERS_CACHE: Set[str] = set()
_MAX_CACHED_STARTERS = 250


def _load_starters_cache() -> Set[str]:
    """Загружает кеш стартеров из файла."""
    global _STARTERS_CACHE
    if _STARTERS_CACHE:
        return _STARTERS_CACHE

    _STARTERS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not _STARTERS_CACHE_FILE.exists():
        # Инициализируем с базовыми стартерами
        initial_starters = {
            "Что такое симбиоз и симбиосеть?",
            "Давай вместе исследовать экосистему!",
            "Как можно улучшать качества биосферы?",
        }
        _save_starters_cache(initial_starters)
        _STARTERS_CACHE = initial_starters
        return _STARTERS_CACHE

    try:
        with open(_STARTERS_CACHE_FILE, "r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
                _STARTERS_CACHE = set(data.get("starters", []))
                log(f"✅ Загружено {len(_STARTERS_CACHE)} стартеров из кеша")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        log(f"⚠️ Ошибка загрузки кеша стартеров: {e}")
        _STARTERS_CACHE = {
            "Что такое симбиоз и симбиосеть?",
            "Давай вместе исследовать экосистему!",
            "Как можно улучшать качества биосферы?",
        }

    return _STARTERS_CACHE


def _save_starters_cache(starters: Set[str]) -> None:
    """Сохраняет кеш стартеров в файл."""
    try:
        with open(_STARTERS_CACHE_FILE, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump({"starters": list(starters)}, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        log(f"⚠️ Ошибка сохранения кеша стартеров: {e}")


# Загружаем кеш при импорте модуля
_load_starters_cache()


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
    Generates conversation starters for the symbiosis project.
    
    Генерирует новые стартеры через LLM и кеширует их.
    После накопления 250 стартеров в кеше, возвращает только из кеша.

    Returns:
        List of 3 conversation starter questions/phrases
    """
    global _STARTERS_CACHE

    # Загружаем кеш если еще не загружен
    cache = _load_starters_cache()

    # Если в кеше уже 250+ стартеров, возвращаем случайные 3 из кеша
    if len(cache) >= _MAX_CACHED_STARTERS:
        log(f"📦 Кеш стартеров полон ({len(cache)}), возвращаем из кеша")
        return random.sample(list(cache), min(3, len(cache)))

    # Генерируем новые стартеры через LLM
    prompt = """
    You are an expert in symbiosis and biosphere research. Generate 3 engaging conversation starters
    for a platform about symbiosis and ecosystem improvement. Each starter should be:
    - In Russian language
    - Concise (under 100 characters)
    - Thought-provoking and relevant to symbiosis/biosphere topics
    - Varied in approach (some questions, some statements)
    - Different from common starters like "что такое симбиоз" or "давай исследовать экосистему"

    Output ONLY a JSON array of strings, e.g. ["question 1", "statement 2", "question 3"].
    """
    try:
        response = await call_llm(prompt, origin="generate_starters")
        # Extract JSON from response
        import re

        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            # Ensure result is a list of strings
            if isinstance(result, list) and all(isinstance(item, str) for item in result):
                new_starters = [s.strip() for s in result[:3] if s.strip()]

                # Добавляем новые стартеры в кеш (исключая дубликаты)
                cache.update(new_starters)
                _STARTERS_CACHE = cache

                # Сохраняем кеш в файл
                _save_starters_cache(cache)

                log(f"✅ Сгенерировано {len(new_starters)} новых стартеров, в кеше теперь {len(cache)}")
                return new_starters

        # Fallback на статичные стартеры при ошибке парсинга
        fallback = ["Что такое симбиоз и симбиосеть?", "Давай вместе исследовать экосистему!", "Как можно улучшать качества биосферы?"]
        cache.update(fallback)
        _STARTERS_CACHE = cache
        _save_starters_cache(cache)
        return fallback

    except Exception as e:
        log(f"⚠️ Starters generation failed: {e}")
        # Fallback на статичные стартеры при ошибке
        fallback = ["Что такое симбиоз и симбиосеть?", "Давай вместе исследовать экосистему!", "Как можно улучшать качества биосферы?"]
        cache.update(fallback)
        _STARTERS_CACHE = cache
        _save_starters_cache(cache)
        return fallback


# Global instance
chat_session_service = ChatSessionService()
