"""Pydantic models for Knowledge Base API.

Models are based on the conversation tree framework documented in
docs/conversation_tree_framework.md (lines 35-62).
"""

from typing import Any, Literal, Optional, TypedDict

import bleach
from pydantic import BaseModel, Field, field_validator

from .constants import (
    SENDER_BOT,
    SENDER_USER,
    SENTIMENT_NEGATIVE,
    SENTIMENT_NEUTRAL,
    SENTIMENT_POSITIVE,
    SOURCE_TYPE_CONFIRM,
    SOURCE_TYPE_DOUBT,
)


class Source(BaseModel):
    """Source reference for a knowledge node.

    Based on docs/conversation_tree_framework.md lines 50-62.
    """

    id: str = Field(..., description="Unique source identifier")
    url: str = Field(..., description="Source URL")
    title: Optional[str] = Field(None, description="Source title")
    type: Literal["confirm", "doubt"] = Field(
        ..., description=f"Source type: '{SOURCE_TYPE_CONFIRM}' or '{SOURCE_TYPE_DOUBT}'"
    )
    tool: Optional[str] = Field(None, description="Tool that detected this source")
    sentiment: Optional[Literal["positive", "negative", "neutral"]] = Field(
        None, description=f"Sentiment: '{SENTIMENT_POSITIVE}', '{SENTIMENT_NEGATIVE}', or '{SENTIMENT_NEUTRAL}'"
    )
    userConfirmed: Optional[bool] = Field(None, description="User confirmation of sentiment")
    reliabilityScore: Optional[float] = Field(None, ge=0.0, le=1.0, description="Reliability score (0-1)")
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")


class ConceptNode(BaseModel):
    """Unified node structure for all node types (TreeNode, ChatNode, ChatConceptNode).

    Based on docs/conversation_tree_framework.md lines 35-46 and docs/architecture/07_unified_node_structure.md
    CRITICAL: This model follows the documentation exactly - do not add undocumented fields.
    """

    # Core fields (lines 37-41 of docs)
    id: str = Field(..., description="Unique node identifier (UUID)")
    parentId: Optional[str] = Field(None, description="Parent node ID for hierarchy (null for root)")
    childrenIds: list[str] = Field(default_factory=list, description="List of child node IDs")
    content: str = Field(..., min_length=1, description="Main content of the node")
    sources: list[Source] = Field(default_factory=list, description="List of source references")
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")

    # Optional fields (lines 43-45 of docs)
    embedding: Optional[list[float]] = Field(None, description="Vector embedding for semantic search")
    expanded: Optional[bool] = Field(None, description="UI state: node expanded")
    selected: Optional[bool] = Field(None, description="UI state: node selected")

    # Chat-specific fields
    sessionId: Optional[str] = Field(None, description="ID of the chat session this node belongs to")
    role: Optional[Literal["user", "assistant", "system"]] = Field(
        None, description="Role of the message sender in chat context"
    )
    type: Literal[
        "question",
        "answer",
        "fact",
        "opinion",
        "solution",
        "message",
        "concept_reference",
        "user_observation",
    ] = Field("message", description="Type of node content")
    category: Literal["threat", "protection", "conservation", "neutral", "metrics"] = Field(
        "neutral", description="Category for visualization"
    )
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}, description="3D position coordinates"
    )
    conceptNodeId: Optional[str] = Field(None, description="Reference to original concept node when used in chat")

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Sanitize HTML content to prevent XSS attacks.

        Removes all HTML tags and strips whitespace.

        Args:
            v: Raw content string

        Returns:
            Sanitized content string

        Example:
            >>> ConceptNode.sanitize_content("<script>alert('xss')</script>Hello")
            'Hello'
        """
        return bleach.clean(v, tags=[], strip=True)


class NodeCreate(BaseModel):
    """Request model for creating a new node."""

    parentId: Optional[str] = Field(None, description="Parent node ID")
    content: str = Field(..., min_length=1, description="Node content")
    role: Optional[Literal["user", "assistant", "system"]] = Field(None, description="Role of the message sender")
    sources: list[Source] = Field(default_factory=list, description="Source references")


class NodeUpdate(BaseModel):
    """Request model for updating an existing node."""

    content: Optional[str] = Field(None, min_length=1, description="Updated content")
    sources: Optional[list[Source]] = Field(None, description="Updated sources")
    expanded: Optional[bool] = Field(None, description="Updated expanded state")
    selected: Optional[bool] = Field(None, description="Updated selected state")


class NodeWithContext(BaseModel):
    """Node with surrounding context (parent, children, siblings)."""

    node: ConceptNode
    parent: Optional[ConceptNode] = None
    children: list[ConceptNode] = Field(default_factory=list)
    siblings: list[ConceptNode] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TreeResponse(BaseModel):
    """Response model for tree structure."""

    root: ConceptNode
    nodes: list[ConceptNode]
    stats: dict[str, Any]


class SearchResult(BaseModel):
    """Search result with relevance score."""

    node: ConceptNode
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0-1)")
    matchedFields: list[str] = Field(default_factory=list, description="Fields that matched the search")


class SearchResponse(BaseModel):
    """Response model for search operation."""

    results: list[SearchResult]
    total: int
    query: str
    limit: int
    offset: int


class StatsResponse(BaseModel):
    """Response model for knowledge base statistics."""

    totalNodes: int
    rootNodes: int
    maxDepth: int
    avgDepth: float
    lastUpdated: int


class DeleteResponse(BaseModel):
    """Response model for delete operation."""

    deleted: bool
    nodeId: str
    deletedCount: int


class ImportRequest(BaseModel):
    """Request model for importing nodes."""

    nodes: list[ConceptNode]
    merge: bool = Field(False, description="Merge with existing data")
    overwrite: bool = Field(False, description="Overwrite existing nodes")


class ImportResponse(BaseModel):
    """Response model for import operation."""

    imported: bool
    nodesCount: int
    conflicts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExportResponse(BaseModel):
    """Response model for export operation."""

    version: str
    exported: int
    nodes: list[ConceptNode]


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error details")


class NodeDict(TypedDict, total=False):
    """Type definition for node dictionary representation.

    This is used for type hints when working with raw dictionaries.
    """

    id: str
    parentId: Optional[str]
    childrenIds: list[str]
    content: str
    sources: list[dict[str, Any]]
    timestamp: int
    embedding: Optional[list[float]]
    expanded: Optional[bool]
    selected: Optional[bool]
    role: Optional[str]
    sessionId: Optional[str]
    type: str
    category: str
    position: dict[str, float]
    conceptNodeId: Optional[str]
    children: list[str]  # Добавляем поле, которое используется в коде


class IndexDict(TypedDict):
    """Type definition for index structure."""

    byCategory: dict[str, list[str]]
    byType: dict[str, list[str]]
    byParent: dict[str, list[str]]


class MetadataDict(TypedDict):
    """Type definition for metadata structure."""

    created: int
    updated: int
    totalNodes: int
    maxDepth: int


class DataDict(TypedDict, total=False):
    """Type definition for complete data structure.

    This represents the entire JSON storage structure with nodes, metadata, and indices.
    """

    version: str
    rootId: Optional[str]
    metadata: MetadataDict
    nodes: dict[str, "NodeDict"]
    index: IndexDict


class TreeStats(TypedDict):
    """Type definition for tree statistics."""

    totalNodes: int
    maxDepth: int
    rootNodes: int
