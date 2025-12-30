"""
Детектор организмов-участников экосистемы в тексте.

Использует LLM для извлечения информации об организмах из текста.
"""

from typing import List, Optional, Dict, Any
from api.llm import call_llm_with_retry
from api.logger import root_logger
from pathlib import Path

log = root_logger.debug


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
    # Загружаем промпт из файла
    prompt_path = Path(__file__).parent.parent / "prompts" / "organism_detector.txt"
    if not prompt_path.exists():
        prompt_path = Path("api/prompts/organism_detector.txt")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        log("⚠️ Промпт organism_detector.txt не найден, используем упрощенный вариант")
        prompt_template = """Извлеки из текста все упоминания организмов (растения, животные, грибы, бактерии).

Текст:
{text}

Верни JSON массив объектов с полями: name, scientific_name (опционально), type, context.
Формат: [{{"name": "...", "type": "...", "context": "..."}}]"""

    # Ограничиваем длину текста для экономии токенов
    text_limited = text[:2000]

    # Форматируем промпт с данными
    prompt = prompt_template.replace("{text}", text_limited)

    try:
        response = await call_llm_with_retry(prompt)
        # Парсим JSON ответ
        import re
        import json

        json_match = re.search(r"\[.*?\]", response, re.DOTALL)
        if json_match:
            organisms = json.loads(json_match.group())
            # Валидируем структуру
            valid_organisms = []
            for org in organisms:
                if isinstance(org, dict) and "name" in org:
                    valid_organisms.append(
                        {
                            "name": org.get("name", ""),
                            "scientific_name": org.get("scientific_name"),
                            "type": org.get("type", "другое"),
                            "category": org.get("category"),  # Категория для растений, насекомых, птиц
                            "context": org.get("context", ""),
                        }
                    )
            return valid_organisms
        else:
            log(f"⚠️ Не удалось извлечь JSON из ответа LLM: {response}")
            return []
    except Exception as e:
        log(f"⚠️ Ошибка при обнаружении организмов: {e}")
        return []
