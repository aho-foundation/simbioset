"""Тесты для API артефактов."""

import pytest
from api.projects.artifacts_service import ArtifactsService


class TestArtifactsService:
    """Тесты для сервиса артефактов."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.service = ArtifactsService()

    def test_format_conversation_for_prompt(self):
        """Тест форматирования диалога для промпта."""
        from api.projects.artifacts_service import format_conversation_for_prompt

        messages = [
            {"role": "user", "content": "Привет, как дела?"},
            {"role": "assistant", "content": "Отлично! Чем могу помочь?"},
            {"role": "user", "content": "Расскажи про экосистемы"},
        ]

        result = format_conversation_for_prompt(messages)

        assert "[1] Пользователь: Привет, как дела?" in result
        assert "[2] Ассистент: Отлично! Чем могу помочь?" in result
        assert "[3] Пользователь: Расскажи про экосистемы" in result

    @pytest.mark.asyncio
    async def test_extract_artifacts_from_conversation_fallback(self):
        """Тест извлечения артефактов с fallback функцией."""
        conversation_messages = [
            {"role": "user", "content": "Нужно создать систему анализа симбиоза в экосистемах"},
            {"role": "assistant", "content": "Отличная идея! Давайте обсудим требования."},
            {"role": "user", "content": "Нужен ИИ для классификации организмов"},
        ]

        # Отключаем LLM для тестирования fallback
        self.service._llm_available = False

        result = await self.service.extract_artifacts_from_conversation(conversation_messages, "test_session")

        assert isinstance(result, dict)
        assert "artifacts" in result
        assert "summary" in result
        assert isinstance(result["artifacts"], list)
        assert isinstance(result["summary"], dict)

    @pytest.mark.asyncio
    async def test_convert_artifacts_to_projects_fallback(self):
        """Тест преобразования артефактов в проекты с fallback."""
        artifacts = [
            {
                "id": "artifact_1",
                "type": "idea",
                "content": "Создать систему анализа симбиоза",
                "original_text": "Нужно создать систему анализа симбиоза",
                "confidence": 0.9,
                "tags": ["симбиоз", "анализ"],
                "rationale": "Полезно для проекта Simbioset",
            }
        ]

        # Отключаем LLM для тестирования fallback
        self.service._llm_available = False

        result = await self.service.convert_artifacts_to_projects(artifacts)

        assert isinstance(result, dict)
        assert "projects" in result
        assert "summary" in result
        assert isinstance(result["projects"], list)
        assert isinstance(result["summary"], dict)

    @pytest.mark.asyncio
    async def test_analyze_conversation_quality(self):
        """Тест анализа качества диалога."""
        conversation_messages = [
            {"role": "user", "content": "Короткое сообщение"},
            {"role": "assistant", "content": "Это более длинное сообщение с дополнительной информацией"},
            {"role": "user", "content": "Еще одно сообщение пользователя"},
        ]

        # Отключаем LLM для тестирования базовых метрик
        self.service._llm_available = False

        result = await self.service.analyze_conversation_quality(conversation_messages)

        assert isinstance(result, dict)
        assert "total_messages" in result
        assert "user_messages" in result
        assert "assistant_messages" in result
        assert "avg_message_length" in result
        assert "engagement_ratio" in result
        assert result["total_messages"] == 3
        assert result["user_messages"] == 2
        assert result["assistant_messages"] == 1

    def test_validate_project_structure(self):
        """Тест валидации структуры проекта."""
        from api.projects.artifacts_service import validate_project_structure

        # Корректный проект
        valid_project = {
            "id": "project_001",
            "type": "crowdsourced",
            "title": "Тестовый проект",
            "description": "Описание проекта",
            "status": "draft",
            "priority": "high",
            "estimated_duration": "3 месяца",
            "estimated_budget": 50000,
            "tags": ["тест"],
            "objectives": ["Цель 1"],
            "tasks": [],
            "resources_needed": [],
            "success_metrics": ["Метрика 1"],
            "source_artifacts": [],
            "rationale": "Обоснование",
        }

        assert validate_project_structure(valid_project)

        # Некорректный проект (отсутствует обязательное поле)
        invalid_project = valid_project.copy()
        del invalid_project["title"]

        assert not validate_project_structure(invalid_project)

    def test_merge_similar_projects(self):
        """Тест объединения похожих проектов."""
        from api.projects.artifacts_service import merge_similar_projects

        projects = [
            {
                "id": "project_1",
                "title": "Проект 1",
                "tags": ["симбиоз", "экосистемы"],
                "objectives": ["Цель 1"],
                "tasks": [{"id": "task_1", "title": "Задача 1"}],
                "source_artifacts": ["artifact_1"],
                "estimated_budget": 10000,
            },
            {
                "id": "project_2",
                "title": "Проект 2",
                "tags": ["симбиоз", "анализ"],
                "objectives": ["Цель 2"],
                "tasks": [{"id": "task_2", "title": "Задача 2"}],
                "source_artifacts": ["artifact_2"],
                "estimated_budget": 20000,
            },
        ]

        merged = merge_similar_projects(projects)

        # Проверяем, что похожие проекты объединены
        # (в данном случае они имеют общий тег "симбиоз")
        assert len(merged) <= len(projects)

        # Проверяем, что бюджет объединен
        total_budget = sum(p["estimated_budget"] for p in projects)
        merged_budget = sum(p["estimated_budget"] for p in merged)
        assert merged_budget >= total_budget  # Может быть больше из-за объединения
