"""FastAPI routes for Projects API."""

from typing import Any, Literal, Optional
from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel, Field

from .models import (
    BaseProject,
    CrowdsourcedProject,
    CrowdfundedProject,
    Idea,
    Contributor,
    Backer,
    FundingTier,
)
from .service import ProjectsService
from .repository import ProjectsRepository

router = APIRouter(prefix="/api/projects", tags=["Projects"])

repository = ProjectsRepository()
service = ProjectsService(repository)


class ProjectCreate(BaseModel):
    """Request model for creating a project."""

    title: str = Field(..., min_length=1, max_length=200, description="Project title")
    description: str = Field(..., min_length=1, description="Project description")
    knowledge_base_id: str = Field(..., description="Linked knowledge base ID")
    tags: list[str] = Field(default_factory=list, description="Project tags")
    status: Literal["draft", "active", "completed", "archived", "failed"] = Field("draft", description="Project status")
    # Crowdfunded specific
    funding_goal: Optional[float] = Field(None, ge=0.0, description="Funding goal (for crowdfunded projects)")
    start_date: Optional[str] = Field(None, description="Funding start date")
    end_date: Optional[str] = Field(None, description="Funding end date")
    funding_tiers: list[FundingTier] = Field(default_factory=list, description="Funding tiers")


class ProjectUpdate(BaseModel):
    """Request model for updating a project."""

    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Project title")
    description: Optional[str] = Field(None, min_length=1, description="Project description")
    status: Optional[Literal["draft", "active", "completed", "archived", "failed"]] = Field(
        None, description="Project status"
    )
    tags: Optional[list[str]] = Field(None, description="Project tags")


class IdeaCreate(BaseModel):
    """Request model for creating an idea."""

    content: str = Field(..., min_length=1, description="Idea content")
    author_id: str = Field(..., description="Author user ID")


class IdeaUpdate(BaseModel):
    """Request model for updating an idea."""

    content: Optional[str] = Field(None, min_length=1, description="Idea content")
    status: Optional[Literal["submitted", "reviewed", "approved", "rejected", "implemented"]] = Field(
        None, description="Idea status"
    )


class ContributionCreate(BaseModel):
    """Request model for adding contribution."""

    user_id: str = Field(..., description="User ID")
    name: str = Field(..., description="Contributor name")
    role: str = Field(..., description="Role in project")
    contributions: list[str] = Field(default_factory=list, description="Contribution descriptions")


class BackingCreate(BaseModel):
    """Request model for adding funding."""

    user_id: str = Field(..., description="User ID")
    name: str = Field(..., description="Backer name")
    amount: float = Field(..., ge=0.0, description="Contribution amount")
    tier_id: Optional[str] = Field(None, description="Funding tier ID")
    public: bool = Field(True, description="Whether backing is public")


class CreateProjectFromArtifacts(BaseModel):
    """Request model for creating crowdfunded project from chat artifacts."""

    session_id: str = Field(..., description="Session ID where artifacts were collected")
    title: str = Field(..., min_length=1, max_length=200, description="Project title")
    description: str = Field(..., min_length=1, description="Project description")
    artifacts: list[dict[str, Any]] = Field(..., description="List of artifacts from chat")
    knowledge_base_id: str = Field(..., description="Linked knowledge base ID")
    tags: Optional[list[str]] = Field(None, description="Project tags")
    funding_goal: float = Field(100000.0, ge=10000.0, description="Target funding amount in RUB")
    start_date: Optional[str] = Field(None, description="Funding campaign start date (ISO format)")
    end_date: Optional[str] = Field(None, description="Funding campaign end date (ISO format)")


