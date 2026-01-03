"""FastAPI routes for Chat API."""

import time
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response, status, Body
from pydantic import BaseModel

from api.logger import root_logger as logger
from api.detect.web_search import web_search_service
from api.chat.models import ChatSession, ChatSessionCreate, ChatMessageCreate, ChatDragToChat
from api.chat.service import chat_session_service, generate_starters


class LocalizeRequest(BaseModel):
    sessionId: str
    latitude: float
    longitude: float
    conversationText: str
    action: Optional[str] = "localize"  # "localize", "expand_context", "new_branch"


from api.kb.models import ConceptNode
from api.kb.service import KBService
from api.storage.paragraph_service import ParagraphService
from api.llm import LLMPermanentError, LLMTemporaryError, call_llm
from api.sessions import session_manager
from api.logger import root_logger
import re

log = root_logger.debug
from api.chat.context_builder import (
    build_context_for_llm,
    should_include_context,
    get_weather_context,
    extract_ecosystem_and_location,
    format_ecosystem_context,
)
from api.detect.localize import reverse_geocode_location

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Services will be injected from app.state in route handlers

# Фильтрация LLM ответов выполняется в прокси (llm_proxy)
# Нормализация и исправление искаженных символов выполняется в call_llm


def remove_sources_section_from_content(content: str) -> str:
    """
    Удаляет раздел "## Источники" из текста ответа LLM.

    Это предотвращает дублирование источников - они показываются отдельно,
    а не в тексте сообщения.

    Args:
        content: Полный текст ответа LLM

    Returns:
        Текст без раздела источников
    """
    # Удаляем раздел "## Источники" в разных вариантах:
    # - ## Источники
    # - ## Источники:
    # - ### Источники
    # - С переносом строки или без
    patterns = [
        # Заголовок с ## или ###, с двоеточием или без, и все содержимое до следующего заголовка или конца
        r"\n?##+\s*Источники:?\s*\n.*?(?=\n?##+|\Z)",
        # Заголовок в начале строки
        r"^##+\s*Источники:?\s*\n.*?(?=\n?##+|\Z)",
        # Заголовок в середине текста
        r"\n##+\s*Источники:?\s*\n.*?(?=\n##+|\n###+|\Z)",
    ]

    cleaned_content = content
    for pattern in patterns:
        cleaned_content = re.sub(pattern, "", cleaned_content, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)

    # Удаляем лишние пустые строки в конце
    return cleaned_content.strip()


