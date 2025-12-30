"""
Simple Telegram Bot implementation using aiohttp.
Bot Manager for Telegram Bot lifecycle management.
"""

import asyncio
import signal
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import aiohttp
from api.logger import root_logger
from api.bot.handler import MessageProcessor
from api.settings import WEBHOOK_URL


log = root_logger.debug


@dataclass
class User:
    """Telegram user."""

    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@dataclass
class Chat:
    """Telegram chat."""

    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None


@dataclass
class Message:
    """Telegram message."""

    message_id: int
    chat: Chat
    from_user: Optional[User] = None
    text: Optional[str] = None
    date: int = 0
    photo: Optional[List[Dict]] = None
    document: Optional[Dict] = None
    sticker: Optional[Dict] = None
    entities: Optional[List[Dict]] = None
    reply_to_message: Optional["Message"] = None


@dataclass
class Update:
    """Telegram update."""

    update_id: int
    message: Optional[Message] = None


class BaseTelegramBot:
    """
    Base Telegram Bot implementation with common functionality.

    Uses aiohttp for HTTP requests to Telegram Bot API.
    """

    def __init__(self, token: str, redis_storage=None):
        """
        Initialize the bot.

        Args:
            token: Telegram bot token
            redis_storage: Optional Redis storage (not used yet)
        """
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.redis_storage = redis_storage

    async def __aenter__(self):
        """Enter async context."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()

    async def close(self) -> None:
        """Close the bot session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def send_message(
        self, chat_id: int, text: str, parse_mode: Optional[str] = None, reply_to_message_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Send a message to a chat.

        Args:
            chat_id: Chat ID
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, etc.)
            reply_to_message_id: Reply to message ID

        Returns:
            Response data or None on error
        """
        if not getattr(self, "session", None):
            raise RuntimeError("Bot session not initialized")

        data = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        if not self.session:
            raise RuntimeError("Bot session not initialized")

        try:
            async with self.session.post(f"{self.base_url}/sendMessage", json=data) as response:
                if response.status != 200:
                    log(f"Send message error: {response.status}")
                    return None

                result = await response.json()
                if not result.get("ok"):
                    log(f"Send message error: {result.get('description')}")
                    return None

                return result.get("result")

        except Exception as e:
            log(f"Error sending message: {e}")
            return None

    async def send_message_reaction(
        self,
        chat_id: int,
        message_id: int,
        emoji: str = "👍",
        is_big: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Set reaction on a message.

        Args:
            chat_id: Chat ID
            message_id: Message ID to react to
            reaction: List of reaction types. Each reaction can be:
                - {"type": "emoji", "emoji": "👍"} for emoji reactions
                - {"type": "custom_emoji", "custom_emoji_id": "123"} for custom emoji
                If None or empty list, removes all reactions
            is_big: If True, reaction will be shown in a bigger size

        Returns:
            Response data or None on error

        Example:
            # Simple emoji reaction
            await bot.send_message_reaction(chat_id, message_id, [{"type": "emoji", "emoji": "👍"}])

            # Remove all reactions
            await bot.send_message_reaction(chat_id, message_id, [])
        """
        if not getattr(self, "session", None):
            raise RuntimeError("Bot session not initialized")

        from typing import Any, Dict

        data: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
        }

        if emoji is not None:
            data["reaction"] = [{"type": "emoji", "emoji": emoji}]
        if is_big:
            data["is_big"] = is_big

        if not self.session:
            raise RuntimeError("Bot session not initialized")

        try:
            async with self.session.post(f"{self.base_url}/setMessageReaction", json=data) as response:
                if response.status != 200:
                    log(f"Send message reaction error: {response.status}")
                    return None

                result = await response.json()
                if not result.get("ok"):
                    log(f"Send message reaction error: {result.get('description')}")
                    return None

                return result.get("result")

        except Exception as e:
            log(f"Error sending message reaction: {e}")
            return None

    async def get_me(self) -> Optional[Dict[str, Any]]:
        """
        Get bot info.

        Returns:
            Bot info or None on error
        """
        if not self.session:
            raise RuntimeError("Bot session not initialized")

        try:
            async with self.session.get(f"{self.base_url}/getMe") as response:
                if response.status != 200:
                    log(f"Get me error: {response.status}")
                    return None

                result = await response.json()
                if not result.get("ok"):
                    log(f"Get me error: {result.get('description')}")
                    return None

                return result.get("result")

        except Exception as e:
            log(f"Error getting bot info: {e}")
            return None

    async def set_my_commands(
        self,
        commands: List[Dict[str, str]],
        scope: Optional[Dict[str, Any]] = None,
        language_code: Optional[str] = None,
    ) -> bool:
        """
        Set bot commands.

        Args:
            commands: List of command dictionaries
            scope: Command scope
            language_code: Language code

        Returns:
            True on success
        """
        if not self.session:
            raise RuntimeError("Bot session not initialized")

        data: Dict[str, Any] = {"commands": commands}
        if scope:
            data["scope"] = scope
        if language_code:
            data["language_code"] = language_code

        try:
            async with self.session.post(f"{self.base_url}/setMyCommands", json=data) as response:
                if response.status != 200:
                    log(f"Set commands error: {response.status}")
                    return False

                result = await response.json()
                return result.get("ok", False)

        except Exception as e:
            log(f"Error setting commands: {e}")
            return False

    def _parse_update(self, update_data: Dict[str, Any]) -> Update:
        """Parse update data from Telegram API."""
        message = None
        if "message" in update_data:
            message = self._parse_message(update_data["message"])

        return Update(
            update_id=update_data["update_id"],
            message=message,
        )

    def _parse_message(self, message_data: Dict[str, Any]) -> Message:
        """Parse message data from Telegram API."""
        chat = Chat(
            id=message_data["chat"]["id"],
            type=message_data["chat"]["type"],
            title=message_data["chat"].get("title"),
            username=message_data["chat"].get("username"),
        )

        from_user = None
        if "from" in message_data:
            from_user = User(
                id=message_data["from"]["id"],
                username=message_data["from"].get("username"),
                first_name=message_data["from"].get("first_name"),
                last_name=message_data["from"].get("last_name"),
            )

        # Parse reply_to_message if present
        reply_to_message = None
        if "reply_to_message" in message_data:
            reply_to_message = self._parse_message(message_data["reply_to_message"])

        return Message(
            message_id=message_data["message_id"],
            chat=chat,
            from_user=from_user,
            text=message_data.get("text"),
            date=message_data.get("date", 0),
            photo=message_data.get("photo"),
            document=message_data.get("document"),
            sticker=message_data.get("sticker"),
            entities=message_data.get("entities"),
            reply_to_message=reply_to_message,
        )


