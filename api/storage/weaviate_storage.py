"""
Weaviate Storage - замена FAISS для векторного поиска параграфов.
Использует Weaviate для персистентного хранения и фильтрации по метаданным.
"""

from typing import Dict, List, Tuple, Optional, Any, cast
import uuid
import numpy as np
from sentence_transformers import SentenceTransformer
from datetime import datetime
import weaviate
from weaviate.classes.query import Filter, MetadataQuery

# Импортируем типы из faiss.py для совместимости
from api.storage.faiss import (
    Paragraph,
    DocumentType,
    ClassificationType,
    FactCheckResult,
)
from api.settings import (
    EMBEDDING_MODEL_NAME,
    MODELS_CACHE_DIR,
    WEAVIATE_URL,
    WEAVIATE_GRPC_URL,
    WEAVIATE_API_KEY,
    WEAVIATE_CLASS_NAME
)
from api.storage.weaviate_schema import create_schema_if_not_exists
from api.logger import root_logger

log = root_logger.debug


class WeaviateStorage:
    """Хранилище параграфов на основе Weaviate с совместимым интерфейсом FAISSStorage"""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, cache_folder: Optional[str] = None):
        """
        Инициализация Weaviate Storage

        Args:
            model_name: Название модели для создания эмбеддингов
            cache_folder: Директория для кэширования моделей
        """
        log(f"🔄 Загрузка модели {model_name}...")

        if cache_folder is None:
            cache_folder = MODELS_CACHE_DIR

        # Загружаем модель для создания эмбеддингов
        self.model = SentenceTransformer(model_name, cache_folder=cache_folder)
        self.dimension = self.model.get_sentence_embedding_dimension()

        # Подключаемся к Weaviate (v4 API)
        auth_config = None
        if WEAVIATE_API_KEY:
            auth_config = weaviate.auth.AuthApiKey(api_key=WEAVIATE_API_KEY)

        # Парсим HTTP URL для подключения
        url_parts = WEAVIATE_URL.replace("http://", "").replace("https://", "").split(":")
        http_host = url_parts[0] if url_parts else "localhost"
        http_port = int(url_parts[1]) if len(url_parts) > 1 else 8080
        http_secure = WEAVIATE_URL.startswith("https://")

        # Парсим gRPC URL отдельно
        grpc_parts = WEAVIATE_GRPC_URL.split(":")
        grpc_host = grpc_parts[0] if grpc_parts else "localhost"
        grpc_port = int(grpc_parts[1]) if len(grpc_parts) > 1 else 50051
        grpc_secure = False  # gRPC обычно не использует SSL во внутренней сети

        # Создаем подключение с приоритетом gRPC для векторных операций
        connection_params = weaviate.connect.base.ConnectionParams.from_params(
            http_host=http_host,
            http_port=http_port,
            http_secure=http_secure,
            grpc_host=grpc_host,
            grpc_port=grpc_port,
            grpc_secure=grpc_secure,
        )

        # Если gRPC предпочтителен, настраиваем клиент для использования gRPC по умолчанию
        client_kwargs = {
            "connection_params": connection_params,
            "auth_client_secret": auth_config,
        }

        self.client = weaviate.WeaviateClient(**client_kwargs)

        # Проверяем подключение и создаем схему
        try:
            self.client.connect()
            meta = self.client.get_meta()
            log(f"✅ Подключено к Weaviate {meta.get('version', 'unknown')} на {WEAVIATE_URL}")

            # Создаем схему, если её нет
            create_schema_if_not_exists(self.client)
        except Exception as e:
            log(f"❌ Ошибка подключения к Weaviate: {e}")
            raise

        log(f"✅ Модель загружена, размерность эмбеддингов: {self.dimension}")

        # Связанный сервис тегов задается снаружи
        self._tag_service: Optional[Any] = None

    def _create_paragraph_id(
        self,
        content: str,
        author: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        index: Optional[int] = None,
    ) -> str:
        """Создает уникальный ID для параграфа"""
        unique_id = str(uuid.uuid4())
        return f"para_{unique_id}"

    def _create_embedding(self, text: str) -> np.ndarray:
        """
        Создает эмбеддинг для текста

        Args:
            text: Текст для создания эмбеддинга

        Returns:
            Нормализованный вектор эмбеддинга
        """
        embedding = self.model.encode(text, convert_to_numpy=True)

        # Нормализуем для косинусного сходства
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return cast(np.ndarray, embedding.astype("float32"))

    def _paragraph_to_weaviate_object(self, paragraph: Paragraph) -> Dict[str, Any]:
        """Конвертирует Paragraph в объект для Weaviate

        Metadata не сохраняется в Weaviate - он используется только для временных данных
        при обработке, которые затем сохраняются в отдельные поля (organism_ids, ecosystem_id).
        """
        # Извлекаем organism_ids из metadata (для обратной совместимости)
        organism_ids = paragraph.metadata.get("organism_ids", []) if paragraph.metadata else []

        obj = {
            "content": paragraph.content,
            "document_id": paragraph.document_id or "",
            "node_id": paragraph.node_id or "",
            "document_type": paragraph.document_type.value if paragraph.document_type else "chat",
            "organism_ids": organism_ids,
            "ecosystem_id": paragraph.ecosystem_id or "",
            "location": paragraph.location or "",
            "tags": paragraph.tags or [],
            "author": paragraph.author or "",
            "author_id": paragraph.author_id or 0,
            "paragraph_index": paragraph.paragraph_index or 0,
        }

        # Добавляем timestamp, если есть
        if paragraph.timestamp:
            obj["timestamp"] = paragraph.timestamp.isoformat()

        return obj

    def _weaviate_object_to_paragraph(self, obj: Any, vector: Optional[np.ndarray] = None) -> Paragraph:
        """Конвертирует объект из Weaviate v4 в Paragraph

        Args:
            obj: Объект Weaviate v4 (Object с properties, uuid, vector, metadata) или dict (для обратной совместимости)
            vector: Вектор эмбеддинга (если не включен в obj)
        """
        # Обрабатываем v4 Object или dict
        if hasattr(obj, "properties"):
            # v4 Object
            props = obj.properties
            paragraph_id = str(obj.uuid) if hasattr(obj, "uuid") else ""
            obj_vector = obj.vector if hasattr(obj, "vector") and obj.vector is not None else None
            if obj_vector is None:
                obj_vector = vector
            else:
                # Преобразуем список в numpy array
                if isinstance(obj_vector, (list, tuple)):
                    obj_vector = np.array(obj_vector, dtype=np.float32)
                elif isinstance(obj_vector, dict):
                    # Если вектор приходит как dict, используем переданный vector
                    obj_vector = vector
                else:
                    # Если это уже numpy array или другой тип
                    try:
                        obj_vector = np.array(obj_vector, dtype=np.float32)
                    except (ValueError, TypeError):
                        obj_vector = vector
            metadata_obj = obj.metadata if hasattr(obj, "metadata") else None
        else:
            # dict (обратная совместимость)
            props = obj if isinstance(obj, dict) else obj.get("properties", obj)
            paragraph_id = obj.get("_id") or obj.get("_additional", {}).get("id") or ""
            obj_vector = vector
            metadata_obj = None

        # Парсим timestamp
        timestamp = None
        if props.get("timestamp"):
            try:
                ts_val = props["timestamp"]
                if isinstance(ts_val, str):
                    timestamp = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                elif isinstance(ts_val, datetime):
                    timestamp = ts_val
                elif hasattr(ts_val, "isoformat"):
                    timestamp = ts_val
                elif isinstance(ts_val, dict):
                    # v4 может возвращать timestamp как dict с полями
                    # Пропускаем, так как это не стандартный формат
                    pass
            except Exception:
                pass

        # Metadata не хранится в Weaviate, создаем пустой dict
        # organism_ids извлекаем из отдельного поля
        organism_ids = props.get("organism_ids", [])
        metadata = {}
        # Сохраняем organism_ids в metadata для обратной совместимости с кодом, который ожидает их там
        if organism_ids:
            metadata["organism_ids"] = organism_ids

        # Безопасно извлекаем числовые поля
        author_id = props.get("author_id")
        if isinstance(author_id, dict):
            log(f"⚠️ author_id is dict: {author_id}")
            author_id = None
        elif author_id is not None:
            try:
                author_id = int(author_id)
            except (ValueError, TypeError) as e:
                log(f"⚠️ Cannot convert author_id {author_id} ({type(author_id)}) to int: {e}")
                author_id = None

        paragraph_index = props.get("paragraph_index")
        if isinstance(paragraph_index, dict):
            log(f"⚠️ paragraph_index is dict: {paragraph_index}")
            paragraph_index = None
        elif paragraph_index is not None:
            try:
                paragraph_index = int(paragraph_index)
            except (ValueError, TypeError) as e:
                log(f"⚠️ Cannot convert paragraph_index {paragraph_index} ({type(paragraph_index)}) to int: {e}")
                paragraph_index = None

        paragraph = Paragraph(
            id=paragraph_id,
            content=props.get("content", ""),
            author=props.get("author"),
            author_id=author_id,
            timestamp=timestamp,
            document_id=props.get("document_id"),
            node_id=props.get("node_id"),
            document_type=DocumentType(props.get("document_type", "chat")),
            metadata=metadata,
            embedding=obj_vector,
            tags=props.get("tags", []),
            location=props.get("location"),
            ecosystem_id=props.get("ecosystem_id"),
            paragraph_index=paragraph_index,
        )

        return paragraph

    # Делегируем методы классификации из FAISSStorage для переиспользования
    def _extract_text(self, message: Dict[str, Any]) -> str:
        """Извлекает текст из сообщения для создания эмбеддинга"""
        from api.storage.faiss import FAISSStorage

        # Создаем временный экземпляр для переиспользования метода
        temp_storage = FAISSStorage()
        return temp_storage._extract_text(message)

    def _create_paragraph_from_message(
        self, message: Dict[str, Any], document_id: str, document_type: DocumentType, index: Optional[int] = None
    ) -> Paragraph:
        """Создает параграф из сообщения"""
        from api.storage.faiss import FAISSStorage

        temp_storage = FAISSStorage()
        return temp_storage._create_paragraph_from_message(message, document_id, document_type, index)

    def _group_consecutive_messages(self, messages: List[Dict[str, Any]]) -> List[Paragraph]:
        """Группирует последовательные сообщения одного автора в один параграф"""
        from api.storage.faiss import FAISSStorage

        temp_storage = FAISSStorage()
        return temp_storage._group_consecutive_messages(messages)

    def _classify_paragraph(self, paragraph: Paragraph, tag_service=None) -> Paragraph:
        """Классифицирует параграф с использованием модулей классификации"""
        from api.storage.faiss import FAISSStorage

        temp_storage = FAISSStorage()
        temp_storage._tag_service = tag_service or self._tag_service
        return temp_storage._classify_paragraph(paragraph, tag_service=tag_service or self._tag_service)

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        document_id: str,
        document_type: DocumentType = DocumentType.KNOWLEDGE,
        classify: bool = True,
    ) -> int:
        """
        Добавляет документы в Weaviate

        Args:
            documents: Список документов для индексации
            document_id: ID документа
            document_type: Тип документа (чат или знание)
            classify: Выполнять ли классификацию и проверку достоверности

        Returns:
            Количество добавленных параграфов
        """
        if not documents:
            return 0

        # Создаем параграфы из документов
        paragraphs = []
        for i, doc in enumerate(documents):
            if isinstance(doc, dict) and "text" in doc:
                paragraph = self._create_paragraph_from_message(doc, document_id, document_type, index=i)
                paragraphs.append(paragraph)
            elif isinstance(doc, str):
                paragraph = Paragraph(
                    id=self._create_paragraph_id(doc, index=i),
                    content=doc,
                    document_id=document_id,
                    document_type=document_type,
                    paragraph_index=i,
                )
                paragraph.embedding = self._create_embedding(doc)
                paragraphs.append(paragraph)

        if not paragraphs:
            return 0

        # Классифицируем параграфы, если нужно
        if classify:
            for paragraph in paragraphs:
                paragraph = self._classify_paragraph(paragraph)

        log(f"🔄 Добавление {len(paragraphs)} параграфов в Weaviate для документа {document_id}...")

        # Добавляем параграфы в Weaviate батчами (v4 API)
        from weaviate.classes.data import DataObject

        collection = self.client.collections.get(WEAVIATE_CLASS_NAME)
        added_count = 0

        # Подготавливаем объекты для batch insert
        objects_to_insert = []
        for paragraph in paragraphs:
            if paragraph.embedding is None:
                paragraph.embedding = self._create_embedding(paragraph.content)

            obj = self._paragraph_to_weaviate_object(paragraph)
            vector = paragraph.embedding.tolist()

            # В v4 используем UUID из paragraph.id или генерируем новый
            para_uuid = paragraph.id.replace("para_", "") if paragraph.id.startswith("para_") else paragraph.id
            try:
                # Проверяем, валидный ли UUID
                para_uuid_obj = uuid.UUID(para_uuid)
            except (ValueError, AttributeError):
                # Если не валидный, генерируем новый
                para_uuid_obj = uuid.uuid4()

            # В v4 используем DataObject для объектов с кастомным вектором
            objects_to_insert.append(
                DataObject(
                    uuid=para_uuid_obj,
                    properties=obj,
                    vector=vector,
                )
            )

        # Вставляем батчами
        if objects_to_insert:
            # В v4 используем insert_many для batch операций
            batch_size = 100
            for i in range(0, len(objects_to_insert), batch_size):
                batch = objects_to_insert[i : i + batch_size]
                result = collection.data.insert_many(batch)
                added_count += len(batch)

        log(f"✅ Добавлено {added_count} параграфов в Weaviate для документа {document_id}")
        return added_count

    def add_chat_messages(
        self, messages: List[Dict[str, Any]], chat_id: str, group_consecutive: bool = True, classify: bool = True
    ) -> int:
        """
        Добавляет чат-сообщения в Weaviate

        Args:
            messages: Список сообщений для индексации
            chat_id: ID чата
            group_consecutive: Группировать ли последовательные сообщения одного автора
            classify: Выполнять ли классификацию и проверку достоверности

        Returns:
            Количество добавленных параграфов
        """
        if not messages:
            return 0

        # Фильтруем сообщения с текстом
        valid_messages = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("text"):
                valid_messages.append(msg)
            elif hasattr(msg, "text") and msg.text:
                valid_messages.append(msg)

        if not valid_messages:
            return 0

        # Создаем параграфы
        if group_consecutive:
            paragraphs = self._group_consecutive_messages(valid_messages)
        else:
            paragraphs = []
            for i, msg in enumerate(valid_messages):
                paragraph = self._create_paragraph_from_message(msg, chat_id, DocumentType.CHAT, index=i)
                paragraphs.append(paragraph)

        if not paragraphs:
            return 0

        # Классифицируем параграфы, если нужно
        if classify:
            for paragraph in paragraphs:
                paragraph = self._classify_paragraph(paragraph)

        log(f"🔄 Добавление {len(paragraphs)} параграфов в Weaviate для чата {chat_id}...")

        # Добавляем в Weaviate батчами (v4 API)
        from weaviate.classes.data import DataObject

        collection = self.client.collections.get(WEAVIATE_CLASS_NAME)
        added_count = 0

        # Подготавливаем объекты для batch insert
        objects_to_insert = []
        for paragraph in paragraphs:
            if paragraph.embedding is None:
                paragraph.embedding = self._create_embedding(paragraph.content)

            obj = self._paragraph_to_weaviate_object(paragraph)
            vector = paragraph.embedding.tolist()

            # В v4 используем UUID из paragraph.id или генерируем новый
            para_uuid = paragraph.id.replace("para_", "") if paragraph.id.startswith("para_") else paragraph.id
            try:
                # Проверяем, валидный ли UUID
                para_uuid_obj = uuid.UUID(para_uuid)
            except (ValueError, AttributeError):
                # Если не валидный, генерируем новый
                para_uuid_obj = uuid.uuid4()

            # В v4 используем DataObject для объектов с кастомным вектором
            objects_to_insert.append(
                DataObject(
                    uuid=para_uuid_obj,
                    properties=obj,
                    vector=vector,
                )
            )

        # Вставляем батчами
        if objects_to_insert:
            # В v4 используем insert_many для batch операций
            batch_size = 100
            for i in range(0, len(objects_to_insert), batch_size):
                batch = objects_to_insert[i : i + batch_size]
                result = collection.data.insert_many(batch)
                added_count += len(batch)

        log(f"✅ Добавлено {added_count} параграфов в Weaviate для чата {chat_id}")
        return added_count

    def search_similar(
        self,
        query: str,
        document_id: str,
        top_k: int = 10,
        classification_filter: Optional[ClassificationType] = None,
        fact_check_filter: Optional[FactCheckResult] = None,
        location_filter: Optional[str] = None,
        ecosystem_id_filter: Optional[str] = None,
        organism_ids_filter: Optional[List[str]] = None,
    ) -> List[Tuple[Paragraph, float]]:
        """
        Ищет наиболее похожие параграфы в Weaviate с фильтрацией по метаданным (v4 API).

        Args:
            query: Поисковый запрос.
            document_id: ID документа для поиска.
            top_k: Количество результатов.
            classification_filter: Фильтр по типу классификации.
            fact_check_filter: Фильтр по результату проверки достоверности.
            location_filter: Фильтр по локации.
            ecosystem_id_filter: Фильтр по ID экосистемы.
            organism_ids_filter: Фильтр по списку ID организмов.

        Returns:
            Список кортежей (параграф, оценка схожести).
        """
        query_embedding = self._create_embedding(query).tolist()
        collection = self.client.collections.get(WEAVIATE_CLASS_NAME)

        # Строим фильтр Weaviate v4
        filters = []

        # Фильтр по document_id
        if document_id:
            filters.append(Filter.by_property("document_id").equal(document_id))

        # Фильтр по классификации (через tags)
        if classification_filter:
            filters.append(Filter.by_property("tags").contains_any([classification_filter.value]))

        # Фильтр по fact_check_result (если есть в схеме)
        if fact_check_filter:
            filters.append(Filter.by_property("fact_check_result").equal(fact_check_filter.value))

        # Фильтр по локации
        if location_filter:
            filters.append(Filter.by_property("location").equal(location_filter))

        # Фильтр по экосистеме
        if ecosystem_id_filter:
            filters.append(Filter.by_property("ecosystem_id").equal(ecosystem_id_filter))

        # Фильтр по organism_ids
        if organism_ids_filter:
            filters.append(Filter.by_property("organism_ids").contains_any(organism_ids_filter))

        # Объединяем фильтры через AND
        combined_filter = Filter.all_of(filters) if len(filters) > 1 else (filters[0] if filters else None)

        try:
            # Выполняем поиск в Weaviate v4
            response = collection.query.near_vector(
                near_vector=query_embedding,
                limit=top_k,
                filters=combined_filter,
                return_metadata=MetadataQuery(distance=True),
                include_vector=True,
            )

            results = []
            for obj in response.objects:
                # Получаем вектор из объекта
                vector = None
                if obj.vector is not None:
                    if isinstance(obj.vector, dict):
                        # Named vectors - извлекаем default или первый доступный
                        if "default" in obj.vector:
                            vector_list = obj.vector["default"]
                        elif len(obj.vector) > 0:
                            vector_list = list(obj.vector.values())[0]
                        else:
                            vector_list = None

                        if vector_list and isinstance(vector_list, (list, tuple)):
                            vector = np.array(vector_list, dtype=np.float32)
                    elif isinstance(obj.vector, (list, tuple)):
                        vector = np.array(obj.vector, dtype=np.float32)

                paragraph = self._weaviate_object_to_paragraph(obj, vector=vector)

                # Weaviate возвращает distance (расстояние), конвертируем в similarity (схожесть)
                distance = 1.0  # Default
                if obj.metadata and hasattr(obj.metadata, "distance"):
                    try:
                        distance_val = obj.metadata.distance
                        if isinstance(distance_val, (int, float)):
                            distance = float(distance_val)
                        elif isinstance(distance_val, dict):
                            # Если distance приходит как dict, используем default
                            log(f"⚠️ distance is dict: {distance_val}")
                            distance = 1.0
                        elif distance_val is not None:
                            distance = float(distance_val)
                        else:
                            distance = 1.0
                    except (ValueError, TypeError) as e:
                        log(f"⚠️ Cannot convert distance {obj.metadata.distance} to float: {e}")
                        distance = 1.0

                similarity = 1.0 - distance  # Для косинусного расстояния
                results.append((paragraph, float(similarity)))

            return results
        except Exception as e:
            log(f"❌ Ошибка поиска в Weaviate: {e}")
            return []

    async def search_similar_paragraphs(
        self,
        query: str,
        document_id: str,
        top_k: int = 10,
        classification_filter: Optional[ClassificationType] = None,
        fact_check_filter: Optional[FactCheckResult] = None,
        location_filter: Optional[str] = None,
        ecosystem_id_filter: Optional[str] = None,
        organism_ids_filter: Optional[List[str]] = None,
    ) -> List[Paragraph]:
        """
        Ищет наиболее похожие параграфы, возвращая только параграфы без оценок.
        Если прямых совпадений мало или нет, использует LLM для перефразирования.
        """
        # 1. Прямой поиск
        similar_pairs = self.search_similar(
            query,
            document_id,
            top_k,
            classification_filter,
            fact_check_filter,
            location_filter,
            ecosystem_id_filter,
            organism_ids_filter,
        )

        # Если результатов достаточно, возвращаем их
        if len(similar_pairs) >= 3:
            return [para for para, score in similar_pairs]

        log(f"🔍 Мало результатов ({len(similar_pairs)}), пробуем перефразировать запрос: '{query}'")
        from api.llm import rephrase_search_query

        rephrased_queries = await rephrase_search_query(query)

        all_results = {}  # Используем dict для дедупликации по paragraph_id

        # Добавляем исходные результаты
        for para, score in similar_pairs:
            all_results[para.id] = (para, score)

        # Ищем по перефразированным запросам
        for new_query in rephrased_queries:
            log(f"🔄 Поиск по перефразированному запросу: '{new_query}'")
            new_pairs = self.search_similar(
                new_query,
                document_id,
                top_k=3,
                classification_filter=classification_filter,
                fact_check_filter=fact_check_filter,
                location_filter=location_filter,
                ecosystem_id_filter=ecosystem_id_filter,
                organism_ids_filter=organism_ids_filter,
            )
            for para, score in new_pairs:
                # Если параграф уже есть, оставляем с лучшим скором
                if para.id not in all_results or score > all_results[para.id][1]:
                    all_results[para.id] = (para, score)

        # Сортируем по скору
        sorted_results = sorted(all_results.values(), key=lambda x: x[1], reverse=True)

        return [para for para, score in sorted_results[:top_k]]

    def get_paragraph_by_id(self, document_id: str, paragraph_id: str) -> Optional[Paragraph]:
        """Получает параграф по ID из Weaviate (v4 API).

        Args:
            document_id: ID документа (для совместимости с FAISSStorage, используется для фильтрации)
            paragraph_id: ID параграфа (UUID в Weaviate)
        """
        try:
            collection = self.client.collections.get(WEAVIATE_CLASS_NAME)

            # Пытаемся получить объект напрямую по UUID
            try:
                para_uuid = paragraph_id.replace("para_", "") if paragraph_id.startswith("para_") else paragraph_id
                para_uuid_obj = uuid.UUID(para_uuid)

                obj = collection.query.fetch_object_by_id(
                    uuid=para_uuid_obj,
                    include_vector=True,
                )

                if obj:
                    # Проверяем document_id, если указан
                    if document_id and obj.properties.get("document_id") != document_id:
                        return None
                    # Конвертируем в Paragraph (вектор обрабатывается внутри _weaviate_object_to_paragraph)
                    return self._weaviate_object_to_paragraph(obj, vector=None)
            except (ValueError, AttributeError) as e:
                # Если не валидный UUID, используем запрос с фильтром
                if not document_id:
                    return None

                # Ищем по document_id и проверяем paragraph_id вручную
                filters = [Filter.by_property("document_id").equal(document_id)]

                response = collection.query.fetch_objects(  # type: ignore
                    limit=10000,  # Получаем все параграфы документа
                    filters=Filter.all_of(filters) if len(filters) > 1 else filters[0],
                    include_vector=True,
                )

                for obj in response.objects:  # type: ignore
                    # Проверяем UUID
                    if str(obj.uuid) == paragraph_id or str(obj.uuid) == para_uuid:
                        # Вектор обрабатывается внутри _weaviate_object_to_paragraph
                        return self._weaviate_object_to_paragraph(obj, vector=None)

            return None
        except Exception as e:
            log(f"❌ Ошибка получения параграфа {paragraph_id} из Weaviate: {e}")
            return None

    def get_document_paragraphs(self, document_id: str) -> List[Paragraph]:
        """Получает все параграфы документа из Weaviate (v4 API)."""
        try:
            collection = self.client.collections.get(WEAVIATE_CLASS_NAME)

            response = collection.query.fetch_objects(
                filters=Filter.by_property("document_id").equal(document_id),
                limit=10000,  # TODO: Implement pagination if documents can be very large
                include_vector=True,
            )

            paragraphs = []
            for obj in response.objects:
                try:
                    vector = None
                    if obj.vector is not None:
                        # В v4 векторы могут быть dict для named vectors или list для default
                        if isinstance(obj.vector, dict):
                            # Если это dict, пробуем извлечь default вектор или первый доступный
                            if "default" in obj.vector:
                                vector_list = obj.vector["default"]
                            elif len(obj.vector) > 0:
                                # Берем первый доступный вектор
                                vector_list = list(obj.vector.values())[0]
                            else:
                                vector_list = None

                            if vector_list and isinstance(vector_list, (list, tuple)):
                                vector = np.array(vector_list, dtype=np.float32)
                            else:
                                log(f"⚠️ Не удалось извлечь вектор из dict: {obj.vector}")
                        elif isinstance(obj.vector, (list, tuple)):
                            vector = np.array(obj.vector, dtype=np.float32)
                        else:
                            log(f"⚠️ Неожиданный тип vector: {type(obj.vector)}")
                    paragraph = self._weaviate_object_to_paragraph(obj, vector=vector)
                    paragraphs.append(paragraph)
                except Exception as e:
                    log(f"❌ Ошибка обработки объекта {obj.uuid}: {e}")
                    import traceback

                    log(f"Traceback: {traceback.format_exc()}")
                    # Продолжаем, чтобы не падать на одном объекте
                    continue

            return paragraphs
        except Exception as e:
            log(f"❌ Ошибка получения параграфов документа {document_id} из Weaviate: {e}")
            import traceback

            log(f"Traceback: {traceback.format_exc()}")
            return []

    def get_all_documents(self) -> List[str]:
        """Получает список всех уникальных document_id из Weaviate (v4 API)."""
        try:
            collection = self.client.collections.get(WEAVIATE_CLASS_NAME)

            # Получаем все объекты с document_id (с пагинацией для больших коллекций)
            document_ids = set()
            limit = 1000
            offset = 0

            while True:
                response = collection.query.fetch_objects(
                    limit=limit,
                    offset=offset,
                    return_properties=["document_id"],
                )

                if not response.objects:
                    break

                for obj in response.objects:
                    doc_id = obj.properties.get("document_id")
                    if doc_id:
                        document_ids.add(doc_id)

                if len(response.objects) < limit:
                    break

                offset += limit

            return sorted([str(doc_id) for doc_id in document_ids])
        except Exception as e:
            log(f"❌ Ошибка получения списка документов из Weaviate: {e}")
            return []

    def update_paragraph(self, document_id: str, paragraph: Paragraph) -> bool:
        """
        Обновляет параграф в Weaviate (v4 API).

        Args:
            document_id: ID документа (для совместимости с FAISSStorage)
            paragraph: Обновленный параграф.

        Returns:
            True если успешно обновлено.
        """
        if not paragraph.id:
            log("❌ Невозможно обновить параграф: отсутствует ID")
            return False

        try:
            collection = self.client.collections.get(WEAVIATE_CLASS_NAME)

            # Создаем эмбеддинг, если его нет
            if paragraph.embedding is None:
                paragraph.embedding = self._create_embedding(paragraph.content)

            obj = self._paragraph_to_weaviate_object(paragraph)
            vector = paragraph.embedding.tolist()

            # Преобразуем paragraph.id в UUID
            para_uuid = paragraph.id.replace("para_", "") if paragraph.id.startswith("para_") else paragraph.id
            try:
                para_uuid_obj = uuid.UUID(para_uuid)
            except (ValueError, AttributeError):
                log(f"❌ Невозможно обновить параграф: невалидный UUID {paragraph.id}")
                return False

            # Обновляем объект в Weaviate v4
            collection.data.update(
                uuid=para_uuid_obj,
                properties=obj,
                vector=vector,
            )
            log(f"✅ Параграф {paragraph.id} успешно обновлен в Weaviate")
            return True
        except Exception as e:
            log(f"❌ Ошибка обновления параграфа {paragraph.id} в Weaviate: {e}")
            return False

    def delete_paragraph(self, _document_id: str, paragraph_id: str) -> bool:
        """
        Удаляет параграф из Weaviate (v4 API).

        Args:
            document_id: ID документа (для совместимости с FAISSStorage)
            paragraph_id: ID параграфа.

        Returns:
            True если успешно удалено.
        """
        try:
            collection = self.client.collections.get(WEAVIATE_CLASS_NAME)

            # Преобразуем paragraph_id в UUID
            para_uuid = paragraph_id.replace("para_", "") if paragraph_id.startswith("para_") else paragraph_id
            try:
                para_uuid_obj = uuid.UUID(para_uuid)
            except (ValueError, AttributeError):
                log(f"❌ Невозможно удалить параграф: невалидный UUID {paragraph_id}")
                return False

            # Удаляем объект в Weaviate v4
            collection.data.delete_by_id(uuid=para_uuid_obj)
            log(f"✅ Параграф {paragraph_id} успешно удален из Weaviate")
            return True
        except Exception as e:
            log(f"❌ Ошибка удаления параграфа {paragraph_id} из Weaviate: {e}")
            return False

    def reclassify_paragraph(self, document_id: str, paragraph_id: str, tag_service=None) -> bool:
        """Переклассифицирует параграф и обновляет его в Weaviate."""
        paragraph = self.get_paragraph_by_id(document_id, paragraph_id)
        if not paragraph:
            return False

        # Обновляем классификацию
        tag_service = tag_service or getattr(self, "_tag_service", None)
        paragraph = self._classify_paragraph(paragraph, tag_service=tag_service)

        # Обновляем параграф в Weaviate
        return self.update_paragraph(document_id, paragraph)

    def reclassify_document(self, document_id: str) -> int:
        """Переклассифицирует все параграфы в документе и обновляет их в Weaviate (v4 API)."""
        paragraphs = self.get_document_paragraphs(document_id)
        updated_count = 0

        for paragraph in paragraphs:
            if self.reclassify_paragraph(document_id, paragraph.id):
                updated_count += 1

        return updated_count
