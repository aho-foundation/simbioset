"""
Unit тесты для форматирования контекста экосистем в context_builder.

Тестирует Weaviate-style форматирование контекстов экосистем и симбионтов.
"""

import pytest
from unittest.mock import Mock, patch

from api.chat.context_builder import format_ecosystem_context


class TestEcosystemContextFormatting:
    """Тесты для форматирования контекста экосистем."""

    def test_format_ecosystem_context_minimal(self):
        """Тест форматирования минимального контекста экосистемы."""
        # Arrange
        ecosystems = [
            {
                "name": "Тестовая экосистема",
                "scale": "habitat",
                "description": "Описание тестовой экосистемы",
                "confidence": 0.8,
            }
        ]
        location = "Тестовое место"
        weather = "Температура: +20°C"

        # Act
        result = format_ecosystem_context(ecosystems, location, weather)

        # Assert
        assert "=== GEOSPATIAL CONTEXT ===" in result
        assert "=== WEATHER METRICS ===" in result
        assert "=== ECOSYSTEM ENTITIES ===" in result
        assert "📍 Location: Тестовое место" in result
        assert "🌡️ Температура: +20°C" in result
        assert "🌿 Entity_1: Тестовая экосистема" in result
        assert "📊 Status: active | Type: ecological" in result
        assert "🏷️ Scale: habitat | Confidence: 80.0%" in result

    def test_format_ecosystem_context_full(self):
        """Тест форматирования полного контекста экосистемы."""
        # Arrange
        ecosystems = [
            {
                "name": "Смешанный лес",
                "scale": "habitat",
                "description": "Лесная экосистема с преобладанием сосны и березы",
                "location": "Московская область",
                "confidence": 0.85,
                "biome": "temperate_forest",
                "threat_level": "medium",
            },
            {
                "name": "Микробиом кишечника",
                "scale": "organ",
                "description": "Комплексная микробная экосистема в кишечнике",
                "confidence": 0.92,
                "biome": "human_microbiome",
            },
        ]
        location = "Москва, Россия"
        weather = "Температура: +15°C\nВлажность: 65%\nДавление: 750 мм рт. ст."

        # Act
        result = format_ecosystem_context(ecosystems, location, weather)

        # Assert
        assert "=== GEOSPATIAL CONTEXT ===" in result
        assert "=== WEATHER METRICS ===" in result
        assert "=== ECOSYSTEM ENTITIES ===" in result
        assert "📍 Location: Москва, Россия" in result
        assert "🌡️ Температура: +15°C" in result
        assert "💧 Влажность: 65%" in result
        assert "🌿 Entity_1: Смешанный лес" in result
        assert "🌿 Entity_2: Микробиом кишечника" in result
        assert "📊 Status: active | Type: ecological" in result
        assert "🏷️ Scale: habitat | Confidence: 85.0%" in result
        assert "🏷️ Scale: organ | Confidence: 92.0%" in result
        assert "🌲 Biome: temperate_forest" in result
        assert "🦠 Biome: human_microbiome" in result
        assert "⚠️ Threat Level: medium" in result

    def test_format_ecosystem_context_with_symbionts(self):
        """Тест форматирования контекста с симбионтами."""
        # Arrange
        ecosystems = [
            {
                "name": "Лесная экосистема",
                "scale": "habitat",
                "description": "Смешанный лес",
                "confidence": 0.8,
            }
        ]

        # Мокаем объекты симбионтов
        mock_symbionts = [
            Mock(
                name="Бифидобактерии",
                scientific_name="Bifidobacterium",
                type="symbiont",
                category="бактерия",
                biochemical_role="ферментация углеводов",
                risk_level="low",
                detection_confidence=0.95,
                prevalence=0.85,
                virulence_factors=[],
                geographic_distribution="всемирно",
            ),
            Mock(
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

        location = "Тестовое место"
        weather = "Температура: +18°C"

        # Act
        result = format_ecosystem_context(ecosystems, location, weather, mock_symbionts)

        # Assert
        assert "=== MICROBIAL ENTITIES ===" in result
        assert "🦠 Entity_1: Бифидобактерии" in result
        assert "🦠 Entity_2: Золотистый стафилококк" in result
        assert "📊 Status: active | Type: symbiotic" in result
        assert "📊 Status: active | Type: pathogenic" in result
        assert "🏷️ Category: бактерия | Risk: low" in result
        assert "🏷️ Category: бактерия | Risk: high" in result
        assert "🔬 Role: ферментация углеводов" in result
        assert "🔬 Role: выработка токсинов" in result
        assert "📈 Prevalence: 85.0% | Confidence: 95.0%" in result
        assert "📈 Prevalence: 25.0% | Confidence: 88.0%" in result
        assert "🗺️ Distribution: всемирно" in result

    def test_format_ecosystem_context_empty_ecosystems(self):
        """Тест форматирования с пустым списком экосистем."""
        # Act
        result = format_ecosystem_context([], "Москва", "Солнечно")

        # Assert
        assert "No ecosystem data available" in result
        assert "=== ECOSYSTEM ENTITIES ===" in result

    def test_format_ecosystem_context_empty_symbionts(self):
        """Тест форматирования с пустым списком симбионтов."""
        # Arrange
        ecosystems = [{"name": "Тест", "scale": "habitat", "description": "Тест", "confidence": 0.8}]

        # Act
        result = format_ecosystem_context(ecosystems, "Москва", "Солнечно", [])

        # Assert
        assert "=== MICROBIAL ENTITIES ===" not in result
        assert "No microbial data available" in result

    def test_format_ecosystem_context_none_location_weather(self):
        """Тест форматирования с None значениями location и weather."""
        # Arrange
        ecosystems = [{"name": "Тест", "scale": "habitat", "description": "Тест", "confidence": 0.8}]

        # Act
        result = format_ecosystem_context(ecosystems, None, None)

        # Assert
        assert "📍 Location: Not specified" in result
        assert "🌤️ Weather: Not available" in result

    def test_format_ecosystem_context_missing_fields(self):
        """Тест форматирования экосистем с отсутствующими полями."""
        # Arrange
        ecosystems = [
            {"name": "Минимальная экосистема", "scale": "habitat"},  # Только обязательные поля
            {
                "name": "Полная экосистема",
                "scale": "organ",
                "description": "Описание",
                "confidence": 1.0,
                "biome": "test",
                "threat_level": "low",
            },
        ]

        # Act
        result = format_ecosystem_context(ecosystems, "Тест", "Тест")

        # Assert
        assert "🌿 Entity_1: Минимальная экосистема" in result
        assert "🌿 Entity_2: Полная экосистема" in result
        assert "🏷️ Scale: habitat | Confidence: N/A" in result  # Для первой экосистемы
        assert "🏷️ Scale: organ | Confidence: 100.0%" in result  # Для второй экосистемы
        assert "🌲 Biome: test" in result
        assert "⚠️ Threat Level: low" in result

    def test_format_ecosystem_context_symbiont_missing_fields(self):
        """Тест форматирования симбионтов с отсутствующими полями."""
        # Arrange
        ecosystems = [{"name": "Тест", "scale": "habitat", "description": "Тест", "confidence": 0.8}]

        # Мокаем симбионта с минимальными полями
        mock_symbiont = Mock(
            name="Минимальный симбионт",
            scientific_name=None,
            type="symbiont",
            category=None,
            biochemical_role=None,
            risk_level="low",
            detection_confidence=0.5,
            prevalence=0.0,
            virulence_factors=[],
            geographic_distribution=None,
        )

        # Act
        result = format_ecosystem_context(ecosystems, "Тест", "Тест", [mock_symbiont])

        # Assert
        assert "🦠 Entity_1: Минимальный симбионт" in result
        assert "🏷️ Category: N/A | Risk: low" in result
        assert "🔬 Role: N/A" in result
        assert "📈 Prevalence: 0.0% | Confidence: 50.0%" in result
        assert "🗺️ Distribution: N/A" in result

    def test_format_ecosystem_context_multiple_ecosystems_limit(self):
        """Тест форматирования большого количества экосистем."""
        # Arrange
        ecosystems = [
            {"name": f"Экосистема {i}", "scale": "habitat", "description": f"Описание {i}", "confidence": 0.8}
            for i in range(10)
        ]

        # Act
        result = format_ecosystem_context(ecosystems, "Тест", "Тест")

        # Assert
        for i in range(1, 11):
            assert f"🌿 Entity_{i}: Экосистема {i - 1}" in result

    def test_format_ecosystem_context_special_characters(self):
        """Тест форматирования с специальными символами."""
        # Arrange
        ecosystems = [
            {
                "name": "Экосистема с символами: @#$%^&*()",
                "scale": "habitat",
                "description": "Описание с эмодзи 🌿🌲 и символами @#$%",
                "confidence": 0.85,
            }
        ]
        location = "Место с символами: @#$%^&*()"
        weather = "Погода: 🌤️🌧️ @ 20°C"

        # Act
        result = format_ecosystem_context(ecosystems, location, weather)

        # Assert
        assert "Экосистема с символами: @#$%^&*()" in result
        assert "🌿🌲 и символами @#$%" in result
        assert "Место с символами: @#$%^&*()" in result
        assert "🌤️🌧️ @ 20°C" in result

    def test_format_ecosystem_context_different_scales(self):
        """Тест форматирования экосистем разных масштабов."""
        # Arrange
        ecosystems = [
            {"name": "Глобальная экосистема", "scale": "global", "description": "Вся планета", "confidence": 0.9},
            {"name": "Региональная экосистема", "scale": "regional", "description": "Континент", "confidence": 0.8},
            {"name": "Локальная экосистема", "scale": "habitat", "description": "Конкретное место", "confidence": 0.7},
            {"name": "Микро экосистема", "scale": "organ", "description": "Орган", "confidence": 0.6},
            {"name": "Клеточная экосистема", "scale": "cellular", "description": "Клетка", "confidence": 0.5},
        ]

        # Act
        result = format_ecosystem_context(ecosystems, "Тест", "Тест")

        # Assert
        for ecosystem in ecosystems:
            assert ecosystem["name"] in result
            assert f"🏷️ Scale: {ecosystem['scale']}" in result

    def test_format_ecosystem_context_symbiont_types(self):
        """Тест форматирования разных типов симбионтов."""
        # Arrange
        ecosystems = [{"name": "Тест", "scale": "habitat", "description": "Тест", "confidence": 0.8}]

        mock_symbionts = [
            Mock(
                name="Симбионт",
                type="symbiont",
                category="бактерия",
                risk_level="low",
                detection_confidence=0.8,
                prevalence=0.9,
                virulence_factors=[],
                geographic_distribution="всемирно",
            ),
            Mock(
                name="Патоген",
                type="pathogen",
                category="вирус",
                risk_level="high",
                detection_confidence=0.9,
                prevalence=0.1,
                virulence_factors=["токсин"],
                geographic_distribution="тропики",
            ),
            Mock(
                name="Комменсал",
                type="commensal",
                category="гриб",
                risk_level="medium",
                detection_confidence=0.7,
                prevalence=0.6,
                virulence_factors=[],
                geographic_distribution="умеренный пояс",
            ),
            Mock(
                name="Паразит",
                type="parasite",
                category="гельминт",
                risk_level="medium",
                detection_confidence=0.6,
                prevalence=0.3,
                virulence_factors=["фактор"],
                geographic_distribution="тропики",
            ),
        ]

        # Act
        result = format_ecosystem_context(ecosystems, "Тест", "Тест", mock_symbionts)

        # Assert
        assert "📊 Status: active | Type: symbiotic" in result
        assert "📊 Status: active | Type: pathogenic" in result
        assert "📊 Status: active | Type: commensal" in result
        assert "📊 Status: active | Type: parasitic" in result

    def test_format_ecosystem_context_weather_multiline(self):
        """Тест форматирования многострочной погоды."""
        # Arrange
        ecosystems = [{"name": "Тест", "scale": "habitat", "description": "Тест", "confidence": 0.8}]
        weather = """Температура: +25°C
Влажность: 70%
Давление: 760 мм рт. ст.
Ветер: 5 м/с, СВ
Осадки: небольшой дождь"""

        # Act
        result = format_ecosystem_context(ecosystems, "Тест", weather)

        # Assert
        assert "🌡️ Температура: +25°C" in result
        assert "💧 Влажность: 70%" in result
        assert "🌪️ Давление: 760 мм рт. ст." in result
        assert "💨 Ветер: 5 м/с, СВ" in result
        assert "🌧️ Осадки: небольшой дождь" in result
