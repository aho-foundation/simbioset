"""Сервис для работы с параграфами: парсинг, векторизация, сохранение."""

import uuid
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np
import faiss  # type: ignore

from typing import Union
from api.storage.db import DatabaseManagerBase
from api.storage.faiss import FAISSStorage, DocumentType, Paragraph
from api.storage.weaviate_storage import WeaviateStorage
from api.logger import root_logger

log = root_logger.debug


class ParagraphService:
    """Сервис для парсинга текста на параграфы, векторизации и сохранения."""

    def __init__(self, db_manager: DatabaseManagerBase, storage: Union[FAISSStorage, WeaviateStorage]):
        """Инициализация сервиса.

        Args:
            db_manager: Менеджер базы данных (DatabaseManager или PostgreSQLManager)
            storage: Хранилище для векторизации (FAISSStorage или WeaviateStorage)
        """
        self.db_manager = db_manager
        self.storage = storage
        # Для обратной совместимости
        self.faiss_storage = storage if isinstance(storage, FAISSStorage) else None
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Создает таблицы если их нет."""
        from pathlib import Path

        # Try multiple possible paths for schema.sql
        possible_paths = [
            Path(__file__).parent / "schema.sql",  # В той же директории, что и paragraph_service
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

    def parse_text_to_paragraphs(self, text: str, min_length: int = 50) -> List[str]:
        """Парсит текст на параграфы.

        Args:
            text: Текст для парсинга
            min_length: Минимальная длина параграфа

        Returns:
            Список параграфов
        """
        # Удаляем лишние пробелы и переносы строк
        text = re.sub(r"\s+", " ", text.strip())

        # Разбиваем на параграфы по двойным переносам строк или точкам с большой буквы
        # Сначала пробуем по двойным переносам
        paragraphs = re.split(r"\n\s*\n", text)

        # Если параграфов мало, пробуем по точкам с большой буквы
        if len(paragraphs) == 1 or all(len(p) < min_length for p in paragraphs):
            # Разбиваем по предложениям (точка + пробел + большая буква)
            sentences = re.split(r"\.\s+([А-ЯЁA-Z])", text)
            paragraphs = []
            current_para = sentences[0] if sentences else ""
            for i in range(1, len(sentences), 2):
                if i + 1 < len(sentences):
                    current_para += ". " + sentences[i] + sentences[i + 1]
                else:
                    current_para += ". " + sentences[i]

                # Если параграф достаточно длинный, сохраняем его
                if len(current_para) >= min_length:
                    paragraphs.append(current_para.strip())
                    current_para = ""
            if current_para.strip():
                paragraphs.append(current_para.strip())

        # Фильтруем слишком короткие параграфы
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) >= min_length]

        return paragraphs

    def save_document_paragraphs(
        self,
        document_id: str,
        paragraphs: List[str],
        document_type: DocumentType = DocumentType.KNOWLEDGE,
        author: Optional[str] = None,
        author_id: Optional[int] = None,
        timestamp: Optional[int] = None,
        node_id: Optional[str] = None,
    ) -> List[str]:
        """Сохраняет параграфы документа в БД и векторизует их.

        Создает Paragraph объекты, добавляет в хранилище (FAISS/Weaviate) и сохраняет в SQLite.
        Если указан node_id, параграфы связываются с узлом знания.

        Args:
            document_id: ID документа
            paragraphs: Список текстов параграфов
            document_type: Тип документа (chat, knowledge, document)
            author: Автор документа
            author_id: ID автора
            timestamp: Временная метка
            node_id: Опциональный ID узла знания для связи параграфов с узлом

        Returns:
            Список ID созданных параграфов
        """
        if not paragraphs:
            return []

        timestamp = timestamp or int(datetime.now().timestamp() * 1000)
        paragraph_objects = []
        cursor = self.db_manager.connection.cursor()

        # Создаем Paragraph объекты с эмбеддингами
        for index, content in enumerate(paragraphs):
            paragraph_id = f"para_{uuid.uuid4()}"

            # Создаем Paragraph объект
            paragraph = Paragraph(
                id=paragraph_id,
                content=content,
                document_id=document_id,
                node_id=node_id,  # Связь с узлом знания, если указан
                document_type=document_type,
                author=author,
                author_id=author_id,
                timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else None,
            )

            # Создаем эмбеддинг
            paragraph.embedding = self.storage._create_embedding(content)

            # Классифицируем параграф (если доступен tag_service)
            tag_service = getattr(self.storage, "_tag_service", None)
            if tag_service:
                paragraph = self.storage._classify_paragraph(paragraph, tag_service=tag_service)

            paragraph_objects.append(paragraph)

            # Сохраняем организмы в БД, если они обнаружены
            if paragraph.metadata and "organisms" in paragraph.metadata:
                try:
                    from api.storage.organism_service import OrganismService

                    organism_service = OrganismService(self.db_manager)
                    saved_organism_ids = organism_service.save_organisms_for_paragraph(
                        paragraph_id=paragraph_id, organisms=paragraph.metadata["organisms"]
                    )

                    # Сохраняем organism_ids в metadata для быстрого доступа
                    if saved_organism_ids:
                        if not paragraph.metadata:
                            paragraph.metadata = {}
                        paragraph.metadata["organism_ids"] = saved_organism_ids
                        log(f"✅ Сохранено {len(saved_organism_ids)} organism_ids в metadata параграфа")
                except Exception as e:
                    log(f"⚠️ Ошибка при сохранении организмов: {e}")

            # Сохраняем параграф в SQLite
            import json

            tags_json = json.dumps(paragraph.tags) if paragraph.tags else None

            # Извлекаем ecosystem_id из metadata, если есть
            ecosystem_id = None
            if paragraph.metadata and "ecosystems" in paragraph.metadata:
                ecosystems = paragraph.metadata["ecosystems"]
                if ecosystems and isinstance(ecosystems, list) and len(ecosystems) > 0:
                    # Берем первую экосистему как основную
                    first_eco = ecosystems[0]
                    if isinstance(first_eco, dict):
                        # Если есть ID экосистемы, используем его
                        ecosystem_id = first_eco.get("id")
                        # Если нет ID, но есть name, можно создать или найти экосистему
                        # Пока просто сохраняем в metadata, связь создадим позже

            cursor.execute(
                """
                INSERT INTO paragraphs 
                (id, content, document_id, node_id, document_type, paragraph_index, 
                 author, author_id, timestamp, tags, location, time_reference, ecosystem_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paragraph_id,
                    content,
                    document_id,
                    node_id,
                    document_type.value,
                    index,
                    author,
                    author_id,
                    timestamp,
                    tags_json,
                    paragraph.location,
                    paragraph.time_reference,
                    ecosystem_id,
                    json.dumps(paragraph.metadata) if paragraph.metadata else None,
                ),
            )

            # Сохраняем вектор в SQLite
            assert paragraph.embedding is not None
            embedding_dim = len(paragraph.embedding)
            cursor.execute(
                """
                INSERT INTO vectors 
                (id, paragraph_id, embedding, embedding_dimension, faiss_index_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (paragraph_id, paragraph_id, paragraph.embedding.tobytes(), embedding_dim, index),
            )

        self.db_manager.connection.commit()

        # Добавляем Paragraph объекты в хранилище (FAISS или Weaviate)
        if paragraph_objects:
            if isinstance(self.storage, WeaviateStorage):
                # Используем Weaviate - добавляем через add_documents
                documents = [{"text": para.content} for para in paragraph_objects]
                self.storage.add_documents(
                    documents=documents,
                    document_id=document_id,
                    document_type=document_type,
                    classify=False,  # Уже классифицировали выше
                )
            else:
                # Используем FAISS - добавляем в индекс
                embeddings_list = [para.embedding for para in paragraph_objects if para.embedding is not None]
                if embeddings_list:
                    embeddings = np.array(embeddings_list).astype(np.float32)

                    # Инициализируем индекс для документа, если его еще нет
                    search_engine = self.faiss_storage._search_engine  # type: ignore
                    if document_id not in search_engine.document_indexes:
                        search_engine.document_indexes[document_id] = faiss.IndexFlatIP(search_engine.dimension)  # type: ignore
                        search_engine.document_paragraph_ids[document_id] = []
                        search_engine.document_paragraphs[document_id] = []
                        search_engine.document_embeddings_cache[document_id] = None

                    # Добавляем в индекс
                    search_engine.document_indexes[document_id].add(embeddings)

                    # Сохраняем метаданные
                    for paragraph in paragraph_objects:
                        search_engine.document_paragraph_ids[document_id].append(paragraph.id)
                        search_engine.document_paragraphs[document_id].append(paragraph)

                    # Кэшируем эмбеддинги
                    search_engine.document_embeddings_cache[document_id] = embeddings

        paragraph_ids = [para.id for para in paragraph_objects]
        storage_type = "Weaviate" if isinstance(self.storage, WeaviateStorage) else "FAISS"
        log(f"✅ Сохранено {len(paragraph_ids)} параграфов для документа {document_id} (SQLite + {storage_type})")

        return paragraph_ids

    def save_node_paragraphs(
        self,
        node_id: str,
        paragraphs: List[str],
        document_type: DocumentType = DocumentType.KNOWLEDGE,
        author: Optional[str] = None,
        author_id: Optional[int] = None,
        timestamp: Optional[int] = None,
    ) -> List[str]:
        """Сохраняет параграфы узла знания в БД и векторизует их.

        Создает Paragraph объекты, добавляет в хранилище (FAISS/Weaviate) и сохраняет в SQLite.

        Args:
            node_id: ID узла знания
            paragraphs: Список текстов параграфов
            document_type: Тип документа (обычно knowledge)
            author: Автор
            author_id: ID автора
            timestamp: Временная метка

        Returns:
            Список ID созданных параграфов
        """
        if not paragraphs:
            return []

        timestamp = timestamp or int(datetime.now().timestamp() * 1000)
        paragraph_objects = []
        cursor = self.db_manager.connection.cursor()

        # Создаем Paragraph объекты с эмбеддингами
        for index, content in enumerate(paragraphs):
            paragraph_id = f"para_{uuid.uuid4()}"

            # Создаем Paragraph объект с node_id для связи с узлом знания
            paragraph = Paragraph(
                id=paragraph_id,
                content=content,
                node_id=node_id,  # Связь с узлом знания
                document_id=node_id,  # Используем node_id как document_id для индексации
                document_type=document_type,
                author=author,
                author_id=author_id,
                timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else None,
            )

            # Создаем эмбеддинг
            paragraph.embedding = self.storage._create_embedding(content)

            # Классифицируем параграф (если доступен tag_service)
            tag_service = getattr(self.storage, "_tag_service", None)
            if tag_service:
                paragraph = self.storage._classify_paragraph(paragraph, tag_service=tag_service)

            paragraph_objects.append(paragraph)

            # Сохраняем организмы в БД, если они обнаружены
            if paragraph.metadata and "organisms" in paragraph.metadata:
                try:
                    from api.storage.organism_service import OrganismService

                    organism_service = OrganismService(self.db_manager)
                    saved_organism_ids = organism_service.save_organisms_for_paragraph(
                        paragraph_id=paragraph_id, organisms=paragraph.metadata["organisms"]
                    )

                    # Сохраняем organism_ids в metadata для быстрого доступа
                    if saved_organism_ids:
                        if not paragraph.metadata:
                            paragraph.metadata = {}
                        paragraph.metadata["organism_ids"] = saved_organism_ids
                        log(f"✅ Сохранено {len(saved_organism_ids)} organism_ids в metadata параграфа")
                except Exception as e:
                    log(f"⚠️ Ошибка при сохранении организмов: {e}")

            # Сохраняем параграф в SQLite
            import json

            tags_json = json.dumps(paragraph.tags) if paragraph.tags else None

            # Извлекаем ecosystem_id из metadata, если есть
            ecosystem_id = None
            if paragraph.metadata and "ecosystems" in paragraph.metadata:
                ecosystems = paragraph.metadata["ecosystems"]
                if ecosystems and isinstance(ecosystems, list) and len(ecosystems) > 0:
                    first_eco = ecosystems[0]
                    if isinstance(first_eco, dict):
                        ecosystem_id = first_eco.get("id")

            cursor.execute(
                """
                INSERT INTO paragraphs 
                (id, content, node_id, document_type, paragraph_index, 
                 author, author_id, timestamp, tags, location, time_reference, ecosystem_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paragraph_id,
                    content,
                    node_id,
                    document_type.value,
                    index,
                    author,
                    author_id,
                    timestamp,
                    tags_json,
                    paragraph.location,
                    paragraph.time_reference,
                    ecosystem_id,
                    json.dumps(paragraph.metadata) if paragraph.metadata else None,
                ),
            )

            # Сохраняем вектор в SQLite
            assert paragraph.embedding is not None
            embedding_dim = len(paragraph.embedding)
            cursor.execute(
                """
                INSERT INTO vectors 
                (id, paragraph_id, embedding, embedding_dimension, faiss_index_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (paragraph_id, paragraph_id, paragraph.embedding.tobytes(), embedding_dim, index),
            )

        self.db_manager.connection.commit()

        # Добавляем Paragraph объекты в хранилище (FAISS или Weaviate)
        if paragraph_objects:
            if isinstance(self.storage, WeaviateStorage):
                # Используем Weaviate - добавляем через add_documents
                documents = [{"text": para.content} for para in paragraph_objects]
                self.storage.add_documents(
                    documents=documents,
                    document_id=node_id,  # Используем node_id как document_id
                    document_type=document_type,
                    classify=False,  # Уже классифицировали выше
                )
            else:
                # Используем FAISS - добавляем в индекс
                embeddings_list = [para.embedding for para in paragraph_objects if para.embedding is not None]
                if embeddings_list:
                    embeddings = np.array(embeddings_list).astype(np.float32)

                    # Инициализируем индекс для узла, если его еще нет
                    search_engine = self.faiss_storage._search_engine  # type: ignore
                    if node_id not in search_engine.document_indexes:
                        search_engine.document_indexes[node_id] = faiss.IndexFlatIP(search_engine.dimension)  # type: ignore
                        search_engine.document_paragraph_ids[node_id] = []
                        search_engine.document_paragraphs[node_id] = []
                        search_engine.document_embeddings_cache[node_id] = None

                    # Добавляем в индекс
                    search_engine.document_indexes[node_id].add(embeddings)

                    # Сохраняем метаданные
                    for paragraph in paragraph_objects:
                        search_engine.document_paragraph_ids[node_id].append(paragraph.id)
                        search_engine.document_paragraphs[node_id].append(paragraph)

                    # Кэшируем эмбеддинги
                    search_engine.document_embeddings_cache[node_id] = embeddings

        paragraph_ids = [para.id for para in paragraph_objects]
        storage_type = "Weaviate" if isinstance(self.storage, WeaviateStorage) else "FAISS"
        log(f"✅ Сохранено {len(paragraph_ids)} параграфов для узла {node_id} (SQLite + {storage_type})")

        return paragraph_ids

    async def save_chat_message_paragraphs(
        self,
        message_content: str,
        session_id: str,
        author: Optional[str] = None,
        author_id: Optional[int] = None,
        timestamp: Optional[int] = None,
    ) -> List[str]:
        """Сохраняет параграфы сообщения чата в БД и векторизует их.

        Args:
            message_content: Содержимое сообщения
            session_id: ID сессии чата
            author: Автор сообщения
            author_id: ID автора
            timestamp: Временная метка

        Returns:
            Список ID созданных параграфов
        """
        # Парсим сообщение на параграфы
        paragraphs = self.parse_text_to_paragraphs(message_content, min_length=20)

        if not paragraphs:
            # Если не удалось разбить, сохраняем как один параграф
            paragraphs = [message_content]

        # Используем session_id как document_id для чата
        # Векторизация может быть долгой, поэтому используем asyncio.to_thread
        import asyncio

        def _save():
            return self.save_document_paragraphs(
                document_id=session_id,
                paragraphs=paragraphs,
                document_type=DocumentType.CHAT,
                author=author,
                author_id=author_id,
                timestamp=timestamp,
            )

        return await asyncio.to_thread(_save)

    def load_paragraphs_from_db(
        self, document_id: Optional[str] = None, document_type: Optional[DocumentType] = None
    ) -> List[Paragraph]:
        """Загружает параграфы из SQLite в хранилище (FAISS/Weaviate).

        Args:
            document_id: Опциональный ID документа для фильтрации
            document_type: Опциональный тип документа для фильтрации

        Returns:
            Список загруженных параграфов
        """
        cursor = self.db_manager.connection.cursor()

        # Строим запрос с фильтрами
        query = "SELECT p.*, v.embedding, v.embedding_dimension FROM paragraphs p LEFT JOIN vectors v ON p.id = v.paragraph_id WHERE 1=1"
        params: List[Any] = []

        if document_id:
            query += " AND p.document_id = ?"
            params.append(document_id)

        if document_type:
            query += " AND p.document_type = ?"
            params.append(document_type.value)

        query += " ORDER BY p.paragraph_index"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        loaded_paragraphs = []
        # Для FAISS нужен search_engine, для Weaviate - нет
        search_engine = None
        if self.faiss_storage:
            search_engine = self.faiss_storage._search_engine  # type: ignore

        for row in rows:
            # Восстанавливаем Paragraph из строки БД
            import json

            tags = []
            if row.get("tags"):
                try:
                    tags = json.loads(row["tags"])
                except (json.JSONDecodeError, TypeError):
                    tags = []

            # Миграция: если есть classification, но нет tags, добавляем classification в tags
            if row.get("classification") and not tags:
                tags = [str(row["classification"])]

            # Восстанавливаем metadata
            metadata = {}
            if row.get("metadata"):
                try:
                    metadata = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            paragraph = Paragraph(
                id=row["id"],
                content=row["content"],
                document_id=row["document_id"],
                node_id=row.get("node_id"),
                document_type=DocumentType(row["document_type"]),
                author=row.get("author"),
                author_id=row.get("author_id"),
                timestamp=datetime.fromtimestamp(row["timestamp"] / 1000) if row.get("timestamp") else None,
                paragraph_index=row.get("paragraph_index"),
                tags=tags,
                fact_check_result=row.get("fact_check_result"),
                fact_check_details=row.get("fact_check_details"),
                location=row.get("location"),
                time_reference=row.get("time_reference"),
                ecosystem_id=row.get("ecosystem_id"),
                metadata=metadata,
            )

            # Восстанавливаем эмбеддинг из BLOB
            if row.get("embedding"):
                embedding_bytes = row["embedding"]
                embedding_dim = row["embedding_dimension"]
                embedding = np.frombuffer(embedding_bytes, dtype=np.float32).reshape(embedding_dim)
                paragraph.embedding = embedding

            # Если эмбеддинга нет, создаем его
            if paragraph.embedding is None:
                paragraph.embedding = self.storage._create_embedding(paragraph.content)

            loaded_paragraphs.append(paragraph)

            # Добавляем в хранилище (FAISS или Weaviate)
            if isinstance(self.storage, WeaviateStorage):
                # Для Weaviate не нужно загружать в память - данные уже в БД
                # Можно пропустить или добавить в Weaviate, если их там еще нет
                pass
            else:
                # Добавляем в FAISS индекс
                doc_id = paragraph.document_id or ""
                search_engine = self.faiss_storage._search_engine  # type: ignore
                if doc_id not in search_engine.document_indexes:
                    search_engine.document_indexes[doc_id] = faiss.IndexFlatIP(search_engine.dimension)  # type: ignore
                    search_engine.document_paragraph_ids[doc_id] = []
                    search_engine.document_paragraphs[doc_id] = []
                    search_engine.document_embeddings_cache[doc_id] = None

                # Добавляем параграф в индекс (накапливаем для батча)
                search_engine.document_paragraph_ids[doc_id].append(paragraph.id)
                search_engine.document_paragraphs[doc_id].append(paragraph)

        # Батч-добавление эмбеддингов в FAISS для каждого документа
        if not isinstance(self.storage, WeaviateStorage) and self.faiss_storage:
            search_engine = self.faiss_storage._search_engine  # type: ignore
            for doc_id in set((p.document_id or "") for p in loaded_paragraphs):
                doc_paragraphs = [p for p in loaded_paragraphs if (p.document_id or "") == doc_id]
                if doc_paragraphs:
                    embeddings = np.array([p.embedding for p in doc_paragraphs if p.embedding is not None]).astype(
                        np.float32
                    )
                    if len(embeddings) > 0:
                        search_engine.document_indexes[doc_id].add(embeddings)
                        search_engine.document_embeddings_cache[doc_id] = embeddings

        storage_type = "Weaviate" if isinstance(self.storage, WeaviateStorage) else "FAISS"
        log(f"✅ Загружено {len(loaded_paragraphs)} параграфов из SQLite в {storage_type}")
        return loaded_paragraphs

    def get_paragraphs_from_db(
        self,
        document_id: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[dict]:
        """Получает параграфы из SQLite без загрузки в хранилище (для экспорта датасета).

        Args:
            document_id: Опциональный ID документа для фильтрации
            document_type: Опциональный тип документа для фильтрации
            limit: Максимальное количество результатов
            offset: Смещение для пагинации

        Returns:
            Список словарей с данными параграфов
        """
        cursor = self.db_manager.connection.cursor()

        query = """
            SELECT 
                p.id, p.content, p.document_id, p.node_id, p.document_type,
                p.author, p.author_id, p.paragraph_index, p.timestamp,
                p.tags, p.fact_check_result, p.fact_check_details,
                p.location, p.time_reference, p.metadata,
                p.created_at, p.updated_at
            FROM paragraphs p
            WHERE 1=1
        """
        params: List[Any] = []

        if document_id:
            query += " AND p.document_id = ?"
            params.append(document_id)

        if document_type:
            query += " AND p.document_type = ?"
            params.append(document_type.value)

        query += " ORDER BY p.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Преобразуем строки в словари и парсим JSON поля
        result = []
        import json

        for row in rows:
            row_dict = dict(row)
            # Парсим tags из JSON
            if row_dict.get("tags"):
                try:
                    row_dict["tags"] = json.loads(row_dict["tags"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["tags"] = []
            else:
                row_dict["tags"] = []
            result.append(row_dict)

        return result
