"""
Тесты обработчика изображений.

Проверяет обработку изображений, извлечение организмов, экосистем и данных об окружающей среде.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO
from PIL import Image
from api.detect.image_processor import ImageProcessor, ImageType


class TestImageProcessor:
    """Тесты обработчика изображений."""

    def setup_method(self):
        """Настройка тестов."""
        self.processor = ImageProcessor()

    @pytest.mark.asyncio
    @patch("api.detect.image_processor.ImageProcessor._analyze_image_with_llm")
    @patch("api.detect.image_processor.ImageProcessor._extract_organisms_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_ecosystems_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_location_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_environment_from_description")
    async def test_process_image_basic(
        self,
        mock_env,
        mock_location,
        mock_ecosystems,
        mock_organisms,
        mock_analyze,
    ):
        """Тест базовой обработки изображения."""
        # Создаем тестовое изображение
        img = Image.new("RGB", (100, 100), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        image_data = img_bytes.read()

        # Настраиваем моки
        mock_analyze.return_value = "Описание изображения: летний лес с дубами и птицами."
        mock_organisms.return_value = [{"name": "дуб", "type": "растение", "category": "дерево"}]
        mock_ecosystems.return_value = [{"name": "лес", "scale": "habitat"}]
        mock_location.return_value = {"location": "Московская область", "time_reference": "лето 2024"}
        mock_env.return_value = {
            "climate": {"temperature": "умеренная", "season": "лето"},
            "environment": {"air_quality": "хорошая"},
            "symbiosis_factors": {"biome_type": "лес"},
            "overall_condition": {"ecosystem_health": "здоровая"},
            "confidence": 0.8,
        }

        result = await self.processor.process_image(image_data, filename="test.jpg")

        assert result["image_type"] == ImageType.PHOTO.value
        assert len(result["detected_organisms"]) == 1
        assert len(result["detected_ecosystems"]) == 1
        assert result["location"] == "Московская область"
        assert "environment" in result
        assert result["environment"]["climate"]["season"] == "лето"
        assert result["environment"]["symbiosis_factors"]["biome_type"] == "лес"

    @pytest.mark.asyncio
    @patch("api.detect.image_processor.ImageProcessor._analyze_image_with_llm")
    @patch("api.detect.image_processor.ImageProcessor._extract_organisms_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_ecosystems_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_location_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_environment_from_description")
    async def test_process_image_with_environment_data(
        self,
        mock_env,
        mock_location,
        mock_ecosystems,
        mock_organisms,
        mock_analyze,
    ):
        """Тест обработки изображения с полными данными об окружающей среде."""
        # Создаем тестовое изображение
        img = Image.new("RGB", (200, 200), color="green")
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        image_data = img_bytes.read()

        # Настраиваем моки
        mock_analyze.return_value = "Зимний лес со снегом и низкой температурой."
        mock_organisms.return_value = []
        mock_ecosystems.return_value = [{"name": "лес", "scale": "habitat"}]
        mock_location.return_value = {"location": "Сибирь", "time_reference": "зима 2024"}
        mock_env.return_value = {
            "climate": {
                "temperature": "холодная (-10°C)",
                "humidity": "средняя",
                "precipitation": "снег",
                "wind": "умеренный",
                "season": "зима",
                "lighting": "пасмурно",
            },
            "environment": {
                "air_quality": "хорошая",
                "water_quality": "неопределено",
                "soil_condition": "хорошая",
                "pollution_level": "низкий",
                "anthropogenic_impact": "низкий",
            },
            "symbiosis_factors": {
                "biome_type": "тайга",
                "resource_availability": {
                    "water": "доступна",
                    "nutrients": "ограничены",
                    "light": "ограничен",
                    "shelter": "доступно",
                },
                "threats": ["холод", "недостаток света"],
                "improvement_potential": ["улучшение укрытий"],
                "symbiosis_conditions": "нейтральные",
            },
            "overall_condition": {
                "ecosystem_health": "здоровая",
                "biodiversity": "среднее",
                "stability": "стабильная",
            },
            "confidence": 0.75,
        }

        result = await self.processor.process_image(image_data, filename="winter_forest.jpg")

        assert result["image_type"] == ImageType.PHOTO.value
        assert "environment" in result
        env = result["environment"]
        assert env["climate"]["season"] == "зима"
        assert env["climate"]["temperature"] == "холодная (-10°C)"
        assert env["symbiosis_factors"]["biome_type"] == "тайга"
        assert len(env["symbiosis_factors"]["threats"]) == 2
        assert env["overall_condition"]["biodiversity"] == "среднее"
        assert env["confidence"] == 0.75

    @pytest.mark.asyncio
    @patch("api.detect.image_processor.ImageProcessor._analyze_image_with_llm")
    @patch("api.detect.image_processor.ImageProcessor._extract_organisms_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_ecosystems_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_location_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_environment_from_description")
    async def test_process_image_environment_error_handling(
        self,
        mock_env,
        mock_location,
        mock_ecosystems,
        mock_organisms,
        mock_analyze,
    ):
        """Тест обработки ошибок при извлечении данных об окружающей среде."""
        # Создаем тестовое изображение
        img = Image.new("RGB", (150, 150), color="blue")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        image_data = img_bytes.read()

        # Настраиваем моки
        mock_analyze.return_value = "Описание изображения."
        mock_organisms.return_value = []
        mock_ecosystems.return_value = []
        mock_location.return_value = {}
        mock_env.return_value = {}  # Пустой результат при ошибке

        result = await self.processor.process_image(image_data)

        assert "environment" in result
        assert result["environment"] == {}  # Пустой словарь при ошибке

    @pytest.mark.asyncio
    @patch("api.detect.image_processor.ImageProcessor._analyze_image_with_llm")
    @patch("api.detect.image_processor.ImageProcessor._extract_organisms_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_ecosystems_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_location_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_environment_from_description")
    async def test_process_image_polluted_environment(
        self,
        mock_env,
        mock_location,
        mock_ecosystems,
        mock_organisms,
        mock_analyze,
    ):
        """Тест обработки изображения с загрязненной средой."""
        # Создаем тестовое изображение
        img = Image.new("RGB", (100, 100), color="gray")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        image_data = img_bytes.read()

        # Настраиваем моки
        mock_analyze.return_value = "Загрязненная городская среда с дымом и мусором."
        mock_organisms.return_value = []
        mock_ecosystems.return_value = [{"name": "городская среда", "scale": "habitat"}]
        mock_location.return_value = {"location": "Москва", "time_reference": "2024"}
        mock_env.return_value = {
            "climate": {"temperature": "умеренная", "season": "весна"},
            "environment": {
                "air_quality": "плохая",
                "water_quality": "плохая",
                "soil_condition": "плохая",
                "pollution_level": "высокий",
                "anthropogenic_impact": "высокий",
            },
            "symbiosis_factors": {
                "biome_type": "городская среда",
                "resource_availability": {
                    "water": "ограничена",
                    "nutrients": "ограничены",
                    "light": "доступен",
                    "shelter": "ограничено",
                },
                "threats": ["загрязнение воздуха", "загрязнение воды"],
                "improvement_potential": ["очистка воздуха", "очистка воды"],
                "symbiosis_conditions": "неблагоприятные",
            },
            "overall_condition": {
                "ecosystem_health": "деградированная",
                "biodiversity": "низкое",
                "stability": "нестабильная",
            },
            "confidence": 0.9,
        }

        result = await self.processor.process_image(image_data, filename="polluted.jpg")

        assert "environment" in result
        env = result["environment"]
        assert env["environment"]["pollution_level"] == "высокий"
        assert env["environment"]["air_quality"] == "плохая"
        assert env["overall_condition"]["ecosystem_health"] == "деградированная"
        assert len(env["symbiosis_factors"]["improvement_potential"]) > 0

    @pytest.mark.asyncio
    @patch("api.detect.image_processor.ImageProcessor._analyze_image_with_llm")
    @patch("api.detect.image_processor.ImageProcessor._extract_organisms_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_ecosystems_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_location_from_description")
    @patch("api.detect.image_processor.ImageProcessor._extract_environment_from_description")
    async def test_process_image_metadata_included(
        self,
        mock_env,
        mock_location,
        mock_ecosystems,
        mock_organisms,
        mock_analyze,
    ):
        """Тест, что метаданные изображения включены в результат."""
        # Создаем тестовое изображение
        img = Image.new("RGB", (300, 200), color="yellow")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        image_data = img_bytes.read()

        # Настраиваем моки
        mock_analyze.return_value = "Описание."
        mock_organisms.return_value = []
        mock_ecosystems.return_value = []
        mock_location.return_value = {}
        mock_env.return_value = {
            "climate": {},
            "environment": {},
            "symbiosis_factors": {},
            "overall_condition": {},
            "confidence": 0.5,
        }

        result = await self.processor.process_image(image_data)

        assert "width" in result
        assert "height" in result
        assert "format" in result
        assert "base64" in result
        assert result["width"] == 300
        assert result["height"] == 200

    def test_load_prompt(self):
        """Тест загрузки промпта из файла."""
        prompt = self.processor._load_prompt("image_analysis_vision.txt")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_load_prompt_nonexistent(self):
        """Тест загрузки несуществующего промпта (fallback)."""
        prompt = self.processor._load_prompt("nonexistent_prompt.txt")
        assert isinstance(prompt, str)
        assert len(prompt) > 0  # Должен вернуться fallback промпт
