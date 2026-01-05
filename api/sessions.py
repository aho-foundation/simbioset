"""Простой менеджер сессий с Redis (async версия для оптимизации производительности)."""

import json
import time
import uuid
from typing import Any, Dict, Optional

import redis.asyncio as aioredis  # type: ignore

from api.settings import REDIS_URL
from api.logger import root_logger

log = root_logger.debug


class SessionManager:
    """Менеджер сессий с хранением в Redis (async для неблокирующих операций)."""

    SESSION_TTL = None  # Бессрочное хранение

    def __init__(self) -> None:
        """Инициализация подключения к Redis (async клиент)."""
        self._redis: Optional[aioredis.Redis] = None
        self._redis_url = REDIS_URL

    async def _get_redis(self) -> aioredis.Redis:
        """Получает или создает async Redis клиент (lazy initialization)."""
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def close(self) -> None:
        """Закрывает соединение с Redis."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def create_session(self, data: Dict[str, Any]) -> str:
        """
        Создает новую сессию (async).

        Args:
            data: Данные сессии

        Returns:
            session_id: Уникальный идентификатор сессии
        """
        session_id = str(uuid.uuid4())
        redis_client = await self._get_redis()
        if self.SESSION_TTL is None:
            await redis_client.set(f"session:{session_id}", json.dumps(data))
        else:
            await redis_client.setex(f"session:{session_id}", self.SESSION_TTL, json.dumps(data))
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает данные сессии (async).

        Args:
            session_id: Идентификатор сессии

        Returns:
            Данные сессии или None если не найдена
        """
        redis_client = await self._get_redis()
        data = await redis_client.get(f"session:{session_id}")
        if data:
            # Обновляем TTL при доступе (только если TTL установлен)
            if self.SESSION_TTL is not None:
                await redis_client.expire(f"session:{session_id}", self.SESSION_TTL)
            return json.loads(data)
        return None

    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        Обновляет данные сессии (async).

        Args:
            session_id: Идентификатор сессии
            data: Новые данные сессии

        Returns:
            True если сессия обновлена, False если не найдена
        """
        redis_client = await self._get_redis()
        key = f"session:{session_id}"
        exists = await redis_client.exists(key)
        if exists:
            if self.SESSION_TTL is None:
                await redis_client.set(key, json.dumps(data))
            else:
                await redis_client.setex(key, self.SESSION_TTL, json.dumps(data))
            return True
        return False

    async def delete_session(self, session_id: str) -> bool:
        """
        Удаляет сессию (async).

        Args:
            session_id: Идентификатор сессии

        Returns:
            True если сессия удалена, False если не найдена
        """
        redis_client = await self._get_redis()
        deleted = await redis_client.delete(f"session:{session_id}")
        return bool(deleted)

    async def get_or_create_telegram_session(self, telegram_user_id: int, username: Optional[str] = None) -> str:
        """
        Получает или создает сессию для Telegram пользователя (async).

        Args:
            telegram_user_id: ID пользователя в Telegram
            username: Username пользователя в Telegram (опционально)

        Returns:
            session_id: Идентификатор сессии
        """
        redis_client = await self._get_redis()
        # Проверяем существующую сессию по Telegram ID
        mapping_key = f"telegram_user:{telegram_user_id}"
        existing_session_id = await redis_client.get(mapping_key)

        if existing_session_id:
            session_id = existing_session_id
            # Проверяем что сессия еще существует
            session_data = await self.get_session(session_id)
            if session_data:
                # Обновляем last_activity
                session_data["last_activity"] = int(time.time())
                await self.update_session(session_id, session_data)
                return session_id

        # Создаем новую сессию
        session_data = {
            "telegram_user_id": telegram_user_id,
            "username": username,
            "created_at": int(time.time()),
            "last_activity": int(time.time()),
            "message_count": 0,
            "platform": "telegram",
        }
        session_id = await self.create_session(session_data)

        # Сохраняем маппинг telegram_user_id -> session_id
        if self.SESSION_TTL is None:
            await redis_client.set(mapping_key, session_id)
        else:
            await redis_client.setex(mapping_key, self.SESSION_TTL, session_id)

        return session_id

    async def get_telegram_session_id(self, telegram_user_id: int) -> Optional[str]:
        """
        Получает session_id по Telegram user ID (async).

        Args:
            telegram_user_id: ID пользователя в Telegram

        Returns:
            session_id или None если не найден
        """
        redis_client = await self._get_redis()
        mapping_key = f"telegram_user:{telegram_user_id}"
        session_id = await redis_client.get(mapping_key)
        if session_id:
            return session_id
        return None

    async def increment_message_count(self, session_id: str) -> bool:
        """
        Увеличивает счетчик сообщений в сессии (async).

        Args:
            session_id: Идентификатор сессии

        Returns:
            True если обновлено успешно, False если сессия не найдена
        """
        session_data = await self.get_session(session_id)
        if session_data:
            session_data["message_count"] = session_data.get("message_count", 0) + 1
            session_data["last_activity"] = int(time.time())
            return await self.update_session(session_id, session_data)
        return False


# Глобальный экземпляр менеджера сессий
session_manager = SessionManager()
