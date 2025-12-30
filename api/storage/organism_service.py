"""Сервис для сохранения организмов в БД."""

import uuid
import json
from typing import List, Dict, Any, Optional
from api.storage.db import DatabaseManagerBase
from api.logger import root_logger

log = root_logger.debug


class OrganismService:
    """Сервис для сохранения организмов в БД."""

    def __init__(self, db_manager: DatabaseManagerBase):
        """Инициализация сервиса.

        Args:
            db_manager: Менеджер базы данных (DatabaseManager или PostgreSQLManager)
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

    def save_organisms_for_paragraph(
        self,
        paragraph_id: str,
        organisms: List[Dict[str, Any]],
    ) -> List[str]:
        """Сохраняет организмы для параграфа в БД.

        Args:
            paragraph_id: ID параграфа
            organisms: Список словарей с информацией об организмах

        Returns:
            Список ID сохраненных организмов
        """
        if not organisms:
            return []

        cursor = self.db_manager.connection.cursor()
        organism_ids = []

        for org in organisms:
            organism_id = f"org_{uuid.uuid4()}"
            organism_ids.append(organism_id)

            # Подготавливаем данные
            biochemical_roles_json = json.dumps(org.get("biochemical_roles", []))
            metabolic_pathways_json = json.dumps(org.get("metabolic_pathways", []))

            cursor.execute(
                """
                INSERT INTO organisms 
                (id, name, scientific_name, type, trophic_level, 
                 biochemical_roles, metabolic_pathways, internal_ecosystem_id,
                 paragraph_id, context, classification_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    organism_id,
                    org.get("name", ""),
                    org.get("scientific_name"),
                    org.get("type", "другое"),
                    org.get("trophic_level", "unknown"),
                    biochemical_roles_json,
                    metabolic_pathways_json,
                    org.get("internal_ecosystem_id"),  # Ссылка на внутреннюю экосистему (микробиом)
                    paragraph_id,
                    org.get("context", ""),
                    org.get("classification_confidence", 0.0),
                ),
            )

        self.db_manager.connection.commit()
        log(f"✅ Сохранено {len(organism_ids)} организмов для параграфа {paragraph_id}")

        return organism_ids

    def get_organisms_for_paragraph(self, paragraph_id: str) -> List[Dict[str, Any]]:
        """Получает организмы для параграфа из БД.

        Args:
            paragraph_id: ID параграфа

        Returns:
            Список словарей с информацией об организмах
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM organisms WHERE paragraph_id = ?
            ORDER BY classification_confidence DESC
            """,
            (paragraph_id,),
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

    def get_organisms_by_trophic_level(self, trophic_level: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Получает организмы по трофическому уровню.

        Args:
            trophic_level: Трофический уровень
            limit: Максимальное количество результатов

        Returns:
            Список организмов
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM organisms 
            WHERE trophic_level = ?
            ORDER BY classification_confidence DESC
            LIMIT ?
            """,
            (trophic_level, limit),
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
