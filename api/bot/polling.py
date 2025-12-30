"""
Lightweight polling-mode Telegram bot wrapper.

Этот модуль предоставляет минимальную реализацию PollingTelegramBot,
совместимую с BotManager.start_polling и MessageProcessor:

- get_updates(offset, timeout)         → список апдейтов Telegram
- set_my_commands(commands, scope)    → no-op заглушки

Реальная логика Telegram API уже инкапсулирована в этом классе и
используется асинхронно из BotManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp

from api.logger import root_logger


log = root_logger.debug


@dataclass
class Update:
    """Простейшая модель Telegram Update, достаточная для MessageProcessor."""

    update_id: int
    message: Optional[Dict[str, Any]] = None


class PollingTelegramBot:
    """
    Минималистичный Telegram Bot для polling-режима.

    Поддерживаем только то, что реально используется:
    - get_updates()
    - set_my_commands()
    """

    def __init__(self, token: str, storage: Any = None) -> None:
        self.token = token
        self.storage = storage
        self._session: Optional[aiohttp.ClientSession] = None
        self._base_url = f"https://api.telegram.org/bot{self.token}"
        self._webhook_deleted = False  # Флаг, чтобы удалить webhook только один раз

    async def __aenter__(self) -> "PollingTelegramBot":
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Выполнить запрос к Telegram Bot API."""
        assert self._session is not None, "HTTP session is not initialized"

        url = f"{self._base_url}/{method}"
        async with self._session.post(url, json=payload or {}) as resp:
            data = await resp.json()
            if not data.get("ok", False):
                error_code = data.get("error_code")
                error_desc = data.get("description", "")

                # Обработка ошибки 409: webhook активен
                if error_code == 409 and "webhook" in error_desc.lower():
                    if not self._webhook_deleted:
                        log("⚠️ Webhook is active, deleting webhook and switching to web API mode")
                        # Удаляем webhook один раз
                        try:
                            await self._delete_webhook()
                            self._webhook_deleted = True
                        except Exception as e:
                            log(f"⚠️ Failed to delete webhook: {e}")
                    # Возвращаем пустой результат, чтобы прекратить polling retry
                    return {"ok": False, "error_code": 409, "description": error_desc, "result": []}

                log(f"Telegram API error for {method}: {data}")
            return data

    async def _delete_webhook(self) -> None:
        """Удалить webhook для переключения на polling/web API режим."""
        assert self._session is not None, "HTTP session is not initialized"
        url = f"{self._base_url}/deleteWebhook"
        async with self._session.post(url, json={"drop_pending_updates": False}) as resp:
            data = await resp.json()
            if data.get("ok"):
                log("✅ Webhook deleted successfully")
            else:
                log(f"⚠️ Failed to delete webhook: {data}")

    async def get_updates(self, offset: int = 0, timeout: int = 30) -> tuple[List[Update], bool]:
        """
        Получить апдейты от Telegram.

        Возвращаем список простых Update-объектов, которые далее обрабатывает MessageProcessor.
        При ошибке 409 (webhook активен) возвращает пустой список без retry.

        Returns:
            Tuple of (updates list, is_webhook_blocked)
        """
        params: Dict[str, Any] = {"timeout": timeout}
        if offset:
            params["offset"] = offset

        data = await self._request("getUpdates", params)

        # Если ошибка 409, возвращаем пустой список (webhook активен, используем web API)
        if not data.get("ok") and data.get("error_code") == 409:
            log("⚠️ Polling blocked by active webhook, switching to web API mode")
            return [], True

        results = data.get("result", [])

        # Логируем сколько апдейтов пришло и с каким offset, чтобы отслеживать работу polling-цикла
        log(f"PollingTelegramBot.get_updates received {len(results)} updates for offset={offset}, timeout={timeout}")

        updates: List[Update] = []
        for raw in results:
            msg = raw.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = (msg.get("text") or "").replace("\n", " ")
            if text:
                text = text[:120]
            log(f"Handling update_id={raw.get('update_id', 0)} chat_id={chat_id} text='{text}'")

            updates.append(Update(update_id=raw.get("update_id", 0), message=msg))

        return updates, False

    async def set_my_commands(self, commands: List[Dict[str, Any]], scope: Dict[str, Any]) -> bool:
        """
        Установка команд бота.

        BotManager сейчас просто очищает команды, поэтому достаточно корректно
        отправить запрос и вернуть bool.
        """
        payload = {"commands": commands, "scope": scope}
        data = await self._request("setMyCommands", payload)
        return bool(data.get("ok", False))
