"""
Классификатор организмов по биологической роли в экосистеме.

Классифицирует организмы по трофическим уровням:
- Продуценты (производители органического вещества)
- Консументы (потребители)
- Редуценты (разлагатели)

С учетом биохимического обмена веществ.
"""

from typing import List, Optional, Dict, Any
from enum import Enum
from api.llm import call_llm_with_retry
from api.logger import root_logger
from pathlib import Path

log = root_logger.debug


class TrophicLevel(Enum):
    """Трофический уровень организма в экосистеме."""

    PRODUCER = "producer"  # Продуцент (производитель)
    PRIMARY_CONSUMER = "primary_consumer"  # Консумент первого порядка (травоядные)
    SECONDARY_CONSUMER = "secondary_consumer"  # Консумент второго порядка (хищники)
    TERTIARY_CONSUMER = "tertiary_consumer"  # Консумент третьего порядка
    DECOMPOSER = "decomposer"  # Редуцент (разлагатель)
    OMNIVORE = "omnivore"  # Всеядный (может быть на разных уровнях)
    UNKNOWN = "unknown"  # Неизвестно


class BiochemicalRole(Enum):
    """Биохимическая роль организма в обмене веществ."""

    PHOTOSYNTHESIS = "photosynthesis"  # Фотосинтез (продуценты)
    CHEMOSYNTHESIS = "chemosynthesis"  # Хемосинтез (продуценты)
    HERBIVORY = "herbivory"  # Травоядность
    CARNIVORY = "carnivory"  # Хищничество
    DECOMPOSITION = "decomposition"  # Разложение органики
    NITROGEN_FIXATION = "nitrogen_fixation"  # Фиксация азота
    SYMBIOSIS = "symbiosis"  # Симбиотические отношения
    PARASITISM = "parasitism"  # Паразитизм
    UNKNOWN = "unknown"  # Неизвестно


async def classify_organism_role(
    organism_name: str,
    organism_type: Optional[str] = None,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Классифицирует организм по биологической роли в экосистеме.

    Args:
        organism_name: Название организма
        organism_type: Тип организма (растение, животное, гриб, бактерия)
        context: Контекст упоминания в тексте

    Returns:
        Словарь с классификацией:
        {
            "trophic_level": "producer|primary_consumer|...",
            "biochemical_roles": ["photosynthesis", "decomposition", ...],
            "metabolic_pathways": ["описание биохимических путей"],
            "confidence": 0.0-1.0
        }
    """
    # Загружаем промпт из файла
    prompt_path = Path(__file__).parent.parent / "prompts" / "organism_classifier.txt"
    if not prompt_path.exists():
        prompt_path = Path("api/prompts/organism_classifier.txt")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        log("⚠️ Промпт organism_classifier.txt не найден, используем упрощенный вариант")
        prompt_template = """Классифицируй организм по биологической роли в экосистеме.

Организм: {organism_name}
Тип: {organism_type}
Контекст: {context}

Верни JSON с полями: trophic_level, biochemical_roles (массив), metabolic_pathways (массив), confidence.
Формат: {{"trophic_level": "...", "biochemical_roles": [...], "metabolic_pathways": [...], "confidence": 0.9}}"""

    prompt = prompt_template.format(
        organism_name=organism_name, organism_type=organism_type or "неизвестно", context=context or ""
    )

    try:
        response = await call_llm_with_retry(prompt)
        # Парсим JSON ответ
        import re
        import json

        json_match = re.search(r"\{.*?\}", response, re.DOTALL)
        if json_match:
            classification = json.loads(json_match.group())
            # Валидируем и нормализуем
            result = {
                "trophic_level": classification.get("trophic_level", "unknown"),
                "biochemical_roles": classification.get("biochemical_roles", []),
                "metabolic_pathways": classification.get("metabolic_pathways", []),
                "confidence": float(classification.get("confidence", 0.5)),
            }
            return result
        else:
            log(f"⚠️ Не удалось извлечь JSON из ответа LLM: {response}")
            return {"trophic_level": "unknown", "biochemical_roles": [], "metabolic_pathways": [], "confidence": 0.0}
    except Exception as e:
        log(f"⚠️ Ошибка при классификации организма: {e}")
        return {"trophic_level": "unknown", "biochemical_roles": [], "metabolic_pathways": [], "confidence": 0.0}


async def classify_organisms_batch(organisms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Классифицирует список организмов по биологической роли.

    Args:
        organisms: Список словарей с информацией об организмах из detect_organisms

    Returns:
        Список организмов с добавленной классификацией
    """
    classified = []
    for org in organisms:
        classification = await classify_organism_role(
            organism_name=org.get("name", ""), organism_type=org.get("type"), context=org.get("context", "")
        )
        # Объединяем исходную информацию с классификацией
        org_with_classification = {
            **org,
            "trophic_level": classification["trophic_level"],
            "biochemical_roles": classification["biochemical_roles"],
            "metabolic_pathways": classification["metabolic_pathways"],
            "classification_confidence": classification["confidence"],
        }
        classified.append(org_with_classification)

    return classified
