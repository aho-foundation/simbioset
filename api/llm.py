"""
LLM API Proxy Client - Provides LLM access through proxy.

Ретраи и очистка текста выполняются в прокси.
"""

import asyncio
import json
import re
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI
from api.logger import root_logger
from api.settings import LLM_PROXY_URL, LLM_PROXY_TOKEN
import aiohttp

log = root_logger.info

# Инициализация клиентов для прокси
_openai_client: Optional[AsyncOpenAI] = None
_http_session: Optional[aiohttp.ClientSession] = None


def get_llm_client() -> AsyncOpenAI:
    """
    Получает OpenAI клиент для прокси (публичный API).

    Returns:
        AsyncOpenAI клиент, настроенный для работы с прокси
    """
    return _get_openai_client()


def _get_openai_client() -> AsyncOpenAI:
    """Получает или создает OpenAI клиент для прокси."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            base_url=f"{LLM_PROXY_URL}/v1",
            api_key=LLM_PROXY_TOKEN or "not-needed",  # OpenAI SDK требует api_key, даже если не используется
            timeout=120.0,
        )
    return _openai_client


def _get_http_session() -> aiohttp.ClientSession:
    """Получает или создает aiohttp сессию для прямых запросов к прокси."""
    global _http_session
    if _http_session is None:
        # Увеличиваем таймаут для длинных запросов к LLM
        timeout = aiohttp.ClientTimeout(total=180.0, connect=30.0)
        _http_session = aiohttp.ClientSession(
            timeout=timeout,
        )
    return _http_session


async def close_llm_clients() -> None:
    """
    Закрывает все клиенты LLM (aiohttp сессию).
    Вызывается при shutdown приложения.
    """
    global _http_session
    if _http_session is not None:
        await _http_session.close()
        _http_session = None
        log("✅ LLM HTTP session closed")


# --- LLM Exceptions ---
class LLMError(Exception):
    """Base exception for LLM errors"""

    pass


class LLMTemporaryError(LLMError):
    """Temporary error, can be retried"""

    pass


class LLMPermanentError(LLMError):
    """Permanent error, retry is useless"""

    pass


async def _call_proxy_api(
    messages: List[dict],
    model: Optional[str] = None,
) -> str:
    """
    Вызывает прокси-сервис для получения ответа от LLM.

    Args:
        messages: Список сообщений в формате OpenAI API
        model: Имя модели (опционально, если не указано - выбирается автоматически)

    Returns:
        Текст ответа от LLM

    Raises:
        LLMTemporaryError: При временных ошибках
        LLMPermanentError: При постоянных ошибках (авторизация и т.д.)
    """
    session = _get_http_session()
    url = f"{LLM_PROXY_URL}/v1/chat/completions"

    try:
        # Формируем тело запроса
        body: Dict[str, Any] = {
            "messages": messages,
            "stream": False,
        }

        # Добавляем опциональные параметры
        if model:
            body["model"] = model

        # Формируем заголовки с токеном авторизации
        headers: Dict[str, str] = {}
        if LLM_PROXY_TOKEN:
            headers["Authorization"] = f"Bearer {LLM_PROXY_TOKEN}"
        else:
            log("⚠️ LLM_PROXY_TOKEN не установлен, запрос может быть отклонен")

        # Выполняем запрос
        async with session.post(url, json=body, headers=headers) as response:
            status_code = response.status

            # Проверяем статус ответа
            if status_code == 401:
                raise LLMPermanentError(f"Authorization error: HTTP {status_code}")
            elif status_code in [503, 504]:  # Service unavailable, Gateway timeout
                raise LLMTemporaryError(f"Service unavailable: HTTP {status_code}")
            elif status_code >= 500:
                raise LLMTemporaryError(f"Server error: HTTP {status_code}")
            elif status_code >= 400:
                raise LLMPermanentError(f"HTTP error {status_code}")

            data = await response.json()

        if not data.get("choices") or len(data["choices"]) == 0:
            raise LLMTemporaryError("Empty response from proxy: no choices returned")

        reply = data["choices"][0].get("message", {}).get("content", "")

        if not reply or len(reply.strip()) < 10:
            raise LLMTemporaryError("Got empty or too short response from proxy")

        return reply.strip()

    except aiohttp.ClientResponseError as e:
        # Обработка HTTP ошибок от aiohttp
        status_code = e.status
        if status_code == 401:
            raise LLMPermanentError(f"Authorization error: {e}")
        elif status_code == 503:
            raise LLMTemporaryError(f"Service unavailable: {e}")
        elif status_code >= 500:
            raise LLMTemporaryError(f"Server error: {e}")
        else:
            raise LLMPermanentError(f"HTTP error {status_code}: {e}")

    except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
        raise LLMTemporaryError(f"Request timeout: {e}")

    except aiohttp.ClientError as e:
        raise LLMTemporaryError(f"Network error: {e}")

    except Exception as e:
        # Неожиданные ошибки
        error_msg = str(e).lower()
        if "api_key" in error_msg or "authorization" in error_msg or "401" in error_msg:
            raise LLMPermanentError(f"Authorization error: {e}")
        raise LLMTemporaryError(f"Unexpected error: {e}")


async def call_llm(
    llm_context: str,
    *,
    origin: str | None = None,
    model: Optional[str] = None,
) -> str:
    """
    Вызывает LLM через прокси.

    Ретраи выполняются в прокси, здесь только простой вызов.

    Args:
        llm_context: Контекст для LLM
        origin: Тег источника для логирования
        model: Имя модели (опционально, если не указано - выбирается автоматически)

    Returns:
        Ответ от LLM

    Raises:
        LLMPermanentError: При невосстановимых ошибках
        LLMTemporaryError: При временных ошибках
    """
    # Логируем входящий контекст для диагностики (короткий превью, без дампа всего текста)
    preview = llm_context.strip().replace("\n", " ")
    if len(preview) > 200:
        preview = preview[:200] + "…"
    origin_tag = origin or "generic"
    log(f"📝 LLM request origin={origin_tag} context_len={len(llm_context)} preview='{preview}'")

    # Вызываем прокси-сервис без указания модели - прокси выберет автоматически
    # Ретраи выполняются в прокси
    log(f"🤖 Generating reply via proxy {LLM_PROXY_URL} (origin={origin_tag})")
    messages = [{"role": "user", "content": llm_context}]
    reply = await _call_proxy_api(messages, model=model)

    log(f"✅ reply successfully generated ({len(reply)} characters)")
    return reply


async def list_models() -> List[Dict[str, Any]]:
    """
    Получает список доступных моделей из прокси.

    Returns:
        Список словарей с информацией о моделях

    Raises:
        LLMPermanentError: При ошибках авторизации
        LLMTemporaryError: При временных ошибках
    """
    session = _get_http_session()
    url = f"{LLM_PROXY_URL}/v1/models"

    try:
        async with session.get(url) as response:
            status_code = response.status

            # Проверяем статус ответа
            if status_code == 401:
                raise LLMPermanentError(f"Authorization error: HTTP {status_code}")
            elif status_code >= 500:
                raise LLMTemporaryError(f"Server error: HTTP {status_code}")
            elif status_code >= 400:
                raise LLMPermanentError(f"HTTP error {status_code}")

            data = await response.json()

        return data.get("data", [])

    except aiohttp.ClientResponseError as e:
        status_code = e.status
        if status_code == 401:
            raise LLMPermanentError(f"Authorization error: {e}")
        elif status_code >= 500:
            raise LLMTemporaryError(f"Server error: {e}")
        else:
            raise LLMPermanentError(f"HTTP error {status_code}: {e}")

    except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
        raise LLMTemporaryError(f"Request timeout: {e}")

    except aiohttp.ClientError as e:
        raise LLMTemporaryError(f"Network error: {e}")

    except Exception as e:
        raise LLMTemporaryError(f"Unexpected error: {e}")


class LLMClientWrapper:
    """
    Обертка над OpenAI клиентом для совместимости с кодом,
    который использует метод generate().
    """

    async def generate(self, prompt: str) -> str:
        """
        Генерирует ответ на промпт через LLM.

        Args:
            prompt: Текст промпта

        Returns:
            Ответ от LLM
        """
        return await call_llm(prompt, origin="llm_client_wrapper")


def get_llm_client_wrapper() -> LLMClientWrapper:
    """
    Получает обертку над LLM клиентом с методом generate().
    Используется для совместимости с кодом, который ожидает метод generate().

    Returns:
        LLMClientWrapper с методом generate()
    """
    return LLMClientWrapper()
