"""PostgreSQL менеджер для работы с базой данных.

Реализует тот же интерфейс, что и DatabaseManager, но для PostgreSQL.
"""

import logging
import re
from typing import Any, List, Optional, Tuple, Union
from contextlib import contextmanager
from urllib.parse import urlparse

try:
    import psycopg2  # type: ignore
    from psycopg2.extras import RealDictCursor  # type: ignore
except ImportError:
    psycopg2 = None  # type: ignore
    RealDictCursor = None  # type: ignore

from api.storage.db import DatabaseManagerBase

log = logging.getLogger(__name__)


class PostgreSQLManager(DatabaseManagerBase):
    """Класс для управления подключением к PostgreSQL базе данных.

    Реализует тот же интерфейс, что и DatabaseManager для SQLite,
    но использует PostgreSQL через psycopg2.
    """

    def __init__(self, database_url: str, min_connections: int = 1, max_connections: int = 5):
        """Инициализирует PostgreSQLManager с URL подключения.

        Args:
            database_url: PostgreSQL connection URL (postgresql://user:pass@host:port/dbname)
            min_connections: Минимальное количество соединений в пуле
            max_connections: Максимальное количество соединений в пуле
        """
        if psycopg2 is None:
            raise ImportError("psycopg2 не установлен. Установите: pip install psycopg2-binary")

        self._database_url = database_url
        self._parsed_url = urlparse(database_url)
        self._connection_pool: Optional[Any] = None
        self._current_connection: Optional[Any] = None
        self._min_connections = min_connections
        self._max_connections = max_connections

        # Создаем соединение сразу для совместимости с интерфейсом
        self._current_connection = self._create_connection()

    @property
    def connection(self) -> Any:
        """Возвращает текущее соединение с базой данных.

        Returns:
            Соединение PostgreSQL
        """
        if self._current_connection is None or self._current_connection.closed:
            self._current_connection = self._create_connection()
        return self._current_connection

    @property
    def db_path(self) -> str:
        """Возвращает URL базы данных.

        Returns:
            URL базы данных
        """
        return self._database_url

    def _create_connection(self) -> Any:
        """Создает новое подключение к базе данных PostgreSQL.

        Returns:
            Соединение PostgreSQL
        """
        if psycopg2 is None:
            raise ImportError("psycopg2 не установлен")
        try:
            conn = psycopg2.connect(
                self._database_url,
                cursor_factory=RealDictCursor,  # Для совместимости с sqlite3.Row
            )
            # Включаем поддержку внешних ключей (по умолчанию включена в PostgreSQL)
            conn.set_session(autocommit=False)
            return conn
        except Exception as e:
            logging.error(f"Ошибка подключения к PostgreSQL: {e}")
            raise

    def connect(self) -> None:
        """Устанавливает подключение к базе данных."""
        if self._current_connection is None or self._current_connection.closed:
            self._current_connection = self._create_connection()

    def disconnect(self) -> None:
        """Закрывает подключение к базе данных."""
        if self._current_connection and not self._current_connection.closed:
            self._current_connection.close()
        if self._connection_pool:
            self._connection_pool.closeall()

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для получения подключения к базе данных."""
        if self._current_connection is None or self._current_connection.closed:
            self.connect()
        try:
            yield self._current_connection
        except Exception as e:
            logging.error(f"Ошибка в операции с базой данных: {e}")
            if self._current_connection and not self._current_connection.closed:
                self._current_connection.rollback()
            raise

    @contextmanager
    def transaction(self):
        """Контекстный менеджер для выполнения транзакций."""
        if self._current_connection is None or self._current_connection.closed:
            self.connect()
        assert self._current_connection is not None
        conn = self._current_connection
        try:
            yield conn
            conn.commit()
        except Exception as e:
            logging.error(f"Ошибка транзакции: {e}")
            conn.rollback()
            raise

    def _convert_params(self, query: str, params: Optional[Tuple]) -> Tuple[str, Optional[Tuple]]:
        """Конвертирует SQL запрос с ? на %s для PostgreSQL.

        Args:
            query: SQL запрос с ? плейсхолдерами
            params: Параметры для подстановки

        Returns:
            Кортеж (конвертированный запрос, параметры)
        """
        if params is None:
            return query, None

        # Заменяем ? на %s для PostgreSQL
        converted_query = query.replace("?", "%s")
        return converted_query, params

    def execute_query(
        self, query: str, params: Optional[Tuple] = None, fetch: bool = False
    ) -> Union[List[Any], int, None]:
        """Выполняет SQL-запрос безопасным образом.

        Args:
            query: SQL-запрос для выполнения
            params: Параметры для подстановки в запрос
            fetch: Если True, возвращает результаты запроса

        Returns:
            Результаты запроса или количество затронутых строк
        """
        if self._current_connection is None or self._current_connection.closed:
            self.connect()
        assert self._current_connection is not None

        converted_query, converted_params = self._convert_params(query, params)

        try:
            cursor = self._current_connection.cursor()
            cursor.execute(converted_query, converted_params)

            if fetch:
                return cursor.fetchall()
            else:
                return cursor.rowcount
        except Exception as e:
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
        if self._current_connection is None or self._current_connection.closed:
            self.connect()
        assert self._current_connection is not None

        converted_query, _ = self._convert_params(query, None)

        try:
            cursor = self._current_connection.cursor()
            cursor.executemany(converted_query, params_list)
            return cursor.rowcount
        except Exception as e:
            logging.error(f"Ошибка выполнения запроса: {e}")
            raise

    def executescript(self, script: str) -> None:
        """Выполняет SQL скрипт, разбивая на отдельные запросы.

        PostgreSQL не поддерживает executescript как SQLite,
        поэтому разбиваем скрипт на отдельные запросы.

        Args:
            script: SQL скрипт для выполнения
        """
        if self._current_connection is None or self._current_connection.closed:
            self.connect()
        assert self._current_connection is not None

        # Разбиваем скрипт на отдельные запросы
        # Удаляем комментарии и пустые строки
        queries = self._split_sql_script(script)

        cursor = self._current_connection.cursor()
        try:
            for query in queries:
                if query.strip():
                    cursor.execute(query)
            self._current_connection.commit()
        except Exception as e:
            logging.error(f"Ошибка выполнения SQL скрипта: {e}")
            self._current_connection.rollback()
            raise

    def _split_sql_script(self, script: str) -> List[str]:
        """Разбивает SQL скрипт на отдельные запросы.

        Args:
            script: SQL скрипт

        Returns:
            Список отдельных SQL запросов
        """
        # Удаляем комментарии (-- и /* */)
        script = re.sub(r"--.*?$", "", script, flags=re.MULTILINE)
        script = re.sub(r"/\*.*?\*/", "", script, flags=re.DOTALL)

        # Разбиваем по точкам с запятой
        queries = []
        current_query: list[str] = []
        in_string = False
        string_char = None

        for line in script.split("\n"):
            i = 0
            while i < len(line):
                char = line[i]

                # Обрабатываем экранированные символы в строках
                if in_string:
                    if char == "\\" and i + 1 < len(line):
                        i += 2
                        continue
                    if char == string_char:
                        in_string = False
                        string_char = None
                else:
                    # Проверяем начало строки
                    if char in ("'", '"'):
                        in_string = True
                        string_char = char
                    # Разделитель запросов
                    elif char == ";" and not in_string:
                        query = " ".join(current_query).strip()
                        if query:
                            queries.append(query)
                        current_query = []
                        i += 1
                        continue

                i += 1

            if current_query or line.strip():
                current_query.append(line)

        # Последний запрос
        if current_query:
            query = " ".join(current_query).strip()
            if query:
                queries.append(query)

        return queries
