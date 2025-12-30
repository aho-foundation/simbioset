"""
Расширенная система векторного поиска на основе FAISS для работы с документами и чатами.
Включает функции классификации, fact-checking и локализации сообщений.
"""

from typing import Dict, List, Tuple, Optional, Any, cast
import json
import faiss  # type: ignore
import numpy as np
from sentence_transformers import SentenceTransformer  # type: ignore
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from datetime import datetime

from api.settings import EMBEDDING_MODEL_NAME, MODELS_CACHE_DIR, ENABLE_AUTOMATIC_DETECTORS
from api.logger import root_logger

log = root_logger.debug


class DocumentType(Enum):
    """Тип документа - чат, знание или документ"""

    CHAT = "chat"
    KNOWLEDGE = "knowledge"
    DOCUMENT = "document"


class ClassificationType(Enum):
    """Тип классификации для экосистемных сообщений"""

    ECOSYSTEM_VULNERABILITY = "ecosystem_vulnerability"  # возможные риски
    ECOSYSTEM_RISK = "ecosystem_risk"  # найденные проблемы
    ECOSYSTEM_SOLUTION = "suggested_ecosystem_solution"  # предлагаемые решения
    NEUTRAL = "neutral"


class FactCheckResult(Enum):
    """Результат проверки достоверности"""

    TRUE = "true"  # утверждение верно
    FALSE = "false"  # утверждение ложно
    PARTIAL = "partial"  # частично верно
    UNVERIFIABLE = "unverifiable"  # невозможно проверить
    UNKNOWN = "unknown"  # неизвестно


@dataclass
class Paragraph:
    """Параграф документа - может быть объединенным чат-сообщением или фрагментом документа.

    Параграф может быть связан с узлом знания (node_id) или документом (document_id).
    В базе знаний параграфы связаны с узлами через node_id для векторного поиска.
    """

    id: str
    content: str
    author: Optional[str] = None
    author_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    document_id: Optional[str] = None
    node_id: Optional[str] = None  # Ссылка на узел знания (для базы знаний)
    document_type: DocumentType = DocumentType.CHAT
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None

    # Поля для классификации и проверки достоверности
    tags: List[str] = field(default_factory=list)  # Множественные теги классификации
    # Типовая классификация параграфа (используется в детекторах и фильтрах поиска)
    classification: Optional[ClassificationType] = None
    fact_check_result: Optional[FactCheckResult] = None
    fact_check_details: Optional[Dict[str, Any]] = None
    location: Optional[str] = None
    time_reference: Optional[str] = None
    ecosystem_id: Optional[str] = None  # Ссылка на основную экосистему параграфа (если относится)
    # Порядковый номер параграфа внутри документа (для сохранения стабильного порядка)
    paragraph_index: Optional[int] = None


class ParagraphVectorSearch:
    """Класс для векторного поиска параграфов с использованием FAISS"""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, cache_folder: Optional[str] = None):
        """
        Инициализация векторного поиска

        Args:
            model_name: Название модели для создания эмбеддингов
                       (по умолчанию многоязычная модель, поддерживающая русский)
            cache_folder: Директория для кэширования моделей
        """
        log(f"🔄 Загрузка модели {model_name}...")

        # Если cache_folder не указан, используем глобальную настройку
        if cache_folder is None:
            cache_folder = MODELS_CACHE_DIR

        # Указываем директорию для кэширования моделей
        self.model = SentenceTransformer(model_name, cache_folder=cache_folder)
        self.dimension = self.model.get_sentence_embedding_dimension()

        # Храним индексы для каждого документа
        self.document_indexes: Dict[str, faiss.Index] = {}  # type: ignore
        self.document_paragraph_ids: Dict[str, List[str]] = {}
        self.document_paragraphs: Dict[str, List[Paragraph]] = {}
        self.document_embeddings_cache: Dict[str, Optional[np.ndarray]] = {}

        log(f"✅ Модель загружена, размерность эмбеддингов: {self.dimension}")


