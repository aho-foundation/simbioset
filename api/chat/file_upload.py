"""File upload endpoint with parsing, vectorization, and storage."""

import uuid
import json
from typing import Optional, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from datetime import datetime

from api.storage.db import DatabaseManagerBase
from api.storage.faiss import FAISSStorage
from api.storage.weaviate_storage import WeaviateStorage
from typing import Union
from api.storage.paragraph_service import ParagraphService
from api.kb.service import KBService
from api.logger import root_logger
from api.detect.image_processor import ImageProcessor, is_image_file, ImageType

log = root_logger.debug

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# Initialize services (will be injected or created on startup)
_db_manager: Optional[DatabaseManagerBase] = None
_faiss_storage: Optional[Union[FAISSStorage, WeaviateStorage]] = None
_paragraph_service: Optional[ParagraphService] = None
_kb_service: Optional[KBService] = None
_image_processor: Optional[ImageProcessor] = None


def init_file_upload_services(
    db_manager: DatabaseManagerBase,
    faiss_storage: Union[FAISSStorage, WeaviateStorage],
    kb_service: KBService,
    tag_service=None,
):
    """Initialize services for file upload.

    Args:
        db_manager: Database manager instance (DatabaseManager or PostgreSQLManager)
        faiss_storage: FAISS storage instance
        kb_service: Knowledge base service instance
        tag_service: Optional tag service instance
    """
    global _db_manager, _faiss_storage, _paragraph_service, _kb_service, _image_processor
    _db_manager = db_manager
    _faiss_storage = faiss_storage
    _kb_service = kb_service
    if tag_service is None:
        from api.classify.tag_service import TagService

        tag_service = TagService(db_manager)

    # Связываем tag_service с faiss_storage для последующей классификации параграфов
    setattr(_faiss_storage, "_tag_service", tag_service)

    # ParagraphService принимает только db_manager и faiss_storage
    _paragraph_service = ParagraphService(db_manager, faiss_storage)
    _image_processor = ImageProcessor()


