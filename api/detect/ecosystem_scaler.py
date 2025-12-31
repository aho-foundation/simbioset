"""
Детектор экосистем в тексте.

Экосистема = большой организм (метаболизм, гомеостаз, симбиотические связи).
Экосистемы могут быть вложенными (экосистема внутри экосистемы).

Использует данные детекта локализации для более точного определения экосистем.
"""

from typing import List, Optional, Dict, Any

from api.detect.entity_extractor import extract_structured_data
from api.detect.localize import extract_location_and_time


# Валидатор для экосистем
def _validate_ecosystem(item: Dict[str, Any]) -> bool:
    """Проверяет, что объект является валидной экосистемой."""
    return isinstance(item, dict) and "name" in item


# Нормализатор для экосистем
def _normalize_ecosystem(
    item: Dict[str, Any], location: Optional[str] = None, time_reference: Optional[str] = None
) -> Dict[str, Any]:
    """Нормализует данные экосистемы."""
    return {
        "name": item.get("name", ""),
        "description": item.get("description"),
        "location": item.get("location") or location,  # Используем локализацию из детекта, если не указана в ответе LLM
        "scale": item.get("scale", "habitat"),  # По умолчанию habitat (лес, озеро)
        "parent_ecosystem": item.get("parent_ecosystem"),
        "context": item.get("context", ""),
        "time_reference": time_reference,  # Добавляем временную ссылку
    }


async def detect_ecosystems(text: str, location_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Обнаруживает экосистемы в тексте, используя данные локализации.

    Args:
        text: Текст для анализа
        location_data: Опциональные данные локализации из extract_location_and_time.
                      Если не указаны, будут извлечены автоматически из текста.

    Returns:
        Список словарей с информацией об экосистемах:
        [
            {
                "name": "название экосистемы",
                "description": "описание",
                "location": "географическое местоположение",
                "scale": "molecular|cellular|tissue|organ|organism|micro_habitat|habitat|landscape|regional|continental|global|planetary",
                "parent_ecosystem": "родительская экосистема (если упомянута)",
                "context": "контекст упоминания в тексте"
            }
        ]
    """
    # Извлекаем данные локализации, если не предоставлены
    if location_data is None:
        location_data = extract_location_and_time(text)

    location = location_data.get("location") if location_data else None
    time_reference = location_data.get("time_reference") if location_data else None

    fallback_prompt = """Извлеки из текста все упоминания экосистем.

КОНЦЕПЦИЯ: Экосистема = большой организм (метаболизм, гомеостаз, симбиотические связи).
Экосистемы могут быть вложенными (экосистема внутри экосистемы).

Текст:
{text}

Извлеченная локализация: {location}
Временная ссылка: {time_reference}

Верни JSON массив объектов с полями: name, description, location, scale, parent_ecosystem, context.
Формат: [{{"name": "...", "scale": "...", "context": "..."}}]"""

    # Создаем нормализатор с замыканием для location и time_reference
    def normalizer(item: Dict[str, Any]) -> Dict[str, Any]:
        return _normalize_ecosystem(item, location=location, time_reference=time_reference)

    return await extract_structured_data(
        text=text,
        prompt_file="ecosystem_scaler.txt",
        fallback_prompt=fallback_prompt,
        validator=_validate_ecosystem,
        normalizer=normalizer,
        prompt_replacements={
            "{location}": location or "не указано",
            "{time_reference}": time_reference or "не указано",
        },
        origin="ecosystem_scaler",
    )
