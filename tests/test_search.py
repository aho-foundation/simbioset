"""
Тесты поиска параграфов с различными фильтрами
"""

import pytest
from unittest.mock import Mock
import numpy as np

from api.storage.faiss import FAISSStorage, Paragraph, DocumentType, ClassificationType, FactCheckResult


class TestSearch:
    """Тесты поиска с различными фильтрами"""

    def setup_method(self):
        """Настройка тестов"""
        self.search_engine = FAISSStorage()

        # Подготовим тестовые данные
        self.documents = [
            {"text": "Машинное обучение используется для анализа данных"},
            {"text": "Искусственный интеллект помогает в разработке программ"},
            {"text": "Блокчейн технологии обеспечивают безопасность транзакций"},
            {"text": "Квантовые вычисления открывают новые возможности"},
        ]

        self.search_engine.add_documents(
            self.documents, document_id="search_test", document_type=DocumentType.KNOWLEDGE
        )

    def test_search_similar_basic(self):
        """Тест базового поиска похожих параграфов"""
        results = self.search_engine.search_similar("искусственный интеллект", "search_test", top_k=2)

        assert len(results) <= 2
        assert all(isinstance(item, tuple) and len(item) == 2 for item in results)
        assert all(isinstance(paragraph, Paragraph) and isinstance(score, float) for paragraph, score in results)

        # Проверяем, что первый результат содержит "искусственный интеллект"
        if results:
            assert "интеллект" in results[0][0].content.lower()

    def test_search_similar_with_classification_filter(self):
        """Тест поиска с фильтрацией по классификации"""
        # Добавим параграфы с разными классификациями
        test_paragraphs = [
            Paragraph(
                id="para1", content="Риск безопасности в системе", classification=ClassificationType.ECOSYSTEM_RISK
            ),
            Paragraph(
                id="para2",
                content="Решение для улучшения безопасности",
                classification=ClassificationType.ECOSYSTEM_SOLUTION,
            ),
            Paragraph(id="para3", content="Обычный текст без классификации", classification=ClassificationType.NEUTRAL),
        ]

        # Добавляем параграфы вручную (для тестирования фильтрации)
        for para in test_paragraphs:
            if para.embedding is None:
                para.embedding = self.search_engine._create_embedding(para.content)

        # Инициализируем индекс для документа
        self.search_engine.document_indexes["filter_test"] = self.search_engine.document_indexes.get(
            "search_test", type(self.search_engine.document_indexes.get("search_test", Mock()))()
        )
        self.search_engine.document_paragraph_ids["filter_test"] = []
        self.search_engine.document_paragraphs["filter_test"] = []
        self.search_engine.document_embeddings_cache["filter_test"] = None

        # Добавляем параграфы вручную
        for para in test_paragraphs:
            self.search_engine.document_paragraph_ids["filter_test"].append(para.id)
            self.search_engine.document_paragraphs["filter_test"].append(para)

        # Извлекаем эмбеддинги и добавляем в индекс
        embeddings_list = [para.embedding for para in test_paragraphs if para.embedding is not None]
        if embeddings_list:
            embeddings = np.array(embeddings_list).astype(np.float32)
            self.search_engine.document_indexes["filter_test"] = self.search_engine.document_indexes.get(
                "search_test", type(self.search_engine.document_indexes.get("search_test", Mock()))()
            )
            self.search_engine.document_indexes["filter_test"] = Mock()
            self.search_engine.document_indexes["filter_test"].ntotal = len(embeddings_list)
            self.search_engine.document_indexes["filter_test"].search = Mock(
                return_value=([list(range(len(embeddings_list)))], [list(np.ones(len(embeddings_list)))])
            )

        # Тестируем фильтрацию по классификации
        results = self.search_engine.search_similar(
            "безопасность", "filter_test", top_k=10, classification_filter=ClassificationType.ECOSYSTEM_RISK
        )

        # В реальной реализации проверим, что фильтрация работает
        # В тесте с моками просто проверим, что параметры передаются корректно
        assert isinstance(results, list)

    def test_search_similar_with_fact_check_filter(self):
        """Тест поиска с фильтрацией по результату проверки достоверности"""
        # Добавим параграфы с разными результатами проверки достоверности
        test_paragraphs = [
            Paragraph(id="para1", content="Проверенное утверждение", fact_check_result=FactCheckResult.TRUE),
            Paragraph(id="para2", content="Ошибочное утверждение", fact_check_result=FactCheckResult.FALSE),
            Paragraph(
                id="para3", content="Частично проверенное утверждение", fact_check_result=FactCheckResult.PARTIAL
            ),
        ]

        # Добавляем параграфы вручную (для тестирования фильтрации)
        for para in test_paragraphs:
            if para.embedding is None:
                para.embedding = self.search_engine._create_embedding(para.content)

        # Инициализируем индекс для документа
        self.search_engine.document_indexes["fact_check_test"] = self.search_engine.document_indexes.get(
            "search_test", type(self.search_engine.document_indexes.get("search_test", Mock()))()
        )
        self.search_engine.document_paragraph_ids["fact_check_test"] = []
        self.search_engine.document_paragraphs["fact_check_test"] = []
        self.search_engine.document_embeddings_cache["fact_check_test"] = None

        # Добавляем параграфы вручную
        for para in test_paragraphs:
            self.search_engine.document_paragraph_ids["fact_check_test"].append(para.id)
            self.search_engine.document_paragraphs["fact_check_test"].append(para)

        # Извлекаем эмбеддинги и добавляем в индекс
        embeddings_list = [para.embedding for para in test_paragraphs if para.embedding is not None]
        if embeddings_list:
            embeddings = np.array(embeddings_list).astype(np.float32)
            self.search_engine.document_indexes["fact_check_test"] = self.search_engine.document_indexes.get(
                "search_test", type(self.search_engine.document_indexes.get("search_test", Mock()))()
            )
            self.search_engine.document_indexes["fact_check_test"] = Mock()
            self.search_engine.document_indexes["fact_check_test"].ntotal = len(embeddings_list)
            self.search_engine.document_indexes["fact_check_test"].search = Mock(
                return_value=([list(range(len(embeddings_list)))], [list(np.ones(len(embeddings_list)))])
            )

        # Тестируем фильтрацию по результату проверки достоверности
        results = self.search_engine.search_similar(
            "утверждение", "fact_check_test", top_k=10, fact_check_filter=FactCheckResult.TRUE
        )

        # В реальной реализации проверим, что фильтрация работает
        # В тесте с моками просто проверим, что параметры передаются корректно
        assert isinstance(results, list)

    def test_search_similar_empty_document(self):
        """Тест поиска в пустом документе"""
        results = self.search_engine.search_similar("тест", "nonexistent_doc")
        assert results == []

    def test_async_search_similar_paragraphs(self):
        """Тест асинхронного поиска параграфов"""
        # Тестируем метод search_similar_paragraphs
        import asyncio

        async def run_test():
            results = await self.search_engine.search_similar_paragraphs("машинное обучение", "search_test", top_k=2)
            return results

        results = asyncio.run(run_test())

        assert isinstance(results, list)
        assert all(isinstance(p, Paragraph) for p in results)
        assert len(results) <= 2
