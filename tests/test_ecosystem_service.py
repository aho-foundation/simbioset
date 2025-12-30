"""
Тесты сервиса для работы с экосистемами.

Проверяет создание, связывание и получение экосистем.
"""

import pytest
import tempfile
import os
from pathlib import Path
from api.storage.db import DatabaseManager
from api.storage.ecosystem_service import EcosystemService


class TestEcosystemService:
    """Тесты сервиса для работы с экосистемами."""

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

        self.service = EcosystemService(self.db_manager)

    def teardown_method(self):
        """Очистка после тестов."""
        if self.db_manager.connection:
            self.db_manager.connection.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_create_ecosystem(self):
        """Тест создания экосистемы."""
        ecosystem_id = self.service.create_ecosystem(
            name="Лес",
            description="Смешанный лес",
            location="Московская область",
            scale="habitat",
        )

        assert ecosystem_id.startswith("eco_")
        ecosystem = self.service.get_ecosystem(ecosystem_id)
        assert ecosystem is not None
        assert ecosystem["name"] == "Лес"
        assert ecosystem["description"] == "Смешанный лес"
        assert ecosystem["location"] == "Московская область"
        assert ecosystem["scale"] == "habitat"

    def test_create_ecosystem_with_metadata(self):
        """Тест создания экосистемы с метаданными."""
        metabolic = {"primary_functions": ["фотосинтез", "круговорот веществ"]}
        homeostasis = {"stability": 0.8, "biodiversity": "high"}

        ecosystem_id = self.service.create_ecosystem(
            name="Лес",
            scale="habitat",
            metabolic_characteristics=metabolic,
            homeostasis_indicators=homeostasis,
        )

        ecosystem = self.service.get_ecosystem(ecosystem_id)
        assert ecosystem["metabolic_characteristics"] == metabolic
        assert ecosystem["homeostasis_indicators"] == homeostasis

    def test_create_nested_ecosystem(self):
        """Тест создания вложенной экосистемы."""
        parent_id = self.service.create_ecosystem(name="Биосфера", scale="global")
        child_id = self.service.create_ecosystem(name="Лес", scale="habitat", parent_ecosystem_id=parent_id)

        child = self.service.get_ecosystem(child_id)
        assert child["parent_ecosystem_id"] == parent_id

    def test_get_ecosystem_not_found(self):
        """Тест получения несуществующей экосистемы."""
        ecosystem = self.service.get_ecosystem("nonexistent_id")
        assert ecosystem is None

    def test_link_organism_to_ecosystem(self):
        """Тест связывания организма с экосистемой."""
        # Создаем экосистему и организм
        ecosystem_id = self.service.create_ecosystem(name="Лес", scale="habitat")

        # Создаем организм через organism_service
        from api.storage.organism_service import OrganismService

        organism_service = OrganismService(self.db_manager)
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            ("org_test", "дуб", "растение"),
        )
        self.db_manager.connection.commit()

        # Связываем
        success = self.service.link_organism_to_ecosystem(
            organism_id="org_test",
            ecosystem_id=ecosystem_id,
            role_in_ecosystem="продуцент",
            interaction_type="symbiotic",
        )

        assert success is True

        # Проверяем связь
        organisms = self.service.get_organisms_in_ecosystem(ecosystem_id)
        assert len(organisms) == 1
        assert organisms[0]["name"] == "дуб"
        assert organisms[0]["role_in_ecosystem"] == "продуцент"

    def test_get_ecosystems_for_organism(self):
        """Тест получения экосистем для организма."""
        # Создаем экосистемы
        forest_id = self.service.create_ecosystem(name="Лес", scale="habitat")
        meadow_id = self.service.create_ecosystem(name="Луг", scale="habitat")

        # Создаем организм
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            ("org_bee", "пчела", "животное"),
        )
        self.db_manager.connection.commit()

        # Связываем организм с обеими экосистемами
        self.service.link_organism_to_ecosystem("org_bee", forest_id, "опылитель")
        self.service.link_organism_to_ecosystem("org_bee", meadow_id, "опылитель")

        # Получаем экосистемы для организма
        ecosystems = self.service.get_ecosystems_for_organism("org_bee")
        assert len(ecosystems) == 2
        ecosystem_names = {eco["name"] for eco in ecosystems}
        assert ecosystem_names == {"Лес", "Луг"}

    def test_get_organisms_in_ecosystem(self):
        """Тест получения организмов в экосистеме."""
        ecosystem_id = self.service.create_ecosystem(name="Лес", scale="habitat")

        # Создаем организмы
        cursor = self.db_manager.connection.cursor()
        cursor.executemany(
            "INSERT INTO organisms (id, name, type) VALUES (?, ?, ?)",
            [("org_1", "дуб", "растение"), ("org_2", "сосна", "растение")],
        )
        self.db_manager.connection.commit()

        # Связываем организмы с экосистемой
        self.service.link_organism_to_ecosystem("org_1", ecosystem_id, "продуцент")
        self.service.link_organism_to_ecosystem("org_2", ecosystem_id, "продуцент")

        # Получаем организмы
        organisms = self.service.get_organisms_in_ecosystem(ecosystem_id)
        assert len(organisms) == 2
        organism_names = {org["name"] for org in organisms}
        assert organism_names == {"дуб", "сосна"}

    def test_all_scales(self):
        """Тест создания экосистем всех масштабов."""
        scales = [
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
        ]

        for scale in scales:
            ecosystem_id = self.service.create_ecosystem(name=f"Экосистема {scale}", scale=scale)
            ecosystem = self.service.get_ecosystem(ecosystem_id)
            assert ecosystem["scale"] == scale
