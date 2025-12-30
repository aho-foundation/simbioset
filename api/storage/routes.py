"""API routes for storage operations: paragraphs, vector search, dataset export."""

from fastapi import APIRouter, HTTPException, Query, Request, status
from typing import Optional, List
import json
from pydantic import BaseModel, Field

from api.storage.paragraph_service import ParagraphService
from api.storage.faiss import FAISSStorage, DocumentType
from api.storage.weaviate_storage import WeaviateStorage

router = APIRouter(prefix="/api/storage", tags=["Storage"])


class ParagraphResponse(BaseModel):
    """Response model for paragraph data."""

    id: str
    content: str
    document_id: Optional[str] = None
    node_id: Optional[str] = None
    document_type: str
    author: Optional[str] = None
    author_id: Optional[int] = None
    paragraph_index: Optional[int] = None
    timestamp: Optional[int] = None
    tags: Optional[List[str]] = None
    fact_check_result: Optional[str] = None
    fact_check_details: Optional[str] = None
    location: Optional[str] = None
    time_reference: Optional[str] = None
    metadata: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class VectorSearchRequest(BaseModel):
    """Request model for vector search."""

    query: str = Field(..., description="Search query")
    document_id: Optional[str] = Field(None, description="Filter by document ID")
    document_type: Optional[str] = Field(None, description="Filter by document type (chat, knowledge, document)")
    top_k: int = Field(10, ge=1, le=100, description="Number of results")
    classification_filter: Optional[str] = Field(None, description="Filter by classification")
    tags_filter: Optional[List[str]] = Field(
        None, description="Filter by tags (paragraph must have at least one of these tags)"
    )
    fact_check_filter: Optional[str] = Field(None, description="Filter by fact check result")


class VectorSearchResult(BaseModel):
    """Result model for vector search."""

    paragraph: ParagraphResponse
    score: float


