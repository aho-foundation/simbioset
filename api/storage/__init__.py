"""Модуль storage предоставляет универсальный интерфейс для хранения и извлечения данных.

Модуль включает в себя:
- DatabaseManager для работы с SQLite базой данных
- PostgreSQLManager для работы с PostgreSQL базой данных
- DatabaseManagerBase - базовый абстрактный класс для менеджеров БД
- BaseStorage - абстрактный интерфейс для разных бэкендов (SQLite, PostgreSQL, Qdrant)
- DatabaseNodeRepository - реализация репозитория узлов знаний (работает с SQLite и PostgreSQL)
- FAISSStorage для векторного поиска параграфов
- ParagraphService для парсинга, векторизации и сохранения параграфов
- Схема базы данных определена в schema.sql (knowledge_nodes, paragraphs, vectors)
"""

from .db import DatabaseManager, DatabaseManagerBase, BaseStorage
from .postgresql_manager import PostgreSQLManager
from .db_factory import create_database_manager
from .faiss import FAISSStorage
from .nodes_repository import DatabaseNodeRepository
from .paragraph_service import ParagraphService
from .organism_service import OrganismService
from .ecosystem_service import EcosystemService


__all__ = [
    "DatabaseManager",
    "DatabaseManagerBase",
    "PostgreSQLManager",
    "create_database_manager",
    "BaseStorage",
    "DatabaseNodeRepository",
    "FAISSStorage",
    "ParagraphService",
    "OrganismService",
    "EcosystemService",
]
