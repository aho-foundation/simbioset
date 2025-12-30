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
from weaviate.classes.query import Filter, MetadataQuery, HybridFusion
from weaviate.config import Timeout, AdditionalConfig
import asyncio
from functools import lru_cache

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
    WEAVIATE_CLASS_NAME,
    WEAVIATE_BATCH_SIZE,
    WEAVIATE_USE_BUILTIN_AUTOSCHEMA,
    ENABLE_AUTOMATIC_DETECTORS,
    WEAVIATE_USE_HYBRID_SEARCH,
    WEAVIATE_HYBRID_ALPHA,
    WEAVIATE_USE_RERANKING,
    WEAVIATE_RERANK_LIMIT,
    WEAVIATE_EMBEDDING_CACHE_SIZE,
)
from api.storage.weaviate_schema import create_schema_if_not_exists, update_schema_if_needed
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
        weaviate_url = WEAVIATE_URL
        if not weaviate_url:
            log("❌ WEAVIATE_URL не задан, невозможно подключиться к Weaviate")
            raise ValueError("WEAVIATE_URL is required for Weaviate connection")

        # Генерируем список возможных хостов для Dokku/Docker среды
        url_parts = weaviate_url.replace("http://", "").replace("https://", "").split(":")
        base_host = url_parts[0] if url_parts else "localhost"
        http_port = int(url_parts[1]) if len(url_parts) > 1 else 8080
        http_secure = weaviate_url.startswith("https://")

        # Возможные варианты DNS имен для Dokku
        possible_hosts = []
        if base_host != "localhost":
            # Разбираем base_host на компоненты
            host_parts = base_host.split(".")
            if len(host_parts) >= 2:
                service_name = host_parts[0]  # 'weaviate'
                app_name = host_parts[1] if len(host_parts) > 1 else None  # 'web'

                # Генерируем варианты
                possible_hosts.extend(
                    [
                        base_host,  # weaviate.web.1
                        f"{service_name}.{app_name}",  # weaviate.web
                        service_name,  # weaviate
                        f"{service_name}.web.1",  # weaviate.web.1 (уже есть)
                    ]
                )
            else:
                possible_hosts.append(base_host)

        # Добавляем localhost как fallback
        if "localhost" not in possible_hosts:
            possible_hosts.append("localhost")

        # Убираем дубликаты
        possible_hosts = list(set(possible_hosts))
        log(f"🔍 Проверяем возможные хосты Weaviate: {possible_hosts}")

        # Парсим gRPC URL или вычисляем из HTTP URL
        weaviate_grpc_url = WEAVIATE_GRPC_URL

        connection_success = False
        last_error: Optional[Exception] = None

        # Пробуем подключиться к каждому возможному хосту
        for http_host in possible_hosts:
            try:
                if not weaviate_grpc_url:
                    # Вычисляем gRPC URL из HTTP URL (предполагаем стандартные порты)
                    # Для Weaviate стандартный HTTP порт 8080, gRPC 50051
                    grpc_host = http_host
                    grpc_port = 50051 if http_port == 8080 else http_port + 1  # 8080 -> 50051, иначе +1
                    weaviate_grpc_url = f"{grpc_host}:{grpc_port}"

                grpc_parts = weaviate_grpc_url.split(":")
                grpc_host = grpc_parts[0] if grpc_parts else "localhost"
                grpc_port = int(grpc_parts[1]) if len(grpc_parts) > 1 else 50051
                grpc_secure = False  # gRPC обычно не использует SSL во внутренней сети

                log(
                    f"🔗 Пробуем подключиться к Weaviate - HTTP: {http_host}:{http_port} (secure: {http_secure}), gRPC: {grpc_host}:{grpc_port} (secure: {grpc_secure})"
                )

                # Создаем подключение с приоритетом gRPC для векторных операций
                connection_params = weaviate.connect.base.ConnectionParams.from_params(
                    http_host=http_host,
                    http_port=http_port,
                    http_secure=http_secure,
                    grpc_host=grpc_host,
                    grpc_port=grpc_port,
                    grpc_secure=grpc_secure,
                )

                # Настраиваем таймауты согласно best practices
                timeout_config = Timeout(
                    init=10,  # таймаут инициализации клиента (был 30 сек в main.py)
                    query=30,  # таймаут для запросов
                    insert=60,  # таймаут для вставки (batch операции могут быть долгими)
                )

                # Настраиваем дополнительные параметры клиента
                additional_config = AdditionalConfig(timeout=timeout_config)

                # Если gRPC предпочтителен, настраиваем клиент для использования gRPC по умолчанию
                client_kwargs = {
                    "connection_params": connection_params,
                    "auth_client_secret": auth_config,
                    "additional_config": additional_config,
                }

                self.client = weaviate.WeaviateClient(**client_kwargs)  # type: ignore[arg-type]

                # Проверяем подключение
                log("🔌 Вызываем client.connect()...")
                self.client.connect()
                log("✅ client.connect() успешен")

                connection_success = True
                log(f"✅ Подключено к Weaviate на {http_host}:{http_port}")
                break

            except weaviate.exceptions.WeaviateConnectionError as e:
                last_error = e
                log(f"❌ Ошибка подключения к Weaviate {http_host}:{http_port} - {e}")
                continue
            except weaviate.exceptions.WeaviateBaseError as e:
                last_error = e
                log(f"❌ Ошибка Weaviate клиента для {http_host}:{http_port} - {e}")
                continue
            except Exception as e:
                last_error = e
                log(f"❌ Непредвиденная ошибка подключения к {http_host}:{http_port} - {e}")
                continue

        if not connection_success:
            log(f"💥 Все варианты подключения к Weaviate провалились. Последняя ошибка: {last_error}")
            if last_error:
                raise last_error
            else:
                raise RuntimeError("Не удалось подключиться к Weaviate: все хосты недоступны")

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

        self.client = weaviate.WeaviateClient(**client_kwargs)  # type: ignore[arg-type]

        # Проверяем подключение и создаем схему
        try:
            log("🔌 Вызываем client.connect()...")
            self.client.connect()
            log("✅ client.connect() успешен")

            log("📊 Получаем метаданные...")
            meta = self.client.get_meta()
            log(f"✅ Подключено к Weaviate {meta.get('version', 'unknown')} на {weaviate_url}")

            # Схема: встроенная AutoSchema Weaviate или ручное управление
            if WEAVIATE_USE_BUILTIN_AUTOSCHEMA:
                log("🤖 Встроенная AutoSchema Weaviate активна - схема будет создаваться автоматически из данных")
                log("📈 Это идеально для симбиосети: связи и паттерны могут эволюционировать органически")
            else:
                log("🔧 Ручное управление схемой - создаем предопределенную схему")
                create_schema_if_not_exists(self.client)
                # Проверяем обновления для совместимости
                if update_schema_if_needed(self.client):
                    log("🔄 Схема была обновлена")
                else:
                    log("✅ Схема актуальна")
        except Exception as e:
            log(f"❌ Ошибка подключения к Weaviate: {e}")
            log(f"🔍 Детали ошибки: {type(e).__name__}: {str(e)}")
            raise

        log(f"✅ Модель загружена, размерность эмбеддингов: {self.dimension}")

        # Связанный сервис тегов задается снаружи
        self._tag_service: Optional[Any] = None

        # Кеш для эмбеддингов (опционально, если включен)
        self._embedding_cache_enabled = WEAVIATE_EMBEDDING_CACHE_SIZE > 0
        if self._embedding_cache_enabled:
            log(f"💾 Кеширование эмбеддингов включено (размер: {WEAVIATE_EMBEDDING_CACHE_SIZE})")

    def close(self) -> None:
        """
        Правильно закрывает соединение с Weaviate согласно best practices.

        Следует вызывать при завершении работы приложения.
        """
        if hasattr(self, "client") and self.client:
            try:
                log("🔌 Закрываем соединение с Weaviate...")
                self.client.close()
                log("✅ Соединение с Weaviate закрыто")
            except Exception as e:
                log(f"⚠️ Ошибка при закрытии соединения с Weaviate: {e}")

    def __enter__(self):
        """Контекстный менеджер - вход"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход с автоматическим закрытием"""
        self.close()

    def __del__(self):
        """Деструктор - финальная попытка закрыть соединение"""
        try:
            self.close()
        except BaseException:
            pass  # Игнорируем ошибки в деструкторе

    def _create_paragraph_id(
        self,
        content: str,
        author: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        index: Optional[int] = None,
    ) -> str:
        """Создает уникальный ID для параграфа"""
        unique_id = str(uuid.uuid4())
        if index is not None:
            return f"para_{unique_id}_idx_{index}"
        return f"para_{unique_id}"

    def _create_embedding(self, text: str) -> np.ndarray:
        """
        Создает эмбеддинг для текста с опциональным кешированием

        Args:
            text: Текст для создания эмбеддинга

        Returns:
            Нормализованный вектор эмбеддинга
        """
        # Используем кешированную версию если включено
        if self._embedding_cache_enabled:
            return self._create_embedding_cached(text)

        embedding = self.model.encode(text, convert_to_numpy=True)

        # Нормализуем для косинусного сходства
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return cast(np.ndarray, embedding.astype("float32"))

    def _create_embedding_cached(self, text: str) -> np.ndarray:
        """
        Кешированная версия создания эмбеддинга
        Использует простой словарь для кеша (lru_cache не работает с numpy arrays)
        """
        if not hasattr(self, "_embedding_cache"):
            self._embedding_cache: Dict[str, np.ndarray] = {}
            self._embedding_cache_max_size = WEAVIATE_EMBEDDING_CACHE_SIZE

        # Проверяем кеш
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        # Создаем эмбеддинг
        embedding = self.model.encode(text, convert_to_numpy=True)

        # Нормализуем для косинусного сходства
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        embedding = cast(np.ndarray, embedding.astype("float32"))

        # Сохраняем в кеш (с ограничением размера)
        if len(self._embedding_cache) >= self._embedding_cache_max_size:
            # Удаляем самый старый элемент (FIFO)
            oldest_key = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest_key]

        self._embedding_cache[text] = embedding
        return embedding

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
            "organisms": paragraph.organisms or [],
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

    def _extract_text(self, message: Dict[str, Any]) -> str:
        """
        Извлекает текст из сообщения для создания эмбеддинга

        Args:
            message: Словарь с данными сообщения или TelegramMessage

        Returns:
            Текст сообщения
        """
        if hasattr(message, "text"):  # TelegramMessage object
            text = message.text or ""
            from_user = getattr(message, "from_user", None)
            if from_user:
                username = getattr(from_user, "username", "") or getattr(from_user, "first_name", "")
            else:
                username = ""
        elif isinstance(message, dict):  # Dictionary
            text = message.get("text", "")
            from_user = message.get("from", message.get("from_user", {}))
            if isinstance(from_user, dict):
                username = from_user.get("username", from_user.get("first_name", ""))
            else:
                username = ""
        else:
            text = ""
            username = ""

        return f"{username}: {text}"

    def _create_paragraph_from_message(
        self, message: Dict[str, Any], document_id: str, document_type: DocumentType, index: Optional[int] = None
    ) -> Paragraph:
        """Создает параграф из сообщения"""
        if isinstance(message, dict):
            text = message.get("text", "")
            author = message.get("from", message.get("from_user", {}))
            if isinstance(author, dict):
                author_name = author.get("username", author.get("first_name", ""))
                author_id = author.get("id")
            else:
                author_name = ""
                author_id = None

            timestamp = message.get("date") if isinstance(message.get("date"), datetime) else None
        else:
            text = ""
            author_name = ""
            author_id = None
            timestamp = None

        # Создаем параграф
        paragraph = Paragraph(
            id=self._create_paragraph_id(text, author_name, timestamp, index),
            content=text,
            author=author_name,
            author_id=author_id,
            timestamp=timestamp,
            document_id=document_id,
            document_type=document_type,
            paragraph_index=index,
        )

        # Создаем эмбеддинг
        paragraph.embedding = self._create_embedding(text)

        return paragraph

    def _group_consecutive_messages(self, messages: List[Dict[str, Any]]) -> List[Paragraph]:
        """Группирует последовательные сообщения одного автора в один параграф"""
        if not messages:
            return []

        grouped_paragraphs = []
        current_author = None
        current_content: list[str] = []
        current_metadata: dict[str, Any] = {}
        current_timestamp = None

        for msg in messages:
            if isinstance(msg, dict):
                author_id: Optional[int] = None
                author_name: Optional[str] = None

                from_user = msg.get("from", msg.get("from_user", {}))
                if isinstance(from_user, dict):
                    author_id = from_user.get("id")
                    author_name = from_user.get("username") or from_user.get("first_name")

                # Если это первый сообщение или автор изменился
                if current_author is None or current_author != author_id:
                    # Сохраняем предыдущий параграф, если он есть
                    if current_content:
                        combined_content = "\n".join(current_content)
                        paragraph = Paragraph(
                            id=self._create_paragraph_id(combined_content, current_author),
                            content=combined_content,
                            author=current_author,
                            metadata=current_metadata.copy(),
                            timestamp=current_timestamp,
                        )
                        grouped_paragraphs.append(paragraph)

                    # Начинаем новый параграф
                    current_author = author_name or f"user_{author_id}" if author_id else "unknown"
                    current_content = []
                    current_metadata = {}
                    current_timestamp = msg.get("date") if isinstance(msg.get("date"), datetime) else None

                current_content.append(msg.get("text", ""))

        # Добавляем последний параграф
        if current_content:
            combined_content = "\n".join(current_content)
            paragraph = Paragraph(
                id=self._create_paragraph_id(combined_content, current_author),
                content=combined_content,
                author=current_author,
                metadata=current_metadata.copy(),
                timestamp=current_timestamp,
            )
            grouped_paragraphs.append(paragraph)

        for paragraph in grouped_paragraphs:
            paragraph.embedding = self._create_embedding(paragraph.content)

        return grouped_paragraphs

    def _classify_paragraph(self, paragraph: Paragraph, tag_service=None) -> Paragraph:
        """Классифицирует параграф с использованием модулей классификации.

        Определяет множественные теги для параграфа, так как он может одновременно
        описывать уязвимости, риски и решения.
        """
        try:
            # Импортируем классификаторы опционально
            try:
                from api.detect.rolestate import classify_message_type
                from api.detect.factcheck import check_factuality
                from api.detect.localize import extract_location_and_time
                from api.detect.organism_detector import detect_organisms
                from api.detect.ecosystem_scaler import detect_ecosystems
            except ImportError:
                log("⚠️ Модули классификации недоступны, пропускаем классификацию")
                return paragraph

            # Используем гибридную классификацию (Weaviate + LLM) если доступны оба компонента
            if tag_service and ENABLE_AUTOMATIC_DETECTORS and self._is_weaviate_available():
                # Гибридная классификация: используем похожие параграфы для контекста
                hybrid_tags = self._classify_with_hybrid_approach(paragraph, tag_service)
                if hybrid_tags:
                    paragraph.tags = hybrid_tags
                    # Устанавливаем classification enum
                    self._set_classification_from_tags(paragraph, hybrid_tags)
                    # Обновляем статистику использования тегов
                    tag_service.update_tag_usage(hybrid_tags)
                    # Добавляем примеры
                    for tag in hybrid_tags:
                        tag_service.add_example_to_tag(tag, paragraph.content[:200])
                else:
                    # Fallback на обычную LLM классификацию
                    self._classify_with_llm_fallback_sync(paragraph, tag_service)
            # Используем обычную LLM классификацию если явно включены автоматические детекторы
            elif tag_service and ENABLE_AUTOMATIC_DETECTORS:
                import asyncio

                try:
                    # Создаем новый event loop если его нет
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    # Предлагаем теги через LLM
                    suggested_tags = loop.run_until_complete(
                        tag_service.suggest_tags_for_paragraph(paragraph.content, paragraph.tags)
                    )
                    if suggested_tags:
                        paragraph.tags = suggested_tags
                        # Устанавливаем classification enum на основе первого тега
                        if suggested_tags:
                            try:
                                classification_map = {
                                    "ecosystem_risk": ClassificationType.ECOSYSTEM_RISK,
                                    "ecosystem_vulnerability": ClassificationType.ECOSYSTEM_VULNERABILITY,
                                    "suggested_ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
                                    "ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
                                }
                                paragraph.classification = classification_map.get(suggested_tags[0])
                            except (ValueError, KeyError):
                                log(f"⚠️ Неизвестный тип классификации в тегах: {suggested_tags[0]}")
                        # Обновляем счетчики использования тегов
                        tag_service.update_tag_usage(suggested_tags)
                        # Добавляем примеры использования
                        for tag in suggested_tags:
                            tag_service.add_example_to_tag(tag, paragraph.content[:200])
                except Exception as e:
                    log(f"⚠️ Ошибка при предложении тегов через LLM: {e}")
                    # Fallback на старый классификатор
                    classification_result = classify_message_type(paragraph.content)
                    if classification_result:
                        if isinstance(classification_result, str):
                            paragraph.tags = [classification_result]
                            # Устанавливаем classification enum на основе строки
                            try:
                                classification_map = {
                                    "ecosystem_risk": ClassificationType.ECOSYSTEM_RISK,
                                    "ecosystem_vulnerability": ClassificationType.ECOSYSTEM_VULNERABILITY,
                                    "suggested_ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
                                    "ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
                                    "neutral": ClassificationType.NEUTRAL,
                                }
                                paragraph.classification = classification_map.get(classification_result)
                            except (ValueError, KeyError):
                                log(f"⚠️ Неизвестный тип классификации: {classification_result}")
                        elif isinstance(classification_result, list):
                            paragraph.tags = classification_result
                            # Берем первый тег для classification
                            if classification_result:
                                try:
                                    classification_map = {
                                        "ecosystem_risk": ClassificationType.ECOSYSTEM_RISK,
                                        "ecosystem_vulnerability": ClassificationType.ECOSYSTEM_VULNERABILITY,
                                        "suggested_ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
                                        "ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
                                        "neutral": ClassificationType.NEUTRAL,
                                    }
                                    paragraph.classification = classification_map.get(classification_result[0])
                                except (ValueError, KeyError):
                                    log(f"⚠️ Неизвестный тип классификации: {classification_result[0]}")

            # Проверка достоверности
            fact_check_result = check_factuality(paragraph.content)
            if fact_check_result:
                paragraph.fact_check_result = FactCheckResult(fact_check_result.get("status", "unknown"))
                paragraph.fact_check_details = fact_check_result.get("details")

            # Локализация (место и время)
            location_result = extract_location_and_time(paragraph.content)
            if location_result:
                paragraph.location = location_result.get("location")
                paragraph.time_reference = location_result.get("time_reference")

            # Автоматические детекторы (экосистемы / организмы) при сохранении параграфов
            # по умолчанию отключены, чтобы не ломать UX быстрого общения.
            if ENABLE_AUTOMATIC_DETECTORS:
                # Обнаружение экосистем (используя данные локализации)
                try:
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    ecosystems = loop.run_until_complete(
                        detect_ecosystems(paragraph.content, location_data=location_result)
                    )

                    if ecosystems:
                        if not paragraph.metadata:
                            paragraph.metadata = {}
                        paragraph.metadata["ecosystems"] = ecosystems
                        log(f"✅ Обнаружено {len(ecosystems)} экосистем в параграфе")
                except ImportError:
                    log("⚠️ Модуль обнаружения экосистем недоступен, пропускаем")
                except Exception as e:
                    log(f"⚠️ Ошибка при обнаружении экосистем: {e}")

                # Обнаружение и классификация организмов
                try:
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    organisms = loop.run_until_complete(detect_organisms(paragraph.content))

                    if organisms:
                        # Импортируем классификатор организмов
                        try:
                            from api.classify.organism_classifier import classify_organisms_batch

                            classified_organisms = loop.run_until_complete(classify_organisms_batch(organisms))
                        except ImportError:
                            # Если классификатор недоступен, используем сырые данные
                            classified_organisms = organisms
                            log("⚠️ Классификатор организмов недоступен, используем сырые данные")

                        # Сохраняем организмы в dedicated поле
                        paragraph.organisms = classified_organisms

                        # Также сохраняем в metadata для обратной совместимости
                        if not paragraph.metadata:
                            paragraph.metadata = {}
                        paragraph.metadata["organisms"] = classified_organisms

                        log(f"✅ Обнаружено и классифицировано {len(classified_organisms)} организмов в параграфе")
                except ImportError:
                    log("⚠️ Модули обнаружения организмов недоступны, пропускаем")
                except Exception as e:
                    log(f"⚠️ Ошибка при обнаружении организмов: {e}")

        except Exception as e:
            log(f"⚠️ Ошибка при классификации параграфа: {e}")

        return paragraph

    def _is_weaviate_available(self) -> bool:
        """Проверяет доступность Weaviate для гибридной классификации"""
        try:
            # Проверяем, что у нас есть URL (уже проверено в __init__)
            return bool(WEAVIATE_URL)
        except:
            return False

    def _classify_with_hybrid_approach(self, paragraph: Paragraph, tag_service) -> Optional[List[str]]:
        """Гибридная классификация: использует Weaviate для поиска похожих параграфов"""
        try:
            # Ищем похожие параграфы в Weaviate
            similar_paragraphs = self._find_similar_classified_paragraphs(paragraph.content, limit=5)

            if not similar_paragraphs:
                log("🤖 Гибридная классификация: похожих параграфов не найдено, используем LLM")
                return None

            # Анализируем классификацию похожих параграфов
            tag_scores: dict[str, int] = {}
            classification_counts: dict[str, int] = {}

            for similar_para in similar_paragraphs:
                # Собираем статистику по тегам
                for tag in similar_para.tags:
                    tag_scores[tag] = tag_scores.get(tag, 0) + 1

                # Собираем статистику по типам классификации
                if similar_para.classification:
                    class_name = similar_para.classification.value
                    classification_counts[class_name] = classification_counts.get(class_name, 0) + 1

            # Выбираем наиболее вероятные теги (score > 1)
            candidate_tags = [tag for tag, score in tag_scores.items() if score > 1]

            if candidate_tags:
                log(f"🤖 Гибридная классификация: найдены кандидаты из похожих параграфов: {candidate_tags}")

                # Используем LLM для финального решения с контекстом похожих параграфов
                return self._refine_classification_with_llm(
                    paragraph.content, candidate_tags, similar_paragraphs[:2], tag_service
                )

            return None

        except Exception as e:
            log(f"⚠️ Ошибка в гибридной классификации: {e}")
            return None

    def _find_similar_classified_paragraphs(self, query: str, limit: int = 5) -> List[Paragraph]:
        """Находит похожие параграфы, которые уже классифицированы"""
        try:
            # Ищем во всех документах с фильтром по классифицированным параграфам
            # Это упрощенная версия - в реальности нужно фильтровать по наличию тегов
            # Используем asyncio для вызова async метода из sync контекста
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Если event loop уже запущен, используем create_task
                    # Но это не сработает в sync контексте, поэтому возвращаем пустой список
                    log("⚠️ Event loop уже запущен, пропускаем поиск похожих параграфов")
                    return []
                else:
                    results = loop.run_until_complete(self.search_similar_paragraphs(query, "all", top_k=limit * 2))
            except RuntimeError:
                # Если нет event loop, создаем новый
                results = asyncio.run(self.search_similar_paragraphs(query, "all", top_k=limit * 2))

            # Фильтруем только классифицированные параграфы
            classified_results = [para for para in results if para.tags and len(para.tags) > 0][:limit]

            log(f"🤖 Найдено {len(classified_results)} классифицированных похожих параграфов")
            return classified_results

        except Exception as e:
            log(f"⚠️ Ошибка при поиске похожих параграфов: {e}")
            return []

    def _classify_with_llm_fallback_sync(self, paragraph: Paragraph, tag_service):
        """Fallback на обычную LLM классификацию (синхронная версия)"""
        import asyncio

        try:
            # Создаем новый event loop если его нет
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Предлагаем теги через LLM
            suggested_tags = loop.run_until_complete(
                tag_service.suggest_tags_for_paragraph(paragraph.content, paragraph.tags)
            )
            if suggested_tags:
                paragraph.tags = suggested_tags
                self._set_classification_from_tags(paragraph, suggested_tags)
                # Обновляем статистику использования тегов
                tag_service.update_tag_usage(suggested_tags)
                # Добавляем примеры
                for tag in suggested_tags:
                    tag_service.add_example_to_tag(tag, paragraph.content[:200])
        except Exception as e:
            log(f"⚠️ Ошибка при LLM классификации: {e}")

    def _set_classification_from_tags(self, paragraph: Paragraph, tags: List[str]):
        """Устанавливает classification enum на основе тегов"""
        if not tags:
            return

        classification_map = {
            "ecosystem_risk": ClassificationType.ECOSYSTEM_RISK,
            "ecosystem_vulnerability": ClassificationType.ECOSYSTEM_VULNERABILITY,
            "suggested_ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
            "ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
            "neutral": ClassificationType.NEUTRAL,
        }
        paragraph.classification = classification_map.get(tags[0])

    def _refine_classification_with_llm(
        self, content: str, candidate_tags: List[str], context_paragraphs: List[Paragraph], tag_service
    ) -> Optional[List[str]]:
        """Уточняет классификацию с помощью LLM, используя контекст похожих параграфов"""
        try:
            # Создаем промпт для уточнения классификации
            context = "\n".join(
                [f"Похожий текст: {p.content[:200]}... Теги: {', '.join(p.tags)}" for p in context_paragraphs]
            )

            prompt = f"""На основе следующих похожих текстов и их классификации,
определи наиболее подходящие теги для нового текста.

ПОХОЖИЕ ТЕКСТЫ:
{context}

НОВЫЙ ТЕКСТ:
{content}

КАНДИДАТЫ ТЕГОВ: {", ".join(candidate_tags)}

Верни только список тегов через запятую, без дополнительных комментариев."""

            # Используем tag_service для вызова LLM
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            result = loop.run_until_complete(tag_service.call_llm_for_tags(prompt))

            if result and isinstance(result, list):
                return result
            elif result and isinstance(result, str):
                return [tag.strip() for tag in result.split(",") if tag.strip()]

        except Exception as e:
            log(f"⚠️ Ошибка при уточнении классификации: {e}")

        return candidate_tags  # Возвращаем исходных кандидатов в случае ошибки

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
            batch_size = WEAVIATE_BATCH_SIZE
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
            batch_size = WEAVIATE_BATCH_SIZE
            for i in range(0, len(objects_to_insert), batch_size):
                batch = objects_to_insert[i : i + batch_size]
                result = collection.data.insert_many(batch)
                added_count += len(batch)

        log(f"✅ Добавлено {added_count} параграфов в Weaviate для чата {chat_id}")
        return added_count

    def _build_filters(
        self,
        document_id: Optional[str] = None,
        classification_filter: Optional[ClassificationType] = None,
        fact_check_filter: Optional[FactCheckResult] = None,
        location_filter: Optional[str] = None,
        ecosystem_id_filter: Optional[str] = None,
        organism_ids_filter: Optional[List[str]] = None,
        tags_filter: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        timestamp_from: Optional[int] = None,
        timestamp_to: Optional[int] = None,
    ) -> Optional[Any]:  # type: ignore[return-value]
        """
        Строит фильтр Weaviate v4 с поддержкой расширенных операций (OR, NOT, диапазоны).

        Args:
            document_id: Фильтр по ID документа
            classification_filter: Фильтр по типу классификации
            fact_check_filter: Фильтр по результату проверки достоверности
            location_filter: Фильтр по локации
            ecosystem_id_filter: Фильтр по ID экосистемы
            organism_ids_filter: Фильтр по списку ID организмов
            tags_filter: Фильтр по тегам (OR логика - любой из тегов)
            exclude_tags: Исключить параграфы с этими тегами (NOT логика)
            timestamp_from: Фильтр по минимальному timestamp
            timestamp_to: Фильтр по максимальному timestamp

        Returns:
            Объединенный фильтр или None
        """
        filters = []

        # Фильтр по document_id
        if document_id:
            filters.append(Filter.by_property("document_id").equal(document_id))

        # Фильтр по классификации (через tags)
        if classification_filter:
            filters.append(Filter.by_property("tags").contains_any([classification_filter.value]))

        # Фильтр по fact_check_result
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

        # Фильтр по тегам (OR логика - любой из тегов)
        if tags_filter:
            filters.append(Filter.by_property("tags").contains_any(tags_filter))

        # Исключение тегов (NOT логика)
        # В Weaviate v4 используем contains_none для исключения тегов
        if exclude_tags:
            filters.append(Filter.by_property("tags").contains_none(exclude_tags))

        # Фильтр по timestamp (диапазон)
        if timestamp_from is not None or timestamp_to is not None:
            timestamp_filters = []
            if timestamp_from is not None:
                timestamp_filters.append(Filter.by_property("timestamp").greater_or_equal(timestamp_from))
            if timestamp_to is not None:
                timestamp_filters.append(Filter.by_property("timestamp").less_or_equal(timestamp_to))
            if timestamp_filters:
                filters.append(Filter.all_of(timestamp_filters))

        # Объединяем фильтры через AND
        # Приводим к Any для совместимости с типами Weaviate
        if len(filters) > 1:
            return cast(Any, Filter.all_of(filters))
        elif len(filters) == 1:
            return cast(Any, filters[0])
        else:
            return None

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
        tags_filter: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        timestamp_from: Optional[int] = None,
        timestamp_to: Optional[int] = None,
        use_hybrid: Optional[bool] = None,
        hybrid_alpha: Optional[float] = None,
    ) -> List[Tuple[Paragraph, float]]:
        """
        Ищет наиболее похожие параграфы в Weaviate с фильтрацией по метаданным (v4 API).
        Поддерживает Hybrid Search (векторный + BM25) для улучшения точности.

        Args:
            query: Поисковый запрос.
            document_id: ID документа для поиска.
            top_k: Количество результатов.
            classification_filter: Фильтр по типу классификации.
            fact_check_filter: Фильтр по результату проверки достоверности.
            location_filter: Фильтр по локации.
            ecosystem_id_filter: Фильтр по ID экосистемы.
            organism_ids_filter: Фильтр по списку ID организмов.
            use_hybrid: Использовать Hybrid Search (по умолчанию из WEAVIATE_USE_HYBRID_SEARCH).
            hybrid_alpha: Баланс между BM25 и векторным поиском (0-1, по умолчанию из WEAVIATE_HYBRID_ALPHA).

        Returns:
            Список кортежей (параграф, оценка схожести).
        """
        collection = self.client.collections.get(WEAVIATE_CLASS_NAME)

        # Определяем использовать ли Hybrid Search
        use_hybrid_search = use_hybrid if use_hybrid is not None else WEAVIATE_USE_HYBRID_SEARCH
        alpha = hybrid_alpha if hybrid_alpha is not None else WEAVIATE_HYBRID_ALPHA

        # Строим фильтр с поддержкой расширенных операций
        combined_filter = self._build_filters(
            document_id=document_id,
            classification_filter=classification_filter,
            fact_check_filter=fact_check_filter,
            location_filter=location_filter,
            ecosystem_id_filter=ecosystem_id_filter,
            organism_ids_filter=organism_ids_filter,
            tags_filter=tags_filter,
            exclude_tags=exclude_tags,
            timestamp_from=timestamp_from,
            timestamp_to=timestamp_to,
        )

        try:
            # Выполняем поиск: Hybrid Search или обычный векторный
            if use_hybrid_search:
                try:
                    # Hybrid Search: комбинация векторного поиска и BM25
                    query_embedding = self._create_embedding(query).tolist()
                    response = collection.query.hybrid(
                        query=query,  # Текст для BM25
                        vector=query_embedding,  # Вектор для векторного поиска
                        alpha=alpha,  # Баланс: 0 = только BM25, 1 = только векторный
                        fusion_type=HybridFusion.RELATIVE_SCORE,  # Относительное объединение скоров
                        limit=top_k,
                        filters=cast(Any, combined_filter),  # type: ignore[arg-type]
                        return_metadata=MetadataQuery(score=True, distance=True),
                        include_vector=True,
                    )
                    log(f"🔍 Hybrid Search (alpha={alpha}): BM25 + векторный поиск")
                except Exception as hybrid_error:
                    # Fallback на обычный векторный поиск если Hybrid Search не поддерживается
                    log(f"⚠️ Hybrid Search не поддерживается, используем векторный поиск: {hybrid_error}")
                    query_embedding = self._create_embedding(query).tolist()
                    response = collection.query.near_vector(
                        near_vector=query_embedding,
                        limit=top_k,
                        filters=cast(Any, combined_filter),  # type: ignore[arg-type]
                        return_metadata=MetadataQuery(distance=True),
                        include_vector=True,
                    )
                    log("🔍 Векторный поиск (fallback)")
            else:
                # Обычный векторный поиск
                query_embedding = self._create_embedding(query).tolist()
                response = collection.query.near_vector(
                    near_vector=query_embedding,
                    limit=top_k,
                    filters=cast(Any, combined_filter),  # type: ignore[arg-type]
                    return_metadata=MetadataQuery(distance=True),
                    include_vector=True,
                )
                log("🔍 Векторный поиск")

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

                # Получаем score (для Hybrid Search) или distance (для векторного поиска)
                similarity = 0.0
                if obj.metadata:
                    # Для Hybrid Search используем score
                    if hasattr(obj.metadata, "score") and obj.metadata.score is not None:
                        try:
                            score_val = obj.metadata.score
                            if isinstance(score_val, (int, float)):
                                similarity = float(score_val)
                            elif isinstance(score_val, dict):
                                # Если score приходит как dict, используем default
                                similarity = 0.5
                            else:
                                similarity = float(score_val) if score_val is not None else 0.0
                        except (ValueError, TypeError) as e:
                            log(f"⚠️ Cannot convert score {obj.metadata.score} to float: {e}")
                            similarity = 0.0
                    # Для векторного поиска используем distance
                    elif hasattr(obj.metadata, "distance") and obj.metadata.distance is not None:
                        try:
                            distance_val = obj.metadata.distance
                            if isinstance(distance_val, (int, float)):
                                distance = float(distance_val)
                            elif isinstance(distance_val, dict):
                                log(f"⚠️ distance is dict: {distance_val}")
                                distance = 1.0
                            else:
                                distance = float(distance_val) if distance_val is not None else 1.0
                            similarity = 1.0 - distance  # Для косинусного расстояния
                        except (ValueError, TypeError) as e:
                            log(f"⚠️ Cannot convert distance {obj.metadata.distance} to float: {e}")
                            similarity = 0.0

                results.append((paragraph, float(similarity)))

            return results
        except Exception as e:
            log(f"❌ Ошибка поиска в Weaviate: {e}")
            return []

    def search_with_reranking(
        self, query: str, document_id: str, top_k: int = 10, rerank_limit: Optional[int] = None, **filters
    ) -> List[Tuple[Paragraph, float]]:
        """
        Поиск с переранжированием через Cross-Encoder для улучшения точности.

        Двухэтапный процесс:
        1. Быстрый первичный поиск (получаем больше кандидатов)
        2. Переранжирование через Cross-Encoder (точная оценка релевантности)

        Args:
            query: Поисковый запрос
            document_id: ID документа для поиска
            top_k: Финальное количество результатов
            rerank_limit: Количество кандидатов для reranking (по умолчанию из WEAVIATE_RERANK_LIMIT)
            **filters: Дополнительные фильтры для поиска

        Returns:
            Список кортежей (параграф, оценка схожести) отсортированных по релевантности
        """
        rerank_limit = rerank_limit or WEAVIATE_RERANK_LIMIT

        # 1. Первичный поиск (быстрый, много кандидатов)
        candidates = self.search_similar(query=query, document_id=document_id, top_k=rerank_limit, **filters)

        if not candidates or len(candidates) <= top_k:
            # Если кандидатов мало, возвращаем как есть
            return candidates[:top_k]

        # 2. Переранжирование через Cross-Encoder
        try:
            from sentence_transformers import CrossEncoder

            # Используем легковесную модель для reranking
            # Можно заменить на более мощную модель для лучшей точности
            cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

            # Подготовка пар (запрос, документ)
            pairs = [(query, para.content) for para, _ in candidates]

            # Получаем новые скоры через Cross-Encoder
            rerank_scores = cross_encoder.predict(pairs)

            # Сортируем по новым скорам
            reranked = sorted(zip(candidates, rerank_scores), key=lambda x: x[1], reverse=True)

            # Возвращаем топ-k результатов
            results = [(para, float(score)) for (para, _), score in reranked[:top_k]]
            log(f"🎯 Reranking: {len(candidates)} кандидатов → {len(results)} результатов")
            return results

        except ImportError:
            log("⚠️ Cross-Encoder не установлен, пропускаем reranking. Установите: pip install sentence-transformers")
            return candidates[:top_k]
        except Exception as e:
            log(f"⚠️ Ошибка при reranking: {e}, возвращаем результаты без reranking")
            return candidates[:top_k]

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
        use_reranking: Optional[bool] = None,
    ) -> List[Paragraph]:
        """
        Ищет наиболее похожие параграфы, возвращая только параграфы без оценок.
        Если прямых совпадений мало или нет, использует LLM для перефразирования.
        Поддерживает Cross-Encoder Reranking для улучшения точности.

        Args:
            query: Поисковый запрос
            document_id: ID документа для поиска
            top_k: Количество результатов
            classification_filter: Фильтр по типу классификации
            fact_check_filter: Фильтр по результату проверки достоверности
            location_filter: Фильтр по локации
            ecosystem_id_filter: Фильтр по ID экосистемы
            organism_ids_filter: Фильтр по списку ID организмов
            use_reranking: Использовать Cross-Encoder Reranking (по умолчанию из WEAVIATE_USE_RERANKING)

        Returns:
            Список параграфов отсортированных по релевантности
        """
        use_rerank = use_reranking if use_reranking is not None else WEAVIATE_USE_RERANKING

        # Используем reranking если включено
        if use_rerank:
            similar_pairs = self.search_with_reranking(
                query=query,
                document_id=document_id,
                top_k=top_k,
                classification_filter=classification_filter,
                fact_check_filter=fact_check_filter,
                location_filter=location_filter,
                ecosystem_id_filter=ecosystem_id_filter,
                organism_ids_filter=organism_ids_filter,
            )
        else:
            # Обычный поиск
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