def parse_sources_from_response(response_content: str) -> List[Dict[str, str]]:
    """
    Парсит источники из ответа LLM с множественными фаллбеками.

    Сначала ищет структурированный раздел "## Источники", затем пытается
    извлечь источники из текста в разных форматах.

    Args:
        response_content: Полный текст ответа LLM

    Returns:
        Список словарей с источниками [{'title': 'Название источника', 'type': 'Тип источника', 'url': 'ссылка'}]
    """
    sources: List[Dict[str, str]] = []

    # ФАЛЛБЕК 1: Ищем структурированный раздел "## Источники"
    sources_match = re.search(
        r"##\s*Источники?\s*\n(.*?)(?=\n##|\n###|\Z)", response_content, re.DOTALL | re.IGNORECASE
    )

    if sources_match:
        sources_text = sources_match.group(1).strip()
        # Парсим пронумерованный список источников
        lines = sources_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Убираем нумерацию в начале строки (1., 2., etc.)
            line = re.sub(r"^\d+\.\s*", "", line)

            # Ищем URL в строке (https://... или http://...)
            url_match = re.search(r'(https?://[^\s]+)', line)
            url = url_match.group(1) if url_match else None

            # Убираем URL из строки для парсинга названия и типа
            line_without_url = re.sub(r'\s*https?://[^\s]+\s*', '', line).strip()

            # Разделяем название и тип (если есть в скобках)
            type_match = re.search(r"\(([^)]+)\)$", line_without_url)
            if type_match:
                title = line_without_url[: type_match.start()].strip()
                source_type = type_match.group(1).strip()
                # Пропускаем источники с типом "Неизвестный тип"
                if source_type.lower() in ("неизвестный тип", "unknown type", "unknown"):
                    continue
            else:
                # Проверяем на эмоджи в конце строки (после названия)
                emoji_match = re.search(r'([^\w\s])\s*$', line_without_url)
                if emoji_match:
                    title = line_without_url[:emoji_match.start()].strip()
                    source_type = emoji_match.group(1).strip()
                else:
                    # Если тип не указан, пропускаем источник
                    continue

            # Добавляем только источники с валидным названием и типом
            if title and source_type:
                source_dict = {"title": title, "type": source_type}
                if url:
                    source_dict["url"] = url
                sources.append(source_dict)

    # ФАЛЛБЕК 2: Ищем упоминания типов источников в тексте
    if not sources:
        # Определяем известные типы источников
        source_type_patterns = {
            'научная литература': 'Научная литература',
            'scientific literature': 'Научная литература',
            'веб-поиск': 'Веб-поиск',
            'web search': 'Веб-поиск',
            'база знаний': 'База знаний',
            'knowledge base': 'База знаний',
            'нейронная сеть': 'Нейронная сеть',
            'neural network': 'Нейронная сеть',
            'экспертные знания': 'Экспертные знания',
            'expert knowledge': 'Экспертные знания',
            'публикация': 'Публикация',
            'publication': 'Публикация',
            'исследование': 'Исследование',
            'research': 'Исследование'
        }

        found_types = []
        content_lower = response_content.lower()

        for pattern, source_type in source_type_patterns.items():
            if pattern in content_lower and source_type not in found_types:
                found_types.append(source_type)

        # Создаем источники на основе найденных типов
        for i, source_type in enumerate(found_types, 1):
            title = f"{source_type} по симбиозу"  # Дефолтный заголовок
            sources.append({"title": title, "type": source_type})

    # ФАЛЛБЕК 3: Если ничего не найдено, добавляем базовые источники
    if not sources:
        # Добавляем базовые источники для симбиоза
        sources = [
            {"title": "База знаний по симбиозу", "type": "База знаний"},
            {"title": "Экспертные знания", "type": "Экспертные знания"}
        ]

    return sources


@router.post("/session", response_model=ChatSession)
async def create_chat_session(session_data: ChatSessionCreate):
    """
    Create a new chat session.

    Creates a new chat session.
    """
    try:
        # Create a new chat session
        session = chat_session_service.create_session(session_data)

        # If ecosystem data is provided, set up the session location
        if session_data.ecosystem:
            ecosystem_data = {
                "location": session_data.ecosystem.get("coordinates", {}),
                "ecosystems": [
                    {"name": session_data.ecosystem.get("type", "неизвестная экосистема"), "scale": "regional"}
                ],
                "coordinates": session_data.ecosystem.get("coordinates"),
                "time_reference": None,
                "source": "branch_creation",
                "parent_session_id": session_data.ecosystem.get("parentSessionId"),
                "artifacts_summary": session_data.ecosystem.get("artifactsSummary"),
            }
            chat_session_service.update_session_location(session.id, ecosystem_data)

        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("/message", response_model=dict)
