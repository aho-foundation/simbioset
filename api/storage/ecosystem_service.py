"""Сервис для работы с экосистемами.

Экосистема = большой организм (метаболизм, гомеостаз, симбиотические связи).
Экосистемы могут быть вложенными (экосистема внутри экосистемы).
"""

import uuid
import json
from typing import List, Dict, Any, Optional
from api.storage.db import DatabaseManager
from api.logger import root_logger

log = root_logger.debug


class EcosystemService:
    """Сервис для работы с экосистемами."""

    def __init__(self, db_manager: DatabaseManager):
        """Инициализация сервиса.

        Args:
            db_manager: Менеджер базы данных SQLite
        """
        self.db_manager = db_manager
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Создает таблицы если их нет."""
        from pathlib import Path

        # Try multiple possible paths for schema.sql
        possible_paths = [
            Path(__file__).parent / "schema.sql",
            self.db_manager.db_path.parent / "api" / "storage" / "schema.sql",
            Path("api/storage/schema.sql"),
        ]

        for schema_path in possible_paths:
            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                if self.db_manager.connection:
                    self.db_manager.connection.executescript(schema_sql)
                    self.db_manager.connection.commit()
                break

    def create_ecosystem(
        self,
        name: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        parent_ecosystem_id: Optional[str] = None,
        scale: str = "habitat",
        metabolic_characteristics: Optional[Dict[str, Any]] = None,
        homeostasis_indicators: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Создает новую экосистему.

        Args:
            name: Название экосистемы
            description: Описание
            location: Географическое местоположение
            parent_ecosystem_id: Родительская экосистема (для вложенных)
            scale: Масштаб (molecular, cellular, tissue, organ, organism, micro_habitat, habitat, landscape, regional, continental, global, planetary)
            metabolic_characteristics: Характеристики метаболизма
            homeostasis_indicators: Показатели гомеостаза

        Returns:
            ID созданной экосистемы
        """
        ecosystem_id = f"eco_{uuid.uuid4()}"
        cursor = self.db_manager.connection.cursor()

        metabolic_json = json.dumps(metabolic_characteristics) if metabolic_characteristics else None
        homeostasis_json = json.dumps(homeostasis_indicators) if homeostasis_indicators else None

        cursor.execute(
            """
            INSERT INTO ecosystems 
            (id, name, description, location, parent_ecosystem_id, scale,
             metabolic_characteristics, homeostasis_indicators)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ecosystem_id,
                name,
                description,
                location,
                parent_ecosystem_id,
                scale,
                metabolic_json,
                homeostasis_json,
            ),
        )

        self.db_manager.connection.commit()
        log(f"✅ Создана экосистема {name} (ID: {ecosystem_id})")

        return ecosystem_id

    def get_ecosystem(self, ecosystem_id: str) -> Optional[Dict[str, Any]]:
        """Получает экосистему по ID.

        Args:
            ecosystem_id: ID экосистемы

        Returns:
            Словарь с информацией об экосистеме или None
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT * FROM ecosystems WHERE id = ?", (ecosystem_id,))
        row = cursor.fetchone()

        if not row:
            return None

        row_dict = dict(row)
        # Парсим JSON поля
        if row_dict.get("metabolic_characteristics"):
            try:
                row_dict["metabolic_characteristics"] = json.loads(row_dict["metabolic_characteristics"])
            except (json.JSONDecodeError, TypeError):
                row_dict["metabolic_characteristics"] = {}
        else:
            row_dict["metabolic_characteristics"] = {}

        if row_dict.get("homeostasis_indicators"):
            try:
                row_dict["homeostasis_indicators"] = json.loads(row_dict["homeostasis_indicators"])
            except (json.JSONDecodeError, TypeError):
                row_dict["homeostasis_indicators"] = {}
        else:
            row_dict["homeostasis_indicators"] = {}

        return row_dict

    def link_organism_to_ecosystem(
        self,
        organism_id: str,
        ecosystem_id: str,
        role_in_ecosystem: Optional[str] = None,
        interaction_type: Optional[str] = None,
    ) -> bool:
        """Связывает организм с экосистемой.

        Args:
            organism_id: ID организма
            ecosystem_id: ID экосистемы
            role_in_ecosystem: Роль организма в экосистеме
            interaction_type: Тип взаимодействия (symbiotic, parasitic, competitive, neutral)

        Returns:
            True если успешно
        """
        cursor = self.db_manager.connection.cursor()
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO organism_ecosystems 
                (organism_id, ecosystem_id, role_in_ecosystem, interaction_type)
                VALUES (?, ?, ?, ?)
                """,
                (organism_id, ecosystem_id, role_in_ecosystem, interaction_type),
            )
            self.db_manager.connection.commit()
            log(f"✅ Организм {organism_id} связан с экосистемой {ecosystem_id}")
            return True
        except Exception as e:
            log(f"⚠️ Ошибка при связывании организма с экосистемой: {e}")
            return False

    def get_ecosystems_for_organism(self, organism_id: str) -> List[Dict[str, Any]]:
        """Получает все экосистемы, в которых участвует организм.

        Args:
            organism_id: ID организма

        Returns:
            Список экосистем
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT e.*, oe.role_in_ecosystem, oe.interaction_type
            FROM ecosystems e
            JOIN organism_ecosystems oe ON e.id = oe.ecosystem_id
            WHERE oe.organism_id = ?
            """,
            (organism_id,),
        )

        rows = cursor.fetchall()
        result = []

        for row in rows:
            row_dict = dict(row)
            # Парсим JSON поля
            if row_dict.get("metabolic_characteristics"):
                try:
                    row_dict["metabolic_characteristics"] = json.loads(row_dict["metabolic_characteristics"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["metabolic_characteristics"] = {}
            else:
                row_dict["metabolic_characteristics"] = {}

            if row_dict.get("homeostasis_indicators"):
                try:
                    row_dict["homeostasis_indicators"] = json.loads(row_dict["homeostasis_indicators"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["homeostasis_indicators"] = {}
            else:
                row_dict["homeostasis_indicators"] = {}

            result.append(row_dict)

        return result

    def get_organisms_in_ecosystem(self, ecosystem_id: str) -> List[Dict[str, Any]]:
        """Получает все организмы в экосистеме.

        Args:
            ecosystem_id: ID экосистемы

        Returns:
            Список организмов
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT o.*, oe.role_in_ecosystem, oe.interaction_type
            FROM organisms o
            JOIN organism_ecosystems oe ON o.id = oe.organism_id
            WHERE oe.ecosystem_id = ?
            """,
            (ecosystem_id,),
        )

        rows = cursor.fetchall()
        result = []

        for row in rows:
            row_dict = dict(row)
            # Парсим JSON поля
            if row_dict.get("biochemical_roles"):
                try:
                    row_dict["biochemical_roles"] = json.loads(row_dict["biochemical_roles"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["biochemical_roles"] = []
            else:
                row_dict["biochemical_roles"] = []

            if row_dict.get("metabolic_pathways"):
                try:
                    row_dict["metabolic_pathways"] = json.loads(row_dict["metabolic_pathways"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["metabolic_pathways"] = []
            else:
                row_dict["metabolic_pathways"] = []

            result.append(row_dict)

        return result
