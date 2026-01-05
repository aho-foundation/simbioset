"""
Тесты детектора организмов.

Проверяет обнаружение организмов в тексте.
"""

import pytest
from unittest.mock import patch, AsyncMock
from api.detect.organism_detector import detect_organisms


class TestOrganismDetector:
    """Тесты детектора организмов."""

    @pytest.mark.asyncio
    @patch("api.llm.call_llm")
    async def test_detect_organisms_basic(self, mock_llm):
        """Тест базового обнаружения организмов."""
        mock_llm.return_value = """[
            {
                "name": "дуб",
                "scientific_name": "Quercus",
                "type": "растение",
                "context": "дубы в лесу производят кислород"
            }
        ]"""

        organisms = await detect_organisms("В лесу растут дубы.")

        assert len(organisms) == 1
        assert organisms[0]["name"] == "дуб"
        assert organisms[0]["scientific_name"] == "Quercus"
        assert organisms[0]["type"] == "растение"

    @pytest.mark.asyncio
    @patch("api.llm.call_llm")
    async def test_detect_organisms_multiple(self, mock_llm):
        """Тест обнаружения нескольких организмов."""
        mock_llm.return_value = """[
            {
                "name": "дуб",
                "type": "растение",
                "context": "дубы в лесу"
            },
            {
                "name": "дождевой червь",
                "scientific_name": "Lumbricina",
                "type": "животное",
                "context": "черви разлагают органику"
            }
        ]"""

        organisms = await detect_organisms("В лесу растут дубы, а черви разлагают органику.")

        assert len(organisms) == 2
        assert organisms[0]["name"] == "дуб"
        assert organisms[1]["name"] == "дождевой червь"

    @pytest.mark.asyncio
    @patch("api.llm.call_llm")
    async def test_detect_organisms_all_types(self, mock_llm):
        """Тест обнаружения организмов всех типов."""
        mock_llm.return_value = """[
            {"name": "дуб", "type": "растение"},
            {"name": "заяц", "type": "животное"},
            {"name": "подберезовик", "type": "гриб"},
            {"name": "лактобактерия", "type": "бактерия"},
            {"name": "планктон", "type": "микроорганизм"}
        ]"""

        organisms = await detect_organisms("Различные организмы.")

        assert len(organisms) == 5
        types = {org["type"] for org in organisms}
        assert types == {"растение", "животное", "гриб", "бактерия", "микроорганизм"}

    @pytest.mark.asyncio
    @patch("api.llm.call_llm")
    async def test_detect_organisms_empty(self, mock_llm):
        """Тест обработки пустого результата."""
        mock_llm.return_value = "[]"

        organisms = await detect_organisms("Обычный текст без организмов.")

        assert len(organisms) == 0

    @pytest.mark.asyncio
    @patch("api.llm.call_llm")
    async def test_detect_organisms_invalid_json(self, mock_llm):
        """Тест обработки невалидного JSON."""
        mock_llm.return_value = "Не JSON ответ"

        organisms = await detect_organisms("Текст с организмами.")

        assert len(organisms) == 0

    @pytest.mark.asyncio
    @patch("api.llm.call_llm")
    async def test_detect_organisms_without_scientific_name(self, mock_llm):
        """Тест обнаружения организмов без научного названия."""
        mock_llm.return_value = """[
            {
                "name": "дуб",
                "type": "растение",
                "context": "дубы в лесу"
            }
        ]"""

        organisms = await detect_organisms("В лесу растут дубы.")

        assert len(organisms) == 1
        assert organisms[0]["scientific_name"] is None
