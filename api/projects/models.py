"""Pydantic models for Projects API.

Models for crowdsourced and crowdfunded projects integrated with knowledge base system.
Based on existing ConceptNode models from api/kb/models.py.
"""

from typing import Any, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class Contributor(BaseModel):
    """Contributor model for project participants."""

    user_id: str = Field(..., description="User ID from authentication system")
    name: str = Field(..., description="Contributor's display name")
    role: str = Field(..., description="Role in the project (e.g., developer, designer)")
    contribution_date: datetime = Field(..., description="When the user joined the project")
    contributions: list[str] = Field(default_factory=list, description="List of contribution descriptions")


class Backer(BaseModel):
    """Backer model for crowdfunded project supporters."""

    user_id: str = Field(..., description="User ID from authentication system")
    name: str = Field(..., description="Backer's display name")
    amount: float = Field(..., ge=0.0, description="Amount contributed")
    backing_date: datetime = Field(..., description="When the backing occurred")
    tier_id: Optional[str] = Field(None, description="Funding tier ID if applicable")
    public: bool = Field(True, description="Whether backing is publicly visible")


class FundingTier(BaseModel):
    """Funding tier model for crowdfunded projects."""

    id: str = Field(..., description="Unique tier identifier")
    title: str = Field(..., description="Tier title")
    description: str = Field(..., description="Tier description")
    amount: float = Field(..., ge=0.0, description="Minimum contribution amount")
    rewards: list[str] = Field(default_factory=list, description="List of rewards for this tier")
    limit: Optional[int] = Field(None, description="Maximum number of backers for this tier")


class Idea(BaseModel):
    """Idea model for crowdsourced projects."""

    id: str = Field(..., description="Unique idea identifier")
    project_id: str = Field(..., description="Parent project ID")
    author_id: str = Field(..., description="User ID of the author")
    content: str = Field(..., min_length=1, description="Idea content")
    submission_date: datetime = Field(..., description="When the idea was submitted")
    votes: int = Field(0, ge=0, description="Number of votes for this idea")
    status: Literal["submitted", "reviewed", "approved", "rejected", "implemented"] = Field(
        "submitted", description="Current status of the idea"
    )

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Sanitize idea content to prevent XSS attacks.

        Removes all HTML tags and strips whitespace.

        Args:
            v: Raw content string

        Returns:
            Sanitized content string

        Example:
            >>> Idea.sanitize_content("<script>alert('xss')</script>Great idea")
            'Great idea'
        """
        try:
            import bleach

            return bleach.clean(v, tags=[], strip=True)
        except ImportError:
            # Fallback sanitization without bleach
            import re

            return re.sub(r"<[^>]+>", "", v).strip()


class BaseProject(BaseModel):
    """Base project model with common fields."""

    id: str = Field(..., description="Unique project identifier")
    title: str = Field(..., min_length=1, max_length=200, description="Project title")
    description: str = Field(..., min_length=1, description="Project description")
    status: Literal["draft", "active", "completed", "archived", "failed"] = Field(
        "draft", description="Current project status"
    )
    creation_date: datetime = Field(..., description="When the project was created")
    update_date: datetime = Field(..., description="When the project was last updated")
    knowledge_base_id: str = Field(..., description="Linked knowledge base ID")
    tags: list[str] = Field(default_factory=list, description="Project tags for categorization")

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        """Sanitize text fields to prevent XSS attacks."""
        try:
            import bleach

            return bleach.clean(v, tags=[], strip=True)
        except ImportError:
            # Fallback sanitization without bleach
            import re

            return re.sub(r"<[^>]+>", "", v).strip()


class CrowdsourcedProject(BaseProject):
    """Crowdsourced project model.

    Extends BaseProject with crowdsourcing-specific fields.
    """

    ideas: list[Idea] = Field(default_factory=list, description="List of user-submitted ideas")
    contributors: list[Contributor] = Field(default_factory=list, description="Project contributors")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cs-proj-001",
                "title": "Open Source AI Assistant",
                "description": "Community-driven AI assistant development",
                "status": "active",
                "creation_date": "2025-01-01T00:00:00Z",
                "update_date": "2025-01-15T10:30:00Z",
                "knowledge_base_id": "kb-ai-assistant",
                "tags": ["ai", "open-source", "community"],
                "ideas": [],
                "contributors": [],
            }
        }


class CrowdfundedProject(BaseProject):
    """Crowdfunded project model.

    Extends BaseProject with crowdfunding-specific fields.
    """

    funding_goal: float = Field(..., ge=0.0, description="Total funding goal amount")
    current_funding: float = Field(0.0, ge=0.0, description="Current amount raised")
    start_date: datetime = Field(..., description="When funding campaign starts")
    end_date: datetime = Field(..., description="When funding campaign ends")
    backers: list[Backer] = Field(default_factory=list, description="Project backers")
    funding_tiers: list[FundingTier] = Field(default_factory=list, description="Available funding tiers")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cf-proj-001",
                "title": "Eco-Friendly Drone",
                "description": "Sustainable drone for environmental monitoring",
                "status": "active",
                "creation_date": "2025-01-01T00:00:00Z",
                "update_date": "2025-01-15T10:30:00Z",
                "knowledge_base_id": "kb-eco-tech",
                "tags": ["ecology", "technology", "sustainability"],
                "funding_goal": 50000.0,
                "current_funding": 15000.0,
                "start_date": "2025-02-01T00:00:00Z",
                "end_date": "2025-03-31T23:59:59Z",
                "backers": [],
                "funding_tiers": [],
            }
        }


# Integration models for knowledge base compatibility
class ProjectWithKnowledgeBase(BaseModel):
    """Project with integrated knowledge base data."""

    project: BaseProject
    knowledge_base_nodes: list[dict[str, Any]] = Field(default_factory=list, description="Related knowledge base nodes")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
