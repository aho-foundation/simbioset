from pydantic import BaseModel, Field
from typing import Literal, Optional


class ChatSessionCreate(BaseModel):
    """Request model for creating a chat session."""

    topic: str = Field(..., description="Topic of the chat session")
    conceptTreeId: Optional[str] = Field(None, description="ID of the concept tree to link")


class ChatSession(BaseModel):
    """Chat session model."""

    id: str = Field(..., description="Unique session identifier")
    topic: str = Field(..., description="Topic of the chat session")
    created_at: int = Field(..., description="Creation timestamp")
    updated_at: int = Field(..., description="Last update timestamp")
    message_count: int = Field(0, description="Number of messages in session")
    conceptTreeId: Optional[str] = Field(None, description="ID of the concept tree to link")


class ChatMessageCreate(BaseModel):
    """Request model for sending a message in chat."""

    sessionId: Optional[str] = Field(
        None, description="ID of the chat session (optional, uses cookies if not provided)"
    )
    message: str = Field(..., description="The message content")
    conceptNodeId: Optional[str] = Field(None, description="ID of the concept node to link to")
    author: str = Field("user", description="Author of the message")
    context: Optional[dict] = Field(None, description="Context information")


class ChatDragToChat(BaseModel):
    """Request model for dragging a concept node to chat."""

    sessionId: str = Field(..., description="ID of the chat session")
    conceptNodeId: str = Field(..., description="ID of the concept node to drag")
    operation: str = Field("drag-to-chat", description="Operation type")
    context: dict = Field(..., description="Context information")
