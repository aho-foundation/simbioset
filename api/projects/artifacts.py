"""Artifacts API - управление артефактами чата для создания проектов."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from api.logger import root_logger
from api.sessions import session_manager

log = root_logger.debug


class Artifact:
    """Модель артефакта чата."""

    def __init__(
        self,
        artifact_id: str,
        message_id: str,
        selected_text: str,
        content: str,
        timestamp: datetime,
        artifact_type: str = "note",
        suggested: bool = False,
        confidence: float = 0.0,
    ):
        self.id = artifact_id
        self.message_id = message_id
        self.selected_text = selected_text
        self.content = content
        self.timestamp = timestamp
        self.type = artifact_type
        self.suggested = suggested  # True для автоматически предложенных артефактов
        self.confidence = confidence  # Уверенность модели (0.0-1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует артефакт в словарь."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "selected_text": self.selected_text,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "type": self.type,
            "suggested": self.suggested,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Artifact":
        """Создает артефакт из словаря."""
        return cls(
            artifact_id=data["id"],
            message_id=data["message_id"],
            selected_text=data["selected_text"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            artifact_type=data.get("type", "note"),
            suggested=data.get("suggested", False),
            confidence=data.get("confidence", 0.0),
        )


class ArtifactsManager:
    """Менеджер артефактов сессии."""

    def __init__(self):
        """Инициализация менеджера артефактов."""
        self._session_manager = session_manager

    async def get_artifacts(self, session_id: str) -> List[Artifact]:
        """
        Получает все артефакты сессии.

        Args:
            session_id: ID сессии

        Returns:
            Список артефактов
        """
        session_data = await self._session_manager.get_session(session_id)
        if not session_data:
            return []

        artifacts_data = session_data.get("artifacts", [])
        return [Artifact.from_dict(artifact) for artifact in artifacts_data]

    async def add_artifact(
        self,
        session_id: str,
        message_id: str,
        selected_text: str,
        content: Optional[str] = None,
        artifact_type: str = "note",
    ) -> Optional[Artifact]:
        """
        Добавляет новый артефакт в сессию.

        Args:
            session_id: ID сессии
            message_id: ID сообщения
            selected_text: Выделенный текст
            content: Полный контент (опционально)
            artifact_type: Тип артефакта

        Returns:
            Созданный артефакт или None если сессия не найдена
        """
        session_data = await self._session_manager.get_session(session_id)
        if not session_data:
            return None

        # Создаем новый артефакт
        artifact = Artifact(
            artifact_id=f"artifact_{datetime.now().timestamp()}_{hash(selected_text) % 10000}",
            message_id=message_id,
            selected_text=selected_text,
            content=content or selected_text,
            timestamp=datetime.now(),
            artifact_type=artifact_type,
        )

        # Добавляем в сессию
        artifacts_data = session_data.get("artifacts", [])
        artifacts_data.append(artifact.to_dict())

        session_data["artifacts"] = artifacts_data
        await self._session_manager.update_session(session_id, session_data)

        log(f"Added artifact {artifact.id} to session {session_id}")
        return artifact

    async def remove_artifact(self, session_id: str, artifact_id: str) -> bool:
        """
        Удаляет артефакт из сессии.

        Args:
            session_id: ID сессии
            artifact_id: ID артефакта

        Returns:
            True если артефакт удален, False если не найден
        """
        session_data = await self._session_manager.get_session(session_id)
        if not session_data:
            return False

        artifacts_data = session_data.get("artifacts", [])
        original_length = len(artifacts_data)

        # Фильтруем артефакты, исключая удаляемый
        session_data["artifacts"] = [artifact for artifact in artifacts_data if artifact["id"] != artifact_id]

        if len(session_data["artifacts"]) < original_length:
            await self._session_manager.update_session(session_id, session_data)
            log(f"Removed artifact {artifact_id} from session {session_id}")
            return True

        return False

    async def clear_artifacts(self, session_id: str) -> bool:
        """
        Очищает все артефакты сессии.

        Args:
            session_id: ID сессии

        Returns:
            True если сессия найдена и артефакты очищены
        """
        session_data = await self._session_manager.get_session(session_id)
        if not session_data:
            return False

        session_data["artifacts"] = []
        await self._session_manager.update_session(session_id, session_data)
        log(f"Cleared all artifacts from session {session_id}")
        return True

    async def get_artifacts_by_type(self, session_id: str, artifact_type: str) -> List[Artifact]:
        """
        Получает артефакты определенного типа.

        Args:
            session_id: ID сессии
            artifact_type: Тип артефакта

        Returns:
            Список артефактов указанного типа
        """
        all_artifacts = await self.get_artifacts(session_id)
        return [artifact for artifact in all_artifacts if artifact.type == artifact_type]

    async def get_suggested_artifacts(self, session_id: str) -> List[Artifact]:
        """
        Получает только предложенные (автоматические) артефакты.

        Args:
            session_id: ID сессии

        Returns:
            Список предложенных артефактов
        """
        all_artifacts = await self.get_artifacts(session_id)
        return [artifact for artifact in all_artifacts if artifact.suggested]

    async def get_unreviewed_suggestions(self, session_id: str) -> List[Artifact]:
        """
        Получает нерассмотренные предложенные артефакты.
        Пока что возвращает все предложенные (позже можно добавить статус review).

        Args:
            session_id: ID сессии

        Returns:
            Список нерассмотренных предложенных артефактов
        """
        return await self.get_suggested_artifacts(session_id)

    async def accept_suggestion(self, session_id: str, artifact_id: str) -> bool:
        """
        Принимает предложенный артефакт (делает его обычным артефактом).

        Args:
            session_id: ID сессии
            artifact_id: ID артефакта

        Returns:
            True если успешно принято
        """
        session_data = await self._session_manager.get_session(session_id)
        if not session_data:
            return False

        artifacts_data = session_data.get("artifacts", [])
        for artifact_data in artifacts_data:
            if artifact_data["id"] == artifact_id and artifact_data.get("suggested", False):
                artifact_data["suggested"] = False
                session_data["artifacts"] = artifacts_data
                await self._session_manager.update_session(session_id, session_data)
                log(f"Accepted suggested artifact {artifact_id} in session {session_id}")
                return True
        return False

    async def reject_suggestion(self, session_id: str, artifact_id: str) -> bool:
        """
        Отклоняет предложенный артефакт (удаляет его).

        Args:
            session_id: ID сессии
            artifact_id: ID артефакта

        Returns:
            True если успешно отклонено
        """
        session_data = await self._session_manager.get_session(session_id)
        if not session_data:
            return False

        artifacts_data = session_data.get("artifacts", [])
        filtered_artifacts_data = [
            artifact_data
            for artifact_data in artifacts_data
            if not (artifact_data["id"] == artifact_id and artifact_data.get("suggested", False))
        ]

        if len(filtered_artifacts_data) < len(artifacts_data):
            session_data["artifacts"] = filtered_artifacts_data
            await self._session_manager.update_session(session_id, session_data)
            log(f"Rejected suggested artifact {artifact_id} in session {session_id}")
            return True
        return False

    async def suggest_artifacts_from_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> int:
        """
        Автоматически предлагает артефакты на основе анализа сообщений.

        Args:
            session_id: ID сессии
            messages: Список сообщений для анализа

        Returns:
            Количество предложенных артефактов
        """
        from .artifacts_service import suggest_artifacts_from_messages

        # Получаем существующие артефакты
        existing_artifacts = await self.get_artifacts(session_id)
        existing_texts = {a.selected_text for a in existing_artifacts}

        # Предлагаем новые артефакты
        suggested_artifacts_data = await suggest_artifacts_from_messages(session_id, messages)

        new_suggestions = 0
        for artifact_data in suggested_artifacts_data:
            # Проверяем, что такой артефакт еще не существует
            if artifact_data["selected_text"] not in existing_texts:
                artifact = Artifact(
                    artifact_id=f"suggested_{session_id}_{len(existing_artifacts) + new_suggestions}",
                    message_id=artifact_data["message_id"],
                    selected_text=artifact_data["selected_text"],
                    content=artifact_data["content"],
                    timestamp=datetime.now(),
                    artifact_type=artifact_data["type"],
                    suggested=True,
                    confidence=artifact_data["confidence"],
                )

                existing_artifacts.append(artifact)
                new_suggestions += 1

        if new_suggestions > 0:
            session_data = await self._session_manager.get_session(session_id)
            if session_data:
                session_data["artifacts"] = [artifact.to_dict() for artifact in existing_artifacts]
                await self._session_manager.update_session(session_id, session_data)
                log(f"Suggested {new_suggestions} new artifacts for session {session_id}")

        return new_suggestions


# Глобальный экземпляр менеджера артефактов
artifacts_manager = ArtifactsManager()
