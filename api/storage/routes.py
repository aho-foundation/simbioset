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


@router.get("/schema")
async def get_schema(request: Request):
    """
    Get Weaviate schema information.

    Returns schema details if using Weaviate, otherwise returns info about storage type.
    """
    try:
        storage = getattr(request.app.state, "storage", None) or getattr(request.app.state, "faiss_storage", None)
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "InternalError", "message": "Storage not initialized"},
            )

        # Проверяем, используем ли Weaviate
        from api.storage.weaviate_storage import WeaviateStorage

        is_weaviate = isinstance(storage, WeaviateStorage)

        if is_weaviate:
            try:
                from api.settings import WEAVIATE_CLASS_NAME, WEAVIATE_USE_BUILTIN_AUTOSCHEMA
                from weaviate.exceptions import UnexpectedStatusCodeError

                # Проверяем, существует ли коллекция
                collection_exists = storage.client.collections.exists(WEAVIATE_CLASS_NAME)

                if not collection_exists:
                    # Если AutoSchema включена, коллекция создастся автоматически при первом сохранении
                    # Если выключена, создаем схему вручную
                    if not WEAVIATE_USE_BUILTIN_AUTOSCHEMA:
                        from api.storage.weaviate_schema import create_schema_if_not_exists

                        create_schema_if_not_exists(storage.client)
                        # Проверяем еще раз после создания
                        collection_exists = storage.client.collections.exists(WEAVIATE_CLASS_NAME)

                    # Если коллекция все еще не существует (AutoSchema включена), возвращаем информацию
                    if not collection_exists:
                        return {
                            "storage_type": "weaviate",
                            "collection_name": WEAVIATE_CLASS_NAME,
                            "autoschema_enabled": WEAVIATE_USE_BUILTIN_AUTOSCHEMA,
                            "collection_exists": False,
                            "message": f"Collection '{WEAVIATE_CLASS_NAME}' does not exist yet. It will be created automatically when first data is saved (AutoSchema enabled).",
                            "properties": [],
                            "total_properties": 0,
                        }

                # Получаем информацию о коллекции
                collection = storage.client.collections.get(WEAVIATE_CLASS_NAME)

                # Получаем конфигурацию коллекции
                config = collection.config.get()

                # Получаем свойства коллекции
                properties = []
                if hasattr(config, "properties") and config.properties:
                    for prop in config.properties:
                        properties.append(
                            {
                                "name": prop.name,
                                "data_type": str(prop.data_type) if hasattr(prop, "data_type") else "unknown",
                                "description": getattr(prop, "description", None),
                            }
                        )

                return {
                    "storage_type": "weaviate",
                    "collection_name": WEAVIATE_CLASS_NAME,
                    "autoschema_enabled": WEAVIATE_USE_BUILTIN_AUTOSCHEMA,
                    "collection_exists": True,
                    "properties": properties,
                    "total_properties": len(properties),
                }
            except UnexpectedStatusCodeError as e:
                # Обрабатываем 404 и другие HTTP ошибки отдельно
                if "404" in str(e) or "not found" in str(e).lower():
                    return {
                        "storage_type": "weaviate",
                        "collection_name": WEAVIATE_CLASS_NAME,
                        "autoschema_enabled": WEAVIATE_USE_BUILTIN_AUTOSCHEMA,
                        "collection_exists": False,
                        "message": f"Collection '{WEAVIATE_CLASS_NAME}' does not exist yet. It will be created automatically when first data is saved.",
                        "properties": [],
                        "total_properties": 0,
                    }
                # Для других HTTP ошибок возвращаем детали
                return {
                    "storage_type": "weaviate",
                    "error": str(e),
                    "autoschema_enabled": WEAVIATE_USE_BUILTIN_AUTOSCHEMA,
                }
            except Exception as e:
                import traceback

                return {
                    "storage_type": "weaviate",
                    "error": f"{str(e)}: {traceback.format_exc()}",
                    "autoschema_enabled": WEAVIATE_USE_BUILTIN_AUTOSCHEMA
                    if "WEAVIATE_USE_BUILTIN_AUTOSCHEMA" in dir()
                    else False,
                }
        else:
            # FAISS storage
            return {
                "storage_type": "faiss",
                "message": "FAISS storage does not use schema - it's an in-memory vector index",
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "SchemaError", "message": str(e)},
        )


