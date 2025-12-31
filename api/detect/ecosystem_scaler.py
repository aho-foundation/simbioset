"""
Детектор экосистем в тексте.

Экосистема = большой организм (метаболизм, гомеостаз, симбиотические связи).
Экосистемы могут быть вложенными (экосистема внутри экосистемы).

Использует данные детекта локализации для более точного определения экосистем.
"""

import re
import json
from pathlib import Path
from string import Template
from typing import List, Optional, Dict, Any

from api.llm import call_llm
from api.logger import root_logger
from api.detect.localize import extract_location_and_time

log = root_logger.debug


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

    # Загружаем промпт из файла
    prompt_path = Path(__file__).parent.parent / "prompts" / "ecosystem_scaler.txt"
    if not prompt_path.exists():
        prompt_path = Path("api/prompts/ecosystem_scaler.txt")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        log("⚠️ Промпт ecosystem_scaler.txt не найден, используем упрощенный вариант")
        prompt_template = """Извлеки из текста все упоминания экосистем.

КОНЦЕПЦИЯ: Экосистема = большой организм (метаболизм, гомеостаз, симбиотические связи).
Экосистемы могут быть вложенными (экосистема внутри экосистемы).

Текст:
{text}

Извлеченная локализация: {location}
Временная ссылка: {time_reference}

Верни JSON массив объектов с полями: name, description, location, scale, parent_ecosystem, context.
Формат: [{{"name": "...", "scale": "...", "context": "..."}}]"""

    # Ограничиваем длину текста для экономии токенов
    text_limited = text[:2000]

    # Форматируем промпт с данными локализации
    # Используем Template для безопасного форматирования с фигурными скобками в JSON

    prompt_template_obj = Template(prompt_template.replace("{", "$").replace("}", ""))
    # Заменяем обратно только нужные поля
    prompt = (
        prompt_template.replace("{text}", text_limited)
        .replace("{location}", location or "не указано")
        .replace("{time_reference}", time_reference or "не указано")
    )

    try:
        response = await call_llm(prompt, origin="ecosystem_scaler")

        # Парсим JSON ответ
        json_match = re.search(r"\[.*?\]", response, re.DOTALL)
        if json_match:
            ecosystems = json.loads(json_match.group())
            # Валидируем структуру
            valid_ecosystems = []
            for eco in ecosystems:
                if isinstance(eco, dict) and "name" in eco:
                    # Используем локализацию из детекта, если она не указана в ответе LLM
                    eco_location = eco.get("location") or location

                    valid_ecosystems.append(
                        {
                            "name": eco.get("name", ""),
                            "description": eco.get("description"),
                            "location": eco_location,  # Используем локализацию из детекта
                            "scale": eco.get("scale", "habitat"),  # По умолчанию habitat (лес, озеро)
                            "parent_ecosystem": eco.get("parent_ecosystem"),
                            "context": eco.get("context", ""),
                            "time_reference": time_reference,  # Добавляем временную ссылку
                        }
                    )
            return valid_ecosystems
        else:
            log(f"⚠️ Не удалось извлечь JSON из ответа LLM: {response}")
            return []
    except Exception as e:
        log(f"⚠️ Ошибка при обнаружении экосистем: {e}")
        return []