class FAISSStorage:
    """Обертка для ParagraphVectorSearch, чтобы соответствовать ожидаемому интерфейсу"""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, cache_folder: Optional[str] = None):
        self._search_engine = ParagraphVectorSearch(model_name, cache_folder)
        # Связанный сервис тегов задается снаружи (см. api.main.init_app),
        # объявляем его явно для mypy, чтобы избежать attr-defined.
        self._tag_service: Optional[Any] = None

    def __getattr__(self, name):
        # Делегируем все атрибуты внутреннему search engine
        return getattr(self._search_engine, name)

    def _create_paragraph_id(
        self,
        content: str,
        author: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        index: Optional[int] = None,
    ) -> str:
        """Создает уникальный ID для параграфа"""
        import uuid

        # Используем UUID для гарантии уникальности, даже для одинакового контента
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

            timestamp = message.get("date")
            if timestamp:
                timestamp = datetime.fromtimestamp(timestamp)
        else:
            text = self._extract_text(message)
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
        current_content: List[str] = []
        current_metadata: Dict[str, Any] = {}

        for msg in messages:
            # Определяем автора сообщения
            if isinstance(msg, dict):
                from_user = msg.get("from", msg.get("from_user", {}))
                if isinstance(from_user, dict):
                    author_id = from_user.get("id")
                    author_name = from_user.get("username", from_user.get("first_name", ""))
                else:
                    author_id = None
                    author_name = ""
            else:
                # Для TelegramMessage объектов
                from_user = getattr(msg, "from_user", None)
                if from_user:
                    author_id = getattr(from_user, "id", None)
                    author_name = getattr(from_user, "username", "") or getattr(from_user, "first_name", "")
                else:
                    author_id = None
                    author_name = ""

            # Если это первый сообщение или автор изменился
            if current_author is None or current_author != author_id:
                # Сохраняем предыдущий параграф, если он есть
                if current_content:
                    combined_content = "\n".join(current_content)
                    paragraph = Paragraph(
                        id=self._create_paragraph_id(combined_content, current_author),
                        content=combined_content,
                        author=current_author,
                        metadata=current_metadata,
                    )
                    grouped_paragraphs.append(paragraph)

                # Начинаем новый параграф
                current_author = author_id
                current_content = [msg.get("text", "") if isinstance(msg, dict) else getattr(msg, "text", "")]
                current_metadata = msg if isinstance(msg, dict) else {}
            else:
                # Добавляем к текущему параграфу
                current_content.append(msg.get("text", "") if isinstance(msg, dict) else getattr(msg, "text", ""))

        # Добавляем последний параграф
        if current_content:
            combined_content = "\n".join(current_content)
            paragraph = Paragraph(
                id=self._create_paragraph_id(combined_content, current_author),
                content=combined_content,
                author=current_author,
                metadata=current_metadata,
            )
            grouped_paragraphs.append(paragraph)

        # Создаем эмбеддинги для параграфов
        for paragraph in grouped_paragraphs:
            paragraph.embedding = self._create_embedding(paragraph.content)

        return grouped_paragraphs

    def _classify_paragraph(self, paragraph: Paragraph, tag_service=None) -> Paragraph:
        """Классифицирует параграф с использованием модулей классификации.

        Определяет множественные теги для параграфа, так как он может одновременно
        описывать уязвимости, риски и решения.

        Args:
            paragraph: Параграф для классификации
            tag_service: Опциональный сервис для управления тегами
        """
        try:
            # Импортируем классификаторы опционально
            try:
                from api.detect.rolestate import classify_message_type
                from api.detect.factcheck import check_factuality
                from api.detect.localize import extract_location_and_time
            except ImportError:
                log("⚠️ Модули классификации недоступны, пропускаем классификацию")
                return paragraph

            # Используем LLM для тегов только если явно включены автоматические детекторы.
            # В обычном UX чата достаточно лёгкой классификации через classify_message_type.
            if tag_service and ENABLE_AUTOMATIC_DETECTORS:
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
                                    "neutral": ClassificationType.NEUTRAL,
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
            else:
                # Fallback на старый классификатор без LLM
                classification_result = classify_message_type(paragraph.content)
                if classification_result:
                    if isinstance(classification_result, str):
                        paragraph.tags = [classification_result]
                        # Устанавливаем classification enum на основе строки
                        try:
                            # Маппинг строковых значений на ClassificationType
                            classification_map = {
                                "ecosystem_risk": ClassificationType.ECOSYSTEM_RISK,
                                "ecosystem_vulnerability": ClassificationType.ECOSYSTEM_VULNERABILITY,
                                "suggested_ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,
                                "ecosystem_solution": ClassificationType.ECOSYSTEM_SOLUTION,  # Альтернативное название
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
                    from api.detect.ecosystem_scaler import detect_ecosystems
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
                    from api.detect.organism_detector import detect_organisms
                    from api.classify.organism_classifier import classify_organisms_batch
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    organisms = loop.run_until_complete(detect_organisms(paragraph.content))

                    if organisms:
                        classified_organisms = loop.run_until_complete(classify_organisms_batch(organisms))

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

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        document_id: str,
        document_type: DocumentType = DocumentType.KNOWLEDGE,
        classify: bool = True,
    ) -> int:
        """
        Добавляет документы в индекс

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
                # Это сообщение чата, создаем параграф
                paragraph = self._create_paragraph_from_message(doc, document_id, document_type, index=i)
                paragraphs.append(paragraph)
            elif isinstance(doc, str):
                # Это текст документа, создаем параграф
                paragraph = Paragraph(
                    id=self._create_paragraph_id(doc, index=i),
                    content=doc,
                    document_id=document_id,
                    document_type=document_type,
                )
                paragraph.embedding = self._create_embedding(doc)
                paragraphs.append(paragraph)

        if not paragraphs:
            return 0

        # Классифицируем параграфы, если нужно
        if classify:
            for paragraph in paragraphs:
                paragraph = self._classify_paragraph(paragraph)

        log(f"🔄 Создание эмбеддингов для {len(paragraphs)} параграфов в документе {document_id}...")

        # Извлекаем эмбеддинги
        embeddings_list = [para.embedding for para in paragraphs if para.embedding is not None]
        if not embeddings_list:
            return 0

        embeddings = np.array(embeddings_list).astype(np.float32)

        # Инициализируем индекс для документа, если его еще нет
        if document_id not in self.document_indexes:
            self.document_indexes[document_id] = faiss.IndexFlatIP(self.dimension)
            self.document_paragraph_ids[document_id] = []
            self.document_paragraphs[document_id] = []
            self.document_embeddings_cache[document_id] = None

        # Добавляем в индекс конкретного документа
        self.document_indexes[document_id].add(embeddings)

        # Сохраняем метаданные для конкретного документа
        for paragraph in paragraphs:
            self.document_paragraph_ids[document_id].append(paragraph.id)
            self.document_paragraphs[document_id].append(paragraph)

        # КЭШИРУЕМ эмбеддинги для повторного использования для конкретного документа
        self.document_embeddings_cache[document_id] = embeddings

        log(f"✅ Добавлено {len(paragraphs)} параграфов в документ {document_id}, эмбеддинги закэшированы")
        return len(paragraphs)

    def add_chat_messages(
        self, messages: List[Dict[str, Any]], chat_id: str, group_consecutive: bool = True, classify: bool = True
    ) -> int:
        """
        Добавляет чат-сообщения в индекс

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
            for msg in valid_messages:
                paragraph = self._create_paragraph_from_message(msg, chat_id, DocumentType.CHAT)
                paragraphs.append(paragraph)

        if not paragraphs:
            return 0

        # Классифицируем параграфы, если нужно
        if classify:
            for paragraph in paragraphs:
                paragraph = self._classify_paragraph(paragraph)

        log(f"🔄 Создание эмбеддингов для {len(paragraphs)} параграфов в чате {chat_id}...")

        # Извлекаем эмбеддинги
        embeddings_list = [para.embedding for para in paragraphs if para.embedding is not None]
        if not embeddings_list:
            return 0

        embeddings = np.array(embeddings_list).astype(np.float32)

        # Инициализируем индекс для чата, если его еще нет
        if chat_id not in self.document_indexes:
            self.document_indexes[chat_id] = faiss.IndexFlatIP(self.dimension)
            self.document_paragraph_ids[chat_id] = []
            self.document_paragraphs[chat_id] = []
            self.document_embeddings_cache[chat_id] = None

        # Добавляем в индекс конкретного чата
        self.document_indexes[chat_id].add(embeddings)

        # Сохраняем метаданные для конкретного чата
        for paragraph in paragraphs:
            self.document_paragraph_ids[chat_id].append(paragraph.id)
            self.document_paragraphs[chat_id].append(paragraph)

        # КЭШИРУЕМ эмбеддинги для повторного использования для конкретного чата
        self.document_embeddings_cache[chat_id] = embeddings

        log(f"✅ Добавлено {len(paragraphs)} параграфов в чат {chat_id}, эмбеддинги закэшированы")
        return len(paragraphs)

    def update_paragraph(self, document_id: str, paragraph: Paragraph) -> bool:
        """
        Обновляет параграф в индексе

        Args:
            document_id: ID документа
            paragraph: Обновленный параграф

        Returns:
            True если успешно обновлено
        """
        if document_id not in self.document_indexes:
            return False

        paragraph_id = paragraph.id
        if not paragraph_id:
            return False

        # Ищем индекс параграфа
        try:
            if paragraph_id in self.document_paragraph_ids[document_id]:
                idx = self.document_paragraph_ids[document_id].index(paragraph_id)

                # Обновляем данные параграфа
                self.document_paragraphs[document_id][idx] = paragraph

                # Обновляем эмбеддинг
                if paragraph.embedding is not None:
                    # Обновляем кэш эмбеддингов
                    embeddings_cache = self.document_embeddings_cache[document_id]
                    if embeddings_cache is not None:
                        embeddings_cache[idx] = paragraph.embedding

                        # Перестраиваем индекс
                        # FAISS IndexFlatIP не поддерживает обновление одного вектора без IDMap
                        # Поэтому проще всего пересоздать индекс из кэша (это быстро)
                        self.document_indexes[document_id].reset()
                        self.document_indexes[document_id].add(embeddings_cache)
                        return True
        except Exception as e:
            log(f"❌ Ошибка обновления параграфа в индексе: {e}")

        return False

    def delete_paragraph(self, document_id: str, paragraph_id: str) -> bool:
        """
        Удаляет параграф из индекса

        Args:
            document_id: ID документа
            paragraph_id: ID параграфа

        Returns:
            True если успешно удалено
        """
        if document_id not in self.document_indexes:
            return False

        try:
            if paragraph_id in self.document_paragraph_ids[document_id]:
                idx = self.document_paragraph_ids[document_id].index(paragraph_id)

                # Удаляем из списков
                self.document_paragraph_ids[document_id].pop(idx)
                self.document_paragraphs[document_id].pop(idx)

                # Удаляем из кэша эмбеддингов
                embeddings_cache = self.document_embeddings_cache[document_id]
                if embeddings_cache is not None:
                    # Удаляем строку из numpy array
                    # np.delete возвращает новый массив, поэтому обновляем кэш
                    new_embeddings_cache = np.delete(embeddings_cache, idx, axis=0)
                    self.document_embeddings_cache[document_id] = new_embeddings_cache

                    # Перестраиваем индекс
                    self.document_indexes[document_id].reset()
                    if len(new_embeddings_cache) > 0:
                        self.document_indexes[document_id].add(new_embeddings_cache)

                    return True
        except Exception as e:
            log(f"❌ Ошибка удаления параграфа из индекса: {e}")

        return False

    def search_similar(
        self,
        query: str,
        document_id: str,
        top_k: int = 10,
        classification_filter: Optional[ClassificationType] = None,
        fact_check_filter: Optional[FactCheckResult] = None,
        location_filter: Optional[str] = None,
        ecosystem_id_filter: Optional[str] = None,
    ) -> List[Tuple[Paragraph, float]]:
        """
        Ищет наиболее похожие параграфы в конкретном документе

        Args:
            query: Поисковый запрос
            document_id: ID документа для поиска
            top_k: Количество результатов
            classification_filter: Фильтр по типу классификации
            fact_check_filter: Фильтр по результату проверки достоверности
            location_filter: Фильтр по локации (None = не фильтровать)
            ecosystem_id_filter: Фильтр по ID экосистемы (None = не фильтровать)

        Returns:
            Список кортежей (параграф, оценка схожести)
        """
        if document_id not in self.document_indexes or self.document_indexes[document_id].ntotal == 0:
            return []

        # Создаем эмбеддинг запроса
        query_embedding = self._create_embedding(query).reshape(1, -1)

        # Ищем похожие в индексе конкретного документа
        # Увеличиваем top_k, чтобы после фильтрации осталось достаточно результатов
        search_k = top_k * 3 if (location_filter or ecosystem_id_filter) else top_k
        search_k = min(search_k, self.document_indexes[document_id].ntotal)
        scores, indices = self.document_indexes[document_id].search(query_embedding, search_k)

        # Формируем результаты
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if int(idx) < len(self.document_paragraphs[document_id]):
                paragraph = self.document_paragraphs[document_id][int(idx)]

                # Применяем фильтры
                # Фильтр по классификации: проверяем, есть ли значение classification_filter в тегах
                if classification_filter and classification_filter.value not in paragraph.tags:
                    continue
                if fact_check_filter and paragraph.fact_check_result != fact_check_filter:
                    continue

                # Фильтр по локации: если указана локация, включаем только параграфы
                # с этой локацией или без локации (универсальные)
                if location_filter:
                    para_location = paragraph.location
                    if para_location:
                        # Проверяем, совпадает ли локация (регистронезависимо)
                        location_lower = location_filter.lower()
                        para_location_lower = para_location.lower()
                        # Включаем, если локации совпадают или параграф относится к более широкой области
                        if location_lower not in para_location_lower and para_location_lower not in location_lower:
                            continue

                # Фильтр по экосистеме: если указана экосистема, включаем только параграфы
                # с этой экосистемой или без экосистемы (универсальные)
                if ecosystem_id_filter:
                    # Проверяем прямое поле ecosystem_id
                    if paragraph.ecosystem_id:
                        if paragraph.ecosystem_id != ecosystem_id_filter:
                            continue
                    else:
                        # Проверяем metadata["ecosystems"] для обратной совместимости
                        ecosystems_in_meta = paragraph.metadata.get("ecosystems", []) if paragraph.metadata else []
                        if ecosystems_in_meta:
                            # Ищем экосистему по ID или имени
                            ecosystem_found = False
                            for eco in ecosystems_in_meta:
                                # Если экосистема в metadata - это словарь с полями, проверяем по name
                                # или создаем ID из name для сравнения
                                eco_id = eco.get("id") if isinstance(eco, dict) else None
                                eco_name = eco.get("name") if isinstance(eco, dict) else str(eco)
                                # Пока просто пропускаем параграфы с другими экосистемами
                                # TODO: улучшить логику сравнения экосистем
                                if eco_id == ecosystem_id_filter:
                                    ecosystem_found = True
                                    break
                            if not ecosystem_found:
                                continue

                results.append((paragraph, float(score)))
                # Останавливаемся, когда набрали достаточно результатов
                if len(results) >= top_k:
                    break

        return results

    async def search_similar_paragraphs(self, query: str, document_id: str, top_k: int = 10) -> List[Paragraph]:
        """
        Ищет наиболее похожие параграфы, возвращая только параграфы без оценок.
        Если прямых совпадений мало или нет, использует LLM для перефразирования.
        """
        # 1. Прямой поиск
        similar_pairs = self.search_similar(query, document_id, top_k)

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
            new_pairs = self.search_similar(new_query, document_id, top_k=3)
            for para, score in new_pairs:
                # Если параграф уже есть, оставляем с лучшим скором
                if para.id not in all_results or score > all_results[para.id][1]:
                    all_results[para.id] = (para, score)

        # Сортируем по скору
        sorted_results = sorted(all_results.values(), key=lambda x: x[1], reverse=True)

        return [para for para, score in sorted_results[:top_k]]

    def get_paragraph_by_id(self, document_id: str, paragraph_id: str) -> Optional[Paragraph]:
        """Получает параграф по ID"""
        if document_id not in self.document_paragraphs:
            return None

        for paragraph in self.document_paragraphs[document_id]:
            if paragraph.id == paragraph_id:
                return paragraph

        return None

    def get_document_paragraphs(self, document_id: str) -> List[Paragraph]:
        """Получает все параграфы документа"""
        return self.document_paragraphs.get(document_id, [])

    def get_all_documents(self) -> List[str]:
        """Получает список всех документов"""
        return list(self.document_indexes.keys())

    def get_paragraphs_by_classification(self, document_id: str, classification: ClassificationType) -> List[Paragraph]:
        """Получает параграфы по типу классификации (проверяет classification или наличие тега)"""
        if document_id not in self.document_paragraphs:
            return []

        return [
            para
            for para in self.document_paragraphs[document_id]
            if para.classification == classification or classification.value in para.tags
        ]

    def get_paragraphs_by_fact_check_result(
        self, document_id: str, fact_check_result: FactCheckResult
    ) -> List[Paragraph]:
        """Получает параграфы по результату проверки достоверности"""
        if document_id not in self.document_paragraphs:
            return []

        return [para for para in self.document_paragraphs[document_id] if para.fact_check_result == fact_check_result]

    def reclassify_paragraph(self, document_id: str, paragraph_id: str, tag_service=None) -> bool:
        """Переклассифицирует параграф"""
        paragraph = self.get_paragraph_by_id(document_id, paragraph_id)
        if not paragraph:
            return False

        # Обновляем классификацию
        tag_service = tag_service or getattr(self, "_tag_service", None)
        paragraph = self._classify_paragraph(paragraph, tag_service=tag_service)

        # Обновляем параграф в индексе
        return self.update_paragraph(document_id, paragraph)

    def reclassify_document(self, document_id: str) -> int:
        """Переклассифицирует все параграфы в документе"""
        paragraphs = self.get_document_paragraphs(document_id)
        updated_count = 0

        for paragraph in paragraphs:
            if self.reclassify_paragraph(document_id, paragraph.id):
                updated_count += 1

        return updated_count
