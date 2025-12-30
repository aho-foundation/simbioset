"""FastAPI routes for Chat API."""

import time
from datetime import datetime
from typing import List, Dict

from fastapi import APIRouter, HTTPException, Request, Response, status

from api.detect.web_search import web_search_service
from api.chat.models import ChatSession, ChatSessionCreate, ChatMessageCreate, ChatDragToChat
from api.chat.service import chat_session_service, generate_starters
from api.kb.models import ConceptNode
from api.kb.service import KBService
from api.storage.paragraph_service import ParagraphService
from api.llm import LLMPermanentError, LLMTemporaryError, call_llm_with_retry
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

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Services will be injected from app.state in route handlers

# Фильтрация LLM ответов выполняется в прокси (llm_proxy)
# Функция clean_llm_response удалена для соблюдения принципа DRY


def parse_sources_from_response(response_content: str) -> List[Dict[str, str]]:
    """Парсит источники из ответа LLM."""
    """
    Парсит источники из ответа LLM.

    Ищет раздел "## Источники" и извлекает пронумерованный список.

    Args:
        response_content: Полный текст ответа LLM

    Returns:
        Список словарей с источниками [{'title': 'Название источника', 'type': 'Тип источника'}]
    """
    sources: List[Dict[str, str]] = []

    # Ищем раздел источников
    sources_match = re.search(r'##\s*Источники?\s*\n(.*?)(?=\n##|\n###|\Z)', response_content, re.DOTALL | re.IGNORECASE)

    if not sources_match:
        return sources

    sources_text = sources_match.group(1).strip()

    # Парсим пронумерованный список источников
    # Формат: 1. Название источника (Тип)
    # Или: 1. Название источника
    lines = sources_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Убираем нумерацию в начале строки (1., 2., etc.)
        line = re.sub(r'^\d+\.\s*', '', line)

        # Разделяем название и тип (если есть в скобках)
        type_match = re.search(r'\(([^)]+)\)$', line)
        if type_match:
            title = line[:type_match.start()].strip()
            source_type = type_match.group(1).strip()
        else:
            title = line
            source_type = "Неизвестный тип"

        if title:  # Только если есть название
            sources.append({
                'title': title,
                'type': source_type
            })

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
        local_stat = message_data.context.get("local_stat", "") if message_data.context else ""
        artifacts_context = message_data.context.get("artifacts_context", "") if message_data.context else ""
        chats_context = message_data.context.get("chats_context", "") if message_data.context else ""
        books_context = message_data.context.get("books_context", "") if message_data.context else ""

        # Perform web search if the message is about symbiosis or related topics
        if needs_web_search:
            websearch_context = await web_search_service.get_symbiosis_context(message_data.message)
        else:
            websearch_context = message_data.context.get("websearch_context", "") if message_data.context else ""

        # Check if the message contains user observation data that should be saved
        user_message_lower = message_data.message.lower()
        observation_indicators = [
            "локация",
            "место",
            "район",
            "город",
            "деревня",
            "лес",
            "река",
            "озеро",
            "наблюдение",
            "увидел",
            "заметил",
            "наблюдение",
            "экосистема",
            "взаимодействие",
            "сезон",
            "погода",
            "температура",
            "влажность",
            "ветер",
            "облачность",
            "местность",
            "ландшафт",
            "природа",
        ]

        # Save user observation if it contains relevant data
        if any(indicator in user_message_lower for indicator in observation_indicators):
            # Extract potential observation details from the message
            # This is a basic extraction - in a real implementation, you might want more sophisticated NLP
            from api.kb.user_metrics import user_metrics_service

            if user_metrics_service:
                user_metrics_service.save_user_observation(
                    user_id=message_data.author,
                    location=None,  # Would require more sophisticated extraction
                    ecosystem_type=None,  # Would require more sophisticated extraction
                    observations=message_data.message,
                    interactions=None,  # Would require more sophisticated extraction
                    season=None,  # Would require more sophisticated extraction
                    weather=None,  # Would require more sophisticated extraction
                    additional_notes=f"Extracted from chat message in session {actual_session_id}",
                )

        # Build context for LLM with smart compression
        from api.llm import get_llm_client_wrapper

        # Извлекаем экосистему и локацию из сообщения для фильтрации контекста
        ecosystem_data = await extract_ecosystem_and_location(message_data.message)
        location = ecosystem_data.get("location")
        ecosystems = ecosystem_data.get("ecosystems", [])

        llm_client = get_llm_client_wrapper()
        conversation_summary, recent_messages = await build_context_for_llm(
            actual_session_id, service, llm_client, location=location, ecosystems=ecosystems
        )

        # Determine which context sections to include
        include_summary, include_recent = should_include_context(conversation_summary, recent_messages)

        # Получаем информацию о погоде, если в сообщении указаны город и время
        weather_context = await get_weather_context(message_data.message)

        # Форматируем контекст локальной экосистемы (объединяем погоду и экосистему)
        ecosystem_context = format_ecosystem_context(ecosystems, location, weather=weather_context)

        # Получаем графовый контекст через симбиотические связи
        graph_context = ""
        try:
            from api.chat.context_builder import build_graph_context

            # Используем универсальное хранилище (может быть FAISS или Weaviate)
            storage = getattr(request.app.state, "storage", None) or getattr(request.app.state, "faiss_storage", None)
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

        # Format the prompt with context and message
        llm_context = prompt_template.format(
            local_stat=local_stat,
            artifacts_context=artifacts_context,
            chats_context=chats_context,
            books_context=books_context,
            websearch_context=websearch_context,
            conversation_summary=f"[CONVERSATION CONTEXT]\n{conversation_summary}\n" if include_summary else "",
            recent_messages=f"[RECENT MESSAGES]\n{recent_messages}\n" if include_recent else "",
            ecosystem_context=f"[LOCAL ECOSYSTEM]\n{ecosystem_context}\n" if ecosystem_context else "",
            graph_context=f"[SYMBIOTIC RELATIONSHIPS]\n{graph_context}\n" if graph_context else "",
            message=message_data.message,
        )

        try:
            # Прокси уже выполняет фильтрацию ответов, дополнительная очистка не нужна
            response_content = await call_llm_with_retry(llm_context, origin="chat_message")

            # Парсим источники из ответа LLM
            sources: List[Dict[str, str]] = parse_sources_from_response(response_content)
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
    Handle dragging a concept node to the chat.

    Adds the concept node to the chat session as a message.
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

        # Get the concept node being dragged
        concept_node = service.get_node(drag_data.conceptNodeId)
        if not concept_node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "ConceptNodeNotFound", "message": f"Concept node {drag_data.conceptNodeId} not found"},
            )

        # Add the concept node to the chat session as a message
        # We'll create a new node that references the original concept
        chat_message_node = service.add_concept(
            parent_id=drag_data.sessionId,
            content=f"Ссылка на концепцию: {concept_node.content}",
            role="system",  # Mark as system since it's a reference
            node_type="concept_reference",
            session_id=drag_data.sessionId,
        )
        return {
            "status": "success",
            "message": "Концепция успешно добавлена в чат",
            "conceptNode": chat_message_node,
            "originalConcept": concept_node,
        }
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
        chat_session_data = ChatSessionCreate(topic="New Chat Session", conceptTreeId=None)
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
