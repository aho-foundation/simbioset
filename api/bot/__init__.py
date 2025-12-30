"""
Telegram Bot Module.

This module provides Telegram bot functionality with vector search and LLM integration.
"""

from .tg import BotManager
from .handler import MessageProcessor
from .routes import router as bot_router

__all__ = [
    "BotManager",
    "MessageProcessor",
    "bot_router",
]
