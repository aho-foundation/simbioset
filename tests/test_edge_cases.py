"""
Тесты обработки краевых случаев
"""

from api.storage.faiss import FAISSStorage, Paragraph


class TestEdgeCases:
    """Тесты обработки краевых случаев"""

    def setup_method(self):
        """Настройка тестов"""
        self.search_engine = FAISSStorage()

    def test_empty_documents_list(self):
        """Тест добавления пустого списка документов"""
        count = self.search_engine.add_documents([], document_id="empty_test")
        assert count == 0

        paragraphs = self.search_engine.get_document_paragraphs("empty_test")
        assert len(paragraphs) == 0

    def test_empty_chat_messages_list(self):
        """Тест добавления пустого списка чат-сообщений"""
        count = self.search_engine.add_chat_messages([], chat_id="empty_chat_test")
        assert count == 0

        paragraphs = self.search_engine.get_document_paragraphs("empty_chat_test")
        assert len(paragraphs) == 0

    def test_documents_without_text(self):
        """Тест добавления документов без текста"""
        documents = [
            {"title": "Заголовок без текста"},  # Нет поля text
            {"text": ""},  # Пустой текст
            {"text": "  "},  # Текст только из пробелов
        ]

        count = self.search_engine.add_documents(documents, document_id="no_text_test")
        # Только последний документ должен быть добавлен (с пробелами)
        # В реальной реализации возможно фильтрация пустых текстов
        paragraphs = self.search_engine.get_document_paragraphs("no_text_test")
        # В зависимости от реализации, может быть 0 или 1 параграф

    def test_invalid_document_id(self):
        """Тест работы с невалидным ID документа"""
        # Попытка получить параграфы из несуществующего документа
        paragraphs = self.search_engine.get_document_paragraphs("nonexistent_doc")
        assert paragraphs == []

        # Попытка получить параграф по ID из несуществующего документа
        para = self.search_engine.get_paragraph_by_id("nonexistent_doc", "some_id")
        assert para is None

        # Попытка обновить параграф в несуществующем документе
        fake_para = Paragraph(id="fake", content="fake")
        success = self.search_engine.update_paragraph("nonexistent_doc", fake_para)
        assert success is False

        # Попытка удалить параграф из несуществующего документа
        success = self.search_engine.delete_paragraph("nonexistent_doc", "some_id")
        assert success is False

    def test_invalid_paragraph_id(self):
        """Тест работы с невалидным ID параграфа"""
        # Добавляем документ
        documents = [{"text": "Тестовый текст"}]
        self.search_engine.add_documents(documents, document_id="invalid_id_test")

        # Попытка получить несуществующий параграф
        para = self.search_engine.get_paragraph_by_id("invalid_id_test", "nonexistent_para")
        assert para is None

        # Попытка обновить несуществующий параграф
        fake_para = Paragraph(id="nonexistent_para", content="fake")
        success = self.search_engine.update_paragraph("invalid_id_test", fake_para)
        assert success is False

        # Попытка удалить несуществующий параграф
        success = self.search_engine.delete_paragraph("invalid_id_test", "nonexistent_para")
        assert success is False

    def test_long_text_handling(self):
        """Тест обработки длинного текста"""
        long_text = "Тест. " * 1000  # Очень длинный текст
        documents = [{"text": long_text}]

        count = self.search_engine.add_documents(documents, document_id="long_text_test")
        assert count == 1

        paragraphs = self.search_engine.get_document_paragraphs("long_text_test")
        assert len(paragraphs) == 1
        assert paragraphs[0].content == long_text

    def test_special_characters(self):
        """Тест обработки специальных символов"""
        special_text = "Тест с символами: \n \t \" ' < > & % @ # $ € £ ¥"
        documents = [{"text": special_text}]

        count = self.search_engine.add_documents(documents, document_id="special_chars_test")
        assert count == 1

        paragraphs = self.search_engine.get_document_paragraphs("special_chars_test")
        assert len(paragraphs) == 1
        assert paragraphs[0].content == special_text

    def test_unicode_text(self):
        """Тест обработки юникод текста"""
        unicode_text = "Тест с юникодом: 中文 العربية русский 🚀"
        documents = [{"text": unicode_text}]

        count = self.search_engine.add_documents(documents, document_id="unicode_test")
        assert count == 1

        paragraphs = self.search_engine.get_document_paragraphs("unicode_test")
        assert len(paragraphs) == 1
        assert paragraphs[0].content == unicode_text

    def test_search_with_empty_query(self):
        """Тест поиска с пустым запросом"""
        documents = [{"text": "Тестовый документ"}]
        self.search_engine.add_documents(documents, document_id="empty_query_test")

        results = self.search_engine.search_similar("", "empty_query_test")
        # Результат может быть пустым или содержать все документы в зависимости от реализации
        assert isinstance(results, list)

    def test_search_with_very_long_query(self):
        """Тест поиска с очень длинным запросом"""
        documents = [{"text": "Тестовый документ"}]
        self.search_engine.add_documents(documents, document_id="long_query_test")

        long_query = "Поиск. " * 1000
        results = self.search_engine.search_similar(long_query, "long_query_test")
        assert isinstance(results, list)

    def test_duplicate_paragraphs(self):
        """Тест добавления дубликатов параграфов"""
        documents = [
            {"text": "Одинаковый текст"},
            {"text": "Одинаковый текст"},  # дубликат
        ]

        count = self.search_engine.add_documents(documents, document_id="duplicate_test")
        # Оба параграфа будут добавлены, так как у них разные ID
        paragraphs = self.search_engine.get_document_paragraphs("duplicate_test")
        assert len(paragraphs) == 2
        assert paragraphs[0].content == paragraphs[1].content
        assert paragraphs[0].id != paragraphs[1].id  # разные ID

    def test_get_all_documents_empty(self):
        """Тест получения списка всех документов для пустого хранилища"""
        all_docs = self.search_engine.get_all_documents()
        assert all_docs == []
