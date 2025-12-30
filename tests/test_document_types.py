"""
Тесты работы с разными типами документов
"""

from api.storage.faiss import FAISSStorage, DocumentType


class TestDocumentTypes:
    """Тесты работы с разными типами документов"""

    def setup_method(self):
        """Настройка тестов"""
        self.search_engine = FAISSStorage()

    def test_chat_document_type(self):
        """Тест работы с документами типа CHAT"""
        messages = [{"text": "Сообщение из чата", "from": {"username": "user"}}]

        count = self.search_engine.add_chat_messages(messages, chat_id="chat_test")
        assert count == 1

        paragraphs = self.search_engine.get_document_paragraphs("chat_test")
        assert len(paragraphs) == 1
        assert paragraphs[0].document_type == DocumentType.CHAT

    def test_knowledge_document_type(self):
        """Тест работы с документами типа KNOWLEDGE"""
        documents = [{"text": "Знание из базы знаний"}]

        count = self.search_engine.add_documents(
            documents, document_id="knowledge_test", document_type=DocumentType.KNOWLEDGE
        )
        assert count == 1

        paragraphs = self.search_engine.get_document_paragraphs("knowledge_test")
        assert len(paragraphs) == 1
        assert paragraphs[0].document_type == DocumentType.KNOWLEDGE

    def test_mixed_document_types(self):
        """Тест работы с разными типами документов в одном хранилище"""
        # Добавляем чат
        chat_messages = [{"text": "Сообщение из чата", "from": {"username": "user"}}]
        self.search_engine.add_chat_messages(chat_messages, chat_id="mixed_chat")

        # Добавляем знания
        knowledge_docs = [{"text": "Факт из базы знаний"}]
        self.search_engine.add_documents(
            knowledge_docs, document_id="mixed_knowledge", document_type=DocumentType.KNOWLEDGE
        )

        # Проверяем, что оба документа существуют
        chat_paragraphs = self.search_engine.get_document_paragraphs("mixed_chat")
        knowledge_paragraphs = self.search_engine.get_document_paragraphs("mixed_knowledge")

        assert len(chat_paragraphs) == 1
        assert len(knowledge_paragraphs) == 1
        assert chat_paragraphs[0].document_type == DocumentType.CHAT
        assert knowledge_paragraphs[0].document_type == DocumentType.KNOWLEDGE

        # Проверяем список всех документов
        all_docs = self.search_engine.get_all_documents()
        assert "mixed_chat" in all_docs
        assert "mixed_knowledge" in all_docs
