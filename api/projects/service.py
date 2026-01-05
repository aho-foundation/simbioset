"""Business logic layer for Projects operations."""

from typing import Any, Optional

from datetime import datetime
from typing import List

from .models import (
    BaseProject,
    CrowdsourcedProject,
    CrowdfundedProject,
    Idea,
    Contributor,
    Backer,
    FundingTier,
)
from .repository import ProjectsRepository


class ProjectsService:
    """Projects service with business logic."""

    def __init__(self, repository: ProjectsRepository):
        """Initialize service with repository dependency."""
        self.repository = repository

    # Project operations
    def get_project(self, project_id: str) -> Optional[BaseProject]:
        """Get project by ID."""
        data = self.repository.get_project_by_id(project_id)
        if not data:
            return None

        # Determine project type and create appropriate model
        if "ideas" in data:
            return CrowdsourcedProject(**data)
        elif "funding_goal" in data:
            return CrowdfundedProject(**data)
        else:
            return BaseProject(**data)

    def get_projects(
        self,
        query: str = "",
        project_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[BaseProject]:
        """Get projects with optional filters."""
        projects_data = self.repository.search_projects(
            query=query, project_type=project_type, status=status, tags=tags, limit=limit, offset=offset
        )

        projects: list[BaseProject] = []
        for data in projects_data:
            if "ideas" in data:
                projects.append(CrowdsourcedProject(**data))
            elif "funding_goal" in data:
                projects.append(CrowdfundedProject(**data))
            else:
                projects.append(BaseProject(**data))

        return projects

    def create_project(self, project_data: dict[str, Any]) -> BaseProject:
        """Create new project."""
        # Validate required fields
        if not project_data.get("title"):
            raise ValueError("Project title is required")
        if not project_data.get("description"):
            raise ValueError("Project description is required")
        if not project_data.get("knowledge_base_id"):
            raise ValueError("Knowledge base ID is required")

        # Determine project type
        project: BaseProject = (
            CrowdfundedProject(**project_data)
            if project_data.get("funding_goal")
            else CrowdsourcedProject(**project_data)
        )

        created_data = self.repository.create_project(project.model_dump())
        if isinstance(project, CrowdfundedProject):
            return CrowdfundedProject(**created_data)
        elif isinstance(project, CrowdsourcedProject):
            return CrowdsourcedProject(**created_data)
        else:
            return BaseProject(**created_data)

    def update_project(self, project_id: str, updates: dict[str, Any]) -> Optional[BaseProject]:
        """Update existing project."""
        updated_data = self.repository.update_project(project_id, updates)
        if not updated_data:
            return None

        # Return appropriate model type
        if "ideas" in updated_data:
            return CrowdsourcedProject(**updated_data)
        elif "funding_goal" in updated_data:
            return CrowdfundedProject(**updated_data)
        else:
            return BaseProject(**updated_data)

    def delete_project(self, project_id: str) -> bool:
        """Delete project."""
        return self.repository.delete_project(project_id)

    # Idea operations
    def get_idea(self, idea_id: str) -> Optional[Idea]:
        """Get idea by ID."""
        data = self.repository.get_idea_by_id(idea_id)
        return Idea(**data) if data else None

    def get_ideas(self, project_id: Optional[str] = None) -> list[Idea]:
        """Get ideas, optionally filtered by project."""
        if project_id:
            ideas_data = self.repository.get_ideas_by_project(project_id)
        else:
            ideas_data = self.repository.get_all_ideas()

        return [Idea(**data) for data in ideas_data]

    def create_idea(self, idea_data: dict[str, Any]) -> Idea:
        """Create new idea."""
        if not idea_data.get("content"):
            raise ValueError("Idea content is required")
        if not idea_data.get("author_id"):
            raise ValueError("Author ID is required")
        if not idea_data.get("project_id"):
            raise ValueError("Project ID is required")

        # Check if project exists
        project = self.repository.get_project_by_id(idea_data["project_id"])
        if not project:
            raise ValueError(f"Project {idea_data['project_id']} does not exist")

        # Check if project is crowdsourced
        if "ideas" not in project:
            raise ValueError("Cannot add ideas to non-crowdsourced projects")

        idea = Idea(**idea_data)
        created_data = self.repository.create_idea(idea.model_dump())
        return Idea(**created_data)

    def update_idea(self, idea_id: str, updates: dict[str, Any]) -> Optional[Idea]:
        """Update existing idea."""
        updated_data = self.repository.update_idea(idea_id, updates)
        return Idea(**updated_data) if updated_data else None

    def delete_idea(self, idea_id: str) -> bool:
        """Delete idea."""
        return self.repository.delete_idea(idea_id)

    # Specialized operations
    def add_idea_to_project(self, project_id: str, idea_data: dict[str, Any]) -> Idea:
        """Add idea to project (convenience method)."""
        idea_data["project_id"] = project_id
        return self.create_idea(idea_data)

    def contribute_to_project(self, project_id: str, contributor_data: dict[str, Any]) -> bool:
        """Add contribution to crowdsourced project."""
        if not contributor_data.get("user_id"):
            raise ValueError("User ID is required")
        if not contributor_data.get("name"):
            raise ValueError("Contributor name is required")
        if not contributor_data.get("role"):
            raise ValueError("Role is required")

        # Check if project exists and is crowdsourced
        project = self.repository.get_project_by_id(project_id)
        if not project:
            raise ValueError(f"Project {project_id} does not exist")
        if "ideas" not in project:
            raise ValueError("Cannot contribute to non-crowdsourced projects")

        contributor = Contributor(**contributor_data)
        return self.repository.add_contribution(project_id, contributor.model_dump())

    def contribute_funding(self, project_id: str, backer_data: dict[str, Any]) -> bool:
        """Add funding contribution to crowdfunded project."""
        if not backer_data.get("user_id"):
            raise ValueError("User ID is required")
        if not backer_data.get("name"):
            raise ValueError("Backer name is required")
        if not backer_data.get("amount") or backer_data["amount"] <= 0:
            raise ValueError("Valid amount is required")

        # Check if project exists and is crowdfunded
        project = self.repository.get_project_by_id(project_id)
        if not project:
            raise ValueError(f"Project {project_id} does not exist")
        if "funding_goal" not in project:
            raise ValueError("Cannot fund non-crowdfunded projects")

        # Check if funding is still active
        if project.get("status") != "active":
            raise ValueError("Project is not accepting funding")

        backer = Backer(**backer_data)
        return self.repository.add_backing(project_id, backer.model_dump())

    def get_contributors(self, project_id: str) -> list[Contributor]:
        """Get contributors for a project."""
        contributors_data = self.repository.get_contributors(project_id)
        return [Contributor(**data) for data in contributors_data]

    def get_backers(self, project_id: str) -> list[Backer]:
        """Get backers for a project."""
        backers_data = self.repository.get_backers(project_id)
        return [Backer(**data) for data in backers_data]

    def get_stats(self) -> dict[str, Any]:
        """Get projects statistics."""
        return self.repository.get_stats()

    def create_project_from_artifacts(
        self,
        session_id: str,
        title: str,
        description: str,
        artifacts: List[dict[str, Any]],
        knowledge_base_id: str,
        tags: Optional[list[str]] = None,
        funding_goal: float = 100000.0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> CrowdfundedProject:
        """
        Create a crowdfunded project from chat artifacts with crowdsourcing components.

        Args:
            session_id: Session ID where artifacts were collected
            title: Project title
            description: Project description
            artifacts: List of artifact dictionaries
            knowledge_base_id: Linked knowledge base ID
            tags: Project tags
            funding_goal: Target funding amount (default 100k RUB)
            start_date: Funding campaign start date
            end_date: Funding campaign end date

        Returns:
            Created CrowdfundedProject instance
        """
        if not title.strip():
            raise ValueError("Project title is required")
        if not description.strip():
            raise ValueError("Project description is required")
        if not artifacts:
            raise ValueError("At least one artifact is required")

        # Create funding tiers based on project complexity
        funding_tiers = [
            FundingTier(
                id="seed_gardener",
                title="Сеятель семян",
                description="Поддержка начального этапа исследований поддержки биоразнообразия",
                amount=1000.0,
                rewards=[
                    "Участие в сохранении локальных экосистем",
                    "Имя в книге благодарностей проекта",
                    "Месячные отчеты о прогрессе исследований",
                    "Сертификат участника природоохранного проекта",
                ],
                limit=None,
            ),
            FundingTier(
                id="forest_guardian",
                title="Страж леса",
                description="Активное участие в мониторинге и защите биоразнообразия",
                amount=5000.0,
                rewards=[
                    "Все награды сеятеля семян",
                    "Участие в планировании полевых исследований",
                    "Доступ к образовательным материалам",
                    "Возможность предложить направления исследований",
                    "Персональная консультация с экспертами",
                ],
                limit=None,
            ),
            FundingTier(
                id="biosphere_steward",
                title="Хранитель биосферы",
                description="Партнерство в научных исследованиях и сохранении экосистем",
                amount=25000.0,
                rewards=[
                    "Все награды стража леса",
                    "Совместные научные публикации",
                    "Полный доступ к собранным датасетам",
                    "Участие в конференциях и семинарах",
                    "Возможность инициировать новые исследования",
                    "Почетное звание 'Хранитель биосферы'",
                ],
                limit=None,
            ),
        ]

        # Set default dates if not provided
        if not start_date:
            start_date = datetime.now().isoformat()
        if not end_date:
            # Default 3 months campaign
            end_date = (datetime.now().replace(month=datetime.now().month + 3)).isoformat()

        # Create project data for crowdfunded project
        project_data = {
            "title": title,
            "description": description,
            "status": "draft",
            "creation_date": datetime.now(),
            "update_date": datetime.now(),
            "knowledge_base_id": knowledge_base_id,
            "tags": tags or ["chat-artifacts", "crowdfunded", "crowdsourcing", "ecology"],
            "funding_goal": funding_goal,
            "current_funding": 0.0,
            "start_date": start_date,
            "end_date": end_date,
            "backers": [],
            "funding_tiers": [tier.model_dump() for tier in funding_tiers],
        }

        # Create project in repository
        created_data = self.repository.create_project(project_data)

        return CrowdfundedProject(**created_data)
