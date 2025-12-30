"""API routes for tag management."""

from fastapi import APIRouter, HTTPException, Query, Request, status
from typing import Optional, List
from pydantic import BaseModel, Field

from .tag_service import TagService

router = APIRouter(prefix="/api/classify/tags", tags=["Tags"])


class TagCreate(BaseModel):
    """Request model for creating a tag."""

    name: str = Field(..., description="Tag name")
    description: Optional[str] = Field(None, description="Tag description")
    category: Optional[str] = Field(None, description="Tag category")
    examples: Optional[List[str]] = Field(None, description="Example paragraphs")


class TagUpdate(BaseModel):
    """Request model for updating a tag."""

    description: Optional[str] = Field(None, description="Tag description")
    category: Optional[str] = Field(None, description="Tag category")
    is_active: Optional[bool] = Field(None, description="Is tag active")


@router.get("", response_model=List[dict])
async def get_tags(
    request: Request,
    active_only: bool = Query(True, description="Return only active tags"),
):
    """
    Get all tags.

    Returns list of all tags with their metadata.
    """
    try:
        tag_service: TagService = request.app.state.tag_service
        tags = tag_service.get_all_tags(active_only=active_only)
        return tags
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/{tag_name}", response_model=dict)
async def get_tag(tag_name: str, request: Request):
    """
    Get a specific tag by name.

    Returns tag metadata.
    """
    try:
        tag_service: TagService = request.app.state.tag_service
        tag = tag_service.get_tag(tag_name)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "TagNotFound", "message": f"Tag {tag_name} not found"},
            )
        return tag
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_tag(tag_data: TagCreate, request: Request):
    """
    Create a new tag.

    Creates a new tag for paragraph classification.
    """
    try:
        tag_service: TagService = request.app.state.tag_service
        tag = tag_service.create_tag(
            name=tag_data.name,
            description=tag_data.description,
            category=tag_data.category,
            examples=tag_data.examples,
        )
        return tag
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.put("/{tag_name}", response_model=dict)
async def update_tag(tag_name: str, tag_data: TagUpdate, request: Request):
    """
    Update a tag.

    Updates tag metadata.
    """
    try:
        tag_service: TagService = request.app.state.tag_service
        tag = tag_service.get_tag(tag_name)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "TagNotFound", "message": f"Tag {tag_name} not found"},
            )

        cursor = tag_service.db_manager.connection.cursor()
        updates = []
        params = []

        if tag_data.description is not None:
            updates.append("description = ?")
            params.append(tag_data.description)

        if tag_data.category is not None:
            updates.append("category = ?")
            params.append(tag_data.category)

        if tag_data.is_active is not None:
            updates.append("is_active = ?")
            params.append("1" if tag_data.is_active else "0")

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(tag_name)
            cursor.execute(f"UPDATE tags SET {', '.join(updates)} WHERE name = ?", params)
            tag_service.db_manager.connection.commit()

        return tag_service.get_tag(tag_name) or {}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("/analyze", response_model=dict)
async def analyze_tags(
    request: Request,
    sample_size: int = Query(100, ge=10, le=1000, description="Number of paragraphs to analyze"),
):
    """
    Analyze paragraphs and update tags through LLM.

    Analyzes existing paragraphs and suggests new tags or improvements.
    """
    try:
        tag_service: TagService = request.app.state.tag_service
        result = await tag_service.analyze_and_update_tags(sample_size=sample_size)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("/suggest", response_model=List[str])
async def suggest_tags(
    request: Request,
    paragraph_content: str = Query(..., description="Paragraph content to analyze"),
):
    """
    Suggest tags for a paragraph using LLM.

    Returns list of suggested tags for the given paragraph.
    """
    try:
        tag_service: TagService = request.app.state.tag_service
        tags = await tag_service.suggest_tags_for_paragraph(paragraph_content)
        return tags
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )
