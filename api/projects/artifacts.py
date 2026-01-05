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
    ):
        self.id = artifact_id
        self.message_id = message_id
        self.selected_text = selected_text
        self.content = content
        self.timestamp = timestamp
        self.type = artifact_type

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует артефакт в словарь."""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "selected_text": self.selected_text,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "type": self.type,
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


# Глобальный экземпляр менеджера артефактов
artifacts_manager = ArtifactsManager()