@router.get("/paragraphs", response_model=List[ParagraphResponse])
async def get_paragraphs(
    request: Request,
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Get paragraphs from SQLite database.

    Returns paragraphs with metadata for dataset preparation.
    """
    try:
        paragraph_service: ParagraphService = request.app.state.paragraph_service

        doc_type = None
        if document_type:
            try:
                doc_type = DocumentType(document_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid document_type: {document_type}. Must be one of: chat, knowledge, document",
                )

        paragraphs = paragraph_service.get_paragraphs_from_db(
            document_id=document_id,
            document_type=doc_type,
            limit=limit,
            offset=offset,
        )

        return paragraphs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/search")
async def simple_search(
    request: Request,
    q: str = Query(..., description="Search query"),
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    location: Optional[str] = Query(None, description="Filter by location"),
    ecosystem_id: Optional[str] = Query(None, description="Filter by ecosystem ID"),
):
    """
    Simple search endpoint for frontend (GET with query params).
    """
    try:
        storage = getattr(request.app.state, "storage", None) or getattr(request.app.state, "faiss_storage", None)
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "InternalError", "message": "Storage not initialized"},
            )

        # Parse tags
        tags_list = None
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Use search_similar_paragraphs for Weaviate (returns paragraphs) or search_similar for FAISS
        if hasattr(storage, "search_similar_paragraphs"):
            # Weaviate path - returns paragraphs directly
            paragraphs = await storage.search_similar_paragraphs(
                query=q,
                document_id=document_id,
                top_k=limit,
                organism_ids_filter=None,  # Not used in simple search
                location_filter=location,
                ecosystem_id_filter=ecosystem_id,
            )
            results = [{"paragraph": para, "score": 1.0} for para in paragraphs[:limit]]
        else:
            # FAISS path - returns tuples (paragraph, score)
            raw_results = storage.search_similar(
                query=q,
                document_id=document_id,
                top_k=limit,
                classification_filter=None,
                fact_check_filter=None,
                location_filter=location,
                ecosystem_id_filter=ecosystem_id,
            )
            results = [{"paragraph": para, "score": score} for para, score in raw_results]

        # Filter by tags if specified
        if tags_list:
            filtered_results = []
            for result in results:
                para = result["paragraph"]
                if para.tags and any(tag in para.tags for tag in tags_list):
                    filtered_results.append(result)
            results = filtered_results[:limit]

        return {"results": results, "total": len(results)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SearchError", "message": str(e)},
        )


@router.post("/search", response_model=List[VectorSearchResult])
async def vector_search(search_request: VectorSearchRequest, request: Request):
    """
    Perform vector search on paragraphs.

    Searches for similar paragraphs using FAISS index.
    """
    try:
        # Используем универсальное хранилище (может быть FAISS или Weaviate)
        storage = getattr(request.app.state, "storage", None) or getattr(request.app.state, "faiss_storage", None)
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "InternalError", "message": "Storage not initialized"},
            )

        if search_request.document_id:
            # Search in specific document
            from api.storage.faiss import ClassificationType, FactCheckResult

            classification_filter = None
            if search_request.classification_filter:
                try:
                    classification_filter = ClassificationType(search_request.classification_filter)
                except ValueError:
                    pass

            fact_check_filter = None
            if search_request.fact_check_filter:
                try:
                    fact_check_filter = FactCheckResult(search_request.fact_check_filter)
                except ValueError:
                    pass

            results = storage.search_similar(
                query=search_request.query,
                document_id=search_request.document_id,
                top_k=search_request.top_k,
                classification_filter=classification_filter,
                fact_check_filter=fact_check_filter,
            )

            # Фильтрация по тегам (если указаны)
            if search_request.tags_filter:
                filtered_results = []
                for para, score in results:
                    # Параграф должен иметь хотя бы один из указанных тегов
                    if para.tags and any(tag in para.tags for tag in search_request.tags_filter):
                        filtered_results.append((para, score))
                results = filtered_results

            return [
                VectorSearchResult(
                    paragraph=ParagraphResponse(
                        id=para.id,
                        content=para.content,
                        document_id=para.document_id,
                        node_id=para.node_id,
                        document_type=para.document_type.value,
                        author=para.author,
                        author_id=para.author_id,
                        paragraph_index=para.paragraph_index,
                        timestamp=int(para.timestamp.timestamp() * 1000) if para.timestamp else None,
                        tags=para.tags if para.tags else [],
                        fact_check_result=para.fact_check_result.value if para.fact_check_result else None,
                        fact_check_details=json.dumps(para.fact_check_details, ensure_ascii=False)
                        if para.fact_check_details is not None
                        else None,
                        location=para.location,
                        time_reference=para.time_reference,
                    ),
                    score=float(score),
                )
                for para, score in results
            ]
        else:
            # Search across all documents (if document_type filter provided)
            # For now, return empty - can be extended to search across multiple documents
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="document_id is required for vector search",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/dataset/export", response_model=List[ParagraphResponse])
async def export_dataset(
    request: Request,
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Export paragraphs as dataset for training.

    Returns all paragraphs with full metadata for dataset preparation.
    """
    try:
        paragraph_service: ParagraphService = request.app.state.paragraph_service

        doc_type = None
        if document_type:
            try:
                doc_type = DocumentType(document_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid document_type: {document_type}. Must be one of: chat, knowledge, document",
                )

        paragraphs = paragraph_service.get_paragraphs_from_db(
            document_id=None,
            document_type=doc_type,
            limit=limit,
            offset=offset,
        )

        return paragraphs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/documents", response_model=List[str])
async def get_documents(request: Request):
    """
    Get list of all document IDs in FAISS index.

    Returns all document IDs that have paragraphs indexed.
    """
    try:
        # Используем универсальное хранилище (может быть FAISS или Weaviate)
        storage = getattr(request.app.state, "storage", None) or getattr(request.app.state, "faiss_storage", None)
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "InternalError", "message": "Storage not initialized"},
            )
        documents = storage.get_all_documents()
        return documents
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/documents/{document_id}/paragraphs", response_model=List[ParagraphResponse])
async def get_document_paragraphs(document_id: str, request: Request):
    """
    Get all paragraphs for a specific document from FAISS index.

    Returns paragraphs loaded in memory (from FAISS index).
    """
    try:
        # Используем универсальное хранилище (может быть FAISS или Weaviate)
        storage = getattr(request.app.state, "storage", None) or getattr(request.app.state, "faiss_storage", None)
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "InternalError", "message": "Storage not initialized"},
            )
        paragraphs = storage.get_document_paragraphs(document_id)

        return [
            ParagraphResponse(
                id=para.id,
                content=para.content,
                document_id=para.document_id,
                node_id=para.node_id,
                document_type=para.document_type.value,
                author=para.author,
                author_id=para.author_id,
                paragraph_index=para.paragraph_index,
                timestamp=int(para.timestamp.timestamp() * 1000) if para.timestamp else None,
                fact_check_result=para.fact_check_result.value if para.fact_check_result else None,
                fact_check_details=json.dumps(para.fact_check_details, ensure_ascii=False)
                if para.fact_check_details is not None
                else None,
                location=para.location,
                time_reference=para.time_reference,
            )
            for para in paragraphs
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/documents/{document_id}/paragraphs/{paragraph_id}")
async def get_paragraph(document_id: str, paragraph_id: str, request: Request):
    """
    Get a specific paragraph by ID.
    """
    try:
        storage = getattr(request.app.state, "storage", None) or getattr(request.app.state, "faiss_storage", None)
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "InternalError", "message": "Storage not initialized"},
            )

        paragraph = storage.get_paragraph_by_id(document_id, paragraph_id)
        if not paragraph:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NotFound", "message": "Paragraph not found"},
            )

        return {
            "id": paragraph.id,
            "content": paragraph.content,
            "document_id": paragraph.document_id,
            "node_id": paragraph.node_id,
            "document_type": paragraph.document_type.value
            if hasattr(paragraph.document_type, "value")
            else paragraph.document_type,
            "tags": paragraph.tags or [],
            "author": paragraph.author,
            "author_id": paragraph.author_id,
            "location": paragraph.location,
            "ecosystem_id": paragraph.ecosystem_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )
