"""
Тесты классификатора организмов.

Проверяет классификацию организмов по биологической роли.
"""

import pytest
from unittest.mock import patch, AsyncMock
from api.classify.organism_classifier import (
    classify_organism_role,
    classify_organisms_batch,
    TrophicLevel,
    BiochemicalRole,
)


class TestOrganismClassifier:
    """Тесты классификатора организмов."""

    @pytest.mark.asyncio
    @patch("api.classify.organism_classifier.call_llm_with_retry")
    async def test_classify_organism_role_producer(self, mock_llm):
        """Тест классификации продуцента."""
        mock_llm.return_value = """{
            "trophic_level": "producer",
            "biochemical_roles": ["photosynthesis"],
            "metabolic_pathways": ["фотосинтез", "гликолиз"],
            "confidence": 0.9
        }"""

        result = await classify_organism_role("дуб", "растение", "дубы производят кислород")

        assert result["trophic_level"] == "producer"
        assert "photosynthesis" in result["biochemical_roles"]
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    @patch("api.classify.organism_classifier.call_llm_with_retry")
    async def test_classify_organism_role_consumer(self, mock_llm):
        """Тест классификации консумента."""
        mock_llm.return_value = """{
            "trophic_level": "primary_consumer",
            "biochemical_roles": ["herbivory"],
            "metabolic_pathways": ["переваривание целлюлозы"],
            "confidence": 0.8
        }"""

        result = await classify_organism_role("заяц", "животное", "зайцы едят траву")

        assert result["trophic_level"] == "primary_consumer"
        assert "herbivory" in result["biochemical_roles"]

    @pytest.mark.asyncio
    @patch("api.classify.organism_classifier.call_llm_with_retry")
    async def test_classify_organism_role_decomposer(self, mock_llm):
        """Тест классификации редуцента."""
        mock_llm.return_value = """{
            "trophic_level": "decomposer",
            "biochemical_roles": ["decomposition"],
            "metabolic_pathways": ["разложение органики"],
            "confidence": 0.95
        }"""

        result = await classify_organism_role("дождевой червь", "животное", "черви разлагают органику")

        assert result["trophic_level"] == "decomposer"
        assert "decomposition" in result["biochemical_roles"]

    @pytest.mark.asyncio
    @patch("api.classify.organism_classifier.call_llm_with_retry")
    async def test_classify_organism_role_multiple_roles(self, mock_llm):
        """Тест классификации с множественными ролями."""
        mock_llm.return_value = """{
            "trophic_level": "omnivore",
            "biochemical_roles": ["herbivory", "carnivory"],
            "metabolic_pathways": ["всеядность"],
            "confidence": 0.85
        }"""

        result = await classify_organism_role("медведь", "животное", "медведи всеядные")

        assert result["trophic_level"] == "omnivore"
        assert len(result["biochemical_roles"]) == 2
        assert "herbivory" in result["biochemical_roles"]
        assert "carnivory" in result["biochemical_roles"]

    @pytest.mark.asyncio
    @patch("api.classify.organism_classifier.call_llm_with_retry")
    async def test_classify_organisms_batch(self, mock_llm):
        """Тест пакетной классификации организмов."""
        mock_llm.side_effect = [
            """{"trophic_level": "producer", "biochemical_roles": ["photosynthesis"], "metabolic_pathways": [], "confidence": 0.9}""",
            """{"trophic_level": "primary_consumer", "biochemical_roles": ["herbivory"], "metabolic_pathways": [], "confidence": 0.8}""",
        ]

        organisms = [
            {"name": "дуб", "type": "растение", "context": "дубы"},
            {"name": "заяц", "type": "животное", "context": "зайцы"},
        ]

        classified = await classify_organisms_batch(organisms)

        assert len(classified) == 2
        assert classified[0]["trophic_level"] == "producer"
        assert classified[1]["trophic_level"] == "primary_consumer"
        assert "classification_confidence" in classified[0]

    @pytest.mark.asyncio
    @patch("api.classify.organism_classifier.call_llm_with_retry")
    async def test_classify_organism_role_invalid_json(self, mock_llm):
        """Тест обработки невалидного JSON."""
        mock_llm.return_value = "Не JSON ответ"

        result = await classify_organism_role("организм", "животное", "контекст")

        assert result["trophic_level"] == "unknown"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    @patch("api.classify.organism_classifier.call_llm_with_retry")
    async def test_classify_organism_role_all_trophic_levels(self, mock_llm):
        """Тест всех трофических уровней."""
        trophic_levels = [
            "producer",
            "primary_consumer",
            "secondary_consumer",
            "tertiary_consumer",
            "decomposer",
            "omnivore",
        ]

        for level in trophic_levels:
            mock_llm.return_value = f"""{{"trophic_level": "{level}", "biochemical_roles": [], "metabolic_pathways": [], "confidence": 0.8}}"""
            result = await classify_organism_role("организм", "животное", "контекст")
            assert result["trophic_level"] == level
