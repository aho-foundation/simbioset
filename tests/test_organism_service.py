"""
Тесты сервиса для работы с организмами.

Проверяет сохранение, получение и классификацию организмов.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from api.storage.db import DatabaseManager
from api.storage.organism_service import OrganismService


class TestOrganismService:
    """Тесты сервиса для работы с организмами."""

    def setup_method(self):
        """Настройка тестов - создаем временную БД."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        self.db_manager = DatabaseManager(db_path=self.db_path)
        self.db_manager.connect()
        self.db_manager.connection.execute("PRAGMA foreign_keys = ON")

        # Загружаем схему
        schema_path = Path(__file__).parent.parent / "api" / "storage" / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        self.db_manager.connection.executescript(schema_sql)
        self.db_manager.connection.commit()

        self.service = OrganismService(self.db_manager)

        # Создаем тестовые параграфы для использования в тестах
        self._create_test_paragraphs()

    def _create_test_paragraphs(self):
        """Создает тестовые параграфы для использования в тестах."""
        cursor = self.db_manager.connection.cursor()
        from datetime import datetime

        timestamp = int(datetime.now().timestamp() * 1000)

        # Создаем несколько тестовых параграфов
        test_paragraphs = ["para_123", "para_456", "para_789", "para_test", "para_trophic", "para_limit", "para_json"]

        for para_id in test_paragraphs:
            cursor.execute(
                """
                INSERT INTO paragraphs (id, content, document_type, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (para_id, f"Тестовый параграф {para_id}", "knowledge", timestamp),
            )
        self.db_manager.connection.commit()

    def teardown_method(self):
        """Очистка после тестов."""
        if self.db_manager.connection:
            self.db_manager.connection.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_save_organisms_for_paragraph(self):
        """Тест сохранения организмов для параграфа."""
        organisms = [
            {
                "name": "дуб",
                "scientific_name": "Quercus",
                "type": "растение",
                "trophic_level": "producer",
                "biochemical_roles": ["photosynthesis"],
                "metabolic_pathways": ["фотосинтез"],
                "context": "дубы в лесу",
                "classification_confidence": 0.9,
            }
        ]

        organism_ids = self.service.save_organisms_for_paragraph("para_123", organisms)

        assert len(organism_ids) == 1
        assert organism_ids[0].startswith("org_")

        # Проверяем сохранение
        saved_organisms = self.service.get_organisms_for_paragraph("para_123")
        assert len(saved_organisms) == 1
        assert saved_organisms[0]["name"] == "дуб"
        assert saved_organisms[0]["scientific_name"] == "Quercus"
        assert saved_organisms[0]["trophic_level"] == "producer"

    def test_save_organisms_with_internal_ecosystem(self):
        """Тест сохранения организмов с внутренней экосистемой."""
        # Создаем экосистему микробиома
        from api.storage.ecosystem_service import EcosystemService

        ecosystem_service = EcosystemService(self.db_manager)
        microbiome_id = ecosystem_service.create_ecosystem(name="Микробиом кишечника", scale="organ")

        organisms = [
            {
                "name": "человек",
                "type": "животное",
                "internal_ecosystem_id": microbiome_id,
                "trophic_level": "omnivore",
            }
        ]

        organism_ids = self.service.save_organisms_for_paragraph("para_456", organisms)

        # Проверяем связь с внутренней экосистемой
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT internal_ecosystem_id FROM organisms WHERE id = ?", (organism_ids[0],))
        row = cursor.fetchone()
        assert row[0] == microbiome_id

    def test_save_organisms_multiple(self):
        """Тест сохранения нескольких организмов."""
        organisms = [
            {"name": "дуб", "type": "растение", "trophic_level": "producer"},
            {"name": "заяц", "type": "животное", "trophic_level": "primary_consumer"},
            {"name": "червь", "type": "животное", "trophic_level": "decomposer"},
        ]

        organism_ids = self.service.save_organisms_for_paragraph("para_789", organisms)

        assert len(organism_ids) == 3
        saved_organisms = self.service.get_organisms_for_paragraph("para_789")
        assert len(saved_organisms) == 3

    def test_get_organisms_for_paragraph(self):
        """Тест получения организмов для параграфа."""
        organisms = [
            {
                "name": "дуб",
                "type": "растение",
                "trophic_level": "producer",
                "biochemical_roles": ["photosynthesis"],
                "metabolic_pathways": ["фотосинтез"],
                "classification_confidence": 0.9,
            }
        ]

        self.service.save_organisms_for_paragraph("para_test", organisms)
        saved = self.service.get_organisms_for_paragraph("para_test")

        assert len(saved) == 1
        assert saved[0]["name"] == "дуб"
        assert saved[0]["biochemical_roles"] == ["photosynthesis"]
        assert saved[0]["metabolic_pathways"] == ["фотосинтез"]

    def test_get_organisms_by_trophic_level(self):
        """Тест получения организмов по трофическому уровню."""
        organisms = [
            {"name": "дуб", "type": "растение", "trophic_level": "producer", "classification_confidence": 0.9},
            {"name": "заяц", "type": "животное", "trophic_level": "primary_consumer", "classification_confidence": 0.8},
            {"name": "сосна", "type": "растение", "trophic_level": "producer", "classification_confidence": 0.95},
        ]

        self.service.save_organisms_for_paragraph("para_trophic", organisms)

        producers = self.service.get_organisms_by_trophic_level("producer")
        assert len(producers) == 2
        assert {p["name"] for p in producers} == {"дуб", "сосна"}

    def test_get_organisms_by_trophic_level_limit(self):
        """Тест ограничения количества результатов."""
        organisms = [
            {
                "name": f"организм_{i}",
                "type": "растение",
                "trophic_level": "producer",
                "classification_confidence": 0.9 - i * 0.01,
            }
            for i in range(10)
        ]

        self.service.save_organisms_for_paragraph("para_limit", organisms)

        limited = self.service.get_organisms_by_trophic_level("producer", limit=5)
        assert len(limited) == 5

    def test_save_organisms_empty_list(self):
        """Тест сохранения пустого списка организмов."""
        organism_ids = self.service.save_organisms_for_paragraph("para_empty", [])
        assert len(organism_ids) == 0

    def test_get_organisms_json_parsing(self):
        """Тест парсинга JSON полей."""
        organisms = [
            {
                "name": "организм",
                "biochemical_roles": ["photosynthesis", "nitrogen_fixation"],
                "metabolic_pathways": ["путь 1", "путь 2"],
            }
        ]

        self.service.save_organisms_for_paragraph("para_json", organisms)
        saved = self.service.get_organisms_for_paragraph("para_json")

        assert len(saved) == 1
        assert isinstance(saved[0]["biochemical_roles"], list)
        assert len(saved[0]["biochemical_roles"]) == 2
        assert isinstance(saved[0]["metabolic_pathways"], list)
        assert len(saved[0]["metabolic_pathways"]) == 2
