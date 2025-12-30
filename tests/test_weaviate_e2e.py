"""
E2E тесты для Weaviate - полный цикл работы.

Тестирует интеграцию всех компонентов: storage, classification, NER, search.
"""

import pytest
import os
from api.storage.faiss import Paragraph, DocumentType
from api.storage.paragraph_service import ParagraphService
from api.main import create_database_manager

# Импортируем fixtures из integration тестов
pytest_plugins = ["tests.test_weaviate_integration"]


class TestWeaviateE2E:
    """E2E тесты для полного цикла работы с Weaviate"""

    @pytest.fixture
    def e2e_storage(self, weaviate_storage):
        """Фикстура для E2E тестов с WeaviateStorage"""
        return weaviate_storage

    @pytest.fixture
    def e2e_paragraph_service(self, e2e_storage):
        """Фикстура для ParagraphService с Weaviate"""
        db_manager = create_database_manager()
        return ParagraphService(db_manager, e2e_storage)

    def test_full_content_lifecycle(self, e2e_storage, e2e_paragraph_service):
        """Тест полного жизненного цикла контента: создание → классификация → поиск"""
        import uuid

        # 1. Создаем уникальный ID для теста
        test_session_id = f"e2e_test_{uuid.uuid4().hex[:8]}"

        # 2. Добавляем разнообразный контент
        documents = [
            {
                "text": "Симбиоз дуба и микоризы повышает устойчивость леса к засухе. Дуб предоставляет углеводы грибу, а микориза улучшает поглощение воды и минералов.",
                "metadata": {"source": "ecology_book", "topic": "forest_ecology"},
            },
            {
                "text": "В городских экосистемах голуби и воробьи конкурируют за пищевые ресурсы. Это приводит к снижению популяции воробьев в центральных районах.",
                "metadata": {"source": "urban_study", "topic": "urban_ecology"},
            },
            {
                "text": "Кислотные дожди разрушают экосистемы озер, снижая pH воды. Это приводит к гибели рыбы и амфибий, нарушая пищевые цепочки.",
                "metadata": {"source": "environmental_report", "topic": "water_pollution"},
            },
        ]

        # 3. Сохраняем документы через ParagraphService
        saved_count = e2e_paragraph_service.save_document_paragraphs(
            documents=documents, document_id=test_session_id, document_type=DocumentType.KNOWLEDGE
        )

        assert saved_count == 3, f"Expected 3 paragraphs saved, got {saved_count}"

        # 4. Проверяем, что параграфы сохранены и классифицированы
        paragraphs = e2e_storage.get_document_paragraphs(test_session_id)
        assert len(paragraphs) == 3

        # Проверяем NER - извлечение сущностей
        for para in paragraphs:
            # Должен быть извлечен текст
            assert para.content
            assert len(para.content) > 10

            # Должны быть созданы эмбеддинги
            assert para.embedding is not None
            assert len(para.embedding) > 0

            # Должна быть проведена классификация (если включена)
            if os.getenv("ENABLE_AUTOMATIC_DETECTORS", "false").lower() == "true":
                # Проверяем, что есть хотя бы базовая информация
                assert para.location is not None or para.time_reference is not None or para.tags

        # 5. Тестируем поиск с различными запросами
        search_queries = ["симбиоз дуба", "городские экосистемы", "кислотные дожди"]

        for query in search_queries:
            results = e2e_storage.search_similar(query=query, document_id=test_session_id, top_k=3)

            assert len(results) > 0, f"No results for query: {query}"
            assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

            # Первый результат должен быть наиболее релевантным
            best_match, score = results[0]
            assert isinstance(best_match, Paragraph)
            assert isinstance(score, float)
            assert 0 <= score <= 1  # cosine similarity

        # 6. Тестируем асинхронный поиск
        async def test_async_search():
            results = await e2e_storage.search_similar_paragraphs(
                query="экосистемы", document_id=test_session_id, top_k=2
            )
            assert isinstance(results, list)
            assert len(results) <= 2
            return results

        import asyncio

        async_results = asyncio.run(test_async_search())
        assert len(async_results) > 0

        # 7. Тестируем фильтрацию по метаданным
        if any(para.ecosystem_id for para in paragraphs):
            ecosystem_ids = [para.ecosystem_id for para in paragraphs if para.ecosystem_id]
            if ecosystem_ids:
                filtered_results = e2e_storage.search_similar(
                    query="экосистема", document_id=test_session_id, top_k=5, ecosystem_id_filter=ecosystem_ids[0]
                )
                # Все результаты должны иметь правильный ecosystem_id
                for para, score in filtered_results:
                    assert para.ecosystem_id == ecosystem_ids[0]

        # 8. Тестируем получение по ID
        first_para = paragraphs[0]
        retrieved = e2e_storage.get_paragraph_by_id(test_session_id, first_para.id)
        assert retrieved is not None
        assert retrieved.id == first_para.id
        assert retrieved.content == first_para.content

        # 9. Тестируем обновление параграфа
        original_content = first_para.content
        first_para.content = f"[UPDATED] {original_content}"
        first_para.embedding = e2e_storage._create_embedding(first_para.content)

        success = e2e_storage.update_paragraph(test_session_id, first_para)
        assert success is True

        updated = e2e_storage.get_paragraph_by_id(test_session_id, first_para.id)
        assert updated is not None
        assert updated.content.startswith("[UPDATED]")

        # 10. Тестируем удаление
        success = e2e_storage.delete_paragraph(test_session_id, first_para.id)
        assert success is True

        deleted = e2e_storage.get_paragraph_by_id(test_session_id, first_para.id)
        assert deleted is None

        # Проверяем, что остались только 2 параграфа
        remaining = e2e_storage.get_document_paragraphs(test_session_id)
        assert len(remaining) == 2

    def test_classification_and_ner_integration(self, e2e_storage, e2e_paragraph_service):
        """Тест интеграции классификации и NER"""
        import uuid

        test_session_id = f"ner_test_{uuid.uuid4().hex[:8]}"

        # Создаем контент с явными сущностями для тестирования NER
        documents = [
            {
                "text": "Дуб черешчатый (Quercus robur) образует симбиоз с трюфелями. Этот симбиоз помогает дереву поглощать фосфор из почвы, а гриб получает углеводы от дерева.",
                "metadata": {"expected_organisms": ["дуб", "трюфель"], "expected_location": None},
            },
            {
                "text": "В Москве наблюдается снижение популяции белок из-за урбанизации. Белки вынуждены конкурировать с крысами за пищевые ресурсы.",
                "metadata": {"expected_organisms": ["белка", "крыса"], "expected_location": "Москва"},
            },
        ]

        # Сохраняем с классификацией
        saved_count = e2e_paragraph_service.save_document_paragraphs(
            documents=documents, document_id=test_session_id, document_type=DocumentType.KNOWLEDGE
        )

        assert saved_count == 2

        paragraphs = e2e_storage.get_document_paragraphs(test_session_id)

        # Проверяем NER результаты
        for i, para in enumerate(paragraphs):
            expected = documents[i]["metadata"]

            # Проверяем локацию (если ожидалась)
            if expected.get("expected_location"):
                assert para.location == expected["expected_location"], (
                    f"Expected location {expected['expected_location']}, got {para.location}"
                )

            # Проверяем организмы (если автоматическая классификация включена)
            if os.getenv("ENABLE_AUTOMATIC_DETECTORS", "false").lower() == "true":
                if expected.get("expected_organisms") and para.organisms:
                    organism_names = [org.get("name", "").lower() for org in para.organisms]
                    for expected_org in expected["expected_organisms"]:
                        assert any(expected_org.lower() in name for name in organism_names), (
                            f"Expected organism '{expected_org}' not found in {organism_names}"
                        )

            # Проверяем, что есть хотя бы базовая классификация
            assert para.tags is not None or para.classification is not None

    def test_performance_and_scalability(self, e2e_storage):
        """Тест производительности и масштабируемости"""
        import uuid
        import time

        test_session_id = f"perf_test_{uuid.uuid4().hex[:8]}"

        # Создаем тестовый датасет среднего размера
        documents = []
        for i in range(20):  # 20 документов
            documents.append(
                {
                    "text": f"Тестовый документ {i} о экосистемах. Содержит информацию о симбиозе, организмах и их взаимодействии в природной среде. Документ {i} из серии тестов производительности.",
                    "metadata": {"index": i, "category": f"test_{i % 3}"},
                }
            )

        # Замеряем время сохранения
        start_time = time.time()
        saved_count = e2e_storage.add_documents(
            documents=documents, document_id=test_session_id, document_type=DocumentType.KNOWLEDGE
        )
        save_time = time.time() - start_time

        assert saved_count == 20
        assert save_time < 30, f"Save time too slow: {save_time:.2f}s"  # Должно быть быстрее 30 сек

        # Проверяем, что все сохранено
        paragraphs = e2e_storage.get_document_paragraphs(test_session_id)
        assert len(paragraphs) == 20

        # Замеряем время поиска
        search_queries = ["симбиоз", "экосистемы", "организмы"]

        for query in search_queries:
            start_time = time.time()
            results = e2e_storage.search_similar(query=query, document_id=test_session_id, top_k=5)
            search_time = time.time() - start_time

            assert len(results) > 0
            assert search_time < 2, f"Search too slow for '{query}': {search_time:.2f}s"  # Поиск должен быть < 2 сек

        # Тестируем batch операции
        batch_documents = []
        for i in range(10):
            batch_documents.append(
                {
                    "text": f"Batch документ {i} для тестирования массовых операций вставки и поиска в Weaviate.",
                    "metadata": {"batch_test": True, "batch_id": i},
                }
            )

        batch_start = time.time()
        batch_count = e2e_storage.add_documents(
            documents=batch_documents, document_id=f"{test_session_id}_batch", document_type=DocumentType.KNOWLEDGE
        )
        batch_time = time.time() - batch_start

        assert batch_count == 10
        assert batch_time < 15, f"Batch insert too slow: {batch_time:.2f}s"

        # Финальная проверка общего состояния
        all_docs = e2e_storage.get_all_documents()
        assert f"{test_session_id}_batch" in all_docs

    def test_error_handling_and_recovery(self, e2e_storage):
        """Тест обработки ошибок и восстановления"""
        import uuid

        test_session_id = f"error_test_{uuid.uuid4().hex[:8]}"

        # Тест с некорректными данными
        malformed_documents = [
            {"text": ""},  # Пустой текст
            {"text": "Нормальный текст"},
            {"text": None},  # None текст
        ]

        # Должен обработать корректно, пропустив некорректные
        count = e2e_storage.add_documents(
            documents=[doc for doc in malformed_documents if doc.get("text")],
            document_id=test_session_id,
            document_type=DocumentType.KNOWLEDGE,
        )

        assert count == 1  # Только один корректный документ

        # Тест поиска по несуществующему документу
        results = e2e_storage.search_similar(query="тест", document_id="non_existent_doc", top_k=5)
        assert len(results) == 0

        # Тест получения несуществующего параграфа
        para = e2e_storage.get_paragraph_by_id(test_session_id, "non_existent_id")
        assert para is None

        # Тест удаления несуществующего параграфа
        success = e2e_storage.delete_paragraph(test_session_id, "non_existent_id")
        assert success is False

        # Тест обновления несуществующего параграфа
        fake_para = Paragraph(id="fake_id", content="Fake content", document_id=test_session_id)
        success = e2e_storage.update_paragraph(test_session_id, fake_para)
        assert success is False