async def send_chat_message(message_data: ChatMessageCreate, request: Request, response: Response):
    """
    Send a message in a chat session.

    Adds the message to the concept tree and potentially generates a response.
    Automatically creates user session if not exists.
    """
    # Check if the message is about symbiosis or related topics to trigger web search
    message_lower = message_data.message.lower()
    trigger_keywords = ["симбиоз", "symbiosis", "symbiotic", "экосистема", "ecosystem", "взаимодействие", "interaction"]
    needs_web_search = any(keyword in message_lower for keyword in trigger_keywords)
    try:
        # Initialize session_id to None to avoid UnboundLocalError
        session_id = None

        # Check if this is a Telegram request with user ID
        telegram_user_id = message_data.context.get("telegram_user_id") if message_data.context else None

        if telegram_user_id:
            # Use persistent session for Telegram user (async)
            session_id = await session_manager.get_or_create_telegram_session(telegram_user_id, message_data.author)
            user_session = await session_manager.get_session(session_id)
        else:
            # Use sessionId from request body if provided, otherwise from cookies
            if message_data.sessionId is not None:
                session_id = message_data.sessionId
                user_session = await session_manager.get_session(session_id)
            else:
                # Try to get session_id from cookies first
                session_id = request.cookies.get("session_id")

                if session_id:
                    # If we have session_id from cookies, get the session (async)
                    user_session = await session_manager.get_session(session_id)
                else:
                    # No session in cookies, create a new one
                    user_session = None

                if not user_session:
                    # Create new session if none exists (async)
                    session_id = await session_manager.create_session(
                        {
                            "user_id": message_data.author,
                            "created_at": "auto",
                            "message_count": 0,
                            "last_activity": datetime.now(),
                        }
                    )
                    response.set_cookie("session_id", session_id, httponly=True, max_age=2592000)  # 30 days
                    user_session = await session_manager.get_session(session_id)

        # Update session activity (async)
        if user_session and session_id:
            # Use the correct session_id for updates
            await session_manager.increment_message_count(session_id)

        # Get services from app.state (injected at startup)
        service: KBService = request.app.state.kb_service
        paragraph_service: ParagraphService = request.app.state.paragraph_service

        # Verify the session exists, create if not found or default
        # Note: ChatSession управляется через chat_session_service, не через ConceptNode
        # ConceptNode может иметь sessionId, но сам не является сессией
        session_node = service.get_node(session_id)  # type: ignore
        if not session_node or session_id == "default-session":
            # Create root node for this chat session (system message, not a session itself)
            # Используем текст первого сообщения как содержание системного узла
            session_node = service.add_concept(
                parent_id=None,
                content=message_data.message,  # Используем текст стартера/первого сообщения
                role="system",
                node_type="message",  # Исправлено: не chat_session, а message с role=system
                session_id=None,  # Root node doesn't have sessionId
                category="neutral",
            )
            # Use the new node ID as session identifier
            actual_session_id = session_node.id
        else:
            actual_session_id = session_id  # type: ignore

        # Update chat session message count
        chat_session_service.increment_message_count(actual_session_id)

        # Link chat session to user session if not already linked (async)
        if session_id and user_session and not user_session.get("chat_session_id"):
            user_session["chat_session_id"] = actual_session_id
            await session_manager.update_session(session_id, user_session)

        # Add the user message to the concept tree
        user_message_node = service.add_concept(
            parent_id=actual_session_id,
            content=message_data.message,
            role="user",
            node_type="message",
            session_id=actual_session_id,
        )

        # Parse message to paragraphs and save for FAISS search
        try:
            await paragraph_service.save_chat_message_paragraphs(
                message_content=message_data.message,
                session_id=actual_session_id,
                author=message_data.author,
                author_id=None,  # TODO: Add author_id to ChatMessageCreate model
                timestamp=user_message_node.timestamp,
            )
        except Exception as e:
            # Log error but don't fail the request
            print(f"Error saving message paragraphs: {e}")

        # Load the simbio expert prompt template
        with open("api/prompts/simbio_expert.txt", "r", encoding="utf-8") as f:
            prompt_template = f.read()

        # Prepare context data for the prompt
        context = message_data.context or {}
        local_stat = context.get("local_stat", "")

        # Weaviate handles semantic search for all internal knowledge (artifacts, chats, books) automatically
        # Only external sources (web, books) need explicit search
        websearch_context = await web_search_service.get_symbiosis_context(message_data.message)
        books_search_context = await search_books_for_message(
            message_data.message, web_search_service, actual_session_id
        )

        # Combine only external sources (web and books)
        external_sources = "\n".join(filter(None, [websearch_context, books_search_context]))

        # User observation extraction is now handled by LLM instead of keyword matching

        # Получаем сохраненную локализацию сессии
        chat_session = chat_session_service.get_session(actual_session_id)
        session_location_data = chat_session.location if chat_session and chat_session.location else None

        # Определяем локацию из текста сообщения пользователя (если явно упомянута)
        user_location_data = None
        if message_data.author != "assistant":  # Только для пользовательских сообщений
            try:
                user_location_data = await extract_ecosystem_and_location(message_data.message)
                if user_location_data.get("location"):
                    logger.info(f"Обнаружена локация в сообщении пользователя: {user_location_data.get('location')}")

                    # Выполняем обратное геокодирование для получения координат
                    if user_location_data.get("location"):
                        try:
                            from api.detect.localize import geocode

                            coordinates = geocode(user_location_data["location"])
                            if coordinates:
                                user_location_data["coordinates"] = {
                                    "latitude": coordinates[0],
                                    "longitude": coordinates[1],
                                }
                                logger.info(
                                    f"Геокодированы координаты для локации {user_location_data['location']}: {coordinates}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Не удалось геокодировать локацию {user_location_data.get('location')}: {e}"
                            )

            except Exception as e:
                logger.warning(f"Ошибка при анализе локации в сообщении: {e}")

        # Используем сохраненную локализацию сессии или определенную из сообщения
        location = None
        ecosystems = []
        if session_location_data:
            # Приоритет сохраненной локализации сессии
            location = session_location_data.get("location")
            ecosystems = session_location_data.get("ecosystems", [])
            logger.info(
                f"Используем сохраненную локализацию сессии: location={location}, ecosystems={[e.get('name') for e in ecosystems]}"
            )
        elif user_location_data and user_location_data.get("location"):
            # Используем локацию из текущего сообщения
            location = user_location_data.get("location")
            ecosystems = user_location_data.get("ecosystems", [])

            # Автоматически сохраняем эту локализацию в сессии
            chat_session_service.update_session_location(
                actual_session_id,
                {
                    "location": location,
                    "ecosystems": ecosystems,
                    "coordinates": user_location_data.get("coordinates"),
                    "time_reference": user_location_data.get("time_reference"),
                    "source": "message_analysis",  # Отмечаем, что локализация определена из анализа сообщения
                },
            )
            logger.info(
                f"Автоматически сохранена локализация из сообщения: location={location}, ecosystems={[e.get('name') for e in ecosystems]}"
            )

        conversation_summary, recent_messages = await build_context_for_llm(
            actual_session_id, service, location=location, ecosystems=ecosystems
        )

        # Context sections are included if they have content (KISS: no conditional logic needed)

        # Получаем информацию о погоде, если в сообщении указаны город и время
        weather_context = await get_weather_context(message_data.message)

        # Форматируем контекст локальной экосистемы (объединяем погоду и экосистему)
        ecosystem_context = format_ecosystem_context(ecosystems, location, weather=weather_context)

        # Получаем графовый контекст через симбиотические связи
        # НЕ строим графовый контекст для первых 2 сообщений (стартер + ответ) - это слишком рано
        graph_context = ""
        try:
            # Проверяем количество сообщений в сессии
            session_messages = service.get_session_messages(actual_session_id)
            message_count = len(session_messages) if session_messages else 0

            # Строим графовый контекст только если в сессии больше 2 сообщений
            # (стартер + ответ = 2 сообщения, после этого уже можно строить граф)
            if message_count > 2:
                from api.chat.context_builder import build_graph_context

                # Используем универсальное хранилище (может быть FAISS или Weaviate)
                storage = getattr(request.app.state, "storage", None) or getattr(
                    request.app.state, "faiss_storage", None
                )
                graph_context = await build_graph_context(
                    message=message_data.message,
                    session_id=actual_session_id,
                    db_manager=request.app.state.db_manager,
                    storage=storage,
                    max_depth=2,
                    max_relationships=10,
                )
        except Exception as e:
            print(f"Error building graph context: {e}")

        # Получаем симбионтов для включения в ecosystem_context
        symbionts = []
        try:
            from api.storage.weaviate_storage import WeaviateStorage
            from api.storage.symbiont_service import SymbiontService

            weaviate_storage = WeaviateStorage()
            symbiont_service = SymbiontService(weaviate_storage)
            symbionts = await symbiont_service.search_symbionts(query=message_data.message, limit=5)
        except Exception as e:
            print(f"Error getting symbionts: {e}")

        # Обновляем ecosystem_context с включенными симбионтами
        ecosystem_context = format_ecosystem_context(ecosystems, location, weather=weather_context, symbionts=symbionts)

        # Format the prompt with context and message
        # Контексты уже отформатированы функциями format_*, без лишних заголовков (KISS: reduce parameters)
        llm_context = prompt_template.format(
            local_stat=local_stat,
            external_sources=external_sources,
            conversation_summary=conversation_summary,
            recent_messages=recent_messages,
            ecosystem_context=ecosystem_context,
            graph_context=graph_context,
            message=message_data.message,
        )

        try:
            # Прокси уже выполняет фильтрацию ответов, дополнительная очистка не нужна
            # Нормализация кодировки выполняется внутри call_llm
            response_content = await call_llm(llm_context, origin="chat_message")

            # Парсим источники из ответа LLM (до удаления раздела из текста)
            sources: List[Dict[str, str]] = parse_sources_from_response(response_content)

            # Удаляем раздел источников из текста, чтобы избежать дублирования
            response_content = remove_sources_section_from_content(response_content)
        except (LLMPermanentError, LLMTemporaryError) as e:
            # До сюда доходим только если LLM не смогла ответить даже после всех ретраев.
            # В логах оставляем детали, но в чат не отправляем никакого текста ошибки модели.
            print(f"Error in send_chat_message (LLM error): {str(e)}")
            return {
                "messageId": user_message_node.id,
                "sessionId": actual_session_id,
                "message": message_data.message,
                "conceptNodeId": message_data.conceptNodeId,
                "author": message_data.author,
                "timestamp": user_message_node.timestamp,
                "response": {
                    "messageId": None,
                    "message": "",
                    "conceptNodeId": None,
                },
            }

        # Add the AI response to the concept tree
        ai_response_node = service.add_concept(
            parent_id=user_message_node.id,
            content=response_content,
            role="assistant",
            node_type="message",
            session_id=actual_session_id,
        )

        # Parse AI response to paragraphs and save for FAISS search
        try:
            await paragraph_service.save_chat_message_paragraphs(
                message_content=response_content,
                session_id=actual_session_id,
                author="assistant",
                author_id=None,
                timestamp=ai_response_node.timestamp,
            )
        except Exception as e:
            # Log error but don't fail the request
            print(f"Error saving AI response paragraphs: {e}")

        # Analysis functions are available through UI buttons (not automatic)

        # Return both the user message and AI response
        return {
            "messageId": user_message_node.id,
            "sessionId": actual_session_id,
            "message": message_data.message,
            "conceptNodeId": message_data.conceptNodeId,
            "author": message_data.author,
            "timestamp": user_message_node.timestamp,
            "response": {
                "messageId": ai_response_node.id,
                "message": ai_response_node.content,
                "conceptNodeId": ai_response_node.id,
                "sources": sources,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in send_chat_message: {str(e)}")
        print(f"message_data type: {type(message_data)}, value: {message_data}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/session/{sessionId}/history", response_model=list[ConceptNode])
async def get_chat_history(sessionId: str, request: Request):
    """
    Get the history of messages in a chat session.

    Returns all messages in the session as a flat list.
    """
    try:
        service: KBService = request.app.state.kb_service
        # Get the session node
        session_node = service.get_node(sessionId)
        if not session_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound", "message": f"Session {sessionId} not found"},
            )

        # Get all messages in the session tree recursively
        messages = service._collect_tree_nodes(sessionId, depth=10, category=None, node_type=None, limit=1000, offset=0)

        # Filter to only message-type nodes - use getattr to safely access type attribute
        messages = [msg for msg in messages if getattr(msg, "type", None) == "message"]

        # Sort messages by timestamp to ensure chronological order
        messages.sort(key=lambda x: x.timestamp)

        return messages
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_chat_history: {str(e)}")
        print(f"sessionId: {sessionId}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("/concept-drag", response_model=dict)
async def drag_concept_to_chat(drag_data: ChatDragToChat, request: Request):
    """
    Handle dragging content to the chat (concepts, images, documents).

    Supports drag & drop of concept nodes, images, and text documents.
    """
    try:
        service: KBService = request.app.state.kb_service
        # Verify the session exists
        session_node = service.get_node(drag_data.sessionId)
        if not session_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound", "message": f"Session {drag_data.sessionId} not found"},
            )

        # Handle concept node drag (existing functionality)
        if drag_data.conceptNodeId:
            concept_node = service.get_node(drag_data.conceptNodeId)
            if not concept_node:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "ConceptNodeNotFound",
                        "message": f"Concept node {drag_data.conceptNodeId} not found",
                    },
                )

            # Add the concept node to the chat session as a message
            chat_message_node = service.add_concept(
                parent_id=drag_data.sessionId,
                content=f"Ссылка на концепцию: {concept_node.content}",
                role="system",
                node_type="concept_reference",
                session_id=drag_data.sessionId,
            )
            return {
                "status": "success",
                "message": "Концепция успешно добавлена в чат",
                "conceptNode": chat_message_node,
                "originalConcept": concept_node,
            }

        # Handle file drag & drop
        elif drag_data.file:
            file_data = drag_data.file
            file_name = file_data.get("name", "unknown")
            file_type = file_data.get("type", "")
            file_content = file_data.get("content", "")

            if not file_content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "InvalidFile", "message": "File content is empty"},
                )

            # Process based on file type
            if file_type.startswith("image/"):
                # Handle image files
                message_content = f"Изображение загружено: {file_name}\n[Изображение: {file_content[:50]}...]"
                node_type = "image_attachment"

            elif file_type.startswith("text/") or file_type in [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ]:
                # Handle text documents
                # For text files, content should be the actual text
                # For binary documents (PDF, DOC), we might need additional processing
                message_content = f"Документ загружен: {file_name}\n\nСодержимое:\n{file_content}"
                node_type = "document_attachment"

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "UnsupportedFileType", "message": f"Unsupported file type: {file_type}"},
                )

            # Add file to chat as a message
            file_message_node = service.add_concept(
                parent_id=drag_data.sessionId,
                content=message_content,
                role="user",  # User uploaded this
                node_type=node_type,
                session_id=drag_data.sessionId,
            )

            return {
                "status": "success",
                "message": f"Файл '{file_name}' успешно добавлен в чат",
                "fileNode": file_message_node,
                "fileType": file_type,
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "InvalidRequest", "message": "Either conceptNodeId or file must be provided"},
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in drag_concept_to_chat: {str(e)}")
        print(f"drag_data type: {type(drag_data)}, value: {drag_data}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/session/current", response_model=ChatSession)
