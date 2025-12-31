"""
Модуль для извлечения сущностей из текста через LLM.

Используется для детекции организмов, экосистем и других биологических сущностей.
Извлекает структурированные данные (JSON) из неструктурированного текста.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from api.llm import call_llm
from api.logger import root_logger

log = root_logger.debug


async def extract_structured_data(
    text: str,
    prompt_file: str,
    fallback_prompt: str,
    validator: Callable[[Dict[str, Any]], bool],
    normalizer: Callable[[Dict[str, Any]], Dict[str, Any]],
    text_limit: int = 2000,
    prompt_replacements: Optional[Dict[str, str]] = None,
    origin: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Извлекает структурированные данные из текста через LLM.

    Args:
        text: Текст для анализа
        prompt_file: Имя файла с промптом (например, "organism_detector.txt")
        fallback_prompt: Упрощенный промпт, если файл не найден
        validator: Функция для валидации извлеченных объектов (должна возвращать bool)
        normalizer: Функция для нормализации извлеченных объектов
        text_limit: Максимальная длина текста для анализа
        prompt_replacements: Словарь замен для промпта (например, {"{location}": "Москва"})
        origin: Происхождение запроса для логирования (например, "organism_detector")

    Returns:
        Список нормализованных и валидированных объектов
    """
    # Загружаем промпт из файла
    prompt_path = Path(__file__).parent.parent / "prompts" / prompt_file
    if not prompt_path.exists():
        prompt_path = Path(f"api/prompts/{prompt_file}")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        log(f"⚠️ Промпт {prompt_file} не найден, используем упрощенный вариант")
        prompt_template = fallback_prompt

    # Ограничиваем длину текста для экономии токенов
    text_limited = text[:text_limit]

    # Форматируем промпт с данными
    prompt = prompt_template.replace("{text}", text_limited)

    # Применяем дополнительные замены, если указаны
    if prompt_replacements:
        for key, value in prompt_replacements.items():
            prompt = prompt.replace(key, value or "не указано")

    try:
        response = await call_llm(prompt, origin=origin)

        # Парсим JSON ответ
        json_match = re.search(r"\[.*?\]", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            # Валидируем и нормализуем структуру
            valid_data = []
            for item in data:
                if isinstance(item, dict) and validator(item):
                    normalized = normalizer(item)
                    valid_data.append(normalized)
            return valid_data
        else:
            log(f"⚠️ Не удалось извлечь JSON из ответа LLM: {response[:200]}")
            return []
    except Exception as e:
        log(f"⚠️ Ошибка при извлечении данных: {e}")
        return []
