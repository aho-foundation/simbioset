"""
Тесты детектора состояния окружающей среды и климатических условий.

Проверяет извлечение данных о климате, состоянии среды и факторах для симбиозов.
"""

import pytest
from unittest.mock import patch, AsyncMock
from api.detect.environment_quality import detect_environment, _get_default_environment_data


class TestEnvironmentDetector:
    """Тесты детектора окружающей среды."""

    @pytest.mark.asyncio
    @patch("api.detect.environment_quality.extract_location_and_time")
    @patch("api.detect.environment_quality.call_llm_with_retry", new_callable=AsyncMock)
    async def test_detect_environment_basic(self, mock_llm, mock_location):
        """Тест базового извлечения данных об окружающей среде."""
        mock_location.return_value = {}
        # Настраиваем мок для async функции - AsyncMock автоматически делает return_value awaitable
        mock_llm.return_value = """{
            "climate": {
                "temperature": "умеренная (15-20°C)",
                "humidity": "высокая",
                "precipitation": "дождь",
                "wind": "слабый",
                "season": "лето",
                "lighting": "солнечно"
            },
            "environment": {
                "air_quality": "хорошая",
                "water_quality": "хорошая",
                "soil_condition": "хорошая",
                "pollution_level": "низкий",
                "anthropogenic_impact": "низкий"
            },
            "symbiosis_factors": {
                "biome_type": "лес",
                "resource_availability": {
                    "water": "доступна",
                    "nutrients": "доступны",
                    "light": "доступен",
                    "shelter": "доступно"
                },
                "threats": [],
                "improvement_potential": [],
                "symbiosis_conditions": "благоприятные"
            },
            "overall_condition": {
                "ecosystem_health": "здоровая",
                "biodiversity": "высокое",
                "stability": "стабильная"
            },
            "confidence": 0.8
        }"""

        result = await detect_environment("Летний лес с высокой влажностью и дождем.")

        # Проверяем, что мок был вызван
        assert mock_llm.called, f"Мок не был вызван! call_count: {mock_llm.call_count}"

        assert result["climate"]["temperature"] == "умеренная (15-20°C)"
        assert result["climate"]["humidity"] == "высокая"
        assert result["climate"]["season"] == "лето"
        assert result["environment"]["air_quality"] == "хорошая"
        assert result["symbiosis_factors"]["biome_type"] == "лес"
        assert result["overall_condition"]["ecosystem_health"] == "здоровая"
        assert result["confidence"] == 0.8

    @pytest.mark.asyncio
    @patch("api.detect.environment_quality.call_llm_with_retry", new_callable=AsyncMock)
    async def test_detect_environment_with_location_data(self, mock_llm):
        """Тест извлечения данных с предоставленными данными локализации."""
        mock_llm.return_value = """{
            "climate": {
                "temperature": "холодная (-5°C)",
                "humidity": "средняя",
                "precipitation": "снег",
                "wind": "умеренный",
                "season": "зима",
                "lighting": "пасмурно"
            },
            "environment": {
                "air_quality": "хорошая",
                "water_quality": "неопределено",
                "soil_condition": "хорошая",
                "pollution_level": "низкий",
                "anthropogenic_impact": "низкий"
            },
            "symbiosis_factors": {
                "biome_type": "лес",
                "resource_availability": {
                    "water": "доступна",
                    "nutrients": "ограничены",
                    "light": "ограничен",
                    "shelter": "доступно"
                },
                "threats": ["холод"],
                "improvement_potential": ["улучшение укрытий"],
                "symbiosis_conditions": "нейтральные"
            },
            "overall_condition": {
                "ecosystem_health": "здоровая",
                "biodiversity": "среднее",
                "stability": "стабильная"
            },
            "confidence": 0.7
        }"""

        location_data = {"location": "Московская область", "time_reference": "зима 2024"}
        result = await detect_environment("Зимний лес со снегом.", location_data=location_data)

        assert result["climate"]["season"] == "зима"
        assert result["climate"]["precipitation"] == "снег"
        assert result["symbiosis_factors"]["threats"] == ["холод"]
        assert result["confidence"] == 0.7

    @pytest.mark.asyncio
    @patch("api.detect.environment_quality.extract_location_and_time")
    @patch("api.detect.environment_quality.call_llm_with_retry", new_callable=AsyncMock)
    async def test_detect_environment_polluted(self, mock_llm, mock_location):
        """Тест обнаружения загрязненной среды."""
        mock_location.return_value = {}
        mock_llm.return_value = """{
            "climate": {
                "temperature": "умеренная",
                "humidity": "средняя",
                "precipitation": "норма",
                "wind": "слабый",
                "season": "весна",
                "lighting": "пасмурно"
            },
            "environment": {
                "air_quality": "плохая",
                "water_quality": "плохая",
                "soil_condition": "плохая",
                "pollution_level": "высокий",
                "anthropogenic_impact": "высокий"
            },
            "symbiosis_factors": {
                "biome_type": "городская среда",
                "resource_availability": {
                    "water": "ограничена",
                    "nutrients": "ограничены",
                    "light": "доступен",
                    "shelter": "ограничено"
                },
                "threats": ["загрязнение воздуха", "загрязнение воды"],
                "improvement_potential": ["очистка воздуха", "очистка воды", "восстановление почвы"],
                "symbiosis_conditions": "неблагоприятные"
            },
            "overall_condition": {
                "ecosystem_health": "деградированная",
                "biodiversity": "низкое",
                "stability": "нестабильная"
            },
            "confidence": 0.9
        }"""

        result = await detect_environment("Загрязненная городская среда с дымом и мусором.")

        assert result["environment"]["pollution_level"] == "высокий"
        assert result["environment"]["air_quality"] == "плохая"
        assert result["symbiosis_factors"]["threats"] == ["загрязнение воздуха", "загрязнение воды"]
        assert result["overall_condition"]["ecosystem_health"] == "деградированная"
        assert len(result["symbiosis_factors"]["improvement_potential"]) > 0

    @pytest.mark.asyncio
    @patch("api.detect.environment_quality.extract_location_and_time")
    @patch("api.detect.environment_quality.call_llm_with_retry", new_callable=AsyncMock)
    async def test_detect_environment_undefined(self, mock_llm, mock_location):
        """Тест обработки неопределенных данных."""
        mock_location.return_value = {}
        mock_llm.return_value = """{
            "climate": {
                "temperature": "неопределено",
                "humidity": "неопределено",
                "precipitation": "неопределено",
                "wind": "неопределено",
                "season": "неопределено",
                "lighting": "неопределено"
            },
            "environment": {
                "air_quality": "неопределено",
                "water_quality": "неопределено",
                "soil_condition": "неопределено",
                "pollution_level": "неопределено",
                "anthropogenic_impact": "неопределено"
            },
            "symbiosis_factors": {
                "biome_type": "неопределено",
                "resource_availability": {
                    "water": "неопределено",
                    "nutrients": "неопределено",
                    "light": "неопределено",
                    "shelter": "неопределено"
                },
                "threats": [],
                "improvement_potential": [],
                "symbiosis_conditions": "неопределено"
            },
            "overall_condition": {
                "ecosystem_health": "неопределено",
                "biodiversity": "неопределено",
                "stability": "неопределено"
            },
            "confidence": 0.0
        }"""

        result = await detect_environment("Неясное изображение без деталей.")

        assert result["climate"]["temperature"] == "неопределено"
        assert result["environment"]["air_quality"] == "неопределено"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("api.detect.environment_quality.extract_location_and_time")
    @patch("api.detect.environment_quality.call_llm_with_retry", new_callable=AsyncMock)
    async def test_detect_environment_invalid_json(self, mock_llm, mock_location):
        """Тест обработки невалидного JSON."""
        mock_location.return_value = {}
        mock_llm.return_value = "Не JSON ответ"

        result = await detect_environment("Текст с описанием среды.")

        # Должен вернуться дефолтный результат
        assert result["climate"]["temperature"] == "неопределено"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("api.detect.environment_quality.extract_location_and_time")
    @patch("api.detect.environment_quality.call_llm_with_retry", new_callable=AsyncMock)
    async def test_detect_environment_exception(self, mock_llm, mock_location):
        """Тест обработки исключения."""
        mock_location.return_value = {}
        mock_llm.side_effect = Exception("Ошибка LLM")

        result = await detect_environment("Текст с описанием среды.")

        # Должен вернуться дефолтный результат
        assert result["climate"]["temperature"] == "неопределено"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("api.detect.environment_quality.extract_location_and_time")
    @patch("api.detect.environment_quality.call_llm_with_retry", new_callable=AsyncMock)
    async def test_detect_environment_symbiosis_factors(self, mock_llm, mock_location):
        """Тест извлечения факторов для симбиозов."""
        mock_location.return_value = {}
        mock_llm.return_value = """{
            "climate": {
                "temperature": "умеренная",
                "humidity": "высокая",
                "precipitation": "норма",
                "wind": "слабый",
                "season": "лето",
                "lighting": "солнечно"
            },
            "environment": {
                "air_quality": "хорошая",
                "water_quality": "хорошая",
                "soil_condition": "хорошая",
                "pollution_level": "низкий",
                "anthropogenic_impact": "низкий"
            },
            "symbiosis_factors": {
                "biome_type": "смешанный лес",
                "resource_availability": {
                    "water": "доступна",
                    "nutrients": "доступны",
                    "light": "доступен",
                    "shelter": "доступно"
                },
                "threats": [],
                "improvement_potential": ["посадка новых видов", "улучшение почвы"],
                "symbiosis_conditions": "благоприятные"
            },
            "overall_condition": {
                "ecosystem_health": "здоровая",
                "biodiversity": "высокое",
                "stability": "стабильная"
            },
            "confidence": 0.85
        }"""

        result = await detect_environment("Здоровый лес с разнообразием видов.")

        assert result["symbiosis_factors"]["biome_type"] == "смешанный лес"
        assert result["symbiosis_factors"]["symbiosis_conditions"] == "благоприятные"
        assert len(result["symbiosis_factors"]["improvement_potential"]) == 2
        assert "посадка новых видов" in result["symbiosis_factors"]["improvement_potential"]

    def test_get_default_environment_data(self):
        """Тест функции получения дефолтных данных."""
        default_data = _get_default_environment_data()

        assert default_data["climate"]["temperature"] == "неопределено"
        assert default_data["environment"]["air_quality"] == "неопределено"
        assert default_data["symbiosis_factors"]["biome_type"] == "неопределено"
        assert default_data["overall_condition"]["ecosystem_health"] == "неопределено"
        assert default_data["confidence"] == 0.0
        assert isinstance(default_data["symbiosis_factors"]["resource_availability"], dict)
        assert isinstance(default_data["symbiosis_factors"]["threats"], list)
        assert isinstance(default_data["symbiosis_factors"]["improvement_potential"], list)
