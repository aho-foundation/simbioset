"""
Message Processor for handling Telegram bot messages.
"""

import asyncio
from typing import Any, Dict, List, Optional

from api.logger import root_logger

log = root_logger.debug


class MessageProcessor:
    """
    Processes incoming Telegram messages and manages chat interactions.

    Handles message storage, vector indexing, and basic bot responses.
    """

    def __init__(self, storage, vector_search, kb_service=None) -> None:
        """
        Initialize the message processor.

        Args:
            storage: Storage instance for messages
            vector_search: Vector search instance for indexing
            kb_service: Knowledge base service instance (optional, will create if not provided)
        """
        self.storage = storage
        self.vector_search = vector_search
        self.kb_service = kb_service

    async def initialize(self) -> None:
        """Initialize processor components."""
        root_logger.info("Initializing message processor")

        # Index existing messages if needed
        # Index existing messages if needed
        # Implementation would require iterating through all known chats
        # and calling _index_chat_messages for each one
        # For now, we skip this step since we don't have a mechanism to retrieve all chat IDs
        pass

        root_logger.info("Message processor initialized")

    async def _index_chat_messages(self, chat_id: int) -> None:
        """Index messages for a specific chat."""
        try:
            # Get messages from storage
            messages = self.storage.get_all_messages(chat_id)

            if not messages:
                return

            # Clear existing index for this chat
            await asyncio.to_thread(self.vector_search.clear, chat_id)

            # Prepare messages for indexing
            messages_for_index = []
            for msg in messages:
                messages_for_index.append(msg.model_dump(by_alias=True))

            # Add to vector search
            added_count = await asyncio.to_thread(self.vector_search.add_messages, messages_for_index, chat_id)

            chat_name = self.storage.get_display_name(chat_id)
            root_logger.info(f"Indexed {added_count} messages for chat {chat_name}")

        except Exception as e:
            chat_name = self.storage.get_display_name(chat_id)
            root_logger.error(f"Error indexing messages for chat {chat_name}: {e}")

    async def process_updates(self, bot, offset: int = 0) -> tuple[int, bool]:
        """
        Process incoming Telegram updates.

        Args:
            bot: Telegram bot instance
            offset: Update offset for polling

        Returns:
            Tuple of (new offset value, is_webhook_blocked)
            is_webhook_blocked=True означает, что polling заблокирован webhook'ом
        """
        try:
            # Get updates from Telegram
            updates, is_webhook_blocked = await bot.get_updates(offset=offset, timeout=30)

            # Если polling заблокирован webhook'ом, возвращаем флаг
            if is_webhook_blocked:
                return offset, True

            for update in updates:
                try:
                    await self._process_single_update(bot, update)
                    offset = max(offset, update.update_id + 1)
                except Exception as e:
                    root_logger.error(f"Error processing update {update.update_id}: {e}")

        except Exception as e:
            log(f"Error getting updates: {e}")
            await asyncio.sleep(5)

        return offset, False

    async def _process_single_update(self, bot, update) -> None:
        """Process a single Telegram update."""
        if not hasattr(update, "message") or not update.message:
            root_logger.debug(f"Update {update.update_id} has no message, skipping")
            return

        message = update.message
        root_logger.info(f"Processing update {update.update_id} from chat {message.chat.id}")

        # Store message
        await self._store_message(message)

        # Index message for search
        await self._index_message(message)

        # Handle commands or special messages
        await self._handle_message(bot, message)

    async def _store_message(self, message) -> None:
        """Store message in storage."""
        try:
            # Convert to storage format
            message_data = self._message_to_dict(message)

            # Store in database
            self.storage.save_message(message_data)

        except Exception as e:
            log(f"Error storing message: {e}")

    async def _index_message(self, message) -> None:
        """Index message for vector search."""
        try:
            message_data = self._message_to_dict(message)
            messages_for_index = [message_data]

            await asyncio.to_thread(self.vector_search.add_messages, messages_for_index, message.chat.id)

        except Exception as e:
            log(f"Error indexing message: {e}")

    async def _handle_message(self, bot, message) -> None:
        """Handle message content and commands."""
        # Check if this is a group chat and the bot is mentioned or it's a reply to bot
        if message.chat.type in ["group", "supergroup"]:
            bot_mentioned = await self._is_bot_mentioned(bot, message)
            is_reply_to_bot = await self._is_reply_to_bot(bot, message)

            # Only process if bot is mentioned or it's a reply to bot
            if not (bot_mentioned or is_reply_to_bot):
                root_logger.debug(f"Message in group chat {message.chat.id} ignored - bot not mentioned")
                return

        # Basic command handling
        if hasattr(message, "text") and message.text:
            text = message.text.strip()
            root_logger.info(f"Handling message text: {text[:100]}...")

            if text.startswith("/"):
                root_logger.info(f"Processing command: {text}")
                await self._handle_command(bot, message, text)
            else:
                # Regular message processing
                root_logger.info("Processing regular message")
                await self._handle_regular_message(bot, message)
        else:
            root_logger.debug("Message has no text, skipping")

    async def _handle_command(self, bot, message, command: str) -> None:
        """Handle bot commands."""
        try:
            pass
        except Exception as e:
            log(f"Error handling command {command}: {e}")

    async def _handle_regular_message(self, bot, message) -> None:
        """Handle regular messages."""
        # In group chats, this method is only reached if the bot was mentioned or replied to
        # So we can process the message normally
        if message.chat.type in ["group", "supergroup"]:
            # Log that the bot was mentioned or replied to in a group chat
            root_logger.info(f"Processing message in group chat {message.chat.id} - bot was mentioned or replied to")
        else:
            root_logger.info(f"Processing message in private chat {message.chat.id}")

        # Process the message with LLM and send response
        await self._process_message_with_llm(bot, message)

    async def _process_message_with_llm(self, bot, message) -> None:
        """Process message with LLM and send response."""
        try:
            from api.llm import call_llm, LLMPermanentError, LLMTemporaryError
            from api.detect.web_search import web_search_service
            from api.kb.user_metrics import user_metrics_service
            from api.chat.context_builder import (
                build_context_for_llm,
                should_include_context,
                get_weather_context,
                extract_ecosystem_and_location,
                format_ecosystem_context,
            )
            from api.sessions import session_manager

            # Use provided KB service or create fallback (should not happen in production)
            kb_service = self.kb_service
            if not kb_service:
                from api.logger import root_logger

                root_logger.warning("KB service not provided to MessageProcessor, creating fallback")
                from api.kb.service import KBService
                from api.storage.nodes_repository import DatabaseNodeRepository
                from api.storage.db_factory import create_database_manager
                from api.settings import DATABASE_URL, DATABASE_PATH

                db_manager = create_database_manager(
                    database_url=DATABASE_URL, db_path=DATABASE_PATH or "data/storage.db"
                )
                db_manager.connect()
                node_repo = DatabaseNodeRepository(db_manager)
                kb_service = KBService(node_repo)

            # Check if the message is about symbiosis or related topics to trigger web search
            message_lower = message.text.lower()
            trigger_keywords = [
                "симбиоз",
                "symbiosis",
                "symbiotic",
                "экосистема",
                "ecosystem",
                "взаимодействие",
                "interaction",
            ]
            needs_web_search = any(keyword in message_lower for keyword in trigger_keywords)

            # Get or create persistent session for Telegram user
            telegram_user_id = message.from_user.id if message.from_user else message.chat.id
            username = (
                message.from_user.username if message.from_user and hasattr(message.from_user, "username") else None
            )

            # Get or create session using Telegram user ID (async)
            chat_id = await session_manager.get_or_create_telegram_session(telegram_user_id, username)

            # Increment message count for this session (async)
            await session_manager.increment_message_count(chat_id)

            # Add the user message to the concept tree
            user_message_node = kb_service.add_concept(
                parent_id=chat_id,
                content=message.text,
                role="user",
                node_type="message",
                session_id=chat_id,
            )

            # Load the simbio expert prompt template
            with open("api/prompts/simbio_expert.txt", "r", encoding="utf-8") as f:
                prompt_template = f.read()

            # Извлекаем экосистему и локацию из сообщения для фильтрации контекста
            ecosystem_data = await extract_ecosystem_and_location(message.text)
            location = ecosystem_data.get("location")
            ecosystems = ecosystem_data.get("ecosystems", [])

            # Build context for LLM with smart compression and filtering by location/ecosystem
            from api.llm import get_llm_client_wrapper

            llm_client = get_llm_client_wrapper()
            conversation_summary, recent_messages = await build_context_for_llm(
                chat_id, kb_service, llm_client, location=location, ecosystems=ecosystems
            )

            # Determine which context sections to include
            include_summary, include_recent = should_include_context(conversation_summary, recent_messages)

            # Получаем информацию о погоде, если в сообщении указаны город и время
            weather_context = await get_weather_context(message.text)

            # Форматируем контекст локальной экосистемы (объединяем погоду и экосистему)
            ecosystem_context = format_ecosystem_context(ecosystems, location, weather=weather_context)

            # Prepare context data for the prompt
            local_stat = ""
            artifacts_context = ""
            chats_context = ""
            books_context = ""

            # Perform web search if the message is about symbiosis or related topics
            if needs_web_search:
                websearch_context = await web_search_service.get_symbiosis_context(message.text)
            else:
                websearch_context = ""

            # Check if the message contains user observation data that should be saved
            user_message_lower = message.text.lower()
            observation_indicators = [
                "локация",
                "место",
                "район",
                "город",
                "деревня",
                "лес",
                "река",
                "озеро",
                "наблюдение",
                "увидел",
                "заметил",
                "наблюдение",
                "экосистема",
                "взаимодействие",
                "сезон",
                "погода",
                "температура",
                "влажность",
                "ветер",
                "облачность",
                "местность",
                "ландшафт",
                "природа",
            ]

            # Save user observation if it contains relevant data
            if any(indicator in user_message_lower for indicator in observation_indicators):
                from api.kb.user_metrics import user_metrics_service

                if user_metrics_service:
                    user_metrics_service.save_user_observation(
                        user_id=str(telegram_user_id),
                        location=None,
                        ecosystem_type=None,
                        observations=message.text,
                        interactions=None,
                        season=None,
                        weather=None,
                        additional_notes=f"Extracted from Telegram message, session {chat_id}",
                    )

            # Format the prompt with context and message
            llm_context = prompt_template.format(
                conversation_summary=f"[CONVERSATION CONTEXT]\n{conversation_summary}\n" if include_summary else "",
                local_stat=local_stat,
                artifacts_context=artifacts_context,
                chats_context=chats_context,
                books_context=books_context,
                websearch_context=websearch_context,
                recent_messages=f"[RECENT MESSAGES]\n{recent_messages}\n" if include_recent else "",
                ecosystem_context=f"[LOCAL ECOSYSTEM]\n{ecosystem_context}\n" if ecosystem_context else "",
                message=message.text,
            )

            # Call LLM to get response
            root_logger.info(f"Processing message from Telegram user {telegram_user_id} (chat_id: {chat_id})")
            try:
                response_content = await call_llm(llm_context, origin="telegram_bot")
                root_logger.info(f"Received LLM response (length: {len(response_content)} chars)")
            except (LLMPermanentError, LLMTemporaryError) as e:
                # До сюда доходим только если LLM не смогла ответить даже после всех ретраев.
                root_logger.error(f"LLM error (permanent or temporary): {str(e)}")
                import traceback

                root_logger.error(f"Traceback: {traceback.format_exc()}")
                # Отправляем сообщение об ошибке пользователю
                await bot.send_message_reaction(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    emoji="🤷‍♂️",
                )
                return

            # Add the AI response to the concept tree
            ai_response_node = kb_service.add_concept(
                parent_id=user_message_node.id,
                content=response_content,
                role="assistant",
                node_type="message",
                session_id=chat_id,
            )

            # Send the response back to the user
            root_logger.info(f"Sending response to Telegram chat {message.chat.id}")
            sent_message = await bot.send_message(chat_id=message.chat.id, text=response_content)
            root_logger.info(f"Response sent successfully to Telegram chat {message.chat.id}")

            # Add success reaction to user's message
            try:
                await bot.send_message_reaction(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    emoji="👍",
                )
            except Exception as reaction_error:
                root_logger.warning(f"Failed to add success reaction: {reaction_error}")

        except Exception as e:
            import traceback

            root_logger.error(f"Error processing message with LLM: {e}")
            root_logger.error(f"Traceback: {traceback.format_exc()}")
            # Send error reaction to user's message
            try:
                await bot.send_message_reaction(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    emoji="🤯",
                )
            except Exception as reaction_error:
                root_logger.error(f"Error sending error reaction: {reaction_error}")
                root_logger.error(f"Traceback: {traceback.format_exc()}")

    async def _is_bot_mentioned(self, bot, message) -> bool:
        """Check if the bot is mentioned in the message."""
        if not hasattr(message, "entities") or not message.entities:
            return False

        # Get bot info to check for mentions
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.get("username", "").lower()

            if not bot_username:
                return False

            # Check text for mentions
            if message.text:
                text_lower = message.text.lower()
                # Check if bot username is mentioned
                if f"@{bot_username}" in text_lower:
                    return True

            # Check entities for user mentions
            for entity in message.entities:
                if entity.get("type") == "mention":
                    mention_text = message.text[entity["offset"] : entity["offset"] + entity["length"]]
                    if mention_text.lower() == f"@{bot_username}":
                        return True
                elif entity.get("type") == "text_mention":
                    # Check if the mentioned user is the bot
                    user = entity.get("user", {})
                    if user and user.get("is_bot") and user.get("id") == bot_info.get("id"):
                        return True

        except Exception as e:
            log(f"Error checking bot mentions: {e}")

        return False

    async def _is_reply_to_bot(self, bot, message) -> bool:
        """Check if the message is a reply to the bot."""
        if not hasattr(message, "reply_to_message") or not message.reply_to_message:
            return False

        try:
            bot_info = await bot.get_me()
            reply_from = message.reply_to_message.from_user

            if reply_from and reply_from.id == bot_info.get("id"):
                return True
        except Exception as e:
            log(f"Error checking reply to bot: {e}")

        return False

    def _message_to_dict(self, message) -> Dict[str, Any]:
        """Convert Telegram message to dictionary format."""
        return {
            "message_id": message.message_id,
            "chat_id": message.chat.id,
            "user_id": message.from_user.id if message.from_user else None,
            "username": message.from_user.username if message.from_user else None,
            "text": message.text if hasattr(message, "text") else "",
            "timestamp": message.date,
            "message_type": self._get_message_type(message),
            "entities": message.entities if hasattr(message, "entities") else None,
            "reply_to_message_id": message.reply_to_message.message_id
            if hasattr(message, "reply_to_message") and message.reply_to_message
            else None,
        }

    def _get_message_type(self, message) -> str:
        """Get message type."""
        if hasattr(message, "text") and message.text:
            return "text"
        elif hasattr(message, "photo"):
            return "photo"
        elif hasattr(message, "document"):
            return "document"
        elif hasattr(message, "sticker"):
            return "sticker"
        elif hasattr(message, "reply_to_message") and message.reply_to_message:
            return "reply"
        else:
            return "unknown"

    async def shutdown(self) -> None:
        """Shutdown processor gracefully."""
        log("Shutting down message processor")
        # Add cleanup logic if needed
