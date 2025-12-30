"""Модуль для работы с базой данных и системой хранения данных.

Модуль предоставляет классы для управления подключением к базе данных,
выполнения запросов, управления транзакциями, а также абстрактный интерфейс
для поддержки разных бэкендов хранилища (SQLite, PostgreSQL, Qdrant и т.д.).
"""

import sqlite3
import logging
from typing import Any, Dict, List, Optional, Union, Tuple, Protocol
from contextlib import contextmanager
from pathlib import Path
from abc import ABC, abstractmethod


class DatabaseConnection(Protocol):
    """Протокол для соединения с базой данных."""

    def cursor(self) -> Any:
        """Создает курсор."""
        ...

    def commit(self) -> None:
        """Коммитит транзакцию."""
        ...

    def rollback(self) -> None:
        """Откатывает транзакцию."""
        ...

    def close(self) -> None:
        """Закрывает соединение."""
        ...

    def executescript(self, script: str) -> Any:
        """Выполняет SQL скрипт (опционально, для SQLite)."""
        ...


class DatabaseManagerBase(ABC):
    """Базовый абстрактный класс для менеджеров баз данных.

    Определяет общий интерфейс для работы с разными БД (SQLite, PostgreSQL).
    """

    @property
    @abstractmethod
    def connection(self) -> DatabaseConnection:
        """Возвращает соединение с базой данных."""
        ...

    @property
    @abstractmethod
    def db_path(self) -> Any:
        """Возвращает путь/URL к базе данных."""
        ...

    @abstractmethod
    def connect(self) -> None:
        """Устанавливает подключение к базе данных."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Закрывает подключение к базе данных."""
        ...

    @abstractmethod
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для получения подключения к базе данных."""
        ...

    @abstractmethod
    @contextmanager
    def transaction(self):
        """Контекстный менеджер для выполнения транзакций."""
        ...

    @abstractmethod
    def execute_query(
        self, query: str, params: Optional[Tuple] = None, fetch: bool = False
    ) -> Union[List[Any], int, None]:
        """Выполняет SQL-запрос безопасным образом."""
        ...

    @abstractmethod
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Выполняет SQL-запрос несколько раз с разными параметрами."""
        ...

    @abstractmethod
    def executescript(self, script: str) -> None:
        """Выполняет SQL скрипт (разбивает на отдельные запросы для PostgreSQL)."""
        ...


