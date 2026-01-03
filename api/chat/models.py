from pydantic import BaseModel, Field
from typing import Literal, Optional


class ChatSessionCreate(BaseModel):
    """Request model for creating a chat session."""

    topic: str = Field(..., description="Topic of the chat session")
    conceptTreeId: Optional[str] = Field(None, description="ID of the concept tree to link")
    ecosystem: Optional[dict] = Field(None, description="Ecosystem data for the session")


class ChatSession(BaseModel):
    """Chat session model."""

    id: str = Field(..., description="Unique session identifier")
    topic: str = Field(..., description="Topic of the chat session")
    created_at: int = Field(..., description="Creation timestamp")
    updated_at: int = Field(..., description="Last update timestamp")
    message_count: int = Field(0, description="Number of messages in session")
    conceptTreeId: Optional[str] = Field(None, description="ID of the concept tree to link")
    location: Optional[dict] = Field(None, description="Location and ecosystem data for the session")
    indexed_books: list = Field(default_factory=list, description="Indexed books for the session")


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
    """Request model for dragging content to chat (concepts, files, etc.)."""

    sessionId: str = Field(..., description="ID of the chat session")

    # Для перетаскивания концепта
    conceptNodeId: Optional[str] = Field(None, description="ID of the concept node to drag")

    # Для перетаскивания файлов
    file: Optional[dict] = Field(None, description="File data for drag & drop (images, documents)")
    # file structure: {
    #   "name": str,
    #   "type": str,  # "image/jpeg", "text/plain", etc.
    #   "content": str,  # base64 for images, text content for documents
    #   "size": int
    # }

    operation: str = Field("drag-to-chat", description="Operation type")
    context: dict = Field(default_factory=dict, description="Context information")