# Project endpoints
@router.get(
    "",
    response_model=list[BaseProject],
    responses={500: {"model": dict}},
)
async def get_projects(
    q: str = Query("", description="Search query"),
    type: Optional[Literal["crowdsourced", "crowdfunded"]] = Query(None, description="Project type filter"),
    status: Optional[str] = Query(None, description="Status filter"),
    tags: Optional[list[str]] = Query(None, description="Tags filter"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Get list of projects with optional filtering.

    Supports search by title/description, filtering by type, status, and tags.
    """
    try:
        return service.get_projects(query=q, project_type=type, status=status, tags=tags, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/{project_id}",
    response_model=BaseProject,
    responses={404: {"model": dict}, 500: {"model": dict}},
)
async def get_project(project_id: str):
    """
    Get project details by ID.
    """
    try:
        project = service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ProjectNotFound", "message": f"Project {project_id} not found"},
            )
        return project
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "",
    response_model=BaseProject,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": dict}, 500: {"model": dict}},
)
async def create_project(project: ProjectCreate):
    """
    Create a new project.

    Automatically determines project type based on presence of funding_goal.
    """
    try:
        return service.create_project(project.model_dump())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.put(
    "/{project_id}",
    response_model=BaseProject,
    responses={404: {"model": dict}, 400: {"model": dict}, 500: {"model": dict}},
)
async def update_project(project_id: str, updates: ProjectUpdate):
    """
    Update an existing project.
    """
    try:
        project = service.update_project(project_id, updates.model_dump(exclude_unset=True))
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ProjectNotFound", "message": f"Project {project_id} not found"},
            )
        return project
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.delete(
    "/{project_id}",
    responses={404: {"model": dict}, 500: {"model": dict}},
)
async def delete_project(project_id: str):
    """
    Delete a project and all its associated ideas.
    """
    try:
        success = service.delete_project(project_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ProjectNotFound", "message": f"Project {project_id} not found"},
            )
        return {"message": "Project deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


# Idea endpoints
@router.get(
    "/ideas",
    response_model=list[Idea],
    responses={500: {"model": dict}},
)
async def get_ideas(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Get list of ideas, optionally filtered by project.
    """
    try:
        return service.get_ideas(project_id=project_id)[offset : offset + limit]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/ideas/{idea_id}",
    response_model=Idea,
    responses={404: {"model": dict}, 500: {"model": dict}},
)
async def get_idea(idea_id: str):
    """
    Get idea details by ID.
    """
    try:
        idea = service.get_idea(idea_id)
        if not idea:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "IdeaNotFound", "message": f"Idea {idea_id} not found"},
            )
        return idea
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "/ideas",
    response_model=Idea,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": dict}, 500: {"model": dict}},
)
async def create_idea(project_id: str = Body(...), idea: IdeaCreate = Body(...)):
    """
    Create a new idea for a project.
    """
    try:
        idea_data = idea.model_dump()
        idea_data["project_id"] = project_id
        return service.create_idea(idea_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.put(
    "/ideas/{idea_id}",
    response_model=Idea,
    responses={404: {"model": dict}, 400: {"model": dict}, 500: {"model": dict}},
)
async def update_idea(idea_id: str, updates: IdeaUpdate):
    """
    Update an existing idea.
    """
    try:
        idea = service.update_idea(idea_id, updates.model_dump(exclude_unset=True))
        if not idea:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "IdeaNotFound", "message": f"Idea {idea_id} not found"},
            )
        return idea
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.delete(
    "/ideas/{idea_id}",
    responses={404: {"model": dict}, 500: {"model": dict}},
)
async def delete_idea(idea_id: str):
    """
    Delete an idea.
    """
    try:
        success = service.delete_idea(idea_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "IdeaNotFound", "message": f"Idea {idea_id} not found"},
            )
        return {"message": "Idea deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


# Specialized endpoints
@router.post(
    "/{project_id}/ideas",
    response_model=Idea,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": dict}, 500: {"model": dict}},
)
async def add_idea_to_project(project_id: str, idea: IdeaCreate):
    """
    Add an idea to a project (convenience endpoint).
    """
    try:
        return service.add_idea_to_project(project_id, idea.model_dump())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "/{project_id}/contribute",
    responses={400: {"model": dict}, 500: {"model": dict}},
)
async def contribute_to_project(project_id: str, contribution: ContributionCreate):
    """
    Add a contribution to a crowdsourced project.
    """
    try:
        success = service.contribute_to_project(project_id, contribution.model_dump())
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ContributionFailed", "message": "Failed to add contribution"},
            )
        return {"message": "Contribution added successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "/{project_id}/back",
    responses={400: {"model": dict}, 500: {"model": dict}},
)
async def back_project(project_id: str, backing: BackingCreate):
    """
    Add funding to a crowdfunded project.
    """
    try:
        success = service.contribute_funding(project_id, backing.model_dump())
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "BackingFailed", "message": "Failed to add backing"},
            )
        return {"message": "Backing added successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/{project_id}/contributors",
    response_model=list[Contributor],
    responses={404: {"model": dict}, 500: {"model": dict}},
)
async def get_project_contributors(project_id: str):
    """
    Get list of contributors for a crowdsourced project.
    """
    try:
        # Check if project exists
        project = service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ProjectNotFound", "message": f"Project {project_id} not found"},
            )

        return service.get_contributors(project_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/{project_id}/backers",
    response_model=list[Backer],
    responses={404: {"model": dict}, 500: {"model": dict}},
)
async def get_project_backers(project_id: str):
    """
    Get list of backers for a crowdfunded project.
    """
    try:
        # Check if project exists
        project = service.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ProjectNotFound", "message": f"Project {project_id} not found"},
            )

        return service.get_backers(project_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "/from-artifacts",
    response_model=CrowdfundedProject,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": dict}, 500: {"model": dict}},
)
async def create_project_from_artifacts(request: CreateProjectFromArtifacts):
    """
    Create a crowdsourced project from chat artifacts.
    """
    try:
        return service.create_project_from_artifacts(
            session_id=request.session_id,
            title=request.title,
            description=request.description,
            artifacts=request.artifacts,
            knowledge_base_id=request.knowledge_base_id,
            tags=request.tags,
            funding_goal=request.funding_goal,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/stats",
    responses={500: {"model": dict}},
)
async def get_projects_stats():
    """
    Get projects statistics.
    """
    try:
        return service.get_stats()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )
