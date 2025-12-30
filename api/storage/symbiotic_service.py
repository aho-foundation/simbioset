"""Сервис для сохранения симбиотических связей между организмами."""

import uuid
import json
from typing import List, Dict, Any, Optional
from api.storage.db import DatabaseManagerBase
from api.logger import root_logger

log = root_logger.debug


class SymbioticService:
    """Сервис для работы с симбиотическими связями между организмами."""

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

    def create_relationship(
        self,
        organism1_id: str,
        organism2_id: str,
        relationship_type: str,
        description: Optional[str] = None,
        biochemical_exchange: Optional[Dict[str, Any]] = None,
        ecosystem_id: Optional[str] = None,
        level: str = "inter_organism",
        strength: float = 0.5,
    ) -> str:
        """Создает симбиотическую связь между организмами.

        Args:
            organism1_id: ID первого организма
            organism2_id: ID второго организма
            relationship_type: Тип связи (mutualism, commensalism, parasitism, competition, neutral)
            description: Описание связи
            biochemical_exchange: JSON с описанием биохимического обмена
            ecosystem_id: ID экосистемы, в которой происходит взаимодействие
            level: Уровень взаимодействия (intra_organism, inter_organism, ecosystem)
            strength: Сила связи (0.0-1.0)

        Returns:
            ID созданной связи

        Raises:
            ValueError: Если organism1_id == organism2_id или неверный тип связи
        """
        if organism1_id == organism2_id:
            raise ValueError("Organism IDs must be different")

        valid_types = ["mutualism", "commensalism", "parasitism", "competition", "neutral"]
        if relationship_type not in valid_types:
            raise ValueError(f"Invalid relationship_type. Must be one of: {valid_types}")

        valid_levels = ["intra_organism", "inter_organism", "ecosystem"]
        if level not in valid_levels:
            raise ValueError(f"Invalid level. Must be one of: {valid_levels}")

        relationship_id = f"symb_{uuid.uuid4()}"
        biochemical_exchange_json = json.dumps(biochemical_exchange) if biochemical_exchange else None

        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            INSERT INTO symbiotic_relationships 
            (id, organism1_id, organism2_id, relationship_type, description, 
             biochemical_exchange, ecosystem_id, level, strength)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relationship_id,
                organism1_id,
                organism2_id,
                relationship_type,
                description,
                biochemical_exchange_json,
                ecosystem_id,
                level,
                strength,
            ),
        )

        self.db_manager.connection.commit()
        log(f"✅ Создана симбиотическая связь {relationship_id}: {organism1_id} - {relationship_type} - {organism2_id}")

        return relationship_id

    def get_relationships_for_organism(self, organism_id: str) -> List[Dict[str, Any]]:
        """Получает все связи для организма.

        Args:
            organism_id: ID организма

        Returns:
            Список словарей с информацией о связях
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM symbiotic_relationships 
            WHERE organism1_id = ? OR organism2_id = ?
            ORDER BY strength DESC, created_at DESC
            """,
            (organism_id, organism_id),
        )

        rows = cursor.fetchall()
        result = []

        for row in rows:
            row_dict = dict(row)
            # Парсим JSON поля
            if row_dict.get("biochemical_exchange"):
                try:
                    row_dict["biochemical_exchange"] = json.loads(row_dict["biochemical_exchange"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["biochemical_exchange"] = {}
            else:
                row_dict["biochemical_exchange"] = {}

            result.append(row_dict)

        return result

    def get_relationships_in_ecosystem(self, ecosystem_id: str) -> List[Dict[str, Any]]:
        """Получает все связи в экосистеме.

        Args:
            ecosystem_id: ID экосистемы

        Returns:
            Список словарей с информацией о связях
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM symbiotic_relationships 
            WHERE ecosystem_id = ?
            ORDER BY strength DESC, created_at DESC
            """,
            (ecosystem_id,),
        )

        rows = cursor.fetchall()
        result = []

        for row in rows:
            row_dict = dict(row)
            # Парсим JSON поля
            if row_dict.get("biochemical_exchange"):
                try:
                    row_dict["biochemical_exchange"] = json.loads(row_dict["biochemical_exchange"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["biochemical_exchange"] = {}
            else:
                row_dict["biochemical_exchange"] = {}

            result.append(row_dict)

        return result

    def relationship_exists(self, organism1_id: str, organism2_id: str) -> bool:
        """Проверяет, существует ли связь между организмами.

        Args:
            organism1_id: ID первого организма
            organism2_id: ID второго организма

        Returns:
            True если связь существует
        """
        cursor = self.db_manager.connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM symbiotic_relationships 
            WHERE (organism1_id = ? AND organism2_id = ?) 
               OR (organism1_id = ? AND organism2_id = ?)
            """,
            (organism1_id, organism2_id, organism2_id, organism1_id),
        )

        count = cursor.fetchone()[0]
        return count > 0
