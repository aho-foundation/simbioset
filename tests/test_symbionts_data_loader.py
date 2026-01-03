"""
Unit тесты для SymbiontsDataLoader.

Тестирует функциональность загрузки данных о симбионтах и патогенах.
Фокус на бизнес-логике, edge cases и качественных данных.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import uuid
from typing import Dict, Any

from scripts.load_symbionts_data import SymbiontsDataLoader
from api.storage.symbiont_service import SymbiontService, SymbiontPathogen


class TestSymbiontsDataLoader:
    """Тесты для SymbiontsDataLoader."""

    @pytest.fixture
    def mock_weaviate_storage(self):
        """Фикстура с мок WeaviateStorage."""
        mock_storage = Mock()
        mock_storage.add_documents = AsyncMock()
        return mock_storage

    @pytest.fixture
    def mock_symbiont_service(self, mock_weaviate_storage):
        """Фикстура с мок SymbiontService."""
        mock_service = Mock(spec=SymbiontService)
        mock_service.create_symbiont = AsyncMock()
        return mock_service

    @pytest.fixture
    def data_loader(self, mock_weaviate_storage, mock_symbiont_service):
        """Фикстура с SymbiontsDataLoader."""
        with patch("scripts.load_symbionts_data.WeaviateStorage", return_value=mock_weaviate_storage):
            loader = SymbiontsDataLoader()
            loader.symbiont_service = mock_symbiont_service
            return loader

    @pytest.mark.asyncio
    async def test_load_microbiome_data_comprehensive(self, data_loader):
        """Комплексный тест загрузки данных о микробиоме человека."""
        # Act
        data = await data_loader.load_microbiome_data()

        # Assert - основные свойства
        assert isinstance(data, list)
        assert len(data) >= 4, "Должен быть минимум базовый набор симбионтов микробиома"

        # Проверяем все элементы на консистентность
        for i, item in enumerate(data):
            # Валидация должна пройти без исключений для корректных данных
            self._validate_symbiont_data_structure(item, "микробиом")

        # Проверяем конкретные известные симбионты
        bifido = next((s for s in data if s["name"] == "Бифидобактерии"), None)
        assert bifido is not None, "Бифидобактерии должны присутствовать в микробиоме"
        assert bifido["scientific_name"] == "Bifidobacterium"
        assert bifido["type"] == "symbiont"
        assert bifido["prevalence"] >= 0.9, "Бифидобактерии должны иметь высокую распространенность"
        assert bifido["risk_level"] == "low", "Бифидобактерии должны иметь низкий риск"

        # Проверяем разнообразие типов взаимодействия
        interaction_types = set(item["interaction_type"] for item in data)
        assert "mutualistic" in interaction_types, "Должны быть мутуалистические симбионты"
        assert len(interaction_types) >= 2, "Должен быть разнообразие типов взаимодействия"

    def _validate_symbiont_data_structure(self, item: Dict[str, Any], context: str):
        """Валидация структуры данных симбионта."""
        # Обязательные поля
        required_fields = [
            "name",
            "scientific_name",
            "type",
            "interaction_type",
            "prevalence",
            "risk_level",
            "detection_confidence",
        ]

        for field in required_fields:
            assert field in item, f"Поле {field} отсутствует в {context}"
            assert item[field] is not None, f"Поле {field} не может быть None в {context}"

        # Типы данных
        assert isinstance(item["name"], str) and item["name"], "name должен быть непустой строкой"
        assert isinstance(item["prevalence"], (int, float)), "prevalence должен быть числом"
        assert isinstance(item["detection_confidence"], (int, float)), "detection_confidence должен быть числом"

        # Диапазоны значений
        assert 0.0 <= item["prevalence"] <= 1.0, f"prevalence должен быть в диапазоне [0,1] в {context}"
        assert 0.0 <= item["detection_confidence"] <= 1.0, (
            f"detection_confidence должен быть в диапазоне [0,1] в {context}"
        )
        assert item["risk_level"] in ["low", "medium", "high"], f"risk_level должен быть low/medium/high в {context}"

        # Логическая консистентность
        if item["type"] == "symbiont":
            assert item["interaction_type"] in ["mutualistic", "commensal"], (
                "Симбионты должны иметь подходящий тип взаимодействия"
            )
        elif item["type"] == "pathogen":
            assert item["interaction_type"] == "pathogenic", "Патогены должны иметь pathogenic тип взаимодействия"

    @pytest.mark.asyncio
    async def test_load_plant_symbionts_comprehensive(self, data_loader):
        """Комплексный тест загрузки данных о симбионтах растений."""
        # Act
        data = await data_loader.load_plant_symbionts()

        # Assert - основные свойства
        assert isinstance(data, list)
        assert len(data) >= 3, "Должен быть минимум базовый набор симбионтов растений"

        # Проверяем все элементы на консистентность
        for i, item in enumerate(data):
            # Валидация должна пройти без исключений для корректных данных
            self._validate_symbiont_data_structure(item, "растения")

        # Проверяем ключевые симбионты растений
        mycorrhiza = next((s for s in data if s["name"] == "Микориза"), None)
        assert mycorrhiza is not None, "Микориза должна присутствовать"
        assert mycorrhiza["scientific_name"] == "Mycorrhiza"
        assert (
            mycorrhiza["organism_ecological_role"]
            == "критично для большинства растений, повышает продуктивность экосистем"
        )

        rhizobium = next((s for s in data if s["name"] == "Клубеньковые бактерии"), None)
        assert rhizobium is not None, "Клубеньковые бактерии должны присутствовать"
        assert rhizobium["scientific_name"] == "Rhizobium"
        assert "азот" in rhizobium["biochemical_role"].lower(), "Клубеньковые должны фиксацию азота"

        # Проверяем разнообразие категорий
        categories = set(item["category"] for item in data)
        assert len(categories) >= 2, "Должно быть разнообразие категорий симбионтов растений"

    @pytest.mark.parametrize(
        "data_type,expected_min_count",
        [
            ("microbiome", 4),
            ("plant_symbionts", 3),
            ("pathogens", 3),
        ],
    )
    @pytest.mark.asyncio
    async def test_load_data_methods_return_valid_counts(self, data_loader, data_type, expected_min_count):
        """Параметризованный тест количества загружаемых данных."""
        # Arrange
        method_map = {
            "microbiome": data_loader.load_microbiome_data,
            "plant_symbionts": data_loader.load_plant_symbionts,
            "pathogens": data_loader.load_pathogens,
        }

        # Act
        data = await method_map[data_type]()

        # Assert
        assert len(data) >= expected_min_count, f"{data_type} должен содержать минимум {expected_min_count} элементов"
        assert all(isinstance(item, dict) for item in data), f"Все элементы {data_type} должны быть словарями"

    @pytest.mark.asyncio
    async def test_load_pathogens_comprehensive(self, data_loader):
        """Комплексный тест загрузки данных о патогенах."""
        # Act
        data = await data_loader.load_pathogens()

        # Assert - основные свойства
        assert isinstance(data, list)
        assert len(data) >= 3, "Должен быть минимум базовый набор патогенов"

        # Проверяем все элементы на консистентность
        for i, item in enumerate(data):
            # Валидация должна пройти без исключений для корректных данных
            self._validate_pathogen_data_structure(item)

        # Проверяем ключевые патогены
        staph = next((s for s in data if s["name"] == "Золотистый стафилококк"), None)
        assert staph is not None, "Золотистый стафилококк должен присутствовать"
        assert staph["scientific_name"] == "Staphylococcus aureus"
        assert staph["type"] == "pathogen"
        assert staph["risk_level"] == "high", "Золотистый стафилококк должен иметь высокий риск"
        assert "токсин TSST-1" in staph["virulence_factors"]
        assert "контактный" in staph["transmission_method"]

        salmonella = next((s for s in data if s["name"] == "Сальмонелла"), None)
        assert salmonella is not None, "Сальмонелла должна присутствовать"
        assert salmonella["transmission_method"] == "пищевой, водный, контактный"

        # Проверяем, что все патогены имеют virulence_factors
        for pathogen in data:
            assert pathogen["virulence_factors"], f"Патоген {pathogen['name']} должен иметь virulence_factors"
            assert isinstance(pathogen["virulence_factors"], list), "virulence_factors должен быть списком"

    def _validate_pathogen_data_structure(self, item: Dict[str, Any]):
        """Валидация структуры данных патогена."""
        # Обязательные поля для патогенов
        required_fields = [
            "name",
            "scientific_name",
            "type",
            "interaction_type",
            "transmission_method",
            "virulence_factors",
            "geographic_distribution",
            "prevalence",
            "risk_level",
            "detection_confidence",
        ]

        for field in required_fields:
            assert field in item, f"Поле {field} отсутствует в патогенах"
            assert item[field] is not None, f"Поле {field} не может быть None в патогенах"

        # Специфические проверки для патогенов
        assert item["type"] in ["pathogen", "commensal"], "Тип должен быть pathogen или commensal"
        # interaction_type может варьироваться для разных типов
        assert isinstance(item["transmission_method"], str), "transmission_method должен быть строкой"
        assert isinstance(item["virulence_factors"], list), "virulence_factors должен быть списком"
        assert len(item["virulence_factors"]) > 0, "virulence_factors не должен быть пустым"

        # Патогены обычно имеют более высокий риск
        assert item["risk_level"] in ["medium", "high"], "Патогены должны иметь medium или high риск"

    @pytest.mark.asyncio
    async def test_data_consistency_across_methods(self, data_loader):
        """Тест консистентности данных между методами загрузки."""
        # Act
        microbiome = await data_loader.load_microbiome_data()
        plants = await data_loader.load_plant_symbionts()
        pathogens = await data_loader.load_pathogens()

        # Assert - проверяем уникальность имен
        all_names = set()
        for dataset_name, dataset in [("microbiome", microbiome), ("plants", plants), ("pathogens", pathogens)]:
            dataset_names = {item["name"] for item in dataset}
            assert len(dataset_names) == len(dataset), f"Дублирующиеся имена в {dataset_name}"
            assert not (all_names & dataset_names), f"Пересекающиеся имена между датасетами в {dataset_name}"
            all_names.update(dataset_names)

        # Assert - проверяем уникальность scientific names
        all_scientific = set()
        for dataset_name, dataset in [("microbiome", microbiome), ("plants", plants), ("pathogens", pathogens)]:
            dataset_scientific = {item["scientific_name"] for item in dataset}
            assert len(dataset_scientific) == len(dataset), f"Дублирующиеся scientific names в {dataset_name}"
            assert not (all_scientific & dataset_scientific), (
                f"Пересекающиеся scientific names между датасетами в {dataset_name}"
            )
            all_scientific.update(dataset_scientific)

    @pytest.mark.parametrize(
        "prevalence,risk_level,expected_valid",
        [
            (0.95, "low", True),  # Высокая распространенность, низкий риск - ок
            (0.1, "high", True),  # Низкая распространенность, высокий риск - ок
            (0.5, "medium", True),  # Средние значения - ок
            (1.5, "low", False),  # Превышение диапазона
            (-0.1, "low", False),  # Отрицательное значение
            (0.8, "unknown", False),  # Неизвестный уровень риска
        ],
    )
    def test_symbiont_data_validation_edge_cases(self, prevalence, risk_level, expected_valid):
        """Тест валидации данных с edge cases."""
        test_item = {
            "name": "Test Symbiont",
            "scientific_name": "Test scientificus",
            "type": "symbiont",
            "interaction_type": "mutualistic",
            "prevalence": prevalence,
            "risk_level": risk_level,
            "detection_confidence": 0.8,
        }

        if expected_valid:
            # Должен пройти валидацию без ошибок
            self._validate_symbiont_data_structure(test_item, "test")
        else:
            # Должен выбросить AssertionError
            with pytest.raises(AssertionError):
                self._validate_symbiont_data_structure(test_item, "test")

    @pytest.mark.asyncio
    async def test_biological_consistency_checks(self, data_loader):
        """Тест биологической консистентности данных."""
        # Act
        microbiome = await data_loader.load_microbiome_data()
        pathogens = await data_loader.load_pathogens()

        # Assert - симбионты микробиома должны иметь низкий риск
        microbiome_symbionts = [s for s in microbiome if s["type"] == "symbiont"]
        high_risk_microbiome = [s for s in microbiome_symbionts if s["risk_level"] == "high"]
        assert len(high_risk_microbiome) == 0, "Симбионты микробиома не должны иметь высокий риск"

        # Assert - патогены должны иметь virulence factors
        for pathogen in pathogens:
            assert len(pathogen["virulence_factors"]) > 0, (
                f"Патоген {pathogen['name']} должен иметь факторы вирулентности"
            )

        # Assert - симбионты должны иметь symbiotic benefits
        for symbiont in microbiome_symbionts:
            assert "symbiotic_benefits" in symbiont, f"Симбионт {symbiont['name']} должен иметь symbiotic_benefits"
            assert len(symbiont["symbiotic_benefits"]) > 0, (
                f"Симбионт {symbiont['name']} должен иметь непустые symbiotic_benefits"
            )

    @pytest.mark.asyncio
    async def test_data_quality_metrics(self, data_loader):
        """Тест метрик качества данных."""
        # Act
        microbiome = await data_loader.load_microbiome_data()
        plants = await data_loader.load_plant_symbionts()
        pathogens = await data_loader.load_pathogens()

        all_data = microbiome + plants + pathogens

        # Assert - высокая confidence для основных данных
        high_confidence_count = sum(1 for item in all_data if item["detection_confidence"] >= 0.8)
        assert high_confidence_count / len(all_data) >= 0.8, "Минимум 80% данных должны иметь высокую confidence"

        # Assert - разнообразие prevalence
        prevalence_values = [item["prevalence"] for item in all_data]
        prevalence_range = max(prevalence_values) - min(prevalence_values)
        assert prevalence_range >= 0.5, "Должен быть широкий диапазон распространенности"

        # Assert - сбалансированность risk levels
        risk_counts = {}
        for item in all_data:
            risk_counts[item["risk_level"]] = risk_counts.get(item["risk_level"], 0) + 1

        # Должны присутствовать все уровни риска
        assert len(risk_counts) >= 2, "Должно быть разнообразие уровней риска"
        # Low risk должен быть наиболее распространенным
        assert risk_counts.get("low", 0) >= risk_counts.get("high", 0), "Low risk должен быть наиболее распространенным"

    @pytest.mark.asyncio
    async def test_create_symbiont_hierarchy(self, data_loader, mock_symbiont_service):
        """Тест создания иерархической структуры симбионтов."""
        # Arrange
        mock_symbiont_service.create_symbiont.side_effect = lambda symbiont: setattr(symbiont, "id", str(uuid.uuid4()))

        # Act
        await data_loader.create_symbiont_hierarchy()

        # Assert
        # Проверяем, что созданы родительские категории
        assert mock_symbiont_service.create_symbiont.call_count >= 3  # Минимум 3 родительские категории

        # Проверяем вызовы для родительских категорий
        parent_calls = mock_symbiont_service.create_symbiont.call_args_list[:3]
        parent_names = ["Микробиом человека", "Симбионты растений", "Патогены"]

        for i, call in enumerate(parent_calls):
            symbiont = call[0][0]
            assert symbiont.name in parent_names
            assert symbiont.detection_confidence == 1.0

        # Проверяем, что созданы дочерние объекты
        # Всего должно быть создано: 3 родителя + (4 микробиома + 3 растения + 3 патогена) = 13 объектов
        assert mock_symbiont_service.create_symbiont.call_count >= 13

    @pytest.mark.asyncio
    async def test_create_symbiont_hierarchy_with_uuid_generation(self, data_loader, mock_symbiont_service):
        """Тест, что при создании иерархии генерируются уникальные UUID."""
        # Arrange
        created_ids = set()

        def mock_create_with_id_tracking(symbiont):
            symbiont.id = str(uuid.uuid4())
            created_ids.add(symbiont.id)
            return symbiont.id

        mock_symbiont_service.create_symbiont.side_effect = mock_create_with_id_tracking

        # Act
        await data_loader.create_symbiont_hierarchy()

        # Assert
        # Все созданные ID должны быть уникальными
        assert len(created_ids) == mock_symbiont_service.create_symbiont.call_count
        # Все ID должны быть валидными UUID
        for symbiont_id in created_ids:
            uuid.UUID(symbiont_id)  # Должно не выбрасывать исключение

    @pytest.mark.asyncio
    async def test_load_from_external_sources(self, data_loader, mock_symbiont_service):
        """Тест загрузки данных из внешних источников."""
        # Act
        await data_loader.load_from_external_sources()

        # Assert
        # Проверяем, что созданы симбионты из внешних источников
        assert mock_symbiont_service.create_symbiont.call_count > 0

        # Проверяем структуру созданных симбионтов
        call_args = mock_symbiont_service.create_symbiont.call_args_list[0][0][0]
        assert hasattr(call_args, "name")
        assert hasattr(call_args, "scientific_name")
        assert hasattr(call_args, "type")
        assert call_args.type == "symbiont"  # Все внешние источники - симбионты

    @pytest.mark.asyncio
    async def test_run_full_loading_process(self, data_loader, mock_symbiont_service):
        """Тест полного процесса загрузки данных."""
        # Act
        await data_loader.run()

        # Assert
        # Проверяем, что вызваны все этапы загрузки
        # 1. create_symbiont_hierarchy должна быть вызвана
        # 2. load_from_external_sources должна быть вызвана

        # Проверяем, что создано достаточное количество симбионтов
        # Минимум: 3 родителя + 4 микробиома + 3 растения + 3 патогена + внешние источники
        assert mock_symbiont_service.create_symbiont.call_count >= 13

    @pytest.mark.asyncio
    async def test_run_handles_exceptions(self, data_loader, mock_symbiont_service):
        """Тест обработки исключений в процессе загрузки."""
        # Arrange
        mock_symbiont_service.create_symbiont.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            await data_loader.run()

    def test_data_loader_initialization(self, mock_weaviate_storage):
        """Тест инициализации SymbiontsDataLoader."""
        # Act
        with patch("scripts.load_symbionts_data.WeaviateStorage", return_value=mock_weaviate_storage):
            loader = SymbiontsDataLoader()

            # Assert
            assert hasattr(loader, "weaviate_storage")
            assert hasattr(loader, "symbiont_service")
            assert isinstance(loader.symbiont_service, SymbiontService)

    @pytest.mark.asyncio
    async def test_load_microbiome_data_structure_validation(self, data_loader):
        """Тест валидации структуры данных микробиома."""
        # Act
        data = await data_loader.load_microbiome_data()

        # Assert - проверяем все обязательные поля для каждого элемента
        for item in data:
            assert "name" in item and item["name"]
            assert "type" in item
            assert "interaction_type" in item
            assert "prevalence" in item and isinstance(item["prevalence"], (int, float))
            assert "risk_level" in item
            assert "detection_confidence" in item and isinstance(item["detection_confidence"], (int, float))

            # Проверяем диапазоны значений
            assert 0.0 <= item["prevalence"] <= 1.0
            assert 0.0 <= item["detection_confidence"] <= 1.0
            assert item["risk_level"] in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_load_plant_symbionts_structure_validation(self, data_loader):
        """Тест валидации структуры данных симбионтов растений."""
        # Act
        data = await data_loader.load_plant_symbionts()

        # Assert
        for item in data:
            assert "name" in item and item["name"]
            assert "scientific_name" in item
            assert "type" in item and item["type"] == "symbiont"
            # organism_ecological_role есть только у некоторых растений (микориза и клубеньковые)
            if item["name"] in ["Микориза", "Клубеньковые бактерии"]:
                assert "organism_ecological_role" in item
            assert "prevalence" in item
            assert "risk_level" in item

    @pytest.mark.asyncio
    async def test_load_pathogens_structure_validation(self, data_loader):
        """Тест валидации структуры данных патогенов."""
        # Act
        data = await data_loader.load_pathogens()

        # Assert
        for item in data:
            assert "name" in item and item["name"]
            assert "scientific_name" in item
            assert "type" in item and item["type"] in ["pathogen", "commensal"]
            assert "transmission_method" in item
            assert "virulence_factors" in item and isinstance(item["virulence_factors"], list)
            assert "geographic_distribution" in item
            assert item["risk_level"] in ["low", "medium", "high"]
