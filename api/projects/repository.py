"""Repository layer for Projects storage operations."""

import json
import fcntl
import uuid
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from .models import (
    BaseProject,
    CrowdsourcedProject,
    CrowdfundedProject,
    Idea,
    Contributor,
    Backer,
    FundingTier,
)


class ProjectsRepository:
    """JSON file-based repository for projects with file locking for thread safety."""

    def __init__(self, file_path: str = "data/projects.json"):
        """Initialize repository with storage file path."""
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Create storage file with initial structure if it doesn't exist."""
        if not self.file_path.exists():
            initial_data = {
                "version": "1.0.0",
                "metadata": {
                    "created": int(datetime.now().timestamp() * 1000),
                    "updated": int(datetime.now().timestamp() * 1000),
                    "totalProjects": 0,
                    "totalIdeas": 0,
                },
                "projects": {},
                "ideas": {},
            }
            self._write_data(initial_data)

    def _read_data(self) -> dict[str, Any]:
        """Read data from JSON file with shared lock."""
        with open(self.file_path, "r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _write_data(self, data: dict[str, Any]) -> None:
        """Write data to JSON file with exclusive lock."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # Project operations
    def get_project_by_id(self, project_id: str) -> Optional[dict]:
        """Get project by ID."""
        data = self._read_data()
        return data["projects"].get(project_id)

    def get_all_projects(self) -> list[dict]:
        """Get all projects."""
        data = self._read_data()
        return list(data["projects"].values())

    def create_project(self, project: dict[str, Any]) -> dict[str, Any]:
        """Create new project."""
        data = self._read_data()

        if "id" not in project or not project["id"]:
            project["id"] = str(uuid.uuid4())

        project_id = project["id"]

        if project_id in data["projects"]:
            raise ValueError(f"Project with ID {project_id} already exists")

        if "creation_date" not in project:
            project["creation_date"] = datetime.now()
        if "update_date" not in project:
            project["update_date"] = datetime.now()

        # Initialize lists if not present
        project.setdefault("ideas", [])
        project.setdefault("contributors", [])
        project.setdefault("backers", [])
        project.setdefault("funding_tiers", [])

        data["projects"][project_id] = project
        data["metadata"]["totalProjects"] = len(data["projects"])
        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return project

    def update_project(self, project_id: str, updates: dict) -> Optional[dict]:
        """Update existing project."""
        data = self._read_data()

        if project_id not in data["projects"]:
            return None

        project = data["projects"][project_id]
        project.update(updates)
        project["update_date"] = datetime.now()

        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return project

    def delete_project(self, project_id: str) -> bool:
        """Delete project and all its ideas."""
        data = self._read_data()

        if project_id not in data["projects"]:
            return False

        # Delete associated ideas
        project = data["projects"][project_id]
        for idea_id in project.get("ideas", []):
            data["ideas"].pop(idea_id, None)

        del data["projects"][project_id]

        data["metadata"]["totalProjects"] = len(data["projects"])
        data["metadata"]["totalIdeas"] = len(data["ideas"])
        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return True

    # Idea operations
    def get_idea_by_id(self, idea_id: str) -> Optional[dict]:
        """Get idea by ID."""
        data = self._read_data()
        return data["ideas"].get(idea_id)

    def get_all_ideas(self) -> list[dict]:
        """Get all ideas."""
        data = self._read_data()
        return list(data["ideas"].values())

    def get_ideas_by_project(self, project_id: str) -> list[dict]:
        """Get ideas for a specific project."""
        data = self._read_data()
        return [
            data["ideas"][idea_id]
            for idea_id in data["projects"].get(project_id, {}).get("ideas", [])
            if idea_id in data["ideas"]
        ]

    def create_idea(self, idea: dict[str, Any]) -> dict[str, Any]:
        """Create new idea."""
        data = self._read_data()

        if "id" not in idea or not idea["id"]:
            idea["id"] = str(uuid.uuid4())

        idea_id = idea["id"]
        project_id = idea.get("project_id")

        if idea_id in data["ideas"]:
            raise ValueError(f"Idea with ID {idea_id} already exists")

        if project_id and project_id not in data["projects"]:
            raise ValueError(f"Project {project_id} does not exist")

        if "submission_date" not in idea:
            idea["submission_date"] = datetime.now()

        data["ideas"][idea_id] = idea

        # Add to project's ideas list
        if project_id:
            project = data["projects"][project_id]
            if idea_id not in project.get("ideas", []):
                project.setdefault("ideas", []).append(idea_id)

        data["metadata"]["totalIdeas"] = len(data["ideas"])
        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return idea

    def update_idea(self, idea_id: str, updates: dict) -> Optional[dict]:
        """Update existing idea."""
        data = self._read_data()

        if idea_id not in data["ideas"]:
            return None

        idea = data["ideas"][idea_id]
        idea.update(updates)

        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return idea

    def delete_idea(self, idea_id: str) -> bool:
        """Delete idea."""
        data = self._read_data()

        if idea_id not in data["ideas"]:
            return False

        idea = data["ideas"][idea_id]
        project_id = idea.get("project_id")

        # Remove from project's ideas list
        if project_id and project_id in data["projects"]:
            project = data["projects"][project_id]
            if idea_id in project.get("ideas", []):
                project["ideas"].remove(idea_id)

        del data["ideas"][idea_id]

        data["metadata"]["totalIdeas"] = len(data["ideas"])
        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return True

    # Specialized operations
    def add_contribution(self, project_id: str, contributor: dict) -> bool:
        """Add contributor to crowdsourced project."""
        data = self._read_data()

        if project_id not in data["projects"]:
            return False

        project = data["projects"][project_id]
        project.setdefault("contributors", []).append(contributor)
        project["update_date"] = datetime.now()

        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return True

    def add_backing(self, project_id: str, backer: dict) -> bool:
        """Add backer to crowdfunded project."""
        data = self._read_data()

        if project_id not in data["projects"]:
            return False

        project = data["projects"][project_id]
        project.setdefault("backers", []).append(backer)
        project["current_funding"] = project.get("current_funding", 0) + backer.get("amount", 0)
        project["update_date"] = datetime.now()

        data["metadata"]["updated"] = int(datetime.now().timestamp() * 1000)

        self._write_data(data)
        return True

    def get_contributors(self, project_id: str) -> list[dict]:
        """Get contributors for a project."""
        data = self._read_data()
        project = data["projects"].get(project_id, {})
        return project.get("contributors", [])

    def get_backers(self, project_id: str) -> list[dict]:
        """Get backers for a project."""
        data = self._read_data()
        project = data["projects"].get(project_id, {})
        return project.get("backers", [])

    def search_projects(
        self,
        query: str = "",
        project_type: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """Search projects with filters."""
        data = self._read_data()
        results = []

        for project in data["projects"].values():
            # Filter by type
            if project_type:
                if project_type == "crowdsourced" and "ideas" not in project:
                    continue
                if project_type == "crowdfunded" and "funding_goal" not in project:
                    continue

            # Filter by status
            if status and project.get("status") != status:
                continue

            # Filter by tags
            if tags:
                project_tags = set(project.get("tags", []))
                if not project_tags.intersection(set(tags)):
                    continue

            # Search in title and description
            if query:
                search_text = f"{project.get('title', '')} {project.get('description', '')}".lower()
                if query.lower() not in search_text:
                    continue

            results.append(project)

        return results[offset : offset + limit]

    def get_stats(self) -> dict:
        """Get projects statistics."""
        data = self._read_data()

        stats = {
            "totalProjects": len(data["projects"]),
            "totalIdeas": len(data["ideas"]),
            "crowdsourcedProjects": 0,
            "crowdfundedProjects": 0,
            "activeProjects": 0,
            "completedProjects": 0,
            "totalFunding": 0,
            "lastUpdated": data["metadata"]["updated"],
        }

        for project in data["projects"].values():
            if "ideas" in project:
                stats["crowdsourcedProjects"] += 1
            if "funding_goal" in project:
                stats["crowdfundedProjects"] += 1
                stats["totalFunding"] += project.get("current_funding", 0)

            if project.get("status") == "active":
                stats["activeProjects"] += 1
            elif project.get("status") == "completed":
                stats["completedProjects"] += 1

        return stats
