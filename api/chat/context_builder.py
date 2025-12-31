"""Модуль для построения контекста для LLM с умным сжатием истории."""

import logging
from typing import List, Dict, Tuple, Optional, Any
from api.kb.service import KBService
from api.detect.localize import extract_location_and_time
from api.detect.weather import get_weather, format_weather_for_context
from api.detect.ecosystem_scaler import detect_ecosystems

logger = logging.getLogger(__name__)


def format_conversation_history(messages: List[Dict], limit: int = 20) -> str:
    """
    Форматирует последние N сообщений для промпта.

    Args:
        messages: Список сообщений
        limit: Максимальное количество сообщений для форматирования

    Returns:
        Отформатированная строка с последними сообщениями
    """
    if not messages:
        return ""

    # Берем последние limit сообщений
    recent_messages = messages[-limit:] if len(messages) > limit else messages

    formatted_messages = []
    for msg in recent_messages:
        sender = msg.get("sender", "user")
        # Нормализуем роль: "assistant" -> "Assistant", "user" -> "User"
        if sender.lower() == "assistant":
            sender_label = "Assistant"
        elif sender.lower() == "user":
            sender_label = "User"
        else:
            sender_label = sender.capitalize()
        content = msg.get("content", "")
        formatted_messages.append(f"{sender_label}: {content}")

    return "\n".join(formatted_messages)


async def build_graph_context(
    message: str,
    session_id: str,
    db_manager,
    storage=None,  # Может быть FAISSStorage или WeaviateStorage
    max_depth: int = 2,
    max_relationships: int = 10,
) -> str:
    """Строит графовый контекст через симбиотические связи.

    Args:
        message: Текст сообщения пользователя
        session_id: ID сессии
        db_manager: Менеджер базы данных
        storage: Storage для поиска параграфов (FAISSStorage или WeaviateStorage, опционально)
        max_depth: Максимальная глубина обхода графа
        max_relationships: Максимальное количество связей

    Returns:
        Отформатированный графовый контекст или пустая строка
    """
    try:
        from api.kb.simbiotic_graph import SimbioticGraphContextBuilder
        from api.storage.symbiotic_service import SymbioticService
        from api.storage.organism_service import OrganismService
        from api.storage.ecosystem_service import EcosystemService

        # Создаем сервисы
        symbiotic_service = SymbioticService(db_manager)
        organism_service = OrganismService(db_manager)
        ecosystem_service = EcosystemService(db_manager)

        # Создаем строитель контекста
        graph_builder = SimbioticGraphContextBuilder(
            symbiotic_service=symbiotic_service,
            organism_service=organism_service,
            ecosystem_service=ecosystem_service,
        )

        # Если есть storage (FAISS или Weaviate), ищем релевантные параграфы
        if storage:
            try:
                # Ищем похожие параграфы (работает для обоих типов storage)
                similar_paragraphs = await storage.search_similar_paragraphs(
                    query=message, document_id=session_id, top_k=5
                )

                if similar_paragraphs:
                    # Строим графовый контекст на основе найденных параграфов
                    graph_context = await graph_builder.build_graph_augmented_context(
                        paragraphs=similar_paragraphs,
                        max_depth=max_depth,
                        max_relationships=max_relationships,
                    )
                    return graph_context
            except Exception as e:
                logger.debug(f"⚠️ Ошибка при поиске параграфов для графового контекста: {e}")

        return ""
    except ImportError:
        logger.debug("⚠️ Модули для графового контекста недоступны")
        return ""
    except Exception as e:
        logger.debug(f"⚠️ Ошибка при построении графового контекста: {e}")
        return ""


async def build_context_for_llm(
    session_id: str,
    kb_service: KBService,
    location: Optional[str] = None,
    ecosystems: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[str], str]:
    """
    Главная функция - строит контекст для LLM с умным сжатием и фильтрацией по локации/экосистеме.

    ВАЖНО: Фильтрация по локации/экосистеме используется только для дополнительного контекста.
    Вся история диалога ВСЕГДА включается, чтобы сохранить контекст разговора.

    Args:
        session_id: ID сессии для получения истории
        kb_service: Сервис для работы с базой знаний
        location: Локация для фильтрации контекста (опционально, используется только для дополнительного контекста)
        ecosystems: Список экосистем для фильтрации контекста (опционально, используется только для дополнительного контекста)

    Returns:
        Кортеж из (conversation_summary, recent_messages)
        - conversation_summary: Всегда None (больше не генерируется)
        - recent_messages: Последние 50 сообщений в формате строки
    """
    # Получаем все сообщения сессии
    all_messages = kb_service.get_session_messages(session_id)

    if not all_messages:
        logger.debug(f"Нет сообщений в сессии {session_id}")
        return None, ""

    logger.info(f"Получено {len(all_messages)} сообщений из сессии {session_id}")

    # КРИТИЧНО: НЕ фильтруем историю по локации/экосистеме!
    # Фильтрация исключает важный контекст диалога (например, общие вопросы о симбиозе).
    # Локация/экосистема используется только для дополнительного контекста (погода, экосистема),
    # но вся история диалога должна быть доступна LLM для понимания контекста.
    # if location or ecosystems:
    #     all_messages = filter_messages_by_location_and_ecosystem(all_messages, location, ecosystems)
    #     logger.info(
    #         f"Отфильтровано сообщений по локации/экосистеме: location={location}, "
    #         f"ecosystems={[e.get('name') for e in (ecosystems or [])]}"
    #     )

    if not all_messages:
        return None, ""

    # Берем последние 50 сообщений вместо генерации сводки через LLM
    # Это проще, быстрее и не требует дополнительных вызовов LLM
    max_recent = 50
    recent_messages_list = all_messages[-max_recent:] if len(all_messages) > max_recent else all_messages
    recent_messages = format_conversation_history(recent_messages_list, max_recent)
    logger.debug(f"Включено {len(recent_messages_list)} сообщений в recent_messages")

    # Сводка больше не генерируется - используем только recent_messages
    return None, recent_messages


def should_include_context(conversation_summary: Optional[str], recent_messages: str) -> Tuple[bool, bool]:
    """
    Определяет, нужно ли включать секции контекста в промпт.

    Args:
        conversation_summary: Сводка старых сообщений
        recent_messages: Последние сообщения

    Returns:
        Кортеж из (включать_сводку, включать_последние_сообщения)
    """
    include_summary = conversation_summary is not None and bool(conversation_summary.strip())
    include_recent = bool(recent_messages.strip())

    return include_summary, include_recent


async def get_weather_context(message: str) -> str:
    """
    Получает информацию о погоде для включения в контекст, если в сообщении указаны город и время.

    Автоматически извлекает локацию из сообщения и запрашивает текущую погоду, если:
    - В сообщении указан город
    - Время не указано или относится к текущему моменту

    Args:
        message: Текст сообщения пользователя

    Returns:
        Отформатированная строка с информацией о погоде или пустая строка
    """
    try:
        # Извлекаем локализацию и время из сообщения
        location_data = extract_location_and_time(message)
        city = location_data.get("location") if location_data else None
        time_reference = location_data.get("time_reference") if location_data else None

        # Если нет города, не запрашиваем погоду
        if not city:
            logger.debug("Локация не найдена в сообщении, погода не запрашивается")
            return ""

        logger.info(f"Найдена локация: {city}, время: {time_reference or 'не указано (текущая погода)'}")

        # Получаем погоду
        weather_data = await get_weather(city, time_reference)
        if weather_data:
            formatted = format_weather_for_context(weather_data)
            logger.info(f"Погода добавлена в контекст для {city}: {weather_data.get('temperature', 'N/A')}°C")
            return formatted
        else:
            logger.debug(f"Погода не получена для {city} (возможно, время относится к прошлому/будущему)")

        return ""
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при получении погоды для контекста: {e}")
        return ""


async def extract_ecosystem_and_location(message: str) -> Dict[str, Any]:
    """
    Извлекает экосистему и локацию из сообщения для ограничения контекста.

    Args:
        message: Текст сообщения пользователя

    Returns:
        Словарь с полями:
        - location: локация (город, регион и т.д.) или None
        - ecosystems: список экосистем или пустой список
        - time_reference: временная ссылка или None
    """
    try:
        # Извлекаем локализацию и время
        location_data = extract_location_and_time(message)
        location = location_data.get("location") if location_data else None
        time_reference = location_data.get("time_reference") if location_data else None

        # Извлекаем экосистемы из сообщения
        ecosystems = await detect_ecosystems(message, location_data=location_data)

        result = {
            "location": location,
            "ecosystems": ecosystems,
            "time_reference": time_reference,
        }

        if location or ecosystems:
            logger.info(
                f"Извлечена экосистема/локация: location={location}, "
                f"ecosystems={[e.get('name') for e in ecosystems]}, time={time_reference}"
            )

        return result
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при извлечении экосистемы/локации: {e}")
        return {"location": None, "ecosystems": [], "time_reference": None}


def filter_messages_by_location_and_ecosystem(
    messages: List[Dict],
    target_location: Optional[str] = None,
    target_ecosystems: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict]:
    """
    Фильтрует сообщения по локации и экосистеме.

    Если указана локация или экосистема, возвращает только сообщения,
    которые упоминают эту локацию/экосистему или не содержат локации/экосистемы.

    Args:
        messages: Список сообщений для фильтрации
        target_location: Целевая локация для фильтрации (None = не фильтровать)
        target_ecosystems: Список целевых экосистем для фильтрации (None = не фильтровать)

    Returns:
        Отфильтрованный список сообщений
    """
    if not target_location and not target_ecosystems:
        # Если нет фильтров, возвращаем все сообщения
        return messages

    filtered = []
    target_ecosystem_names = (
        [e.get("name", "").lower() for e in target_ecosystems if e.get("name")] if target_ecosystems else []
    )

    for msg in messages:
        content = msg.get("content", "").lower()
        should_include = True

        # Проверяем локацию
        if target_location:
            location_lower = target_location.lower()
            # Включаем сообщение, если оно упоминает локацию или не содержит локации
            if location_lower not in content:
                # Проверяем, есть ли в сообщении другая локация
                # Если есть другая локация, исключаем сообщение
                location_indicators = ["в ", "на ", "около ", "возле ", "рядом с "]
                has_location = any(indicator in content for indicator in location_indicators)
                if has_location:
                    should_include = False

        # Проверяем экосистемы
        if should_include and target_ecosystem_names:
            # Включаем сообщение, если оно упоминает целевую экосистему
            # или не содержит упоминаний экосистем
            mentions_target_ecosystem = any(name in content for name in target_ecosystem_names)
            if not mentions_target_ecosystem:
                # Проверяем, есть ли в сообщении упоминания других экосистем
                ecosystem_keywords = [
                    "экосистема",
                    "лес",
                    "озеро",
                    "река",
                    "поле",
                    "луг",
                    "болото",
                    "степь",
                    "тундра",
                ]
                has_ecosystem_mention = any(keyword in content for keyword in ecosystem_keywords)
                if has_ecosystem_mention:
                    should_include = False

        if should_include:
            filtered.append(msg)

    return filtered


def format_ecosystem_context(
    ecosystems: List[Dict[str, Any]], location: Optional[str] = None, weather: Optional[str] = None
) -> str:
    """
    Форматирует информацию о локальной экосистеме для включения в контекст промпта.
    Объединяет информацию о локации, экосистемах и погоде в единый контекст.

    Args:
        ecosystems: Список экосистем
        location: Локация (если указана)
        weather: Информация о погоде (если указана)

    Returns:
        Отформатированная строка с информацией о локальной экосистеме
    """
    parts = []

    # Локация
    if location:
        parts.append(f"Локация: {location}")

    # Погода (часть локальной экосистемы)
    if weather:
        parts.append(f"Погода:\n{weather}")

    # Экосистемы
    if ecosystems:
        eco_info = []
        for eco in ecosystems:
            name = eco.get("name", "")
            description = eco.get("description", "")
            scale = eco.get("scale", "")
            eco_str = f"- {name}"
            if description:
                eco_str += f" ({description})"
            if scale:
                eco_str += f" [масштаб: {scale}]"
            eco_info.append(eco_str)

        if eco_info:
            parts.append("Экосистемы:\n" + "\n".join(eco_info))

    # Если нет никакой информации, возвращаем пустую строку
    if not parts:
        return ""

    return "\n".join(parts)