@router.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    parent_id: Optional[str] = None,
    author: Optional[str] = None,
):
    """Upload and process a file: parse to paragraphs, vectorize, and save.

    Args:
        file: Uploaded file
        parent_id: Optional parent node ID
        author: Optional author name

    Returns:
        Dictionary with created node and paragraph information
    """
    if not _paragraph_service or not _kb_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload services not initialized",
        )

    try:
        # Read file content
        content = await file.read()

        # Проверяем, является ли файл изображением
        if is_image_file(file.filename or ""):
            return await _process_image_file(content, file.filename, parent_id, author)

        # Обрабатываем как текстовый файл
        text_content = content.decode("utf-8", errors="ignore")

        if not text_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty or cannot be decoded",
            )

        # Create document in documents table
        document_id = f"doc_{uuid.uuid4()}"
        timestamp = int(datetime.now().timestamp() * 1000)

        assert _db_manager is not None
        cursor = _db_manager.connection.cursor()
        cursor.execute(
            """
            INSERT INTO documents (id, title, content, source_url, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                file.filename,
                text_content,
                None,  # source_url
                '{"uploaded_at": ' + str(timestamp) + "}",
            ),
        )
        _db_manager.connection.commit()

        # Create knowledge node for the document first
        node_data: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "parentId": parent_id,
            "content": f"File: {file.filename}",
            "type": "message",
            "category": "neutral",
            "role": "user",
            "timestamp": timestamp,
            "sources": [],
            "metadata": {
                "document_id": document_id,
                "filename": file.filename,
            },
        }

        created_node = _kb_service.repository.create(node_data)
        node_id = created_node["id"]

        # Parse text to paragraphs
        paragraphs = _paragraph_service.parse_text_to_paragraphs(text_content)

        if not paragraphs:
            # If parsing failed, use entire content as one paragraph
            paragraphs = [text_content]

        # Save paragraphs and vectorize, linking them to the knowledge node
        paragraph_ids = _paragraph_service.save_document_paragraphs(
            document_id=document_id,
            paragraphs=paragraphs,
            author=author,
            timestamp=timestamp,
            node_id=node_id,  # Связываем параграфы с узлом знания
        )

        # Update node metadata with paragraph count
        _kb_service.repository.update(
            node_id,
            {
                "metadata": {
                    **node_data["metadata"],
                    "paragraph_count": len(paragraph_ids),
                }
            },
        )

        log(f"✅ File uploaded: {file.filename}, {len(paragraphs)} paragraphs, node {created_node['id']}")

        return {
            "node": created_node,
            "document_id": document_id,
            "filename": file.filename,
            "paragraph_count": len(paragraph_ids),
            "paragraph_ids": paragraph_ids,
        }

    except HTTPException:
        raise
    except Exception as e:
        log(f"❌ Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}",
        )


async def _process_image_file(
    image_data: bytes,
    filename: Optional[str],
    parent_id: Optional[str],
    author: Optional[str],
) -> dict:
    """
    Обрабатывает загруженное изображение.

    Args:
        image_data: Байты изображения
        filename: Имя файла
        parent_id: Опциональный ID родительского узла
        author: Опциональное имя автора

    Returns:
        Словарь с информацией об обработанном изображении
    """
    if not _image_processor or not _paragraph_service or not _kb_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image processing services not initialized",
        )

    try:
        # Обрабатываем изображение
        image_info = await _image_processor.process_image(
            image_data=image_data,
            filename=filename,
        )

        if "error" in image_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing image: {image_info['error']}",
            )

        # Создаем документ в documents table
        document_id = f"doc_{uuid.uuid4()}"
        timestamp = int(datetime.now().timestamp() * 1000)

        assert _db_manager is not None
        cursor = _db_manager.connection.cursor()
        cursor.execute(
            """
            INSERT INTO documents (id, title, content, source_url, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                filename or "image",
                image_info.get("description", ""),  # Описание изображения как контент
                None,  # source_url
                json.dumps(
                    {
                        "uploaded_at": timestamp,
                        "image_type": image_info.get("image_type"),
                        "width": image_info.get("width"),
                        "height": image_info.get("height"),
                        "format": image_info.get("format"),
                        "base64": image_info.get("base64"),  # Сохраняем изображение в base64
                        "metadata": image_info.get("metadata", {}),
                    }
                ),
            ),
        )
        _db_manager.connection.commit()

        # Создаем узел знания для изображения
        node_data: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "parentId": parent_id,
            "content": f"Image: {filename or 'image'} - {image_info.get('description', '')[:100]}",
            "type": "message",
            "category": "neutral",
            "role": "user",
            "timestamp": timestamp,
            "sources": [],
            "metadata": {
                "document_id": document_id,
                "filename": filename,
                "image_type": image_info.get("image_type"),
                "width": image_info.get("width"),
                "height": image_info.get("height"),
            },
        }

        created_node = _kb_service.repository.create(node_data)
        node_id = created_node["id"]

        # Создаем параграфы из описания изображения
        description = image_info.get("description", "")
        if description:
            paragraphs = _paragraph_service.parse_text_to_paragraphs(description)
            if not paragraphs:
                paragraphs = [description]

            # Сохраняем параграфы с метаданными об организмах и экосистемах
            paragraph_ids = _paragraph_service.save_document_paragraphs(
                document_id=document_id,
                paragraphs=paragraphs,
                author=author,
                timestamp=timestamp,
                node_id=node_id,
            )
        else:
            paragraph_ids = []

        # Обновляем метаданные узла
        _kb_service.repository.update(
            node_id,
            {
                "metadata": {
                    **node_data["metadata"],
                    "paragraph_count": len(paragraph_ids),
                    "detected_organisms": image_info.get("detected_organisms", []),
                    "detected_ecosystems": image_info.get("detected_ecosystems", []),
                    "location": image_info.get("location"),
                    "time_reference": image_info.get("time_reference"),
                }
            },
        )

        log(
            f"✅ Image uploaded: {filename}, type: {image_info.get('image_type')}, "
            f"{len(paragraph_ids)} paragraphs, node {created_node['id']}"
        )

        return {
            "node": created_node,
            "document_id": document_id,
            "filename": filename,
            "image_type": image_info.get("image_type"),
            "paragraph_count": len(paragraph_ids),
            "paragraph_ids": paragraph_ids,
            "detected_organisms": image_info.get("detected_organisms", []),
            "detected_ecosystems": image_info.get("detected_ecosystems", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        log(f"❌ Error processing image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing image: {str(e)}",
        )
