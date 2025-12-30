"""
Telegram Bot Main Entry Point.

This module initializes and runs the Telegram bot with all its components.
"""

import asyncio
import os
from typing import Optional
from api.logger import root_logger
from api.storage.faiss import ParagraphVectorSearch
from api.bot.tg import BotManager
from api.bot.routes import set_bot_manager
from api.settings import TELEGRAM_BOT_TOKEN, MODEL_PATH

log = root_logger.debug


async def create_bot_manager(kb_service=None) -> BotManager:
    """
    Create and initialize the bot manager.

    Args:
        kb_service: Knowledge base service instance (optional)

    Returns:
        Initialized BotManager instance
    """
    # Get configuration from environment
    telegram_token = TELEGRAM_BOT_TOKEN
    if not telegram_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

    # Initialize storage (placeholder - should be injected)
    # For now, create a simple storage instance
    storage = None  # TODO: Initialize proper storage

    # Initialize vector search
    model_path = MODEL_PATH if MODEL_PATH else "./models"
    vector_search = ParagraphVectorSearch(cache_folder=str(model_path))

    # Create bot manager
    manager = BotManager(
        telegram_token=telegram_token,
        storage=storage,
        vector_search=vector_search,
        kb_service=kb_service,
    )

    # Initialize components
    await manager.initialize()

    return manager


async def start_bot(kb_service=None) -> None:
    """
    Main entry point for the Telegram bot.

    Initializes all components and starts the bot.
    """
    try:
        log("Starting Telegram bot application")

        # Create bot manager
        manager = await create_bot_manager(kb_service=kb_service)

        # Set manager for API routes
        set_bot_manager(manager)

        if not os.getenv("DOKKU_PROXY_PORT"):
            await manager.start_polling()
        else:
            if hasattr(manager, "start_webhook"):
                await manager.start_webhook()
            else:
                log("Webhook method not available, using polling")
                await manager.start_polling()

    except KeyboardInterrupt:
        log("Received keyboard interrupt")
    except Exception as e:
        log(f"Error in main: {e}")
        raise
    finally:
        log("Bot application shutdown")


if __name__ == "__main__":
    # Run the bot
    asyncio.run(start_bot())
