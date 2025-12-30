"""
LLM API Proxy Client - Provides LLM access with retry logic and model management
Поддерживает context_size_hint для оптимизации выбора модели.
"""

import asyncio
import json
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
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
        timeout = aiohttp.ClientTimeout(total=120.0)
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
    context_size_hint: Optional[str] = None,
) -> str:
    """
    Вызывает прокси-сервис для получения ответа от LLM.
    Использует прямой HTTP запрос для поддержки context_size_hint.

    Args:
        messages: Список сообщений в формате OpenAI API
        model: Имя модели (опционально, если не указано - выбирается автоматически)
        context_size_hint: Подсказка о размере контекста ("normal" или "large")

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
        if context_size_hint:
            body["context_size_hint"] = context_size_hint

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
            elif status_code == 503:
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


def _determine_context_size_hint(context: str) -> str:
    """
    Определяет подсказку о размере контекста на основе его длины.

    Args:
        context: Текст контекста

    Returns:
        "normal" или "large"
    """
    # Приблизительный расчет: 1 токен ≈ 4 символа
    # Большой контекст: > 10000 символов (≈ 2500 токенов)
    return "large" if len(context) > 10000 else "normal"


@retry(
    retry=retry_if_exception_type(LLMTemporaryError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True,
)
async def call_llm_with_retry(
    llm_context: str,
    *,
    origin: str | None = None,
    context_size_hint: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Вызывает LLM с автоматическими повторами при временных ошибках.
    Автоматически определяет context_size_hint на основе размера контекста.

    Args:
        llm_context: Контекст для LLM
        origin: Тег источника для логирования
        context_size_hint: Подсказка о размере контекста ("normal" или "large").
                          Если не указано, определяется автоматически.
        model: Имя модели (опционально, если не указано - выбирается автоматически)

    Returns:
        Ответ от LLM

    Raises:
        LLMPermanentError: При невосстановимых ошибках
        LLMTemporaryError: При временных ошибках (будет повторено)
    """
    try:
        # Логируем входящий контекст для диагностики (короткий превью, без дампа всего текста)
        preview = llm_context.strip().replace("\n", " ")
        if len(preview) > 200:
            preview = preview[:200] + "…"
        origin_tag = origin or "generic"
        log(f"📝 LLM request origin={origin_tag} context_len={len(llm_context)} preview='{preview}'")

        # Определяем context_size_hint если не указан
        if context_size_hint is None:
            context_size_hint = _determine_context_size_hint(llm_context)

        # Вызываем прокси-сервис без указания модели - прокси выберет автоматически
        log(f"🤖 Generating reply via proxy {LLM_PROXY_URL} (origin={origin_tag}, context_hint={context_size_hint})")
        messages = [{"role": "user", "content": llm_context}]
        reply = await _call_proxy_api(messages, model=model, context_size_hint=context_size_hint)

        log(f"✅ reply successfully generated ({len(reply)} characters)")
        return reply

    except asyncio.TimeoutError as e:
        log(f"⏱️ Timeout calling proxy: {e}")
        raise LLMTemporaryError(f"Timeout: {e}")
    except LLMTemporaryError:
        # Пробрасываем временные ошибки как есть
        raise
    except LLMPermanentError as e:
        # Постоянные ошибки (например, авторизация) - модель уже удалена из списка в прокси
        # Пробрасываем как есть
        raise
    except Exception as e:
        error_msg = str(e).lower()
        log(f"❌ Unexpected error calling proxy: {e}")
        raise LLMTemporaryError(f"Unexpected error: {e}")


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

    async def generate(self, prompt: str, *, context_size_hint: Optional[str] = None) -> str:
        """
        Генерирует ответ на промпт через LLM.

        Args:
            prompt: Текст промпта
            context_size_hint: Подсказка о размере контекста ("normal" или "large")

        Returns:
            Ответ от LLM
        """
        return await call_llm_with_retry(prompt, origin="llm_client_wrapper", context_size_hint=context_size_hint)


def get_llm_client_wrapper() -> LLMClientWrapper:
    """
    Получает обертку над LLM клиентом с методом generate().
    Используется для совместимости с кодом, который ожидает метод generate().

    Returns:
        LLMClientWrapper с методом generate()
    """
    return LLMClientWrapper()


async def rephrase_search_query(query: str) -> List[str]:
    """
    Перефразирует поисковый запрос для поиска косвенных совпадений через LLM.
    Генерирует 2-3 альтернативные формулировки.

    Args:
        query: Исходный поисковый запрос

    Returns:
        Список альтернативных формулировок запроса
    """
    prompt = f"""
    You are a search expert. The user's query returned no results.
    Generate 3 alternative search queries that might find relevant information even if the exact keywords are missing.
    Focus on:
    1. Synonyms and related concepts
    2. Broader or narrower terms
    3. Different linguistic formulations
     
    User Query: "{query}"
     
    Output ONLY a JSON array of strings, e.g. ["query 1", "query 2", "query 3"].
    """
    try:
        response = await call_llm_with_retry(prompt, origin="rephrase_search_query", context_size_hint="normal")
        # Extract JSON from response (it might have markdown code blocks)
        import re

        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            # Ensure result is a list of strings
            if isinstance(result, list) and all(isinstance(item, str) for item in result):
                return result
            else:
                return []
        return []
    except Exception as e:
        log(f"⚠️ Query rephrasing failed: {e}")
        return []