class DatabaseManager(DatabaseManagerBase):
    """Класс для управления подключением к базе данных и выполнением запросов.

    Класс предоставляет методы для подключения к базе данных, выполнения
    SQL-запросов, управления транзакциями и безопасного закрытия соединений.
    """

    def __init__(self, db_path: str = "data/storage.db"):
        """Инициализирует DatabaseManager с указанным путем к базе данных.

        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # Соединение создаем сразу, чтобы в остальном коде connection всегда был sqlite3.Connection,
        # а не Optional. Это упрощает работу mypy и устраняет union-attr ошибки.
        self._connection: sqlite3.Connection = self._create_connection()

    @property
    def connection(self) -> sqlite3.Connection:
        """Возвращает соединение с базой данных."""
        return self._connection

    @property
    def db_path(self) -> Path:
        """Возвращает путь к базе данных."""
        return self._db_path

    def _create_connection(self) -> sqlite3.Connection:
        """Создает новое подключение к базе данных SQLite.

        Функция вынесена отдельно, чтобы переиспользовать логику
        в __init__ и connect без дублирования кода.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            connection = sqlite3.connect(self._db_path, check_same_thread=False)
            connection.row_factory = sqlite3.Row  # Позволяет обращаться к столбцам по имени
            # Включаем поддержку внешних ключей (требуется для CASCADE DELETE)
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.Error as e:
            logging.error(f"Ошибка подключения к базе данных: {e}")
            raise

    def connect(self) -> None:
        """Устанавливает подключение к базе данных.

        SQLite по умолчанию запрещает использование соединения из другого потока
        (`check_same_thread=True`), что приводит к ошибке:

        `SQLite objects created in a thread can only be used in that same thread.`

        При работе через uv/granian и асинхронные обработчики один и тот же
        `DatabaseManager` может вызываться из разных потоков внутри одного процесса.
        Чтобы избежать падений, явно включаем `check_same_thread=False`.
        Параллельный доступ мы контролируем на уровне приложения: операции записи
        выполняются последовательно внутри обработчика запроса.
        """
        # Переинициализируем соединение, если оно по какой-то причине было закрыто или повреждено.
        self._connection = self._create_connection()

    def disconnect(self) -> None:
        """Закрывает подключение к базе данных."""
        # Мы намеренно не обнуляем self.connection до None, чтобы тип оставался sqlite3.Connection.
        # После вызова disconnect() соединение закрыто и использовать его повторно нельзя,
        # но в текущей архитектуре это делается только на этапе завершения работы приложения.
        if self._connection:
            self._connection.close()

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для получения подключения к базе данных."""
        if not self._connection:
            self.connect()
        try:
            yield self._connection
        except Exception as e:
            logging.error(f"Ошибка в операции с базой данных: {e}")
            if self._connection:
                self._connection.rollback()
            raise

    @contextmanager
    def transaction(self):
        """Контекстный менеджер для выполнения транзакций."""
        if not self._connection:
            self.connect()
        # После connect() гарантированно не None
        assert self._connection is not None
        conn = self._connection
        try:
            yield conn
            conn.commit()
        except Exception as e:
            logging.error(f"Ошибка транзакции: {e}")
            conn.rollback()
            raise

    def execute_query(
        self, query: str, params: Optional[Tuple] = None, fetch: bool = False
    ) -> Union[List[sqlite3.Row], int, None]:
        """Выполняет SQL-запрос безопасным образом.

        Args:
            query: SQL-запрос для выполнения
            params: Параметры для подстановки в запрос
            fetch: Если True, возвращает результаты запроса

        Returns:
            Результаты запроса или количество затронутых строк
        """
        if not self._connection:
            self.connect()
        # После connect() гарантированно не None
        assert self._connection is not None

        params = params or ()
        try:
            cursor = self._connection.cursor()
            cursor.execute(query, params)

            if fetch:
                return cursor.fetchall()
            else:
                return cursor.rowcount
        except sqlite3.Error as e:
            logging.error(f"Ошибка выполнения запроса: {e}")
            raise

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Выполняет SQL-запрос несколько раз с разными параметрами.

        Args:
            query: SQL-запрос для выполнения
            params_list: Список параметров для выполнения запроса

        Returns:
            Количество затронутых строк
        """
        if not self._connection:
            self.connect()
        # После connect() гарантированно не None
        assert self._connection is not None

        try:
            cursor = self._connection.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount
        except sqlite3.Error as e:
            logging.error(f"Ошибка выполнения запроса: {e}")
            raise

    def executescript(self, script: str) -> None:
        """Выполняет SQL скрипт.

        Args:
            script: SQL скрипт для выполнения
        """
        if not self._connection:
            self.connect()
        assert self._connection is not None
        self._connection.executescript(script)


class BaseStorage(ABC):
    """Абстрактный базовый класс для хранения и извлечения данных.

    Предоставляет унифицированный интерфейс для разных бэкендов хранилища:
    - SQLite (через DatabaseManager)
    - PostgreSQL (через asyncpg или SQLAlchemy)
    - Qdrant (для векторного поиска)
    - Другие специализированные хранилища

    Этот интерфейс позволяет легко переключаться между разными реализациями
    без изменения бизнес-логики.

    Пример использования:
        class SQLiteStorage(BaseStorage):
            def save(self, data: Dict[str, Any]) -> bool: ...
            def get(self, key: str) -> Optional[Dict[str, Any]]: ...
            def delete(self, key: str) -> bool: ...
            def list_keys(self) -> List[str]: ...

        class PostgreSQLStorage(BaseStorage):
            def save(self, data: Dict[str, Any]) -> bool: ...
            # ... реализация для PostgreSQL

        class QdrantStorage(BaseStorage):
            def save(self, data: Dict[str, Any]) -> bool: ...
            # ... реализация для Qdrant
    """

    @abstractmethod
    def save(self, data: Dict[str, Any]) -> bool:
        """Сохраняет данные в хранилище.

        Args:
            data: Словарь с данными для сохранения

        Returns:
            True, если данные успешно сохранены, иначе False
        """
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Получает данные из хранилища по ключу.

        Args:
            key: Ключ для поиска данных

        Returns:
            Словарь с данными или None, если данные не найдены
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Удаляет данные из хранилища по ключу.

        Args:
            key: Ключ для удаления данных

        Returns:
            True, если данные успешно удалены, иначе False
        """
        pass

    @abstractmethod
    def list_keys(self) -> List[str]:
        """Возвращает список всех ключей в хранилище.

        Returns:
            Список ключей
        """
        pass
