"""Фабрика для создания менеджеров баз данных.

Автоматически выбирает SQLite или PostgreSQL на основе DATABASE_URL.
"""

import logging
from typing import Union
from urllib.parse import urlparse

from api.storage.db import DatabaseManager
from api.storage.postgresql_manager import PostgreSQLManager

log = logging.getLogger(__name__)


def create_database_manager(
    database_url: str, db_path: str = "data/storage.db"
) -> Union[DatabaseManager, PostgreSQLManager]:
    """Создает менеджер базы данных на основе URL.

    Args:
        database_url: URL базы данных (postgresql://... или sqlite:///...)
        db_path: Путь к файлу SQLite (используется если database_url указывает на SQLite)

    Returns:
        DatabaseManager для SQLite или PostgreSQLManager для PostgreSQL

    Examples:
        >>> # SQLite
        >>> manager = create_database_manager("sqlite:///data/storage.db")
        >>> # PostgreSQL
        >>> manager = create_database_manager("postgresql://user:pass@host:5432/dbname")
    """
    if not database_url:
        # По умолчанию используем SQLite
        log.info(f"Используется SQLite: {db_path}")
        return DatabaseManager(db_path=db_path)

    parsed = urlparse(database_url)

    # Проверяем схему URL
    if parsed.scheme in ("postgresql", "postgres"):
        log.info(f"Используется PostgreSQL: {parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}")
        return PostgreSQLManager(database_url=database_url)
    elif parsed.scheme == "sqlite" or database_url.startswith("sqlite:///"):
        # Извлекаем путь из URL (sqlite:///path/to/db.db)
        sqlite_path = database_url.replace("sqlite:///", "")
        log.info(f"Используется SQLite: {sqlite_path}")
        return DatabaseManager(db_path=sqlite_path)
    else:
        # По умолчанию используем SQLite
        log.warning(f"Неизвестная схема URL '{parsed.scheme}', используется SQLite: {db_path}")
        return DatabaseManager(db_path=db_path)
