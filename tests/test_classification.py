"""
Тесты классификации и проверки достоверности параграфов
"""

import pytest
from unittest.mock import patch

from api.storage.faiss import FAISSStorage, Paragraph, ClassificationType, FactCheckResult


class TestClassificationAndFactChecking:
    """Тесты классификации и проверки достоверности"""

    def setup_method(self):
        """Настройка тестов"""
        self.search_engine = FAISSStorage()

    @patch("api.detect.rolestate.classify_message_type")
    @patch("api.detect.factcheck.check_factuality")
    @patch("api.detect.localize.extract_location_and_time")
    def test_classify_paragraph(self, mock_localize, mock_factcheck, mock_rolestate):
        """Тест классификации параграфа"""
        # Настраиваем моки
        mock_rolestate.return_value = "ecosystem_risk"
        mock_factcheck.return_value = {"status": "true", "details": {"confidence": 0.9}}
        mock_localize.return_value = {"location": "Москва", "time_reference": "2023 год"}

        paragraph = Paragraph(id="test_classify", content="Существует риск в системе безопасности")

        # Классифицируем параграф
        classified_paragraph = self.search_engine._classify_paragraph(paragraph)

        # Проверяем, что поля классификации установлены
        assert classified_paragraph.classification == ClassificationType.ECOSYSTEM_RISK
        assert classified_paragraph.fact_check_result == FactCheckResult.TRUE
        assert classified_paragraph.fact_check_details == {"confidence": 0.9}
        assert classified_paragraph.location == "Москва"
        assert classified_paragraph.time_reference == "2023 год"

    @patch("api.detect.rolestate.classify_message_type")
    @patch("api.detect.factcheck.check_factuality")
    @patch("api.detect.localize.extract_location_and_time")
    def test_add_documents_with_classification(self, mock_localize, mock_factcheck, mock_rolestate):
        """Тест добавления документов с классификацией"""
        # Настраиваем моки
        mock_rolestate.return_value = "suggested_ecosystem_solution"
        mock_factcheck.return_value = {"status": "partial", "details": {"confidence": 0.7}}
        mock_localize.return_value = {"location": "СПб", "time_reference": "2024 год"}

        documents = [{"text": "Предлагаемое решение проблемы"}]

        count = self.search_engine.add_documents(documents, document_id="classify_test", classify=True)

        assert count == 1
        paragraphs = self.search_engine.get_document_paragraphs("classify_test")
        assert len(paragraphs) == 1

        classified_para = paragraphs[0]
        assert classified_para.classification == ClassificationType.ECOSYSTEM_SOLUTION
        assert classified_para.fact_check_result == FactCheckResult.PARTIAL
        assert classified_para.location == "СПб"
        assert classified_para.time_reference == "2024 год"

    def test_add_documents_without_classification(self):
        """Тест добавления документов без классификации"""
        documents = [{"text": "Текст без классификации"}]

        count = self.search_engine.add_documents(documents, document_id="no_classify_test", classify=False)

        assert count == 1
        paragraphs = self.search_engine.get_document_paragraphs("no_classify_test")
        assert len(paragraphs) == 1

        para = paragraphs[0]
        # Проверяем, что поля классификации не установлены
        assert para.classification is None
        assert para.fact_check_result is None
        assert para.location is None
        assert para.time_reference is None

    @patch("api.detect.rolestate.classify_message_type")
    @patch("api.detect.factcheck.check_factuality")
    @patch("api.detect.localize.extract_location_and_time")
    def test_reclassify_paragraph(self, mock_localize, mock_factcheck, mock_rolestate):
        """Тест переклассификации параграфа"""
        # Настраиваем моки
        mock_rolestate.return_value = "ecosystem_vulnerability"
        mock_factcheck.return_value = {"status": "false", "details": {"confidence": 0.8}}
        mock_localize.return_value = {"location": "Новосибирск", "time_reference": "2025 год"}

        # Добавляем параграф
        documents = [{"text": "Тестовый параграф для переклассификации"}]
        self.search_engine.add_documents(documents, document_id="reclassify_test")

        paragraphs = self.search_engine.get_document_paragraphs("reclassify_test")
        assert len(paragraphs) == 1
        original_para_id = paragraphs[0].id

        # Переклассифицируем параграф
        success = self.search_engine.reclassify_paragraph("reclassify_test", original_para_id)
        assert success is True

        # Проверяем обновленную классификацию
        updated_para = self.search_engine.get_paragraph_by_id("reclassify_test", original_para_id)
        assert updated_para.classification == ClassificationType.ECOSYSTEM_VULNERABILITY
        assert updated_para.fact_check_result == FactCheckResult.FALSE
        assert updated_para.location == "Новосибирск"
        assert updated_para.time_reference == "2025 год"

    @patch("api.detect.rolestate.classify_message_type")
    @patch("api.detect.factcheck.check_factuality")
    @patch("api.detect.localize.extract_location_and_time")
    def test_reclassify_document(self, mock_localize, mock_factcheck, mock_rolestate):
        """Тест переклассификации всех параграфов в документе"""
        # Настраиваем моки
        mock_rolestate.return_value = "neutral"
        mock_factcheck.return_value = {"status": "unknown", "details": {"confidence": 0.5}}
        mock_localize.return_value = {"location": "Казань", "time_reference": "2026 год"}

        # Добавляем несколько параграфов
        documents = [{"text": "Параграф 1"}, {"text": "Параграф 2"}, {"text": "Параграф 3"}]
        self.search_engine.add_documents(documents, document_id="reclassify_doc_test")

        # Переклассифицируем весь документ
        updated_count = self.search_engine.reclassify_document("reclassify_doc_test")
        assert updated_count == 3  # Все 3 параграфа должны быть обновлены

        # Проверяем, что все параграфы обновлены
        paragraphs = self.search_engine.get_document_paragraphs("reclassify_doc_test")
        for para in paragraphs:
            assert para.classification == ClassificationType.NEUTRAL
            assert para.fact_check_result == FactCheckResult.UNKNOWN
            assert para.location == "Казань"
            assert para.time_reference == "2026 год"

    def test_get_paragraphs_by_classification(self):
        """Тест получения параграфов по типу классификации"""
        # Создаем параграфы с разными классификациями
        para1 = Paragraph(id="risk1", content="Риск безопасности", classification=ClassificationType.ECOSYSTEM_RISK)
        para2 = Paragraph(
            id="solution1", content="Решение безопасности", classification=ClassificationType.ECOSYSTEM_SOLUTION
        )
        para3 = Paragraph(id="risk2", content="Другой риск", classification=ClassificationType.ECOSYSTEM_RISK)

        # Добавляем параграфы вручную
        doc_id = "classification_filter_test"
        self.search_engine.document_paragraphs[doc_id] = [para1, para2, para3]

        # Получаем параграфы с классификацией ECOSYSTEM_RISK
        risk_paragraphs = self.search_engine.get_paragraphs_by_classification(doc_id, ClassificationType.ECOSYSTEM_RISK)

        assert len(risk_paragraphs) == 2
        assert all(p.classification == ClassificationType.ECOSYSTEM_RISK for p in risk_paragraphs)
        assert {p.id for p in risk_paragraphs} == {"risk1", "risk2"}

    def test_get_paragraphs_by_fact_check_result(self):
        """Тест получения параграфов по результату проверки достоверности"""
        # Создаем параграфы с разными результатами проверки достоверности
        para1 = Paragraph(id="true1", content="Правдивое утверждение", fact_check_result=FactCheckResult.TRUE)
        para2 = Paragraph(id="false1", content="Ложное утверждение", fact_check_result=FactCheckResult.FALSE)
        para3 = Paragraph(id="true2", content="Еще одно правдивое утверждение", fact_check_result=FactCheckResult.TRUE)

        # Добавляем параграфы вручную
        doc_id = "fact_check_filter_test"
        self.search_engine.document_paragraphs[doc_id] = [para1, para2, para3]

        # Получаем параграфы с результатом проверки TRUE
        true_paragraphs = self.search_engine.get_paragraphs_by_fact_check_result(doc_id, FactCheckResult.TRUE)

        assert len(true_paragraphs) == 2
        assert all(p.fact_check_result == FactCheckResult.TRUE for p in true_paragraphs)
        assert {p.id for p in true_paragraphs} == {"true1", "true2"}
