#!/usr/bin/env python3
"""
Скрипт для тестирования Weaviate-style форматирования контекстов.

Проверяет, что новый структурированный формат работает корректно.
"""

import asyncio
import sys

import pytest

# Импорты из проекта
sys.path.append("/Users/tony/code/simbioset-website")

from api.chat.context_builder import format_ecosystem_context
from api.logger import root_logger

log = root_logger.debug


@pytest.mark.asyncio
async def test_ecosystem_context_formatting():
    """Тестирует форматирование контекста экосистемы."""

    log("🧪 Тестирование Weaviate-style форматирования экосистем...")

    # Тестовые данные
    test_ecosystems = [
        {
            "name": "Смешанный лес",
            "scale": "habitat",
            "description": "Лесная экосистема с преобладанием сосны и березы, типичная для умеренного пояса",
            "location": "Московская область",
            "confidence": 0.85,
            "biome": "temperate_forest",
            "threat_level": "medium",
        },
        {
            "name": "Микробиом кишечника",
            "scale": "organ",
            "description": "Комплексная микробная экосистема в кишечнике человека с разнообразными бактериями",
            "confidence": 0.92,
            "biome": "human_microbiome",
        },
    ]

    test_location = "Москва, Россия"
    test_weather = "Температура: +15°C\nВлажность: 65%\nДавление: 750 мм рт. ст."

    # Форматируем контекст
    formatted_context = format_ecosystem_context(
        ecosystems=test_ecosystems, location=test_location, weather=test_weather
    )

    print("\n" + "=" * 80)
    print("ECOSYSTEM CONTEXT FORMATTING TEST")
    print("=" * 80)
    print(formatted_context)
    print("=" * 80)

    # Проверки
    assert "=== GEOSPATIAL CONTEXT ===" in formatted_context
    assert "=== WEATHER METRICS ===" in formatted_context
    assert "=== ECOSYSTEM ENTITIES ===" in formatted_context
    assert "📍 Location: Москва, Россия" in formatted_context
    assert "🌡️ Температура: +15°C" in formatted_context
    assert "🌿 Entity_1: Смешанный лес" in formatted_context
    assert "📊 Status: active | Type: ecological" in formatted_context

    log("✅ Форматирование экосистем прошло проверку")


@pytest.mark.asyncio
async def test_unified_ecosystem_context_formatting():
    """Тестирует объединённое форматирование контекста экосистемы с симбионтами."""

    log("🧪 Тестирование объединённого Weaviate-style форматирования экосистемы + симбионтов...")

    # Тестовые данные экосистем
    test_ecosystems = [
        {
            "name": "Смешанный лес",
            "scale": "habitat",
            "description": "Лесная экосистема с преобладанием сосны и березы",
            "location": "Московская область",
            "confidence": 0.85,
            "biome": "temperate_forest",
            "threat_level": "medium",
        }
    ]

    # Тестовые данные симбионтов
    class MockSymbiont:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    mock_symbionts = [
        MockSymbiont(
            name="Бифидобактерии",
            scientific_name="Bifidobacterium",
            type="symbiont",
            category="бактерия",
            biochemical_role="ферментация углеводов, защита от патогенов",
            risk_level="low",
            detection_confidence=0.95,
            prevalence=0.85,
            virulence_factors=[],
            geographic_distribution="всемирно",
        ),
        MockSymbiont(
            name="Золотистый стафилококк",
            scientific_name="Staphylococcus aureus",
            type="pathogen",
            category="бактерия",
            biochemical_role="выработка токсинов",
            risk_level="high",
            detection_confidence=0.88,
            prevalence=0.25,
            virulence_factors=["токсин TSST-1"],
            geographic_distribution="всемирно",
        ),
    ]

    test_location = "Москва, Россия"
    test_weather = "Температура: +15°C\nВлажность: 65%"

    # Тестируем объединённое форматирование
    formatted_context = format_ecosystem_context(
        ecosystems=test_ecosystems, location=test_location, weather=test_weather, symbionts=mock_symbionts
    )

    print("\n" + "=" * 80)
    print("UNIFIED ECOSYSTEM + SYMBIONTS CONTEXT FORMATTING TEST")
    print("=" * 80)
    print(formatted_context)
    print("=" * 80)

    # Проверки
    assert "=== GEOSPATIAL CONTEXT ===" in formatted_context
    assert "=== WEATHER METRICS ===" in formatted_context
    assert "=== ECOSYSTEM ENTITIES ===" in formatted_context
    assert "=== MICROBIAL ENTITIES ===" in formatted_context
    assert "📍 Location: Москва, Россия" in formatted_context
    assert "🌿 Entity_1: Смешанный лес" in formatted_context
    assert "🦠 Entity_1: Бифидобактерии" in formatted_context
    assert "🦠 Entity_2: Золотистый стафилококк" in formatted_context
    assert "📊 Status: active | Type: ecological" in formatted_context

    log("✅ Объединённое форматирование экосистемы + симбионтов прошло проверку")


@pytest.mark.asyncio
async def test_empty_contexts():
    """Тестирует обработку пустых контекстов."""

    log("🧪 Тестирование пустых контекстов...")

    # Пустой контекст экосистемы
    empty_ecosystem = format_ecosystem_context([], None, None)
    # Теперь функция всегда возвращает базовые секции, даже для пустых данных
    assert "=== GEOSPATIAL CONTEXT ===" in empty_ecosystem
    assert "📍 Location: Not specified" in empty_ecosystem
    assert "=== WEATHER METRICS ===" in empty_ecosystem
    assert "🌤️ Weather: Not available" in empty_ecosystem
    log("✅ Пустой контекст экосистем обработан")

    # Пустой контекст симбионтов (через мок)
    import api.chat.context_builder as cb
    from api.storage.symbiont_service import SymbiontService

    original_method = SymbiontService.search_symbionts

    async def mock_empty_search(query, limit=5):
        return []

    SymbiontService.search_symbionts = mock_empty_search

    try:
        # Test format_ecosystem_context with empty symbionts
        empty_ecosystem_context = format_ecosystem_context([], None, None, [])
        # Should not contain symbionts section when symbionts list is empty
        assert "MICROBIAL ENTITIES" not in empty_ecosystem_context
        log("✅ Пустой контекст симбионтов обработан")
    finally:
        SymbiontService.search_symbionts = original_method


# Тесты будут автоматически обнаружены pytest
