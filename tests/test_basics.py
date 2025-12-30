"""
Тесты базовых операций системы хранения параграфов
"""

import pytest
from datetime import datetime

from api.storage.faiss import FAISSStorage, Paragraph, DocumentType


class TestStorageBasics:
    """Тесты базовых операций (добавление, обновление, удаление параграфов)"""

    def setup_method(self):
        """Настройка тестов"""
        self.search_engine = FAISSStorage()

    def test_create_paragraph(self):
        """Тест создания параграфа"""
        content = "Тестовый параграф"
        paragraph = Paragraph(
            id="test_id",
            content=content,
            author="test_author",
            timestamp=datetime.now(),
            document_id="test_doc",
            document_type=DocumentType.CHAT,
        )

        assert paragraph.content == content
        assert paragraph.author == "test_author"
        assert paragraph.document_type == DocumentType.CHAT

    def test_add_documents_basic(self):
        """Тест добавления документов"""
        documents = [{"text": "Первый параграф"}, {"text": "Второй параграф"}]

        count = self.search_engine.add_documents(
            documents, document_id="test_doc", document_type=DocumentType.KNOWLEDGE
        )

        assert count == 2
        paragraphs = self.search_engine.get_document_paragraphs("test_doc")
        assert len(paragraphs) == 2

    def test_add_chat_messages_basic(self):
        """Тест добавления чат-сообщений"""
        messages = [
            {"text": "Привет", "from": {"username": "user1"}},
            {"text": "Как дела?", "from": {"username": "user2"}},
        ]

        count = self.search_engine.add_chat_messages(messages, chat_id="test_chat")

        assert count == 2
        paragraphs = self.search_engine.get_document_paragraphs("test_chat")
        assert len(paragraphs) == 2

    def test_add_chat_messages_with_grouping(self):
        """Тест добавления чат-сообщений с группировкой"""
        messages = [
            {"text": "Привет", "from": {"id": 1, "username": "user1"}},
            {"text": "Как дела?", "from": {"id": 1, "username": "user1"}},  # тот же автор
            {"text": "Отлично!", "from": {"id": 2, "username": "user2"}},  # другой автор
        ]

        count = self.search_engine.add_chat_messages(messages, chat_id="test_chat_grouped", group_consecutive=True)

        # Должно быть 2 параграфа: 1 с объединенными сообщениями user1 и 1 от user2
        assert count == 2
        paragraphs = self.search_engine.get_document_paragraphs("test_chat_grouped")
        assert len(paragraphs) == 2

    def test_update_paragraph(self):
        """Тест обновления параграфа"""
        # Добавляем документ
        documents = [{"text": "Оригинальный текст"}]
        self.search_engine.add_documents(documents, document_id="update_test")

        paragraphs = self.search_engine.get_document_paragraphs("update_test")
        assert len(paragraphs) == 1

        original_paragraph = paragraphs[0]
        original_id = original_paragraph.id

        # Создаем обновленный параграф
        updated_paragraph = Paragraph(
            id=original_id,
            content="Обновленный текст",
            author=original_paragraph.author,
            timestamp=original_paragraph.timestamp,
            document_id=original_paragraph.document_id,
            document_type=original_paragraph.document_type,
            embedding=self.search_engine._create_embedding("Обновленный текст"),
        )

        # Обновляем параграф
        success = self.search_engine.update_paragraph("update_test", updated_paragraph)
        assert success is True

        # Проверяем, что параграф обновлен
        updated_from_storage = self.search_engine.get_paragraph_by_id("update_test", original_id)
        assert updated_from_storage.content == "Обновленный текст"

    def test_delete_paragraph(self):
        """Тест удаления параграфа"""
        # Добавляем документ с несколькими параграфами
        documents = [{"text": "Первый параграф"}, {"text": "Второй параграф"}, {"text": "Третий параграф"}]
        self.search_engine.add_documents(documents, document_id="delete_test")

        paragraphs = self.search_engine.get_document_paragraphs("delete_test")
        assert len(paragraphs) == 3

        # Удаляем первый параграф
        paragraph_id_to_delete = paragraphs[0].id
        success = self.search_engine.delete_paragraph("delete_test", paragraph_id_to_delete)
        assert success is True

        # Проверяем, что параграф удален
        remaining_paragraphs = self.search_engine.get_document_paragraphs("delete_test")
        assert len(remaining_paragraphs) == 2

        # Проверяем, что удаленного параграфа больше нет
        deleted_paragraph = self.search_engine.get_paragraph_by_id("delete_test", paragraph_id_to_delete)
        assert deleted_paragraph is None

    def test_get_paragraph_by_id(self):
        """Тест получения параграфа по ID"""
        documents = [{"text": "Тестовый параграф"}]
        self.search_engine.add_documents(documents, document_id="get_test")

        paragraphs = self.search_engine.get_document_paragraphs("get_test")
        assert len(paragraphs) == 1

        original_paragraph = paragraphs[0]
        retrieved_paragraph = self.search_engine.get_paragraph_by_id("get_test", original_paragraph.id)

        assert retrieved_paragraph is not None
        assert retrieved_paragraph.id == original_paragraph.id
        assert retrieved_paragraph.content == original_paragraph.content

    def test_get_document_paragraphs(self):
        """Тест получения всех параграфов документа"""
        documents = [{"text": "Параграф 1"}, {"text": "Параграф 2"}, {"text": "Параграф 3"}]
        self.search_engine.add_documents(documents, document_id="doc_test")

        paragraphs = self.search_engine.get_document_paragraphs("doc_test")
        assert len(paragraphs) == 3
        assert all(isinstance(p, Paragraph) for p in paragraphs)
