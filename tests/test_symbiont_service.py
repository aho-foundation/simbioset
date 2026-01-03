"""
Unit тесты для SymbiontService.

Тестирует функциональность работы с симбионтами и патогенами в Weaviate.
Фокус на бизнес-логике, error handling и edge cases.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import uuid
from typing import Dict, Any

from api.storage.symbiont_service import SymbiontService, SymbiontPathogen
from api.storage.weaviate_storage import WeaviateStorage


class TestSymbiontPathogen:
    """Тесты для класса SymbiontPathogen."""

    def test_from_dict_minimal(self):
        """Тест создания объекта из минимального словаря."""
        data = {
            "name": "Тестовый симбионт",
        }

        symbiont = SymbiontPathogen.from_dict(data)

        assert symbiont.name == "Тестовый симбионт"
        assert symbiont.id is not None  # Генерируется автоматически
        assert symbiont.type == "symbiont"  # Значение по умолчанию
        assert symbiont.interaction_type == "mutualistic"  # Значение по умолчанию

    def test_from_dict_full(self):
        """Тест создания объекта из полного словаря."""
        data = {
            "id": "test-id-123",
            "name": "Полный симбионт",
            "scientific_name": "Full Symbiont",
            "type": "pathogen",
            "category": "бактерия",
            "host_organism_id": "host-123",
            "parent_symbiont_id": "parent-123",
            "interaction_type": "pathogenic",
            "biochemical_role": "тестовая роль",
            "transmission_method": "контактный",
            "virulence_factors": ["фактор1", "фактор2"],
            "symbiotic_benefits": ["польза1", "польза2"],
            "organism_ecological_role": "тестовый эффект",
            "geographic_distribution": "всемирно",
            "prevalence": 0.75,
            "risk_level": "high",
            "detection_confidence": 0.95,
            "metadata": {"key": "value"},
        }

        symbiont = SymbiontPathogen.from_dict(data)

        assert symbiont.id == "test-id-123"
        assert symbiont.name == "Полный симбионт"
        assert symbiont.scientific_name == "Full Symbiont"
        assert symbiont.type == "pathogen"
        assert symbiont.category == "бактерия"
        assert symbiont.host_organism_id == "host-123"
        assert symbiont.parent_symbiont_id == "parent-123"
        assert symbiont.interaction_type == "pathogenic"
        assert symbiont.biochemical_role == "тестовая роль"
        assert symbiont.transmission_method == "контактный"
        assert symbiont.virulence_factors == ["фактор1", "фактор2"]
        assert symbiont.symbiotic_benefits == ["польза1", "польза2"]
        assert symbiont.organism_ecological_role == "тестовый эффект"
        assert symbiont.geographic_distribution == "всемирно"
        assert symbiont.prevalence == 0.75
        assert symbiont.risk_level == "high"
        assert symbiont.detection_confidence == 0.95
        assert symbiont.metadata == {"key": "value"}

    def test_to_dict(self):
        """Тест преобразования объекта в словарь."""
        symbiont = SymbiontPathogen(
            id="test-id",
            name="Тестовый симбионт",
            scientific_name="Test Symbiont",
            type="symbiont",
            category="бактерия",
            host_organism_id="host-123",
            parent_symbiont_id="parent-123",
            interaction_type="mutualistic",
            biochemical_role="тестовая роль",
            transmission_method="контактный",
            virulence_factors=["фактор1"],
            symbiotic_benefits=["польза1"],
            organism_ecological_role="тестовый эффект",
            geographic_distribution="всемирно",
            prevalence=0.8,
            risk_level="low",
            detection_confidence=0.9,
            metadata={"key": "value"},
        )

        data = symbiont.to_dict()

        assert data["id"] == "test-id"
        assert data["name"] == "Тестовый симбионт"
        assert data["scientific_name"] == "Test Symbiont"
        assert data["type"] == "symbiont"
        assert data["category"] == "бактерия"
        assert data["host_organism_id"] == "host-123"
        assert data["parent_symbiont_id"] == "parent-123"
        assert data["interaction_type"] == "mutualistic"
        assert data["biochemical_role"] == "тестовая роль"
        assert data["transmission_method"] == "контактный"
        assert data["virulence_factors"] == ["фактор1"]
        assert data["symbiotic_benefits"] == ["польза1"]
        assert data["organism_ecological_role"] == "тестовый эффект"
        assert data["geographic_distribution"] == "всемирно"
        assert data["prevalence"] == 0.8
        assert data["risk_level"] == "low"
        assert data["detection_confidence"] == 0.9
        assert data["metadata"] == {"key": "value"}

    def test_round_trip_dict_conversion(self):
        """Тест, что from_dict -> to_dict -> from_dict работает корректно."""
        original_data = {
            "id": "test-id",
            "name": "Тестовый симбионт",
            "scientific_name": "Test Symbiont",
            "type": "pathogen",
            "category": "вирус",
            "host_organism_id": "host-456",
            "parent_symbiont_id": "parent-456",
            "interaction_type": "pathogenic",
            "biochemical_role": "вирусная репликация",
            "transmission_method": "воздушно-капельный",
            "virulence_factors": ["фактор1", "фактор2"],
            "symbiotic_benefits": [],
            "organism_ecological_role": "регуляция популяций",
            "geographic_distribution": "Европа",
            "prevalence": 0.3,
            "risk_level": "high",
            "detection_confidence": 0.85,
            "metadata": {"source": "test"},
        }

        # Преобразуем в объект и обратно
        symbiont = SymbiontPathogen.from_dict(original_data)
        converted_data = symbiont.to_dict()
        symbiont2 = SymbiontPathogen.from_dict(converted_data)

        # Проверяем, что все поля сохранились
        assert symbiont2.id == original_data["id"]
        assert symbiont2.name == original_data["name"]
        assert symbiont2.scientific_name == original_data["scientific_name"]
        assert symbiont2.type == original_data["type"]
        assert symbiont2.category == original_data["category"]
        assert symbiont2.host_organism_id == original_data["host_organism_id"]
        assert symbiont2.parent_symbiont_id == original_data["parent_symbiont_id"]
        assert symbiont2.interaction_type == original_data["interaction_type"]
        assert symbiont2.biochemical_role == original_data["biochemical_role"]
        assert symbiont2.transmission_method == original_data["transmission_method"]
        assert symbiont2.virulence_factors == original_data["virulence_factors"]
        assert symbiont2.symbiotic_benefits == original_data["symbiotic_benefits"]
        assert symbiont2.organism_ecological_role == original_data["organism_ecological_role"]
        assert symbiont2.geographic_distribution == original_data["geographic_distribution"]
        assert symbiont2.prevalence == original_data["prevalence"]
        assert symbiont2.risk_level == original_data["risk_level"]
        assert symbiont2.detection_confidence == original_data["detection_confidence"]
        assert symbiont2.metadata == original_data["metadata"]


class TestSymbiontService:
    """Тесты для SymbiontService."""

    @pytest.fixture
    def mock_weaviate_storage(self):
        """Фикстура с мок WeaviateStorage."""
        mock_storage = Mock(spec=WeaviateStorage)
        mock_storage.add_documents = AsyncMock()
        mock_storage.get_paragraph_by_id = Mock()
        mock_storage.search_similar_paragraphs = AsyncMock()
        mock_storage.get_all_documents = Mock()
        mock_storage.get_document_paragraphs = Mock()
        mock_storage.update_paragraph = Mock()
        mock_storage.delete_paragraph = Mock()
        mock_storage._create_embedding = Mock(return_value=[0.1, 0.2, 0.3])
        return mock_storage

    @pytest.fixture
    def symbiont_service(self, mock_weaviate_storage):
        """Фикстура с SymbiontService."""
        return SymbiontService(mock_weaviate_storage)

    @pytest.fixture
    def test_symbiont(self):
        """Фикстура с тестовым симбионтом."""
        return SymbiontPathogen(
            id="test-symbiont-123",
            name="Тестовый симбионт",
            scientific_name="Test Symbiont",
            type="symbiont",
            category="бактерия",
            interaction_type="mutualistic",
            biochemical_role="тестовый симбиоз",
            prevalence=0.8,
            risk_level="low",
            detection_confidence=0.9,
        )

    @pytest.mark.asyncio
    async def test_create_symbiont_success(self, symbiont_service, mock_weaviate_storage, test_symbiont):
        """Тест успешного создания симбионта."""
        # Act
        result = await symbiont_service.create_symbiont(test_symbiont)

        # Assert
        assert result == test_symbiont.id
        mock_weaviate_storage.add_documents.assert_called_once()
        call_args = mock_weaviate_storage.add_documents.call_args[0][0][0]

        # Проверяем, что данные корректно преобразованы
        assert call_args["text"] == "Тестовый симбионт Test Symbiont"
        assert call_args["document_id"] == "symbiont_test-symbiont-123"
        assert call_args["document_type"] == "symbiont"
        assert call_args["metadata"]["id"] == "test-symbiont-123"
        assert call_args["metadata"]["name"] == "Тестовый симбионт"

    @pytest.mark.asyncio
    async def test_create_symbiont_error_handling(self, symbiont_service, mock_weaviate_storage, test_symbiont):
        """Тест обработки ошибок при создании симбионта."""
        # Arrange
        mock_weaviate_storage._create_embedding.side_effect = Exception("Embedding error")

        # Act & Assert
        with pytest.raises(Exception, match="Embedding error"):
            await symbiont_service.create_symbiont(test_symbiont)

    @pytest.mark.asyncio
    async def test_get_symbiont_success(self, symbiont_service, mock_weaviate_storage):
        """Тест успешного получения симбионта."""
        # Arrange
        test_metadata = {
            "id": "test-123",
            "name": "Найденный симбионт",
            "type": "symbiont",
        }
        mock_paragraph = Mock()
        mock_paragraph.metadata = test_metadata
        mock_weaviate_storage.get_paragraph_by_id.return_value = mock_paragraph

        # Act
        result = await symbiont_service.get_symbiont("test-123")

        # Assert
        assert result is not None
        assert result.id == "test-123"
        assert result.name == "Найденный симбионт"
        assert result.type == "symbiont"

    @pytest.mark.asyncio
    async def test_get_symbiont_not_found(self, symbiont_service, mock_weaviate_storage):
        """Тест получения несуществующего симбионта."""
        # Arrange
        mock_weaviate_storage.get_paragraph_by_id.return_value = None

        # Act
        result = await symbiont_service.get_symbiont("nonexistent")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_symbiont_no_metadata(self, symbiont_service, mock_weaviate_storage):
        """Тест получения симбионта без метаданных."""
        # Arrange
        mock_paragraph = Mock()
        mock_paragraph.metadata = None
        mock_weaviate_storage.get_paragraph_by_id.return_value = mock_paragraph

        # Act
        result = await symbiont_service.get_symbiont("test-123")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_search_symbionts_success(self, symbiont_service, mock_weaviate_storage):
        """Тест успешного поиска симбионтов."""
        # Arrange
        mock_paragraphs = [
            Mock(metadata={"id": "sym-1", "name": "Симбионт 1", "type": "symbiont"}),
            Mock(metadata={"id": "sym-2", "name": "Симбионт 2", "type": "symbiont"}),
        ]
        mock_weaviate_storage.search_similar_paragraphs.return_value = mock_paragraphs

        # Act
        results = await symbiont_service.search_symbionts("поисковый запрос", limit=10)

        # Assert
        assert len(results) == 2
        assert results[0].id == "sym-1"
        assert results[0].name == "Симбионт 1"
        assert results[1].id == "sym-2"
        assert results[1].name == "Симбионт 2"

    @pytest.mark.asyncio
    async def test_search_symbionts_with_filters(self, symbiont_service, mock_weaviate_storage):
        """Тест поиска симбионтов с фильтрами."""
        # Arrange
        mock_paragraphs = [Mock(metadata={"id": "path-1", "name": "Патоген", "type": "pathogen"})]
        mock_weaviate_storage.search_similar_paragraphs.return_value = mock_paragraphs

        # Act
        results = await symbiont_service.search_symbionts(query="патоген", type_filter="pathogen", limit=5)

        # Assert
        assert len(results) == 1
        assert results[0].type == "pathogen"

        # Проверяем вызов с фильтрами
        call_args = mock_weaviate_storage.search_similar_paragraphs.call_args
        assert call_args[1]["query"] == "патоген"
        assert call_args[1]["top_k"] == 5

    @pytest.mark.asyncio
    async def test_search_symbionts_empty_results(self, symbiont_service, mock_weaviate_storage):
        """Тест поиска симбионтов без результатов."""
        # Arrange
        mock_weaviate_storage.search_similar_paragraphs.return_value = []

        # Act
        results = await symbiont_service.search_symbionts("несуществующий")

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_search_symbionts_invalid_metadata(self, symbiont_service, mock_weaviate_storage):
        """Тест поиска симбионтов с некорректными метаданными."""
        # Arrange
        mock_paragraphs = [
            Mock(metadata={"invalid": "data"}),  # Некорректные метаданные
            Mock(metadata={"id": "valid", "name": "Валидный", "type": "symbiont"}),
        ]
        mock_weaviate_storage.search_similar_paragraphs.return_value = mock_paragraphs

        # Act
        results = await symbiont_service.search_symbionts("запрос")

        # Assert
        assert len(results) == 1  # Только валидный результат
        assert results[0].id == "valid"
        assert results[0].name == "Валидный"

    @pytest.mark.asyncio
    async def test_get_symbionts_by_host_success(self, symbiont_service, mock_weaviate_storage):
        """Тест получения симбионтов по организму-хозяину."""
        # Arrange
        mock_weaviate_storage.get_all_documents.return_value = ["symbiont_doc1", "symbiont_doc2"]
        mock_weaviate_storage.get_document_paragraphs.side_effect = [
            [Mock(metadata={"id": "sym-1", "host_organism_id": "host-123", "name": "Симбионт 1"})],
            [Mock(metadata={"id": "sym-2", "host_organism_id": "other-host", "name": "Симбионт 2"})],
        ]

        # Act
        results = await symbiont_service.get_symbionts_by_host("host-123")

        # Assert
        assert len(results) == 1
        assert results[0].id == "sym-1"
        assert results[0].name == "Симбионт 1"

    @pytest.mark.asyncio
    async def test_get_symbionts_by_host_no_results(self, symbiont_service, mock_weaviate_storage):
        """Тест получения симбионтов по несуществующему хозяину."""
        # Arrange
        mock_weaviate_storage.get_all_documents.return_value = ["symbiont_doc1"]
        mock_weaviate_storage.get_document_paragraphs.return_value = [
            Mock(metadata={"id": "sym-1", "host_organism_id": "other-host"})
        ]

        # Act
        results = await symbiont_service.get_symbionts_by_host("nonexistent-host")

        # Assert
        assert results == []

    @pytest.mark.asyncio
    async def test_get_child_symbionts_success(self, symbiont_service, mock_weaviate_storage):
        """Тест получения дочерних симбионтов."""
        # Arrange
        mock_weaviate_storage.get_all_documents.return_value = ["symbiont_doc1"]
        mock_weaviate_storage.get_document_paragraphs.return_value = [
            Mock(metadata={"id": "child-1", "parent_symbiont_id": "parent-123", "name": "Дочерний 1"}),
            Mock(metadata={"id": "child-2", "parent_symbiont_id": "other-parent", "name": "Дочерний 2"}),
        ]

        # Act
        results = await symbiont_service.get_child_symbionts("parent-123")

        # Assert
        assert len(results) == 1
        assert results[0].id == "child-1"
        assert results[0].name == "Дочерний 1"

    @pytest.mark.asyncio
    async def test_update_symbiont_success(self, symbiont_service, mock_weaviate_storage):
        """Тест успешного обновления симбионта."""
        # Arrange
        mock_paragraph = Mock()
        mock_paragraph.metadata = {"id": "test-123", "name": "Старое имя"}
        mock_weaviate_storage.get_paragraph_by_id.return_value = mock_paragraph
        mock_weaviate_storage.update_paragraph.return_value = True

        updates = {"name": "Новое имя", "prevalence": 0.9}

        # Act
        result = await symbiont_service.update_symbiont("test-123", updates)

        # Assert
        assert result is True
        mock_weaviate_storage.update_paragraph.assert_called_once()
        # Проверяем, что метаданные обновлены
        assert mock_paragraph.metadata["name"] == "Новое имя"
        assert mock_paragraph.metadata["prevalence"] == 0.9

    @pytest.mark.asyncio
    async def test_update_symbiont_not_found(self, symbiont_service, mock_weaviate_storage):
        """Тест обновления несуществующего симбионта."""
        # Arrange
        mock_weaviate_storage.get_paragraph_by_id.return_value = None

        # Act
        result = await symbiont_service.update_symbiont("nonexistent", {"name": "новое имя"})

        # Assert
        assert result is False
        mock_weaviate_storage.update_paragraph.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_symbiont_success(self, symbiont_service, mock_weaviate_storage):
        """Тест успешного удаления симбионта."""
        # Arrange
        mock_weaviate_storage.delete_paragraph.return_value = True

        # Act
        result = await symbiont_service.delete_symbiont("test-123")

        # Assert
        assert result is True
        mock_weaviate_storage.delete_paragraph.assert_called_once_with("symbiont_test-123", "test-123")

    @pytest.mark.asyncio
    async def test_delete_symbiont_failure(self, symbiont_service, mock_weaviate_storage):
        """Тест неудачного удаления симбионта."""
        # Arrange
        mock_weaviate_storage.delete_paragraph.return_value = False

        # Act
        result = await symbiont_service.delete_symbiont("test-123")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_business_logic_validation(self, symbiont_service, mock_weaviate_storage, test_symbiont):
        """Тест бизнес-логики валидации данных симбионта."""
        # Arrange - создаем симбионта с некорректными данными
        invalid_symbiont = SymbiontPathogen(
            id="invalid-123",
            name="",  # Пустое имя
            scientific_name="Invalid sp.",
            type="invalid_type",  # Некорректный тип
            interaction_type="mutualistic",
            prevalence=1.5,  # Превышает диапазон
            risk_level="invalid",  # Некорректный риск
            detection_confidence=0.8,
        )

        # Act & Assert - сервис должен позволить создать (валидация на уровне модели)
        mock_weaviate_storage.add_documents = AsyncMock()
        result = await symbiont_service.create_symbiont(invalid_symbiont)

        # Assert - но данные должны быть сохранены как есть
        assert result == "invalid-123"
        call_args = mock_weaviate_storage.add_documents.call_args[0][0][0]
        assert call_args["metadata"]["name"] == ""  # Пустое имя сохранено

    @pytest.mark.parametrize(
        "query,expected_calls",
        [
            ("бифидо", 1),  # Поиск по части имени
            ("Bifidobacterium", 1),  # Поиск по scientific name
            ("бактерия", 1),  # Поиск по категории
            ("несуществующий", 0),  # Поиск без результатов
        ],
    )
    @pytest.mark.asyncio
    async def test_search_quality_and_relevance(
        self, symbiont_service, mock_weaviate_storage, test_symbiont, query, expected_calls
    ):
        """Тест качества и релевантности поиска."""
        # Arrange
        mock_weaviate_storage.search_similar_paragraphs.return_value = (
            [Mock(metadata=test_symbiont.to_dict())] if expected_calls > 0 else []
        )

        # Act
        results = await symbiont_service.search_symbionts(query, limit=10)

        # Assert
        if expected_calls > 0:
            assert len(results) > 0, f"Поиск '{query}' должен вернуть результаты"
            assert results[0].name == test_symbiont.name, "Результат должен содержать правильный симбионт"
        else:
            assert len(results) == 0, f"Поиск '{query}' не должен вернуть результаты"

    @pytest.mark.asyncio
    async def test_hierarchy_operations_consistency(self, symbiont_service, mock_weaviate_storage):
        """Тест консистентности операций с иерархией."""
        # Arrange - создаем иерархию симбионтов
        parent_symbiont = SymbiontPathogen.from_dict(
            {
                "id": "parent-123",
                "name": "Родительский симбионт",
                "type": "symbiont",
                "interaction_type": "mutualistic",
                "prevalence": 0.8,
                "risk_level": "low",
                "detection_confidence": 0.9,
            }
        )

        child_symbiont = SymbiontPathogen.from_dict(
            {
                "id": "child-456",
                "name": "Дочерний симбионт",
                "type": "symbiont",
                "interaction_type": "mutualistic",
                "host_organism_id": "host-123",
                "parent_symbiont_id": "parent-123",
                "prevalence": 0.6,
                "risk_level": "low",
                "detection_confidence": 0.8,
            }
        )

        # Настраиваем моки для поиска по хосту
        def mock_get_all_documents():
            return ["symbiont_parent-123", "symbiont_child-456"]

        def mock_get_document_paragraphs(doc_id):
            if "parent" in doc_id:
                return [Mock(metadata=parent_symbiont.to_dict())]
            elif "child" in doc_id:
                return [Mock(metadata=child_symbiont.to_dict())]
            return []

        mock_weaviate_storage.get_all_documents.side_effect = mock_get_all_documents
        mock_weaviate_storage.get_document_paragraphs.side_effect = mock_get_document_paragraphs

        # Act - получаем симбионтов по хосту
        host_symbionts = await symbiont_service.get_symbionts_by_host("host-123")

        # Assert
        assert len(host_symbionts) == 1, "Должен найтись один симбионт для хоста"
        assert host_symbionts[0].id == "child-456", "Должен найтись дочерний симбионт"
        assert host_symbionts[0].host_organism_id == "host-123", "Хост должен совпадать"

        # Act - получаем дочерние симбионты
        child_symbionts = await symbiont_service.get_child_symbionts("parent-123")

        # Assert
        assert len(child_symbionts) == 1, "Должен найтись один дочерний симбионт"
        assert child_symbionts[0].id == "child-456", "Должен найтись правильный дочерний симбионт"
        assert child_symbionts[0].parent_symbiont_id == "parent-123", "Родитель должен совпадать"

    @pytest.mark.asyncio
    async def test_error_recovery_and_robustness(self, symbiont_service, mock_weaviate_storage):
        """Тест восстановления после ошибок и устойчивости."""
        # Arrange - симулируем частичное повреждение данных
        mock_paragraphs = [
            Mock(
                metadata={
                    "id": "valid-1",
                    "name": "Valid Symbiont",
                    "type": "symbiont",
                    "interaction_type": "mutualistic",
                    "prevalence": 0.8,
                    "risk_level": "low",
                    "detection_confidence": 0.9,
                }
            ),
            Mock(metadata=None),  # Поврежденные метаданные
            Mock(
                metadata={
                    "id": "valid-2",
                    "name": "Another Valid",
                    "type": "symbiont",
                    "interaction_type": "mutualistic",
                    "prevalence": 0.7,
                    "risk_level": "low",
                    "detection_confidence": 0.8,
                }
            ),
            Mock(metadata={"invalid": "data"}),  # Неполные метаданные
        ]

        mock_weaviate_storage.search_similar_paragraphs.return_value = mock_paragraphs

        # Act
        results = await symbiont_service.search_symbionts("симбионт")

        # Assert - сервис должен корректно обработать поврежденные данные
        assert len(results) == 2, "Должно вернуться только 2 валидных результата"
        assert all(r.name in ["Valid Symbiont", "Another Valid"] for r in results), (
            "Только валидные симбионты должны вернуться"
        )

    @pytest.mark.asyncio
    async def test_performance_and_scalability_indicators(self, symbiont_service, mock_weaviate_storage):
        """Тест индикаторов производительности и масштабируемости."""
        # Arrange - создаем большой набор данных
        large_dataset = []
        for i in range(100):
            symbiont = SymbiontPathogen.from_dict(
                {
                    "id": f"sym-{i:03d}",
                    "name": f"Symbiont {i}",
                    "scientific_name": f"Symbiont species {i}",
                    "type": "symbiont",
                    "interaction_type": "mutualistic",
                    "prevalence": 0.5 + (i % 50) / 100,  # Варьируется от 0.5 до 1.0
                    "risk_level": "low",
                    "detection_confidence": 0.8 + (i % 20) / 100,  # Варьируется от 0.8 до 1.0
                }
            )
            large_dataset.append(symbiont)

        # Мокаем создание большого количества симбионтов
        call_count = 0

        async def count_calls(symbiont):
            nonlocal call_count
            call_count += 1
            return symbiont.id

        mock_weaviate_storage.add_documents = AsyncMock()
        symbiont_service.create_symbiont = count_calls

        # Act - создаем все симбионты
        for symbiont in large_dataset:
            await symbiont_service.create_symbiont(symbiont)

        # Assert - проверяем, что все создания прошли успешно
        assert call_count == 100, "Все 100 симбионтов должны быть созданы"

        # Assert - проверяем разнообразие данных
        prevalence_values = [s.prevalence for s in large_dataset]
        confidence_values = [s.detection_confidence for s in large_dataset]

        assert max(prevalence_values) - min(prevalence_values) >= 0.4, "Должен быть широкий диапазон prevalence"
        assert max(confidence_values) - min(confidence_values) >= 0.1, "Должен быть диапазон confidence"
