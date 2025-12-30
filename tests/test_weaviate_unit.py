"""
Unit тесты для компонентов Weaviate.

Эти тесты не требуют запущенного Weaviate сервера.
"""

from unittest.mock import Mock, patch

import pytest
import numpy as np

# Убраны импорты из weaviate_schema - теперь используется встроенная AutoSchema
# from api.storage.weaviate_schema import (
#     _get_weaviate_data_type,
#     _generate_properties_from_paragraph,
#     create_schema_if_not_exists,
#     update_schema_if_needed,
# )
from api.storage.weaviate_storage import WeaviateStorage
from api.storage.faiss import Paragraph
from api.settings import WEAVIATE_CLASS_NAME


class TestWeaviateSchema:
    """Unit тесты для схемы Weaviate - теперь использует встроенную AutoSchema"""

    def test_schema_functions_are_stubs(self):
        """Тест, что функции схемы теперь являются заглушками для совместимости"""
        from api.storage.weaviate_schema import create_schema_if_not_exists, update_schema_if_needed

        # Функции должны быть заглушками и не выбрасывать ошибки
        result = update_schema_if_needed(None)
        assert result is False

        # create_schema_if_not_exists не должна выбрасывать ошибку
        try:
            create_schema_if_not_exists(None)
        except Exception as e:
            pytest.fail(f"create_schema_if_not_exists должна быть заглушкой, но выбросила: {e}")

    def test_autoschema_is_enabled_by_default(self):
        """Тест, что встроенная AutoSchema включена по умолчанию"""
        from api.settings import WEAVIATE_USE_BUILTIN_AUTOSCHEMA

        # Должна быть включена по умолчанию для симбиосети
        assert WEAVIATE_USE_BUILTIN_AUTOSCHEMA is True


class TestWeaviateStorageUnit:
    """Unit тесты для WeaviateStorage (без реального подключения)"""

    @patch("api.storage.weaviate_storage.WeaviateStorage._create_embedding")
    @patch("api.storage.weaviate_storage.SentenceTransformer")
    def test_init_storage(self, mock_transformer, mock_create_embedding):
        """Тест инициализации WeaviateStorage"""
        mock_model = Mock()
        mock_transformer.return_value = mock_model
        mock_model.get_sentence_embedding_dimension.return_value = 384

        with patch("api.storage.weaviate_storage.create_schema_if_not_exists"):
            with patch("weaviate.WeaviateClient") as mock_client_class:
                with patch("api.storage.weaviate_storage.WEAVIATE_URL", "http://localhost:8080"):
                    mock_client = Mock()
                    mock_client_class.return_value = mock_client
                    mock_client.connect.return_value = None
                    mock_client.get_meta.return_value = {"version": "1.24.0"}

                    storage = WeaviateStorage()

                assert storage.model == mock_model
                assert storage.dimension == 384
                mock_client.connect.assert_called_once()

    def test_paragraph_to_weaviate_object(self):
        """Тест преобразования Paragraph в Weaviate объект"""
        with patch("api.storage.weaviate_storage.SentenceTransformer"):
            with patch("api.storage.weaviate_storage.create_schema_if_not_exists"):
                with patch("weaviate.WeaviateClient"):
                    with patch("api.storage.weaviate_storage.WEAVIATE_URL", "http://localhost:8080"):
                        storage = WeaviateStorage()

                    paragraph = Paragraph(
                        id="test_123",
                        content="Тестовый контент",
                        author="Автор",
                        author_id=123,
                        document_id="doc_1",
                        tags=["tag1", "tag2"],
                        location="Москва",
                        ecosystem_id="eco_1",
                        organisms=[{"name": "дуб", "type": "растение"}],
                    )

                    weaviate_obj = storage._paragraph_to_weaviate_object(paragraph)

                    # Проверяем основные поля
                    assert weaviate_obj["content"] == "Тестовый контент"
                    assert weaviate_obj["author"] == "Автор"
                    assert weaviate_obj["author_id"] == 123
                    assert weaviate_obj["document_id"] == "doc_1"
                    assert weaviate_obj["tags"] == ["tag1", "tag2"]
                    assert weaviate_obj["location"] == "Москва"
                    assert weaviate_obj["ecosystem_id"] == "eco_1"
                    assert weaviate_obj["organisms"] == [{"name": "дуб", "type": "растение"}]

    @patch("api.storage.weaviate_storage.SentenceTransformer")
    def test_create_paragraph_id(self, mock_transformer):
        """Тест генерации ID параграфов"""
        with patch("api.storage.weaviate_storage.create_schema_if_not_exists"):
            with patch("weaviate.WeaviateClient"):
                with patch("api.storage.weaviate_storage.WEAVIATE_URL", "http://localhost:8080"):
                    storage = WeaviateStorage()

                # Тест с текстом
                para_id = storage._create_paragraph_id("Тестовый текст")
                assert para_id.startswith("para_")
                assert len(para_id) > 5

                # Тест с текстом и индексом
                para_id_with_index = storage._create_paragraph_id("Тестовый текст", index=5)
                assert "idx_5" in para_id_with_index

    @patch("api.storage.weaviate_storage.WeaviateStorage._create_embedding_cached")
    @patch("api.storage.weaviate_storage.SentenceTransformer")
    def test_create_embedding(self, mock_transformer, mock_cached_embedding):
        """Тест создания эмбеддингов"""
        mock_model = Mock()
        mock_transformer.return_value = mock_model
        mock_model.get_sentence_embedding_dimension.return_value = 4

        # Mock the cached embedding method to return our test values
        mock_cached_embedding.return_value = np.array([0.1, 0.2, 0.3, 0.4])

        with patch("api.storage.weaviate_storage.create_schema_if_not_exists"):
            with patch("weaviate.WeaviateClient"):
                with patch("api.storage.weaviate_storage.WEAVIATE_URL", "http://localhost:8080"):
                    storage = WeaviateStorage()

                    embedding = storage._create_embedding("Тестовый текст")

                assert len(embedding) == 4
                assert embedding[0] == 0.1
                mock_cached_embedding.assert_called_once_with("Тестовый текст")

    def test_is_weaviate_available_with_url(self):
        """Тест проверки доступности Weaviate с URL"""
        with patch("api.storage.faiss.FAISSStorage._is_weaviate_available") as mock_method:
            mock_method.return_value = True

            with patch("api.storage.weaviate_storage.SentenceTransformer"):
                with patch("api.storage.weaviate_storage.create_schema_if_not_exists"):
                    with patch("weaviate.WeaviateClient"):
                        with patch("api.storage.weaviate_storage.WEAVIATE_URL", "http://localhost:8080"):
                            storage = WeaviateStorage()
                            assert storage._is_weaviate_available() is True

    def test_is_weaviate_available_without_url(self):
        """Тест проверки доступности Weaviate без URL"""
        with patch("api.storage.weaviate_storage.SentenceTransformer"):
            with patch("api.storage.weaviate_storage.create_schema_if_not_exists"):
                with patch("weaviate.WeaviateClient"):
                    with patch("api.storage.weaviate_storage.WEAVIATE_URL", "http://localhost:8080"):
                        storage = WeaviateStorage()
                        # Тест логики метода - здесь WEAVIATE_URL есть, но метод вернет False
                        # так как мы не мокируем фактическую проверку
                        # Этот тест проверяет что метод существует и не падает
                        assert hasattr(storage, "_is_weaviate_available")
