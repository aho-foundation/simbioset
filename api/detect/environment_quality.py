"""
Детектор состояния окружающей среды и климатических условий.

Извлекает информацию о:
- Климатических условиях (температура, влажность, осадки, ветер, сезон)
- Состоянии окружающей среды (качество воздуха, воды, почвы, загрязнение)
- Факторах для поиска симбиозов (тип биома, доступность ресурсов, угрозы)
"""

from typing import Dict, Any, Optional
from pathlib import Path

from api.llm import call_llm
from api.logger import root_logger
from api.detect.localize import extract_location_and_time

log = root_logger.debug


async def detect_environment(text: str, location_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Извлекает информацию о состоянии окружающей среды и климатических условиях.

    Args:
        text: Текст для анализа (описание изображения)
        location_data: Опциональные данные локализации из extract_location_and_time.
                      Если не указаны, будут извлечены автоматически из текста.

    Returns:
        Словарь с информацией об окружающей среде:
        {
            "climate": {
                "temperature": "<в градусах Цельсия>",
                "humidity": "<высокая/средняя/низкая и цифровое значение от 0 до 100>",
                "precipitation": "<дождь/снег/засуха/норма и цифровое значение от 0 до 100>",
                "wind": "<сильный/слабый/умеренный, с порывами ли и скоростью в м/с>",
                "season": "<весна/лето/осень/зима>",
                "lighting": "<солнечно/пасмурно/сумерки>"
            },
            "environment": {
                "air_quality": "<цифровое значение от 0 до 100>",
                "water_quality": "<цифровое значение от 0 до 100>",
                "soil_condition": "<цифровое значение от 0 до 100>",
                "pollution_level": "<цифровое значение от 0 до 100>",
                "anthropogenic_impact": "<цифровое значение от 0 до 100>"
            },
            "symbiosis_factors": {
                "biome_type": "<тип биома>",
                "resource_availability": {...},
                "threats": [...],
                "improvement_potential": [...],
                "symbiosis_conditions": "<благоприятные/нейтральные/неблагоприятные>"
            },
            "overall_condition": {
                "ecosystem_health": "<здоровая/нарушенная/деградированная>",
                "biodiversity": "<высокое/среднее/низкое>",
                "stability": "<стабильная/нестабильная>"
            },
            "confidence": 0.0-1.0
        }
    """
    # Извлекаем данные локализации, если не предоставлены
    if location_data is None:
        location_data = extract_location_and_time(text)

    location = location_data.get("location") if location_data else None
    time_reference = location_data.get("time_reference") if location_data else None

    # Загружаем промпт из файла
    prompt_path = Path(__file__).parent.parent / "prompts" / "environment_quality.txt"
    if not prompt_path.exists():
        prompt_path = Path("api/prompts/environment_quality.txt")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        log("⚠️ Промпт environment_quality.txt не найден, используем упрощенный вариант")
        prompt_template = """Извлеки из текста информацию о состоянии окружающей среды и климатических условиях.

Текст:
{text}

Извлеченная локализация: {location}
Временная ссылка: {time_reference}

Верни JSON объект с полями: climate, environment, symbiosis_factors, overall_condition, confidence.
Формат: {{"climate": {{...}}, "environment": {{...}}, ...}}"""

    # Ограничиваем длину текста для экономии токенов
    text_limited = text[:2000]

    # Форматируем промпт
    prompt = (
        prompt_template.replace("{text}", text_limited)
        .replace("{location}", location or "не указано")
        .replace("{time_reference}", time_reference or "не указано")
    )

    try:
        response = await call_llm(prompt, origin="environment_quality")
        # Парсим JSON ответ
        import re
        import json

        # Сначала пробуем распарсить весь ответ как JSON
        try:
            environment_data = json.loads(response.strip())
        except json.JSONDecodeError:
            # Если не получилось, ищем JSON блок с жадным поиском
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                try:
                    environment_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    # Если и это не сработало, пробуем найти JSON с балансом скобок
                    start_idx = response.find("{")
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = start_idx
                        for i in range(start_idx, len(response)):
                            if response[i] == "{":
                                brace_count += 1
                            elif response[i] == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        if brace_count == 0:
                            json_str = response[start_idx:end_idx]
                            environment_data = json.loads(json_str)
                        else:
                            raise ValueError("Не удалось найти полный JSON блок")
                    else:
                        raise ValueError("Не найден JSON блок в ответе")
            else:
                raise ValueError("Не найден JSON блок в ответе")

        # Валидируем и нормализуем структуру
        result = {
            "climate": environment_data.get("climate", {}),
            "environment": environment_data.get("environment", {}),
            "symbiosis_factors": environment_data.get("symbiosis_factors", {}),
            "overall_condition": environment_data.get("overall_condition", {}),
            "confidence": float(environment_data.get("confidence", 0.5)),
        }
        return result
    except Exception as e:
        log(f"⚠️ Ошибка при извлечении данных об окружающей среде: {e}")
        return _get_default_environment_data()


def _get_default_environment_data() -> Dict[str, Any]:
    """Возвращает структуру по умолчанию для данных об окружающей среде."""
    return {
        "climate": {
            "temperature": "неопределено",
            "humidity": "неопределено",
            "precipitation": "неопределено",
            "wind": "неопределено",
            "season": "неопределено",
            "lighting": "неопределено",
        },
        "environment": {
            "air_quality": "неопределено",
            "water_quality": "неопределено",
            "soil_condition": "неопределено",
            "pollution_level": "неопределено",
            "anthropogenic_impact": "неопределено",
        },
        "symbiosis_factors": {
            "biome_type": "неопределено",
            "resource_availability": {
                "water": "неопределено",
                "nutrients": "неопределено",
                "light": "неопределено",
                "shelter": "неопределено",
            },
            "threats": [],
            "improvement_potential": [],
            "symbiosis_conditions": "неопределено",
        },
        "overall_condition": {
            "ecosystem_health": "неопределено",
            "biodiversity": "неопределено",
            "stability": "неопределено",
        },
        "confidence": 0.0,
    }