@router.get("/search")
async def simple_search(
    request: Request,
    q: str = Query(..., description="Search query"),
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated, OR logic)"),
    exclude_tags: Optional[str] = Query(None, description="Exclude tags (comma-separated, NOT logic)"),
    location: Optional[str] = Query(None, description="Filter by location"),
    ecosystem_id: Optional[str] = Query(None, description="Filter by ecosystem ID"),
    use_hybrid: Optional[str] = Query(None, description="Use Hybrid Search (true/false, default: from config)"),
    hybrid_alpha: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Hybrid search alpha (0=BM25, 1=vector, default: 0.5)"
    ),
    use_reranking: Optional[str] = Query(None, description="Use Cross-Encoder reranking (true/false, default: false)"),
    timestamp_from: Optional[int] = Query(None, description="Filter by minimum timestamp"),
    timestamp_to: Optional[int] = Query(None, description="Filter by maximum timestamp"),
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

        exclude_tags_list = None
        if exclude_tags:
            exclude_tags_list = [tag.strip() for tag in exclude_tags.split(",") if tag.strip()]

        # Парсим булевы параметры из query string
        use_hybrid_bool = None
        if use_hybrid:
            use_hybrid_bool = use_hybrid.lower() in ["true", "1", "yes"]

        use_reranking_bool = None
        if use_reranking:
            use_reranking_bool = use_reranking.lower() in ["true", "1", "yes"]

        # Определяем тип хранилища и используем соответствующий метод
        is_weaviate = hasattr(storage, "search_similar_paragraphs") or hasattr(storage, "_build_filters")

        # Функция для сериализации Paragraph в dict
        def paragraph_to_dict(para):
            """Конвертирует Paragraph в dict с правильной сериализацией timestamp"""
            return {
                "id": para.id,
                "content": para.content,
                "document_id": para.document_id or "",
                "node_id": para.node_id or "",
                "document_type": para.document_type.value if para.document_type else "chat",
                "tags": para.tags or [],
                "author": para.author,
                "author_id": para.author_id,
                "location": para.location,
                "ecosystem_id": para.ecosystem_id or "",
                "timestamp": para.timestamp.isoformat() if para.timestamp else None,
            }

        if is_weaviate and hasattr(storage, "search_similar"):
            # Weaviate с расширенными возможностями
            # Используем search_similar с расширенными фильтрами
            raw_results = storage.search_similar(
                query=q,
                document_id=document_id,
                top_k=limit,
                classification_filter=None,
                fact_check_filter=None,
                location_filter=location,
                ecosystem_id_filter=ecosystem_id,
                organism_ids_filter=None,
                tags_filter=tags_list,  # OR фильтр по тегам
                exclude_tags=exclude_tags_list,  # NOT фильтр по тегам
                timestamp_from=timestamp_from,
                timestamp_to=timestamp_to,
                use_hybrid=use_hybrid_bool,
                hybrid_alpha=hybrid_alpha,
            )
            results = [{"paragraph": paragraph_to_dict(para), "score": score} for para, score in raw_results]

            # Для Weaviate фильтры по тегам применяются через _build_filters внутри search_similar
            # Но если нужно применить дополнительную фильтрацию на уровне API, делаем это здесь
            # (обычно это не нужно, так как фильтры уже применены)
        elif hasattr(storage, "search_similar_paragraphs"):
            # Weaviate через search_similar_paragraphs (старый способ, без расширенных фильтров)
            paragraphs = await storage.search_similar_paragraphs(
                query=q,
                document_id=document_id,
                top_k=limit,
                organism_ids_filter=None,
                location_filter=location,
                ecosystem_id_filter=ecosystem_id,
                use_reranking=use_reranking_bool,
            )
            results = [{"paragraph": paragraph_to_dict(para), "score": 1.0} for para in paragraphs[:limit]]
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
            results = [{"paragraph": paragraph_to_dict(para), "score": score} for para, score in raw_results]

        # Дополнительная фильтрация по тегам для FAISS (для Weaviate фильтры уже применены)
        if not is_weaviate:
            # Filter by tags if specified
            if tags_list:
                filtered_results = []
                for result in results:
                    para = result["paragraph"]
                    if para.tags and any(tag in para.tags for tag in tags_list):
                        filtered_results.append(result)
                results = filtered_results[:limit]

            # Exclude tags
            if exclude_tags_list:
                filtered_results = []
                for result in results:
                    para = result["paragraph"]
                    if not para.tags or not any(tag in para.tags for tag in exclude_tags_list):
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
