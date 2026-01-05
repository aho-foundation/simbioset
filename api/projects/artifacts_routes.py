"""FastAPI routes for Artifacts API."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, HTTPException, Query, status

from .artifacts import artifacts_manager, Artifact
from .artifacts_service import artifacts_service

router = APIRouter(prefix="/api/artifacts", tags=["Artifacts"])


@router.get(
    "",
    response_model=List[Dict[str, Any]],
    responses={500: {"model": Dict}},
)
async def get_artifacts(
    session_id: str = Query(..., description="Session ID to get artifacts for"),
    artifact_type: Optional[str] = Query(None, description="Filter by artifact type"),
):
    """
    Get all artifacts for a session, optionally filtered by type.
    """
    try:
        if artifact_type:
            artifacts = await artifacts_manager.get_artifacts_by_type(session_id, artifact_type)
        else:
            artifacts = await artifacts_manager.get_artifacts(session_id)

        return [artifact.to_dict() for artifact in artifacts]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": Dict}, 500: {"model": Dict}},
)
async def add_artifact(
    session_id: str = Body(..., description="Session ID"),
    message_id: str = Body(..., description="Message ID where text was selected"),
    selected_text: str = Body(..., description="Selected text content"),
    content: Optional[str] = Body(None, description="Full content (optional)"),
    artifact_type: str = Body("note", description="Type of artifact"),
):
    """
    Add a new artifact to the session.
    """
    try:
        if not selected_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": "Selected text cannot be empty"},
            )

        artifact = await artifacts_manager.add_artifact(session_id, message_id, selected_text, content, artifact_type)

        if not artifact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound", "message": f"Session {session_id} not found"},
            )

        return artifact.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.delete(
    "/{artifact_id}",
    responses={404: {"model": Dict}, 500: {"model": Dict}},
)
async def remove_artifact(
    artifact_id: str,
    session_id: str = Query(..., description="Session ID"),
):
    """
    Remove an artifact from the session.
    """
    try:
        success = await artifacts_manager.remove_artifact(session_id, artifact_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ArtifactNotFound", "message": f"Artifact {artifact_id} not found"},
            )

        return {"message": "Artifact removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.delete(
    "",
    responses={404: {"model": Dict}, 500: {"model": Dict}},
)
async def clear_artifacts(
    session_id: str = Query(..., description="Session ID to clear artifacts for"),
):
    """
    Clear all artifacts from a session.
    """
    try:
        success = await artifacts_manager.clear_artifacts(session_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound", "message": f"Session {session_id} not found"},
            )

        return {"message": "All artifacts cleared successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "/analyze-conversation",
    response_model=Dict[str, Any],
    responses={400: {"model": Dict}, 500: {"model": Dict}},
)
async def analyze_conversation(
    session_id: str = Body(..., description="Session ID"),
    conversation_messages: list[Dict[str, Any]] = Body(..., description="List of conversation messages"),
):
    """
    Analyze conversation quality and extract potential artifacts.
    """
    try:
        if not conversation_messages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": "Conversation messages cannot be empty"},
            )

        # Анализируем качество диалога
        quality_analysis = await artifacts_service.analyze_conversation_quality(conversation_messages)

        # Извлекаем артефакты
        artifacts_result = await artifacts_service.extract_artifacts_from_conversation(
            conversation_messages, session_id
        )

        return {
            "quality_analysis": quality_analysis,
            "artifacts_analysis": artifacts_result,
            "recommendations": [
                "Используйте извлеченные артефакты для создания проектов"
                if artifacts_result.get("artifacts")
                else "Диалог содержит мало значимых артефактов",
                "Рассмотрите возможность углубления обсуждения конкретных тем"
                if quality_analysis.get("artifacts_count", 0) < 3
                else "Диалог имеет хороший потенциал для проектов",
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "/create-project-from-conversation",
    response_model=Dict[str, Any],
    responses={400: {"model": Dict}, 500: {"model": Dict}},
)
async def create_project_from_conversation(
    session_id: str = Body(..., description="Session ID"),
    conversation_messages: list[Dict[str, Any]] = Body(..., description="List of conversation messages"),
    project_title: str = Body(..., description="Title for the created project"),
    project_description: str = Body(..., description="Description for the created project"),
):
    """
    Complete workflow: extract artifacts from conversation and create a project.
    """
    try:
        if not conversation_messages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": "Conversation messages cannot be empty"},
            )

        if not project_title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": "Project title cannot be empty"},
            )

        project = await artifacts_service.create_project_from_conversation_artifacts(
            session_id=session_id,
            conversation_messages=conversation_messages,
            project_title=project_title,
            project_description=project_description,
        )

        if not project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ProjectCreationFailed", "message": "Could not create project from conversation"},
            )

        return {"project": project, "message": "Project created successfully from conversation artifacts"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post(
    "/convert-artifacts-to-projects",
    response_model=Dict[str, Any],
    responses={400: {"model": Dict}, 500: {"model": Dict}},
)
async def convert_artifacts_to_projects(
    artifacts: list[Dict[str, Any]] = Body(..., description="List of artifacts to convert"),
):
    """
    Convert artifacts into structured projects using AI analysis.
    """
    try:
        if not artifacts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": "Artifacts list cannot be empty"},
            )

        result = await artifacts_service.convert_artifacts_to_projects(artifacts)

        return {
            "projects": result.get("projects", []),
            "summary": result.get("summary", {}),
            "message": f"Converted {len(artifacts)} artifacts into {len(result.get('projects', []))} projects",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )
