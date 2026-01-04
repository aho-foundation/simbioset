"""FastAPI routes for Knowledge Base API."""

import asyncio
import json
from typing import Literal, Optional
from fastapi import APIRouter, Body, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .models import (
    ConceptNode,
    NodeUpdate,
    NodeWithContext,
    Source,
    TreeResponse,
    SearchResponse,
    StatsResponse,
    DeleteResponse,
    ImportRequest,
    ImportResponse,
    ExportResponse,
    ErrorResponse,
)
from .service import KBService
from fastapi import Request

router = APIRouter(prefix="/api/kb", tags=["Knowledge Base"])


def get_kb_service(request: Request) -> KBService:
    """Get KB service from app state."""
    return request.app.state.kb_service


class SourceCreate(BaseModel):
    """Request model for creating a source."""

    url: str = Field(..., description="Source URL")
    title: Optional[str] = Field(None, description="Source title")
    type: Literal["confirm", "doubt"] = Field(..., description="Source type: 'confirm' or 'doubt'")
    tool: Optional[str] = Field(None, description="Tool that detected this source")
    sentiment: Optional[Literal["positive", "negative", "neutral"]] = Field(
        None, description="Sentiment: 'positive', 'negative', or 'neutral'"
    )
    userConfirmed: Optional[bool] = Field(None, description="User confirmation of sentiment")
    reliabilityScore: Optional[float] = Field(None, ge=0.0, le=1.0, description="Reliability score (0-1)")


@router.get(
    "/nodes/{node_id}",
    response_model=NodeWithContext,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_node(
    node_id: str,
    request: Request,
    include_parent: bool = Query(True, description="Include parent node"),
    include_children: bool = Query(True, description="Include child nodes"),
    include_siblings: bool = Query(True, description="Include sibling nodes"),
    max_depth: int = Query(1, ge=1, le=10, description="Maximum depth for loading children"),
):
    """
    Get node with surrounding context (parent, children, siblings).

    This endpoint returns a node along with its surrounding context to enable
    efficient 3D tree visualization and navigation.
    """
    try:
        service = get_kb_service(request)
        result = service.get_node_with_context(node_id, include_parent, include_children, include_siblings, max_depth)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NodeNotFound", "message": f"Node with id '{node_id}' not found", "nodeId": node_id},
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/tree",
    response_model=TreeResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_tree(
    request: Request,
    root_id: Optional[str] = Query(None, description="Specific root node ID"),
    depth: int = Query(2, ge=1, le=10, description="Tree depth to load"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of nodes"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by node type"),
):
    """
    Get tree structure with optional filters and pagination.

    Returns root node and a list of nodes up to specified depth.
    Useful for loading large tree structures efficiently.
    """
    try:
        service = get_kb_service(request)
        result = service.get_tree(root_id, depth, limit, offset, category, type)
        return result

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
    "/search",
    response_model=SearchResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def search_nodes(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by node type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Search nodes by content with optional filters.

    Performs full-text search on node content and returns results
    with relevance scores.
    """
    try:
        service = get_kb_service(request)
        result = service.search_nodes(q, category, type, limit, offset)
        return result

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
    "/nodes",
    response_model=ConceptNode,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def create_node_endpoint(
    request: Request,
    parentId: Optional[str] = None,
    content: str = Body(...),
    role: Literal["user", "assistant", "system"] = "user",
) -> ConceptNode:
    """
    Create a new concept node.

    According to docs/conversation_tree_framework.md line 69.

    Args:
        parentId: ID of parent node (None for root)
        content: Text content of the node
        sender: Type of sender ('user' or 'bot')

    Returns:
        Created ConceptNode
    """
    try:
        service = get_kb_service(request)
        return service.add_concept(parent_id=parentId, content=content, role=role)

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
    "/nodes/{node_id}",
    response_model=NodeWithContext,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def update_node(node_id: str, updates: NodeUpdate, request: Request):
    """
    Update an existing node with partial updates.

    Only provided fields will be updated. Returns updated node with context.
    """
    try:
        service = get_kb_service(request)
        updated_node = service.update_node(node_id, updates)

        if not updated_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NodeNotFound", "message": f"Node with id '{node_id}' not found", "nodeId": node_id},
            )

        context = service.get_node_with_context(node_id)

        return context

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
    "/nodes/{node_id}",
    response_model=DeleteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def delete_node(
    node_id: str,
    request: Request,
    cascade: bool = Query(True, description="Delete children recursively"),
):
    """
    Delete a node and optionally its children.

    If cascade=false and node has children, returns 409 Conflict.
    Returns count of deleted nodes.
    """
    try:
        service = get_kb_service(request)
        result = service.delete_node(node_id, cascade)
        return result

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NodeNotFound", "message": error_msg, "nodeId": node_id},
            )
        elif "children" in error_msg.lower():
            children_count = int(error_msg.split()[5]) if "with" in error_msg else 0
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "ConflictError",
                    "message": "Cannot delete node with children without cascade=true",
                    "childrenCount": children_count,
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": error_msg},
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/stats",
    response_model=StatsResponse,
    responses={500: {"model": ErrorResponse}},
)
async def get_stats(request: Request):
    """
    Get knowledge base statistics.

    Returns metrics about total nodes, depth, categories, types, and last update time.
    """
    try:
        service = get_kb_service(request)
        result = service.get_stats()
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get(
    "/export",
    response_model=ExportResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def export_tree(
    request: Request,
    root_id: Optional[str] = Query(None, description="Export specific subtree"),
    format: str = Query("json", description="Export format (currently only json)"),
):
    """
    Export knowledge base to JSON format.

    Can export entire tree or specific subtree by providing root_id.
    """
    try:
        service = get_kb_service(request)
        if format != "json":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": f"Unsupported format: {format}"},
            )

        result = service.export_tree(root_id)
        return result

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


@router.post(
    "/import",
    response_model=ImportResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def import_tree(import_data: ImportRequest, request: Request):
    """
    Import nodes from external data.

    Options:
    - merge: Update existing nodes with imported data
    - overwrite: Replace existing nodes completely
    - neither: Skip conflicting nodes (returns conflicts list)
    """
    try:
        service = get_kb_service(request)
        result = service.import_tree(import_data.nodes, import_data.merge, import_data.overwrite)
        return result

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


@router.get("/root", response_model=ConceptNode, responses={404: {"model": ErrorResponse}})
async def get_root_node(request: Request) -> ConceptNode:
    """
    Get the root node of the tree.

    Returns:
        Root ConceptNode or 404 if not found

    Raises:
        HTTPException: 404 if root not found
    """
    service = get_kb_service(request)
    root = service.get_root()
    if not root:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Root node not found")
    return root


@router.post("/nodes/{node_id}/expand")
async def set_node_expanded(node_id: str, request: Request, expanded: bool = True) -> dict:
    """
    Set expanded state of a node.

    Args:
        node_id: ID of the node
        expanded: Expanded state (default: True)

    Returns:
        Success response with node ID and expanded state
    """
    service = get_kb_service(request)
    service.set_expanded(node_id, expanded)
    return {"success": True, "nodeId": node_id, "expanded": expanded}


@router.post("/nodes/{node_id}/toggle-expand")
async def toggle_node_expanded(node_id: str, request: Request) -> dict:
    """
    Toggle expanded state of a node.

    Args:
        node_id: ID of the node

    Returns:
        Success response with node ID and new expanded state
    """
    service = get_kb_service(request)
    service.toggle_expanded(node_id)
    node = service.get_node(node_id)
    return {"success": True, "nodeId": node_id, "expanded": node.expanded if node else False}


@router.post("/nodes/{node_id}/select")
async def set_node_selected(node_id: str, request: Request, selected: bool = True) -> dict:
    """
    Set selected state of a node.

    Args:
        node_id: ID of the node
        selected: Selected state (default: True)

    Returns:
        Success response with node ID and selected state
    """
    service = get_kb_service(request)
    service.set_selected(node_id, selected)
    return {"success": True, "nodeId": node_id, "selected": selected}


@router.post("/nodes/{node_id}/toggle-select")
async def toggle_node_selected(node_id: str, request: Request) -> dict:
    """
    Toggle selected state of a node.

    Args:
        node_id: ID of the node

    Returns:
        Success response with node ID and new selected state
    """
    service = get_kb_service(request)
    service.toggle_selected(node_id)
    node = service.get_node(node_id)
    return {"success": True, "nodeId": node_id, "selected": node.selected if node else False}


@router.get("/nodes/selected")
async def get_selected_nodes(request: Request) -> list[ConceptNode]:
    """
    Get all nodes that are currently selected.

    Returns:
        List of selected ConceptNodes
    """
    service = get_kb_service(request)
    return service.get_selected_nodes()


@router.post("/nodes/clear-selection")
async def clear_selection(request: Request) -> dict:
    """
    Clear selection state for all nodes.

    Returns:
        Success response with count of cleared nodes
    """
    service = get_kb_service(request)
    cleared_count = service.clear_selection()
    return {"success": True, "clearedCount": cleared_count}


@router.get("/sessions", response_model=list[ConceptNode])
async def get_chat_sessions(request: Request) -> list[ConceptNode]:
    """
    Get all chat sessions (root nodes).

    Returns:
        List of chat session ConceptNodes
    """
    service = get_kb_service(request)
    return service.get_chat_sessions()


@router.get("/sessions/{session_id}", response_model=ConceptNode, responses={404: {"model": ErrorResponse}})
async def get_chat_session(session_id: str, request: Request) -> ConceptNode:
    """
    Get chat session by ID.

    Args:
        session_id: ID of the session

    Returns:
        ConceptNode of the session

    Raises:
        HTTPException: 404 if session not found
    """
    service = get_kb_service(request)
    session = service.get_chat_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found")
    return session


@router.post("/nodes/{node_id}/sources", response_model=Source, responses={404: {"model": ErrorResponse}})
async def add_source_to_node(node_id: str, source: SourceCreate, request: Request) -> Source:
    """
    Add a source to a concept node.

    Args:
        node_id: ID of the node
        source: Source data to add

    Returns:
        Created Source

    Raises:
        HTTPException: 404 if node not found
    """
    try:
        service = get_kb_service(request)
        created_source = service.add_source(node_id, source.model_dump(exclude_none=True))
        return created_source
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/continue-from-node")
async def continue_conversation_from_node(
    request: Request,
    node_id: str = Body(..., embed=True),
    message: str = Body(..., embed=True),
    session_id: Optional[str] = Body(None, embed=True),
) -> dict:
    """
    Continue a conversation from a specific node in the knowledge tree.

    This endpoint allows users to pick up a conversation from any point in the
    knowledge tree, using the selected node as context for the new interaction.

    Args:
        node_id: The node ID to use as context for the new conversation
        message: The new message to start the conversation with
        session_id: Optional existing session ID, creates new if not provided

    Returns:
        Dictionary with conversation continuation results
    """
    try:
        service = get_kb_service(request)
        # Validate that the node exists
        node = service.get_node(node_id)
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NodeNotFound", "message": f"Node with id '{node_id}' not found", "nodeId": node_id},
            )

        # If no session_id provided, create a new session
        if not session_id:
            import uuid
            from datetime import datetime

            session_id = str(uuid.uuid4())

            # Create a new root node for this chat session (system message, not a session itself)
            session_node = service.add_concept(
                parent_id=None,
                content=f"Continuation from node: {node.content[:50]}...",
                role="system",
                node_type="message",  # Исправлено: не chat_session, а message с role=system
                session_id=session_id,
                category="neutral",
            )
        else:
            # Verify session exists
            existing_session = service.get_node(session_id)
            if not existing_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "SessionNotFound",
                        "message": f"Session {session_id} not found",
                        "sessionId": session_id,
                    },
                )

        # Add the user's message to the session as a child of the session node
        user_message_node = service.add_concept(
            parent_id=session_id,
            content=message,
            role="user",
            node_type="message",
            session_id=session_id,
        )

        # Add a relationship/pointer to the node we're continuing from
        # This creates a reference so we can track the context origin
        context_reference_node = service.add_concept(
            parent_id=user_message_node.id,
            content=f"Context reference: {node.content}",
            role="system",
            node_type="context_reference",
            session_id=session_id,
            concept_node_id=node_id,  # Link back to the original node
        )

        # In a real implementation, you would likely call an LLM here to generate
        # a response based on the context from the original node and the new message
        # For now, we'll return information about the continuation

        return {
            "status": "success",
            "message": "Conversation continued from node successfully",
            "sessionId": session_id,
            "nodeId": node_id,
            "userMessageId": user_message_node.id,
            "contextReferenceId": context_reference_node.id,
            "originalNodeContent": node.content,
            "newMessage": message,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Knowledge Base API", "version": "1.0.0"}


@router.get("/tree/stream")
async def stream_tree_updates(
    request: Request,
    depth: int = Query(2, ge=1, le=10, description="Tree depth to load"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of nodes"),
    category: Optional[str] = Query(None, description="Filter by category"),
    type: Optional[str] = Query(None, description="Filter by node type"),
):
    """
    Stream tree updates via Server-Sent Events (SSE).

    Automatically sends tree updates when nodes are added, updated, or deleted.
    Updates are sent every 2 seconds to keep the tree synchronized.

    Args:
        depth: Tree depth to load
        limit: Maximum number of nodes
        category: Filter by category
        type: Filter by node type

    Returns:
        SSE stream with tree updates
    """
    service = get_kb_service(request)

    async def event_generator():
        """Generate SSE events with tree updates."""
        last_update_time = None

        while True:
            try:
                # Get current tree state
                tree_response = service.get_tree(
                    root_id=None,
                    depth=depth,
                    limit=limit,
                    offset=0,
                    category=category,
                    node_type=type,
                )

                # Check if tree has changed (simple timestamp-based check)
                current_update_time = int(tree_response.stats.get("totalNodes", 0)) if tree_response.stats else 0

                # Send update if tree changed or on first connection
                if last_update_time is None or current_update_time != last_update_time:
                    tree_data = {
                        "root": tree_response.root.model_dump() if tree_response.root else None,
                        "nodes": [node.model_dump() for node in tree_response.nodes],
                        "stats": tree_response.stats,
                    }

                    # Format as SSE event
                    event_data = json.dumps(tree_data, ensure_ascii=False)
                    yield f"data: {event_data}\n\n"

                    last_update_time = current_update_time

                # Wait before next check
                await asyncio.sleep(2)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Send error event
                error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
                yield f"data: {error_data}\n\n"
                await asyncio.sleep(5)  # Wait longer on error

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        },
    )


class AgREECompleteRequest(BaseModel):
    """Request model for AgREE knowledge completion."""

    organism_name: str = Field(..., description="Название организма")
    organism_type: Optional[str] = Field(None, description="Тип организма (растение, животное, гриб, бактерия)")
    context: Optional[str] = Field(None, description="Контекст упоминания организма")


@router.post(
    "/agree/complete",
    response_model=dict,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def agree_complete_knowledge(
    request_data: AgREECompleteRequest,
    request: Request,
):
    """
    Дополняет граф знаний информацией об организме используя агентный подход AgREE.

    Выполняет итеративный поиск информации о новом организме и автоматически создает
    триплеты (организм → связь → организм/экосистема) для дополнения графа знаний.
    """
    try:
        from api.kb.agree_agent import AgREEAgent
        from api.storage.symbiotic_service import SymbioticService
        from api.storage.organism_service import OrganismService
        from api.storage.ecosystem_service import EcosystemService

        # Получаем сервисы из app state
        db_manager = request.app.state.db_manager

        # Создаем сервисы
        symbiotic_service = SymbioticService(db_manager)
        organism_service = OrganismService(db_manager)
        ecosystem_service = EcosystemService(db_manager)

        # Создаем агента
        agent = AgREEAgent(
            symbiotic_service=symbiotic_service,
            organism_service=organism_service,
            ecosystem_service=ecosystem_service,
        )

        # Запускаем дополнение графа знаний
        result = await agent.complete_knowledge_for_organism(
            organism_name=request_data.organism_name,
            organism_type=request_data.organism_type,
            context=request_data.context,
        )

        return {
            "success": True,
            "organism_id": result["organism_id"],
            "triplets_created": result["triplets_created"],
            "iterations": result["iterations"],
            "final_info": result["final_info"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )
