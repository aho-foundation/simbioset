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

    Использует несколько источников с fallback:
    1. OpenWeatherMap (если есть API ключ)
    2. WeatherAPI.com (если есть API ключ)
    3. Gismeteo парсинг (fallback)

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
    except Exception:
        # Молча игнорируем ошибки - погода не критична
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
    ecosystems: List[Dict[str, Any]],
    location: Optional[str] = None,
    weather: Optional[str] = None,
    symbionts: Optional[List] = None,
) -> str:
    """
    Форматирует информацию о локальной экосистеме для включения в контекст промпта.

    Использует структурированный формат, адаптированный для Weaviate-style метрик:
    - Четкие категории и метки
    - Структурированная информация
    - Типы данных и статусы
    - Машиночитаемый формат

    Args:
        ecosystems: Список экосистем с метаданными
        location: Географическая локация
        weather: Метеорологические данные
        symbionts: Список симбионтов/патогенов (опционально)

    Returns:
        Структурированная строка контекста экосистемы
    """
    context_parts = []

    # === ГЕОГРАФИЧЕСКИЙ КОНТЕКСТ ===
    if location:
        context_parts.append("=== GEOSPATIAL CONTEXT ===")
        context_parts.append(f"📍 Location: {location}")
        context_parts.append("📊 Status: active | Type: geographic")
        context_parts.append("")

    # === МЕТЕОРОЛОГИЧЕСКИЕ МЕТРИКИ ===
    if weather:
        context_parts.append("=== WEATHER METRICS ===")
        # Разбираем погоду на структурированные метрики
        weather_lines = weather.strip().split("\n")
        for line in weather_lines:
            if ":" in line:
                key, value = line.split(":", 1)
                context_parts.append(f"🌡️ {key.strip()}: {value.strip()}")
            else:
                context_parts.append(f"🌤️ {line}")
        context_parts.append("📊 Status: current | Type: meteorological")
        context_parts.append("")

    # === ЭКОСИСТЕМНЫЕ СУЩНОСТИ ===
    if ecosystems:
        context_parts.append("=== ECOSYSTEM ENTITIES ===")

        for i, eco in enumerate(ecosystems, 1):
            name = eco.get("name", "unknown")
            scale = eco.get("scale", "unspecified")
            description = eco.get("description", "")
            confidence = eco.get("confidence", 0.0)

            # Форматируем как Weaviate-style метрику
            context_parts.append(f"🌿 Entity_{i}: {name}")
            context_parts.append(f"   ├── Scale: {scale} | Type: ecosystem")
            context_parts.append(f"   ├── Status: active | Confidence: {confidence:.2f}")

            if description:
                # Разбиваем длинное описание на строки
                desc_lines = [description[i : i + 60] for i in range(0, len(description), 60)]
                for j, desc_line in enumerate(desc_lines):
                    prefix = "   ├── Description:" if j == 0 else "   │   "
                    context_parts.append(f"{prefix} {desc_line}")

            # Добавляем метаданные если есть
            metadata = []
            if eco.get("location"):
                metadata.append(f"location={eco['location']}")
            if eco.get("biome"):
                metadata.append(f"biome={eco['biome']}")
            if eco.get("threat_level"):
                metadata.append(f"threat_level={eco['threat_level']}")

            if metadata:
                context_parts.append(f"   └── Metadata: {', '.join(metadata)}")
            else:
                context_parts.append("   └── Metadata: none")
            context_parts.append("")  # Пустая строка между сущностями

        # === МИКРОБНЫЕ СУЩНОСТИ ===
        if symbionts:
            context_parts.append("=== MICROBIAL ENTITIES ===")

            for i, symbiont in enumerate(symbionts, 1):
                # Основная информация
                context_parts.append(f"🦠 Entity_{i}: {symbiont.name}")
                context_parts.append(f"   ├── Type: {symbiont.type} | Category: {symbiont.category or 'unspecified'}")
                context_parts.append(f"   ├── Status: active | Confidence: {symbiont.detection_confidence:.2f}")

                # Научное название
                if symbiont.scientific_name:
                    context_parts.append(f"   ├── Scientific Name: {symbiont.scientific_name}")

                # Биохимическая роль
                if symbiont.biochemical_role:
                    # Разбиваем длинный текст на строки
                    role_lines = [
                        symbiont.biochemical_role[i : i + 60] for i in range(0, len(symbiont.biochemical_role), 60)
                    ]
                    for j, role_line in enumerate(role_lines):
                        prefix = "   ├── Biochemical Role:" if j == 0 else "   │   "
                        context_parts.append(f"{prefix} {role_line}")

                # Уровень риска с визуальными индикаторами
                risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "💀"}.get(
                    symbiont.risk_level or "low", "❓"
                )

                context_parts.append(f"   ├── Risk Level: {symbiont.risk_level or 'low'} {risk_emoji}")

                # Дополнительные метрики
                metrics = []
                if symbiont.prevalence and symbiont.prevalence > 0:
                    metrics.append(f"prevalence={symbiont.prevalence:.2f}")
                if symbiont.virulence_factors:
                    metrics.append(f"virulence_factors={len(symbiont.virulence_factors)}")
                if symbiont.geographic_distribution:
                    metrics.append(f"distribution={symbiont.geographic_distribution}")

                if metrics:
                    context_parts.append(f"   └── Metrics: {', '.join(metrics)}")
                else:
                    context_parts.append("   └── Metrics: none")
                context_parts.append("")  # Пустая строка между сущностями

        # Сводная статистика
        context_parts.append("=== ECOSYSTEM SUMMARY ===")
        context_parts.append(f"📊 Ecosystem Entities: {len(ecosystems)}")
        if symbionts:
            context_parts.append(f"📊 Microbial Entities: {len(symbionts)}")
            context_parts.append(f"📊 Total Biological Entities: {len(ecosystems) + len(symbionts)}")

        scales = [eco.get("scale", "unspecified") for eco in ecosystems]
        scale_counts: dict[str, int] = {}
        for scale in scales:
            scale_counts[scale] = scale_counts.get(scale, 0) + 1
        scale_summary = ", ".join([f"{scale}: {count}" for scale, count in scale_counts.items()])
        context_parts.append(f"📊 Ecosystem Scales: {scale_summary}")

        if symbionts:
            # Распределение типов симбионтов
            sym_types = [s.type or "unknown" for s in symbionts]
            type_counts: dict[str, int] = {}
            for sym_type in sym_types:
                type_counts[sym_type] = type_counts.get(sym_type, 0) + 1
            type_summary = ", ".join([f"{t}: {c}" for t, c in type_counts.items()])
            context_parts.append(f"📊 Microbial Types: {type_summary}")

        context_parts.append("📊 Status: active | Type: ecological")

    # === СИСТЕМНЫЕ МЕТРИКИ ===
    if context_parts:
        context_parts.append("=== SYSTEM METRICS ===")
        context_parts.append("⏱️ Timestamp: real-time")
        context_parts.append("🔄 Update Frequency: per_message")
        context_parts.append("📈 Data Source: user_location + ai_detection")
        context_parts.append("🎯 Confidence Threshold: 0.5")

    # Если контекст пустой, возвращаем специальное сообщение
    if not context_parts:
        return "=== ECOSYSTEM CONTEXT ===\n📊 Status: inactive | Message: No ecosystem data available"

    return "\n".join(context_parts)


# DEPRECATED: get_symbionts_context больше не используется.
# Симбионты теперь включаются в format_ecosystem_context для объединения биологического контекста.
