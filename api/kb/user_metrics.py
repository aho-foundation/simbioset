"""Module for handling user-provided metrics and observations."""

import time
from typing import Optional
from api.kb.models import ConceptNode
from api.kb.service import KBService


class UserMetricsService:
    """Service for collecting and storing user-provided metrics and observations."""

    def __init__(self, kb_service: Optional[KBService] = None):
        """
        Initialize the user metrics service.

        Args:
            kb_service: Knowledge base service instance (optional, will create if not provided)
        """
        if kb_service is None:
            # Fallback: create service with database repository
            from api.storage.nodes_repository import DatabaseNodeRepository
            from api.storage.db_factory import create_database_manager
            from api.settings import DATABASE_URL, DATABASE_PATH

            db_manager = create_database_manager(database_url=DATABASE_URL, db_path=DATABASE_PATH or "data/storage.db")
            db_manager.connect()
            node_repo = DatabaseNodeRepository(db_manager)
            self.kb_service = KBService(node_repo)
        else:
            self.kb_service = kb_service

    def save_user_observation(
        self,
        user_id: str,
        location: Optional[str] = None,
        ecosystem_type: Optional[str] = None,
        observations: Optional[str] = None,
        interactions: Optional[str] = None,
        season: Optional[str] = None,
        weather: Optional[str] = None,
        additional_notes: Optional[str] = None,
    ) -> ConceptNode:
        """
        Save user-provided observation as a metrics node.

        Args:
            user_id: ID of the user providing the observation
            location: User's location
            ecosystem_type: Type of ecosystem observed
            observations: Detailed observations
            interactions: Observed interactions
            season: Season when observation was made
            weather: Weather conditions
            additional_notes: Any additional notes

        Returns:
            Created ConceptNode with the observation data
        """
        # Create content string with the observation data
        content_parts = []

        if location:
            content_parts.append(f"📍 Локация: {location}")
        if ecosystem_type:
            content_parts.append(f"🌱 Тип экосистемы: {ecosystem_type}")
        if observations:
            content_parts.append(f"👀 Наблюдения: {observations}")
        if interactions:
            content_parts.append(f"🤝 Взаимодействия: {interactions}")
        if season:
            content_parts.append(f"📅 Сезон: {season}")
        if weather:
            content_parts.append(f"🌡️ Погода: {weather}")
        if additional_notes:
            content_parts.append(f"📝 Примечания: {additional_notes}")

        content = "\n".join(content_parts)

        # Create a node to store the user observation
        observation_node = self.kb_service.add_concept(
            parent_id=None,  # This could be linked to a user-specific root node in the future
            content=content,
            role="user",
            node_type="user_observation",
            session_id=None,
            category="metrics",
        )

        # Add metadata as sources to the node
        if any([user_id, location, ecosystem_type, observations, interactions, season, weather, additional_notes]):
            metadata = {
                "user_id": user_id,
                "location": location,
                "ecosystem_type": ecosystem_type,
                "observations": observations,
                "interactions": interactions,
                "season": season,
                "weather": weather,
                "additional_notes": additional_notes,
                "timestamp": int(time.time() * 1000),
            }

            # Add the metadata as a source to the created node
            self.kb_service.add_source(
                observation_node.id,
                {
                    "url": f"observation:{observation_node.id}",
                    "title": "User Observation Metadata",
                    "type": "confirm",  # Changed from "metadata" to "confirm" to match Source model validation
                    "content": metadata,
                },
            )

        return observation_node


# Global instance (will be initialized with kb_service from app.state in main.py)
user_metrics_service: Optional[UserMetricsService] = None


def init_user_metrics_service(kb_service: KBService) -> None:
    """Initialize global user metrics service with KB service."""
    global user_metrics_service
    user_metrics_service = UserMetricsService(kb_service)
