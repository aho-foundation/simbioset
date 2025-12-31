"""
Тесты детектора экосистем.

Проверяет обнаружение экосистем в тексте с использованием данных локализации.
"""

import pytest
from unittest.mock import patch, AsyncMock
from api.detect.ecosystem_scaler import detect_ecosystems
from api.detect.localize import extract_location_and_time


class TestEcosystemDetector:
    """Тесты детектора экосистем."""

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_basic(self, mock_llm):
        """Тест базового обнаружения экосистем."""
        mock_llm.return_value = """[
            {
                "name": "лес",
                "description": "смешанный лес",
                "location": "Московская область",
                "scale": "habitat",
                "parent_ecosystem": null,
                "context": "лес производит кислород"
            }
        ]"""

        ecosystems = await detect_ecosystems("В лесу обитают различные организмы.")

        assert len(ecosystems) == 1
        assert ecosystems[0]["name"] == "лес"
        assert ecosystems[0]["scale"] == "habitat"
        assert ecosystems[0]["location"] == "Московская область"

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_with_location_data(self, mock_llm):
        """Тест обнаружения экосистем с данными локализации."""
        mock_llm.return_value = """[
            {
                "name": "лес",
                "description": "смешанный лес",
                "location": "Московская область",
                "scale": "habitat",
                "parent_ecosystem": null,
                "context": "лес производит кислород"
            }
        ]"""

        location_data = {"location": "Московская область", "time_reference": "2024 год"}
        ecosystems = await detect_ecosystems("В лесу обитают различные организмы.", location_data=location_data)

        assert len(ecosystems) == 1
        assert ecosystems[0]["location"] == "Московская область"
        assert ecosystems[0]["time_reference"] == "2024 год"

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_auto_location(self, mock_llm):
        """Тест автоматического извлечения локализации."""
        mock_llm.return_value = """[
            {
                "name": "лес",
                "scale": "habitat",
                "location": null,
                "context": "лес производит кислород"
            }
        ]"""

        # extract_location_and_time должен быть вызван автоматически
        ecosystems = await detect_ecosystems("В лесу Московской области обитают организмы.")

        assert len(ecosystems) == 1
        # Локализация должна быть извлечена из текста
        assert ecosystems[0]["name"] == "лес"

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_multiple(self, mock_llm):
        """Тест обнаружения нескольких экосистем."""
        mock_llm.return_value = """[
            {
                "name": "лес",
                "scale": "habitat",
                "location": "Московская область",
                "context": "лес производит кислород"
            },
            {
                "name": "микробиом кишечника",
                "scale": "organ",
                "location": null,
                "context": "микробиом помогает переваривать пищу"
            }
        ]"""

        ecosystems = await detect_ecosystems(
            "В лесу обитают организмы. Микробиом кишечника помогает переваривать пищу."
        )

        assert len(ecosystems) == 2
        assert ecosystems[0]["name"] == "лес"
        assert ecosystems[1]["name"] == "микробиом кишечника"
        assert ecosystems[0]["scale"] == "habitat"
        assert ecosystems[1]["scale"] == "organ"

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_nested(self, mock_llm):
        """Тест обнаружения вложенных экосистем."""
        mock_llm.return_value = """[
            {
                "name": "лес",
                "scale": "habitat",
                "parent_ecosystem": "биосфера",
                "context": "лес в биосфере"
            }
        ]"""

        ecosystems = await detect_ecosystems("Лес является частью биосферы.")

        assert len(ecosystems) == 1
        assert ecosystems[0]["parent_ecosystem"] == "биосфера"

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_empty(self, mock_llm):
        """Тест обработки пустого результата."""
        mock_llm.return_value = "[]"

        ecosystems = await detect_ecosystems("Обычный текст без экосистем.")

        assert len(ecosystems) == 0

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_invalid_json(self, mock_llm):
        """Тест обработки невалидного JSON."""
        mock_llm.return_value = "Не JSON ответ"

        ecosystems = await detect_ecosystems("Текст с экосистемами.")

        assert len(ecosystems) == 0

    @pytest.mark.asyncio
    @patch("api.detect.ecosystem_scaler.call_llm")
    async def test_detect_ecosystems_all_scales(self, mock_llm):
        """Тест всех масштабов экосистем."""
        mock_llm.return_value = """[
            {"name": "молекула", "scale": "molecular"},
            {"name": "клетка", "scale": "cellular"},
            {"name": "ткань", "scale": "tissue"},
            {"name": "кишечник", "scale": "organ"},
            {"name": "организм", "scale": "organism"},
            {"name": "улей", "scale": "micro_habitat"},
            {"name": "лес", "scale": "habitat"},
            {"name": "ландшафт", "scale": "landscape"},
            {"name": "регион", "scale": "regional"},
            {"name": "континент", "scale": "continental"},
            {"name": "биосфера", "scale": "global"},
            {"name": "планета", "scale": "planetary"}
        ]"""

        ecosystems = await detect_ecosystems("Различные экосистемы.")

        assert len(ecosystems) == 12
        scales = {eco["scale"] for eco in ecosystems}
        assert scales == {
            "molecular",
            "cellular",
            "tissue",
            "organ",
            "organism",
            "micro_habitat",
            "habitat",
            "landscape",
            "regional",
            "continental",
            "global",
            "planetary",
        }