class WebhookTelegramBot(BaseTelegramBot):
    """
    Webhook Telegram Bot implementation.

    Uses aiohttp for HTTP requests to Telegram Bot API.
    """

    async def set_webhook(
        self,
        url: str,
        certificate: Optional[str] = None,
        ip_address: Optional[str] = None,
        max_connections: int = 40,
        allowed_updates: Optional[List[str]] = None,
        drop_pending_updates: bool = False,
        secret_token: Optional[str] = None,
    ) -> bool:
        """
        Set webhook URL for the bot.

        Args:
            url: HTTPS URL to send updates to
            certificate: Upload your public key certificate
            ip_address: Fixed IP address for outgoing webhook requests
            max_connections: Maximum allowed number of simultaneous HTTPS connections
            allowed_updates: List of allowed update types
            drop_pending_updates: Drop all pending updates
            secret_token: Secret token to be sent in a header

        Returns:
            True on success
        """
        if not self.session:
            raise RuntimeError("Bot session not initialized")

        data: Dict[str, Any] = {
            "url": url,
            "max_connections": max_connections,
            "drop_pending_updates": drop_pending_updates,
        }
        if certificate:
            data["certificate"] = certificate
        if ip_address:
            data["ip_address"] = ip_address
        if allowed_updates:
            data["allowed_updates"] = json.dumps(allowed_updates)
        if secret_token:
            data["secret_token"] = secret_token

        try:
            async with self.session.post(f"{self.base_url}/setWebhook", json=data) as response:
                if response.status != 200:
                    log(f"Set webhook error: {response.status}")
                    return False

                result = await response.json()
                return result.get("ok", False)

        except Exception as e:
            log(f"Error setting webhook: {e}")
            return False

    async def delete_webhook(self, drop_pending_updates: bool = False) -> bool:
        """
        Remove webhook integration.

        Args:
            drop_pending_updates: Drop all pending updates

        Returns:
            True on success
        """
        if not self.session:
            raise RuntimeError("Bot session not initialized")

        data: Dict[str, Any] = {"drop_pending_updates": drop_pending_updates}

        try:
            async with self.session.post(f"{self.base_url}/deleteWebhook", json=data) as response:
                if response.status != 200:
                    log(f"Delete webhook error: {response.status}")
                    return False

                result = await response.json()
                return result.get("ok", False)

        except Exception as e:
            log(f"Error deleting webhook: {e}")
            return False

    def handle_webhook_update(self, update_data: Dict[str, Any]) -> Update:
        """
        Handle incoming webhook update.

        Args:
            update_data: Raw update data from webhook

        Returns:
            Parsed Update object
        """
        return self._parse_update(update_data)