async def get_current_chat_session(request: Request, response: Response):
    """
    Get the current chat session for the user.

    Creates a new session if none exists.
    """
    try:
        # Try to get session_id from cookies
        session_id = request.cookies.get("session_id")

        if session_id:
            # Get user session (async)
            user_session = await session_manager.get_session(session_id)
            if user_session and user_session.get("chat_session_id"):
                # Get chat session
                chat_session = chat_session_service.get_session(user_session["chat_session_id"])
                if chat_session:
                    return chat_session

        # No valid session, create new ones
        # Create user session (async)
        user_session_id = await session_manager.create_session(
            {
                "user_id": "anonymous",
                "created_at": "auto",
                "message_count": 0,
                "last_activity": int(time.time()),
            }
        )

        # Create chat session
        chat_session_data = ChatSessionCreate(topic="New Chat Session", conceptTreeId=None, ecosystem=None)
        chat_session = chat_session_service.create_session(chat_session_data)

        # Link them (async)
        user_session = await session_manager.get_session(user_session_id)
        if user_session:
            user_session["chat_session_id"] = chat_session.id
            await session_manager.update_session(user_session_id, user_session)

        # Set cookie
        response.set_cookie("session_id", user_session_id, httponly=True, max_age=2592000)  # 30 days

        return chat_session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/session/{sessionId}", response_model=ChatSession)
