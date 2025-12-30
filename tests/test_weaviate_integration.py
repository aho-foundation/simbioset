"""
Интеграционные тесты для WeaviateStorage.

Требования:
- Weaviate должен быть запущен локально (http://localhost:8080)
- Или установлена переменная окружения WEAVIATE_URL
- Для локального запуска без Docker: используйте pytest --weaviate-local
"""

import pytest
import os
import subprocess
import time
import requests
import shutil
from typing import Optional
from datetime import datetime

from api.storage.weaviate_storage import WeaviateStorage
from api.storage.faiss import Paragraph, DocumentType, ClassificationType, FactCheckResult


# Глобальная переменная для хранения процесса Weaviate
_weaviate_process: Optional[subprocess.Popen] = None


def check_weaviate_available(url: str = "http://localhost:8080") -> bool:
    """Проверяет доступность Weaviate"""
    try:
        response = requests.get(f"{url}/v1/meta", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def check_disk_space(min_free_percent: int = 15) -> bool:
    """Проверяет, достаточно ли места на диске"""
    try:
        stat = shutil.disk_usage("/")
        free_percent = (stat.free / stat.total) * 100
        return free_percent >= min_free_percent
    except Exception:
        return False


def start_local_weaviate() -> Optional[subprocess.Popen]:
    """Запускает локальный Weaviate без Docker (требует установленный бинарник)"""
    # Проверяем, есть ли бинарник Weaviate
    weaviate_binary = os.getenv("WEAVIATE_BINARY", "weaviate")

    try:
        # Проверяем, доступен ли бинарник
        result = subprocess.run([weaviate_binary, "--version"], capture_output=True, timeout=5)
        if result.returncode != 0:
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    # Запускаем Weaviate в фоне
    process = subprocess.Popen(
        [
            weaviate_binary,
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--scheme",
            "http",
            "--persistence-data-path",
            "/tmp/weaviate-test-data",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Ждем запуска
    for _ in range(30):  # Максимум 30 секунд
        if check_weaviate_available():
            return process
        time.sleep(1)

    # Если не запустился, убиваем процесс
    process.terminate()
    return None


def stop_local_weaviate(process: subprocess.Popen):
    """Останавливает локальный Weaviate"""
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture(scope="session")
def weaviate_server(request):
    """Фикстура для запуска Weaviate сервера"""
    global _weaviate_process

    # Проверяем место на диске
    if not check_disk_space():
        pytest.skip("Недостаточно места на диске для запуска Weaviate (требуется минимум 15% свободного места)")

    # Проверяем, нужно ли запускать локально
    use_local = request.config.getoption("--weaviate-local", default=False)
    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")

    # Проверяем доступность существующего Weaviate
    if check_weaviate_available(weaviate_url):
        yield weaviate_url
        return

    # Если нужно запустить локально
    if use_local:
        _weaviate_process = start_local_weaviate()
        if _weaviate_process:
            yield "http://localhost:8080"
            stop_local_weaviate(_weaviate_process)
            _weaviate_process = None
            return

    # Если Weaviate недоступен, пропускаем тесты
    pytest.skip("Weaviate не доступен. Установите WEAVIATE_URL или используйте --weaviate-local")


@pytest.fixture
def weaviate_storage(weaviate_server, monkeypatch):
    """Фикстура для создания WeaviateStorage с тестовым классом"""
    # Используем тестовый класс для изоляции
    test_class_name = "ParagraphTest"

    # Переопределяем настройки через monkeypatch
    from api import settings

    original_class_name = settings.WEAVIATE_CLASS_NAME
    original_url = settings.WEAVIATE_URL

    monkeypatch.setattr(settings, "WEAVIATE_CLASS_NAME", test_class_name)
    monkeypatch.setattr(settings, "WEAVIATE_URL", weaviate_server)
    monkeypatch.setenv("WEAVIATE_URL", weaviate_server)
    monkeypatch.setenv("WEAVIATE_CLASS_NAME", test_class_name)

    try:
        storage = WeaviateStorage()
        yield storage
    finally:
        # Очищаем тестовые данные
        try:
            # Удаляем тестовый класс (v4 API)
            if storage.client.collections.exists(test_class_name):
                storage.client.collections.delete(test_class_name)
        except Exception:
            pass

        # Восстанавливаем оригинальные настройки
        monkeypatch.setattr(settings, "WEAVIATE_CLASS_NAME", original_class_name)
        monkeypatch.setattr(settings, "WEAVIATE_URL", original_url)


class TestWeaviateStorageIntegration:
    """Интеграционные тесты для WeaviateStorage"""

    def test_add_documents(self, weaviate_storage):
        """Тест добавления документов в Weaviate"""
        import uuid

        # Используем уникальный document_id для каждого теста
        test_doc_id = f"test_doc_{uuid.uuid4().hex[:8]}"

        documents = [
            {"text": "Машинное обучение используется для анализа данных"},
            {"text": "Искусственный интеллект помогает в разработке программ"},
        ]

        count = weaviate_storage.add_documents(documents, document_id=test_doc_id, document_type=DocumentType.KNOWLEDGE)

        assert count == 2

        # Проверяем, что параграфы добавлены
        paragraphs = weaviate_storage.get_document_paragraphs(test_doc_id)
        assert len(paragraphs) == 2, f"Expected 2 paragraphs, got {len(paragraphs)}"
        assert all(isinstance(p, Paragraph) for p in paragraphs)

    def test_add_chat_messages(self, weaviate_storage):
        """Тест добавления чат-сообщений в Weaviate"""
        import uuid

        test_chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"

        messages = [
            {"text": "Привет", "from": {"username": "user1"}},
            {"text": "Как дела?", "from": {"username": "user2"}},
        ]

        count = weaviate_storage.add_chat_messages(messages, chat_id=test_chat_id, group_consecutive=False)

        assert count == 2

        paragraphs = weaviate_storage.get_document_paragraphs(test_chat_id)
        assert len(paragraphs) == 2

    def test_search_similar(self, weaviate_storage):
        """Тест поиска похожих параграфов"""
        import uuid

        test_doc_id = f"search_test_{uuid.uuid4().hex[:8]}"

        # Добавляем тестовые данные
        documents = [
            {"text": "Машинное обучение используется для анализа данных"},
            {"text": "Искусственный интеллект помогает в разработке программ"},
            {"text": "Блокчейн технологии обеспечивают безопасность транзакций"},
        ]

        weaviate_storage.add_documents(documents, document_id=test_doc_id, document_type=DocumentType.KNOWLEDGE)

        # Ищем похожие параграфы
        results = weaviate_storage.search_similar(query="искусственный интеллект", document_id=test_doc_id, top_k=2)

        assert len(results) <= 2
        assert all(isinstance(item, tuple) and len(item) == 2 for item in results)
        assert all(isinstance(paragraph, Paragraph) and isinstance(score, float) for paragraph, score in results)

        # Проверяем, что результаты релевантны
        if results:
            assert "интеллект" in results[0][0].content.lower() or "машинное" in results[0][0].content.lower()

    @pytest.mark.asyncio
    async def test_search_similar_paragraphs(self, weaviate_storage):
        """Тест асинхронного поиска параграфов"""
        import uuid

        test_doc_id = f"async_search_test_{uuid.uuid4().hex[:8]}"

        # Добавляем тестовые данные
        documents = [
            {"text": "Машинное обучение используется для анализа данных"},
            {"text": "Искусственный интеллект помогает в разработке программ"},
        ]

        weaviate_storage.add_documents(documents, document_id=test_doc_id, document_type=DocumentType.KNOWLEDGE)

        # Ищем похожие параграфы
        results = await weaviate_storage.search_similar_paragraphs(
            query="машинное обучение", document_id=test_doc_id, top_k=2
        )

        assert isinstance(results, list)
        assert all(isinstance(p, Paragraph) for p in results)
        assert len(results) <= 2

    def test_search_with_filters(self, weaviate_storage):
        """Тест поиска с фильтрацией по метаданным"""
        import uuid

        test_doc_id = f"filter_test_{uuid.uuid4().hex[:8]}"

        # Создаем параграфы напрямую с нужными свойствами
        para1 = Paragraph(
            id=weaviate_storage._create_paragraph_id("Риск безопасности в системе"),
            content="Риск безопасности в системе",
            document_id=test_doc_id,
            document_type=DocumentType.KNOWLEDGE,
            tags=["ecosystem_risk"],
            ecosystem_id="eco_1",
        )
        para1.embedding = weaviate_storage._create_embedding(para1.content)

        para2 = Paragraph(
            id=weaviate_storage._create_paragraph_id("Решение для улучшения безопасности"),
            content="Решение для улучшения безопасности",
            document_id=test_doc_id,
            document_type=DocumentType.KNOWLEDGE,
            tags=["suggested_ecosystem_solution"],
            ecosystem_id="eco_1",
        )
        para2.embedding = weaviate_storage._create_embedding(para2.content)

        # Добавляем параграфы через v4 API
        from weaviate.classes.data import DataObject
        from api.settings import WEAVIATE_CLASS_NAME
        import uuid as uuid_lib

        collection = weaviate_storage.client.collections.get(WEAVIATE_CLASS_NAME)

        # Преобразуем ID в UUID
        para1_uuid = uuid_lib.UUID(para1.id.replace("para_", "") if para1.id.startswith("para_") else para1.id)
        para2_uuid = uuid_lib.UUID(para2.id.replace("para_", "") if para2.id.startswith("para_") else para2.id)

        objects_to_insert = [
            DataObject(
                uuid=para1_uuid,
                properties=weaviate_storage._paragraph_to_weaviate_object(para1),
                vector=para1.embedding.tolist(),
            ),
            DataObject(
                uuid=para2_uuid,
                properties=weaviate_storage._paragraph_to_weaviate_object(para2),
                vector=para2.embedding.tolist(),
            ),
        ]

        collection.data.insert_many(objects_to_insert)

        # Ищем с фильтром по классификации
        results = weaviate_storage.search_similar(
            query="безопасность",
            document_id=test_doc_id,
            top_k=10,
            classification_filter=ClassificationType.ECOSYSTEM_RISK,
        )

        # Проверяем, что результаты отфильтрованы
        assert isinstance(results, list)
        # Все результаты должны иметь нужный тег
        for para, score in results:
            assert "ecosystem_risk" in para.tags

    def test_get_paragraph_by_id(self, weaviate_storage):
        """Тест получения параграфа по ID"""
        import uuid

        test_doc_id = f"get_test_{uuid.uuid4().hex[:8]}"

        documents = [{"text": "Тестовый параграф для получения по ID"}]

        weaviate_storage.add_documents(documents, document_id=test_doc_id, document_type=DocumentType.KNOWLEDGE)

        paragraphs = weaviate_storage.get_document_paragraphs(test_doc_id)
        assert len(paragraphs) == 1

        paragraph_id = paragraphs[0].id
        retrieved = weaviate_storage.get_paragraph_by_id(test_doc_id, paragraph_id)

        assert retrieved is not None
        assert retrieved.id == paragraph_id
        assert retrieved.content == "Тестовый параграф для получения по ID"

    def test_update_paragraph(self, weaviate_storage):
        """Тест обновления параграфа"""
        import uuid

        test_doc_id = f"update_test_{uuid.uuid4().hex[:8]}"

        documents = [{"text": "Оригинальный текст"}]

        weaviate_storage.add_documents(documents, document_id=test_doc_id, document_type=DocumentType.KNOWLEDGE)

        paragraphs = weaviate_storage.get_document_paragraphs(test_doc_id)
        assert len(paragraphs) == 1

        original_para = paragraphs[0]
        original_para.content = "Обновленный текст"
        original_para.embedding = weaviate_storage._create_embedding(original_para.content)

        success = weaviate_storage.update_paragraph(test_doc_id, original_para)
        assert success is True

        updated = weaviate_storage.get_paragraph_by_id(test_doc_id, original_para.id)
        assert updated is not None
        assert updated.content == "Обновленный текст"

    def test_delete_paragraph(self, weaviate_storage):
        """Тест удаления параграфа"""
        import uuid

        test_doc_id = f"delete_test_{uuid.uuid4().hex[:8]}"

        documents = [
            {"text": "Первый параграф"},
            {"text": "Второй параграф"},
            {"text": "Третий параграф"},
        ]

        weaviate_storage.add_documents(documents, document_id=test_doc_id, document_type=DocumentType.KNOWLEDGE)

        paragraphs = weaviate_storage.get_document_paragraphs(test_doc_id)
        assert len(paragraphs) == 3

        paragraph_id_to_delete = paragraphs[0].id
        success = weaviate_storage.delete_paragraph(test_doc_id, paragraph_id_to_delete)
        assert success is True

        # Проверяем, что параграф удален
        remaining = weaviate_storage.get_document_paragraphs(test_doc_id)
        assert len(remaining) == 2

        deleted = weaviate_storage.get_paragraph_by_id(test_doc_id, paragraph_id_to_delete)
        assert deleted is None

    def test_get_all_documents(self, weaviate_storage):
        """Тест получения списка всех документов"""
        import uuid

        # Используем уникальные ID для изоляции теста
        doc1_id = f"doc1_{uuid.uuid4().hex[:8]}"
        doc2_id = f"doc2_{uuid.uuid4().hex[:8]}"
        doc3_id = f"doc3_{uuid.uuid4().hex[:8]}"

        # Добавляем несколько документов
        weaviate_storage.add_documents(
            [{"text": "Документ 1"}], document_id=doc1_id, document_type=DocumentType.KNOWLEDGE
        )
        weaviate_storage.add_documents(
            [{"text": "Документ 2"}], document_id=doc2_id, document_type=DocumentType.KNOWLEDGE
        )
        weaviate_storage.add_documents(
            [{"text": "Документ 3"}], document_id=doc3_id, document_type=DocumentType.KNOWLEDGE
        )

        documents = weaviate_storage.get_all_documents()

        assert isinstance(documents, list)
        assert doc1_id in documents
        assert doc2_id in documents
        assert doc3_id in documents

    def test_search_with_ecosystem_filter(self, weaviate_storage):
        """Тест поиска с фильтром по экосистеме"""
        import uuid
        import uuid as uuid_lib

        test_doc_id = f"eco_test_{uuid.uuid4().hex[:8]}"

        para1 = Paragraph(
            id=weaviate_storage._create_paragraph_id("Параграф про экосистему 1"),
            content="Параграф про экосистему 1",
            document_id=test_doc_id,
            document_type=DocumentType.KNOWLEDGE,
            ecosystem_id="eco_1",
        )
        para1.embedding = weaviate_storage._create_embedding(para1.content)

        para2 = Paragraph(
            id=weaviate_storage._create_paragraph_id("Параграф про экосистему 2"),
            content="Параграф про экосистему 2",
            document_id=test_doc_id,
            document_type=DocumentType.KNOWLEDGE,
            ecosystem_id="eco_2",
        )
        para2.embedding = weaviate_storage._create_embedding(para2.content)

        # Добавляем параграфы через v4 API
        from weaviate.classes.data import DataObject
        from api.settings import WEAVIATE_CLASS_NAME

        collection = weaviate_storage.client.collections.get(WEAVIATE_CLASS_NAME)

        para1_uuid = uuid_lib.UUID(para1.id.replace("para_", "") if para1.id.startswith("para_") else para1.id)
        para2_uuid = uuid_lib.UUID(para2.id.replace("para_", "") if para2.id.startswith("para_") else para2.id)

        objects_to_insert = [
            DataObject(
                uuid=para1_uuid,
                properties=weaviate_storage._paragraph_to_weaviate_object(para1),
                vector=para1.embedding.tolist(),
            ),
            DataObject(
                uuid=para2_uuid,
                properties=weaviate_storage._paragraph_to_weaviate_object(para2),
                vector=para2.embedding.tolist(),
            ),
        ]

        collection.data.insert_many(objects_to_insert)

        # Ищем с фильтром по экосистеме
        results = weaviate_storage.search_similar(
            query="экосистема",
            document_id=test_doc_id,
            top_k=10,
            ecosystem_id_filter="eco_1",
        )

        # Все результаты должны относиться к eco_1
        for para, score in results:
            assert para.ecosystem_id == "eco_1"

    def test_search_with_organism_ids_filter(self, weaviate_storage):
        """Тест поиска с фильтром по organism_ids"""
        import uuid
        import uuid as uuid_lib

        test_doc_id = f"org_test_{uuid.uuid4().hex[:8]}"

        para1 = Paragraph(
            id=weaviate_storage._create_paragraph_id("Параграф про организм 1"),
            content="Параграф про организм 1",
            document_id=test_doc_id,
            document_type=DocumentType.KNOWLEDGE,
            metadata={"organism_ids": ["org_1", "org_2"]},
        )
        para1.embedding = weaviate_storage._create_embedding(para1.content)

        para2 = Paragraph(
            id=weaviate_storage._create_paragraph_id("Параграф про организм 3"),
            content="Параграф про организм 3",
            document_id=test_doc_id,
            document_type=DocumentType.KNOWLEDGE,
            metadata={"organism_ids": ["org_3"]},
        )
        para2.embedding = weaviate_storage._create_embedding(para2.content)

        # Добавляем параграфы через v4 API
        from weaviate.classes.data import DataObject
        from api.settings import WEAVIATE_CLASS_NAME

        collection = weaviate_storage.client.collections.get(WEAVIATE_CLASS_NAME)

        para1_uuid = uuid_lib.UUID(para1.id.replace("para_", "") if para1.id.startswith("para_") else para1.id)
        para2_uuid = uuid_lib.UUID(para2.id.replace("para_", "") if para2.id.startswith("para_") else para2.id)

        objects_to_insert = [
            DataObject(
                uuid=para1_uuid,
                properties=weaviate_storage._paragraph_to_weaviate_object(para1),
                vector=para1.embedding.tolist(),
            ),
            DataObject(
                uuid=para2_uuid,
                properties=weaviate_storage._paragraph_to_weaviate_object(para2),
                vector=para2.embedding.tolist(),
            ),
        ]

        collection.data.insert_many(objects_to_insert)

        # Ищем с фильтром по organism_ids
        results = weaviate_storage.search_similar(
            query="организм",
            document_id=test_doc_id,
            top_k=10,
            organism_ids_filter=["org_1"],
        )

        # Все результаты должны содержать org_1 в organism_ids
        for para, score in results:
            organism_ids = para.metadata.get("organism_ids", []) if para.metadata else []
            assert "org_1" in organism_ids
