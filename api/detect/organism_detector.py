"""
Детектор организмов-участников экосистемы в тексте.

Использует LLM для извлечения информации об организмах из текста.
"""

from typing import List, Dict, Any

from api.detect.entity_extractor import extract_structured_data


# Валидатор для организмов
def _validate_organism(item: Dict[str, Any]) -> bool:
    """Проверяет, что объект является валидным организмом."""
    return isinstance(item, dict) and "name" in item


# Нормализатор для организмов
def _normalize_organism(item: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует данные организма."""
    return {
        "name": item.get("name", ""),
        "scientific_name": item.get("scientific_name"),
        "type": item.get("type", "другое"),
        "category": item.get("category"),  # Категория для растений, насекомых, птиц
        "context": item.get("context", ""),
    }


async def detect_organisms(text: str) -> List[Dict[str, Any]]:
    """
    Обнаруживает организмы-участники экосистемы в тексте.

    Args:
        text: Текст для анализа

    Returns:
        Список словарей с информацией об организмах:
        [
            {
                "name": "название организма",
                "scientific_name": "научное название (если известно)",
                "type": "растение|животное|гриб|бактерия|другое",
                "category": "категория (дерево, насекомое, птица и т.д.) - опционально",
                "context": "контекст упоминания в тексте"
            }
        ]
    """
    fallback_prompt = """Извлеки из текста все упоминания организмов (растения, животные, грибы, бактерии).

Текст:
{text}

Верни JSON массив объектов с полями: name, scientific_name (опционально), type, context.
Формат: [{{"name": "...", "type": "...", "context": "..."}}]"""

    return await extract_structured_data(
        text=text,
        prompt_file="organism_detector.txt",
        fallback_prompt=fallback_prompt,
        validator=_validate_organism,
        normalizer=_normalize_organism,
        origin="organism_detector",
    )
