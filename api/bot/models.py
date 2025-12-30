"""
Models for Telegram Bot API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TelegramWebhookResponse(BaseModel):
    """Response model for Telegram webhook."""

    ok: bool
    result: Optional[Any] = None
    description: Optional[str] = None


class ChatInfo(BaseModel):
    """Chat information."""

    chat_id: int
    name: Optional[str] = None
    message_count: Optional[int] = None


class MessageData(BaseModel):
    """Message data for storage."""

    message_id: int
    chat_id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    text: str = ""
    timestamp: int
    message_type: str = "text"
    entities: Optional[List[Dict[str, Any]]] = None
    reply_to_message_id: Optional[int] = None


class TelegramSessionData(BaseModel):
    """Data model for Telegram user session."""

    telegram_user_id: int
    username: Optional[str] = None
    created_at: int
    last_activity: int
    message_count: int = 0
    platform: str = "telegram"
    context: Optional[Dict[str, Any]] = None