class PollingTelegramBot(BaseTelegramBot):
    """
    Polling Telegram Bot implementation with polling.

    Uses aiohttp for HTTP requests to Telegram Bot API.
    """

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 30,
        allowed_updates: Optional[List[str]] = None,
    ) -> List[Update]:
        """
        Get updates from Telegram.

        Args:
            offset: Update offset
            limit: Maximum number of updates
            timeout: Timeout in seconds
            allowed_updates: List of allowed update types

        Returns:
            List of Update objects
        """
        if not self.session:
            raise RuntimeError("Bot session not initialized")

        params: Dict[str, Any] = {
            "limit": limit,
            "timeout": timeout,
        }
        if offset is not None:
            params["offset"] = offset
        if allowed_updates:
            params["allowed_updates"] = json.dumps(allowed_updates)

        try:
            async with self.session.get(f"{self.base_url}/getUpdates", params=params) as response:
                if response.status != 200:
                    log(f"Telegram API error: {response.status}")
                    return []

                data = await response.json()
                if not data.get("ok"):
                    log(f"Telegram API error: {data.get('description')}")
                    return []

                return [self._parse_update(update) for update in data.get("result", [])]

        except Exception as e:
            log(f"Error getting updates: {e}")
            return []


class BotManager:
    """
    Manages the lifecycle of the Telegram bot.

    Handles initialization, startup, shutdown, and coordination
    of bot components including message processing.
    """

    def __init__(self, telegram_token: str, storage, vector_search, kb_service=None) -> None:
        """
        Initialize the bot manager.

        Args:
            telegram_token: Telegram bot token
            storage: Storage instance for messages
            vector_search: Vector search instance
            kb_service: Knowledge base service instance (optional)
        """
        self.telegram_token = telegram_token
        self.storage = storage
        self.vector_search = vector_search
        # Экземпляр PollingTelegramBot/WebhookTelegramBot создается лениво в start_*.
        # Используем Any, так как конкретный тип зависит от режима работы и импортируется динамически.
        self.bot: Any | None = None
        self.processor = MessageProcessor(storage, vector_search, kb_service)
        self.shutdown_requested = False

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    async def start_webhook(self) -> None:
        """Start the bot with webhook - only set the webhook, don't run a separate server."""
        log("Setting up Telegram bot webhook")

        try:
            async with WebhookTelegramBot(self.telegram_token) as bot:
                self.bot = bot

                # Setup bot commands
                await self._setup_commands()

                # Set webhook
                webhook_url = WEBHOOK_URL
                if not webhook_url:
                    raise ValueError("WEBHOOK_URL environment variable is required for webhook mode")

                if self.bot and hasattr(self.bot, "set_webhook"):
                    if not await self.bot.set_webhook(webhook_url):
                        raise RuntimeError("Failed to set webhook")
                else:
                    raise RuntimeError("Bot instance not available or has no set_webhook method")

                log(f"Webhook set to {webhook_url}")
                log("Bot webhook setup complete - using existing Granian server for webhook handling")

        except Exception as e:
            log(f"Error setting up bot webhook: {e}")
            raise
        finally:
            log("Bot webhook setup finished")

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        root_logger.info(f"Received signal {signal_name}, initiating graceful shutdown")
        self.shutdown_requested = True

    async def initialize(self) -> None:
        """Initialize bot components."""
        log("Initializing bot components")

        # Initialize vector search if needed
        if hasattr(self.vector_search, "initialize"):
            await self.vector_search.initialize()

        # Initialize processor
        await self.processor.initialize()

        log("Bot components initialized")

    async def start_polling(self) -> None:
        """Start the bot."""
        log("Starting Telegram bot polling")

        try:
            # Import here to avoid circular imports
            from api.bot.polling import PollingTelegramBot

            async with PollingTelegramBot(self.telegram_token, storage=self.storage) as bot:
                self.bot = bot

                # Setup bot commands
                await self._setup_commands()

                # Start background tasks
                await self._run_background_tasks()

        except Exception as e:
            log(f"Error starting bot polling: {e}")
            raise
        finally:
            log("Bot polling shutdown complete")

    async def _setup_commands(self) -> None:
        """Setup bot commands."""
        if not self.bot:
            return

        log("Setting up bot commands")

        # Clear existing commands
        await self.bot.set_my_commands([], scope={"type": "default"})
        await self.bot.set_my_commands([], scope={"type": "all_private_chats"})
        await self.bot.set_my_commands([], scope={"type": "all_group_chats"})

        log("Bot commands cleared")

    async def _run_background_tasks(self) -> None:
        """Run background tasks for message processing."""
        if not self.bot:
            return

        # Start message processing
        process_task = asyncio.create_task(self._process_updates())

        try:
            # Wait for both tasks
            await asyncio.gather(process_task)
        except asyncio.CancelledError:
            log("Background tasks cancelled")
        finally:
            # Cleanup
            process_task.cancel()
            try:
                await asyncio.gather(process_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

    async def _process_updates(self) -> None:
        """Process incoming Telegram updates."""
        if not self.bot:
            return

        log("Starting message processing loop")

        offset = 0
        consecutive_webhook_blocks = 0
        while not self.shutdown_requested:
            try:
                # Process updates
                offset, is_webhook_blocked = await self.processor.process_updates(self.bot, offset)

                # Если polling заблокирован webhook'ом
                if is_webhook_blocked:
                    consecutive_webhook_blocks += 1
                    # После нескольких блокировок прекращаем polling (webhook активен)
                    if consecutive_webhook_blocks >= 3:
                        log("⚠️ Polling blocked by active webhook, switching to web API mode (webhook)")
                        log("ℹ️ Bot will work via webhook endpoint only, polling stopped")
                        break
                else:
                    consecutive_webhook_blocks = 0

                # Small delay to prevent busy waiting
                await asyncio.sleep(1)

            except Exception as e:
                log(f"Error in message processing: {e}")
                await asyncio.sleep(5)

    async def shutdown(self) -> None:
        """Shutdown the bot gracefully."""
        log("Shutting down bot manager")

        self.shutdown_requested = True

        if self.bot:
            await self.bot.close()

        # MessageProcessor doesn't have a shutdown method, so we skip this
        pass

        log("Bot manager shutdown complete")
