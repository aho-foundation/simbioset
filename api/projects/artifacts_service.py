"""Сервис для работы с артефактами и их преобразованием в проекты."""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from api.logger import root_logger
from api.llm import call_llm
from .artifacts import artifacts_manager
from api.projects.service import ProjectsService
from api.projects.repository import ProjectsRepository

log = root_logger.debug


def load_prompt_from_file(filename: str) -> str:
    """Загружает промпт из .txt файла."""
    try:
        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        filepath = os.path.join(prompts_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log(f"Prompt file not found: {filename}")
        return ""
    except Exception as e:
        log(f"Error loading prompt {filename}: {e}")
        return ""


def format_conversation_for_prompt(messages: List[Dict[str, Any]]) -> str:
    """
    Форматирует сообщения диалога для передачи в промпт.

    Args:
        messages: Список сообщений с полями role, content, etc.

    Returns:
        Отформатированный текст диалога
    """
    formatted_lines = []

    for i, message in enumerate(messages):
        role = message.get("role", "unknown")
        content = message.get("content", "")

        # Форматируем роль
        role_display = {"user": "Пользователь", "assistant": "Ассистент", "system": "Система"}.get(role, role.title())

        formatted_lines.append(f"[{i + 1}] {role_display}: {content}")

    return "\n\n".join(formatted_lines)


def extract_artifacts_from_dialog_stub(conversation_text: str) -> Dict[str, Any]:
    """
    Заглушка для извлечения артефактов из диалога (fallback функция).
    """
    return {
        "artifacts": [],
        "summary": {"total_artifacts": 0, "main_themes": [], "project_potential": "unknown", "recommendations": []},
    }


def convert_artifacts_to_projects_stub(artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Заглушка для преобразования артефактов в проекты (fallback функция).
    """
    return {
        "projects": [],
        "summary": {
            "total_projects": 0,
            "project_types": {"crowdsourced": 0, "crowdfunded": 0, "internal": 0},
            "total_estimated_budget": 0,
            "risks_assessment": "unknown",
            "recommendations": [],
        },
    }


def extract_potential_artifacts_from_message(
    message_content: str, message_id: str, confidence_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Анализирует сообщение и извлекает потенциальные артефакты.

    Args:
        message_content: Текст сообщения
        message_id: ID сообщения
        confidence_threshold: Минимальная уверенность для предложения

    Returns:
        Список потенциальных артефактов
    """
    potential_artifacts = []

    # Простые правила для поиска потенциальных артефактов
    # Можно расширить с помощью LLM в будущем

    # Ищем предложения, которые выглядят как идеи проектов
    import re

    # Паттерны для поиска идей проектов
    project_patterns = [
        r"(?:создать|разработать|реализовать|сделать|запустить)\s+([^.!?]+)",
        r"(?:проект|идея|инициатива)\s*:\s*([^.!?]+)",
        r"(?:предлагаю|хотелось бы|нужно)\s+([^.!?]+)",
        r"(?:платформа|приложение|сервис|система)\s+(?:для|по)\s+([^.!?]+)",
    ]

    sentences = re.split(r"[.!?]+", message_content)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:  # Пропускаем слишком короткие предложения
            continue

        confidence = 0.0
        artifact_type = "note"

        # Проверяем на соответствие паттернам
        for pattern in project_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                confidence = 0.8
                artifact_type = "project_idea"
                break

        # Дополнительные проверки для повышения уверенности
        if any(word in sentence.lower() for word in ["экосистема", "биосфера", "экология", "проект", "инициатива"]):
            confidence = min(confidence + 0.2, 1.0)

        # Проверяем на наличие конкретных деталей
        if re.search(r"\d+", sentence):  # Цифры
            confidence = min(confidence + 0.1, 1.0)
        if len(sentence.split()) > 10:  # Длинное предложение
            confidence = min(confidence + 0.1, 1.0)

        # Если уверенность выше порога, добавляем как потенциальный артефакт
        if confidence >= confidence_threshold:
            potential_artifacts.append(
                {
                    "selected_text": sentence,
                    "content": sentence,
                    "type": artifact_type,
                    "confidence": confidence,
                    "message_id": message_id,
                }
            )

    return potential_artifacts


async def suggest_artifacts_from_messages(session_id: str, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Анализирует сообщения диалога и предлагает артефакты автоматически.

    Args:
        session_id: ID сессии
        messages: Список сообщений для анализа

    Returns:
        Список предложенных артефактов
    """
    suggested_artifacts = []

    # Анализируем последние сообщения (не более 10)
    recent_messages = messages[-10:] if len(messages) > 10 else messages

    for message in recent_messages:
        if message.get("role") != "assistant":  # Анализируем только ответы ассистента
            continue

        content = message.get("content", "")
        message_id = message.get("id", str(hash(content)))  # Используем hash если нет ID

        # Извлекаем потенциальные артефакты из сообщения
        potential_artifacts = extract_potential_artifacts_from_message(content, message_id)

        for artifact in potential_artifacts:
            suggested_artifacts.append(artifact)

    return suggested_artifacts


def validate_project_structure(project_data: Dict[str, Any]) -> bool:
    """
    Проверяет корректность структуры проекта.

    Args:
        project_data: Данные проекта для валидации

    Returns:
        True если структура корректна
    """
    required_fields = [
        "id",
        "type",
        "title",
        "description",
        "status",
        "priority",
        "estimated_duration",
        "estimated_budget",
        "tags",
        "objectives",
        "tasks",
        "resources_needed",
        "success_metrics",
        "source_artifacts",
        "rationale",
    ]

    # Проверяем наличие обязательных полей
    for field in required_fields:
        if field not in project_data:
            return False

    # Проверяем тип проекта
    if project_data["type"] not in ["crowdsourced", "crowdfunded", "internal"]:
        return False

    # Проверяем приоритет
    if project_data["priority"] not in ["high", "medium", "low"]:
        return False

    # Проверяем статус
    if project_data["status"] not in ["draft", "active", "completed", "archived", "failed"]:
        return False

    return True


def merge_similar_projects(projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Объединяет похожие проекты для избежания дублирования.

    Args:
        projects: Список проектов для анализа

    Returns:
        Список объединенных проектов
    """
    # Простая логика объединения по тегам и темам
    merged = []
    processed_ids = set()

    for project in projects:
        if project["id"] in processed_ids:
            continue

        similar_projects = [
            p
            for p in projects
            if p["id"] != project["id"]
            and set(p.get("tags", [])) & set(project.get("tags", []))
            and p["id"] not in processed_ids
        ]

        if similar_projects:
            # Объединяем похожие проекты
            merged_project = project.copy()
            merged_project["objectives"].extend([obj for p in similar_projects for obj in p.get("objectives", [])])
            merged_project["tasks"].extend([task for p in similar_projects for task in p.get("tasks", [])])
            merged_project["source_artifacts"].extend(
                [aid for p in similar_projects for aid in p.get("source_artifacts", [])]
            )

            # Обновляем бюджет и продолжительность
            merged_project["estimated_budget"] += sum(p.get("estimated_budget", 0) for p in similar_projects)

            merged.append(merged_project)

            # Помечаем как обработанные
            processed_ids.update([p["id"] for p in similar_projects])
        else:
            merged.append(project)

        processed_ids.add(project["id"])

    return merged


class ArtifactsService:
    """Сервис для обработки артефактов и создания проектов."""

    def __init__(self):
        """Инициализация сервиса."""
        self._llm_available = True
        try:
            # Проверяем доступность LLM API
            import api.llm
        except ImportError:
            self._llm_available = False
            log("LLM API недоступен, будет использоваться заглушка")

        # Инициализируем сервис проектов
        self._projects_service = ProjectsService(ProjectsRepository())

    async def extract_artifacts_from_conversation(
        self, conversation_messages: List[Dict[str, Any]], session_id: str
    ) -> Dict[str, Any]:
        """
        Извлекает артефакты из диалога используя LLM.

        Args:
            conversation_messages: Сообщения диалога
            session_id: ID сессии

        Returns:
            Dict с артефактами и анализом
        """
        try:
            # Форматируем диалог для промпта
            conversation_text = format_conversation_for_prompt(conversation_messages)

            if self._llm_available:
                # Загружаем промпт из файла и используем реальный LLM API
                base_prompt = load_prompt_from_file("dialog_artifacts_extractor.txt")
                if base_prompt:
                    prompt = base_prompt.replace("{conversation_text}", conversation_text)
                else:
                    return extract_artifacts_from_dialog_stub(conversation_text)

                llm_response = await call_llm(prompt, origin="artifacts_processing")

                if llm_response:
                    try:
                        result = json.loads(llm_response)
                        log(f"Извлечено {len(result.get('artifacts', []))} артефактов из диалога")
                        return result
                    except json.JSONDecodeError as e:
                        log(f"Ошибка парсинга JSON от LLM: {e}")
                        return extract_artifacts_from_dialog_stub(conversation_text)
                else:
                    log("LLM API вернул пустой ответ, используем fallback")
                    return extract_artifacts_from_dialog_stub(conversation_text)
            else:
                # Используем fallback функцию
                return extract_artifacts_from_dialog_stub(conversation_text)

        except Exception as e:
            log(f"Ошибка при извлечении артефактов: {e}")
            return {
                "artifacts": [],
                "summary": {
                    "total_artifacts": 0,
                    "main_themes": [],
                    "project_potential": "unknown",
                    "recommendations": [],
                },
            }

    async def convert_artifacts_to_projects(self, artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Преобразует артефакты в проекты используя LLM.

        Args:
            artifacts: Список артефактов

        Returns:
            Dict с проектами и анализом
        """
        try:
            if not artifacts:
                return {
                    "projects": [],
                    "summary": {
                        "total_projects": 0,
                        "project_types": {"crowdsourced": 0, "crowdfunded": 0, "internal": 0},
                        "total_estimated_budget": 0,
                        "risks_assessment": "unknown",
                        "recommendations": [],
                    },
                }

            # Форматируем артефакты для промпта
            artifacts_json = json.dumps(artifacts, ensure_ascii=False, indent=2)

            if self._llm_available:
                # Загружаем промпт из файла и используем реальный LLM API
                base_prompt = load_prompt_from_file("artifacts_to_project_converter.txt")
                if base_prompt:
                    prompt = base_prompt.replace("{artifacts_json}", artifacts_json)
                else:
                    return convert_artifacts_to_projects_stub(artifacts)

                llm_response = await call_llm(prompt, origin="artifacts_processing")

                if llm_response:
                    try:
                        result = json.loads(llm_response)

                        # Валидируем и объединяем проекты
                        valid_projects = [p for p in result.get("projects", []) if validate_project_structure(p)]

                        merged_projects = merge_similar_projects(valid_projects)
                        result["projects"] = merged_projects
                        result["summary"]["total_projects"] = len(merged_projects)

                        log(f"Создано {len(merged_projects)} проектов из {len(artifacts)} артефактов")
                        return result

                    except json.JSONDecodeError as e:
                        log(f"Ошибка парсинга JSON от LLM: {e}")
                        return convert_artifacts_to_projects_stub(artifacts)
                else:
                    log("LLM API вернул пустой ответ, используем fallback")
                    return convert_artifacts_to_projects_stub(artifacts)
            else:
                # Используем fallback функцию
                return convert_artifacts_to_projects_stub(artifacts)

        except Exception as e:
            log(f"Ошибка при преобразовании артефактов в проекты: {e}")
            return {
                "projects": [],
                "summary": {
                    "total_projects": 0,
                    "project_types": {"crowdsourced": 0, "crowdfunded": 0, "internal": 0},
                    "total_estimated_budget": 0,
                    "risks_assessment": "unknown",
                    "recommendations": [],
                },
            }

    async def create_project_from_conversation_artifacts(
        self, session_id: str, conversation_messages: List[Dict[str, Any]], project_title: str, project_description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Полный цикл: извлечение артефактов → создание проектов → сохранение.

        Args:
            session_id: ID сессии
            conversation_messages: Сообщения диалога
            project_title: Название итогового проекта
            project_description: Описание итогового проекта

        Returns:
            Созданный проект или None
        """
        try:
            # Шаг 1: Извлекаем артефакты из диалога
            artifacts_result = await self.extract_artifacts_from_conversation(conversation_messages, session_id)

            artifacts = artifacts_result.get("artifacts", [])
            if not artifacts:
                log("Артефакты не найдены в диалоге")
                return None

            # Шаг 2: Сохраняем артефакты в сессии
            saved_artifacts = []
            for artifact in artifacts:
                saved = await artifacts_manager.add_artifact(
                    session_id=session_id,
                    message_id=f"msg_{artifact.get('message_index', 0)}",
                    selected_text=artifact.get("original_text", ""),
                    content=artifact.get("content", ""),
                    artifact_type=artifact.get("type", "note"),
                )
                if saved:
                    saved_artifacts.append(saved.to_dict())

            if not saved_artifacts:
                log("Не удалось сохранить артефакты")
                return None

            # Шаг 3: Преобразуем артефакты в проекты
            projects_result = await self.convert_artifacts_to_projects(saved_artifacts)
            projects = projects_result.get("projects", [])

            if not projects:
                log("Проекты не созданы из артефактов")
                return None

            # Шаг 4: Создаем финальный проект через сервис проектов
            # Используем первый проект из AI анализа как основу
            primary_project_data = projects[0]

            # Создаем краудфандинговый проект через сервис
            final_project = self._projects_service.create_project_from_artifacts(
                session_id=session_id,
                title=project_title,
                description=project_description,
                artifacts=saved_artifacts,
                knowledge_base_id="chat-session-" + session_id,
                tags=primary_project_data.get("tags", ["chat-artifacts", "crowdfunded"]),
                funding_goal=primary_project_data.get("estimated_budget", 100000.0),
            )

            log(f"Создан краудфандинговый проект '{project_title}' из {len(saved_artifacts)} артефактов")
            return final_project.model_dump()

        except Exception as e:
            log(f"Ошибка в полном цикле создания проекта: {e}")
            return None

    async def analyze_conversation_quality(self, conversation_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Анализирует качество диалога для определения потенциала создания проектов.

        Args:
            conversation_messages: Сообщения диалога

        Returns:
            Метрики качества диалога
        """
        try:
            # Базовые метрики
            total_messages = len(conversation_messages)
            user_messages = len([m for m in conversation_messages if m.get("role") == "user"])
            assistant_messages = len([m for m in conversation_messages if m.get("role") == "assistant"])

            # Анализ длин сообщений
            avg_message_length = sum(len(m.get("content", "")) for m in conversation_messages) / max(total_messages, 1)

            # Оценка вовлеченности (отношение ответов к вопросам)
            engagement_ratio = assistant_messages / max(user_messages, 1)

            # Извлекаем артефакты для оценки потенциала
            artifacts_result = await self.extract_artifacts_from_conversation(conversation_messages, "temp")
            artifacts_count = len(artifacts_result.get("artifacts", []))
            project_potential = artifacts_result.get("summary", {}).get("project_potential", "unknown")

            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "avg_message_length": round(avg_message_length, 1),
                "engagement_ratio": round(engagement_ratio, 2),
                "artifacts_count": artifacts_count,
                "project_potential": project_potential,
                "quality_score": min(100, artifacts_count * 10 + total_messages * 2),  # Простая формула оценки
            }

        except Exception as e:
            log(f"Ошибка при анализе качества диалога: {e}")
            return {"total_messages": len(conversation_messages), "error": str(e)}


# Глобальный экземпляр сервиса
artifacts_service = ArtifactsService()