async def get_chat_session(sessionId: str):
    """
    Get a chat session by ID.

    Returns the chat session.
    """
    try:
        session = chat_session_service.get_session(sessionId)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound", "message": f"Session {sessionId} not found"},
            )

        return session
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_chat_session: {str(e)}")
        print(f"sessionId: {sessionId}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/sessions", response_model=list[ChatSession])
async def get_all_chat_sessions():
    """
    Get all chat sessions.

    Returns all chat sessions.
    """
    try:
        # Get all chat sessions
        sessions = chat_session_service.get_all_sessions()
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/starters", response_model=list[str])
async def get_conversation_starters():
    """
    Get conversation starters for the symbiosis project.

    Generates 3 engaging conversation starters using LLM.
    """
    try:
        starters = await generate_starters()
        return starters
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("/localize")
async def localize_ecosystem(request: LocalizeRequest):
    """
    Localize ecosystem for a chat session based on user location.

    Takes user coordinates and conversation text, determines the local ecosystem
    and updates the session context for better localization.
    """
    try:
        # Обратное геокодирование для получения адреса
        location_info = await reverse_geocode_location(request.latitude, request.longitude)

        # Извлекаем экосистему и локацию из текста диалога
        ecosystem_data = await extract_ecosystem_and_location(request.conversationText)

        # Обновляем данные экосистемы с реальной локацией пользователя
        if location_info:
            ecosystem_data["location"] = location_info.get("display_name", f"{request.latitude}, {request.longitude}")
            ecosystem_data["coordinates"] = {"latitude": request.latitude, "longitude": request.longitude}

        # Получаем сессию чата
        chat_session = chat_session_service.get_session(request.sessionId)
        if not chat_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "SessionNotFound", "message": "Chat session not found"},
            )

        # Определяем источник локализации
        source_type = "user_provided"
        if getattr(request, "action", None) == "expand_context":
            source_type = "context_expansion"
        elif getattr(request, "action", None) == "new_branch":
            source_type = "branch_creation"

        # Сохраняем информацию о локации в сессии (перезаписываем существующую)
        updated_location_data = {
            **ecosystem_data,
            "source": source_type,
            "timestamp": int(time.time() * 1000),  # Время обновления
            "action": getattr(request, "action", "localize"),
        }
        chat_session_service.update_session_location(request.sessionId, updated_location_data)

        # Логируем обновление локализации
        logger.info(f"Обновлена локализация сессии {request.sessionId}: {updated_location_data}")

        # Формируем описание локализованной экосистемы
        location_name = location_info.get("display_name", "Неизвестная локация") if location_info else "Координаты"
        ecosystem_names = [e.get("name", "") for e in ecosystem_data.get("ecosystems", [])]
        ecosystem_str = ", ".join(ecosystem_names) if ecosystem_names else "общая экосистема"

        description = f"Экосистема диалога локализована в {location_name}. "
        if ecosystem_names:
            description += f"Обнаружены экосистемы: {ecosystem_str}. "
        description += "Контекст поиска теперь учитывает локальные условия."

        return {
            "success": True,
            "location": location_info,
            "ecosystems": ecosystem_data.get("ecosystems", []),
            "description": description,
        }

    except Exception as e:
        log(f"Error localizing ecosystem: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.get("/symbionts/search")
async def search_symbionts(q: str = "", type: Optional[str] = None, category: Optional[str] = None, limit: int = 10):
    """
    Search for symbionts and pathogens in the knowledge base.

    Args:
        q: Search query
        type: Filter by type (symbiont, pathogen, commensal, parasite)
        category: Filter by category (bacteria, virus, fungus, etc.)
        limit: Maximum number of results

    Returns:
        List of matching symbionts/pathogens
    """
    try:
        # Получаем доступ к хранилищу Weaviate через глобальные сервисы
        # В реальном приложении это должно быть внедрено через dependency injection
        from api.storage.weaviate_storage import WeaviateStorage
        from api.storage.symbiont_service import SymbiontService

        weaviate_storage = WeaviateStorage()
        symbiont_service = SymbiontService(weaviate_storage)

        # Выполняем поиск
        symbionts = await symbiont_service.search_symbionts(
            query=q, type_filter=type, category_filter=category, limit=limit
        )

        # Преобразуем в JSON-совместимый формат
        results = []
        for symbiont in symbionts:
            results.append(
                {
                    "id": symbiont.id,
                    "name": symbiont.name,
                    "scientific_name": symbiont.scientific_name,
                    "type": symbiont.type,
                    "category": symbiont.category,
                    "interaction_type": symbiont.interaction_type,
                    "biochemical_role": symbiont.biochemical_role,
                    "risk_level": symbiont.risk_level,
                    "prevalence": symbiont.prevalence,
                    "detection_confidence": symbiont.detection_confidence,
                }
            )

        return {"success": True, "query": q, "total": len(results), "symbionts": results}

    except Exception as e:
        log(f"Error searching symbionts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("/search/web")
async def search_web(query: str = Body(...)):
    """
    Perform web search for the given query.

    Args:
        query: Search query

    Returns:
        Search results
    """
    try:
        results = await web_search_service.search_and_extract(query, max_results=3)

        if not results:
            return {"results": "Не найдено результатов поиска"}

        formatted_results = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "Без названия")
            content = result.get("content", "")[:500]
            url = result.get("url", "")

            formatted_results.append(f"{i}. {title}")
            if url:
                formatted_results.append(f"   Источник: {url}")
            formatted_results.append(f"   {content}")
            formatted_results.append("")

        return {"results": "\n".join(formatted_results)}

    except Exception as e:
        log(f"Error performing web search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


@router.post("/search/books")
async def search_books(query: str = Body(...), session_id: Optional[str] = None):
    """
    Search for books related to the query and index them for the session.

    Args:
        query: Search query
        session_id: Optional chat session ID for book indexing

    Returns:
        Book search results with indexing information
    """
    try:
        # Perform book search and indexing
        context = await search_books_for_message(query, web_search_service, session_id)

        return {
            "query": query,
            "session_id": session_id,
            "books_context": context,
            "indexed": session_id is not None,
            "timestamp": int(time.time() * 1000),
        }

    except Exception as e:
        log(f"Error performing book search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "InternalError", "message": str(e)},
        )


async def search_books_for_message(message: str, web_search_service, session_id: Optional[str] = None) -> str:
    """
    Search for books related to the message content and index them for the session.

    Args:
        message: User message to search books for
        web_search_service: Web search service instance
        session_id: Chat session ID for book indexing

    Returns:
        Formatted context string with book information
    """
    try:
        # Create book-focused search query
        book_query = f"books about {message}"

        # Use the web search service to find book information
        results = await web_search_service.search_and_extract(book_query, max_results=5)

        if not results:
            return ""

        context_parts = []
        context_parts.append("### Из книг:")

        indexed_books = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "Без названия")
            content = result.get("content", "")[:1000]  # Longer excerpts for books
            url = result.get("url", "")

            # Create book index entry
            book_entry = {
                "id": f"book_{session_id}_{i}_{int(time.time())}",
                "title": title,
                "content": content,
                "url": url,
                "indexed_at": int(time.time() * 1000),
                "session_id": session_id,
                "search_query": message,
            }
            indexed_books.append(book_entry)

            # Format as book reference
            context_parts.append(f"📚 {title}")
            if url:
                context_parts.append(f"   Источник: {url}")
            context_parts.append(f"   {content}")
            context_parts.append("")

        # TODO: Save indexed_books to database for future searches within session
        # This will allow searching within already indexed books
        if session_id and indexed_books:
            try:
                # Save to session context for now (temporary solution)
                # In future: create proper books table and indexing
                chat_session = chat_session_service.get_session(session_id)
                if chat_session:
                    current_books = chat_session.indexed_books or []
                    current_books.extend(indexed_books)
                    # Keep only last 50 books per session to avoid memory issues
                    if len(current_books) > 50:
                        current_books = current_books[-50:]
                    chat_session_service.update_session_books(session_id, current_books)
            except Exception as e:
                log(f"Error saving indexed books: {e}")

        return "\n".join(context_parts)

    except Exception as e:
        log(f"Error searching books: {e}")
        return ""


# Removed automatic analysis - now handled through UI buttons
