"""State management for asset generation.

This module handles persisting project state for tracking what's been
generated and deployed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStep(str, Enum):
    """Current step in the generation workflow."""

    INITIALIZED = "initialized"
    GENERATED = "generated"
    DEPLOYED = "deployed"


class DeploymentInfo(BaseModel):
    """Information about deployment to themes."""

    theme: str
    deployed_at: datetime
    files: dict[str, str] = Field(default_factory=dict)


class ProjectState(BaseModel):
    """State for a platform asset generation project."""

    platform_id: str
    platform_name: str

    step: WorkflowStep = WorkflowStep.INITIALIZED
    generated_assets: list[str] = Field(default_factory=list)
    deployments: list[DeploymentInfo] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        use_enum_values = True

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)


class StateManager:
    """Manages project state persistence and loading."""

    STATE_FILENAME = "state.json"

    def __init__(self, output_dir: Path) -> None:
        """Initialize state manager.

        Args:
            output_dir: Base output directory for all projects.
        """
        self.output_dir = output_dir

    def get_project_dir(self, platform_id: str) -> Path:
        """Get the project directory for a platform (matches theme structure)."""
        return self.output_dir / "assets" / "images" / platform_id

    def get_state_path(self, platform_id: str) -> Path:
        """Get the state file path for a platform."""
        return self.get_project_dir(platform_id) / self.STATE_FILENAME

    def project_exists(self, platform_id: str) -> bool:
        """Check if a project exists."""
        return self.get_state_path(platform_id).exists()

    def load_state(self, platform_id: str) -> ProjectState | None:
        """Load project state from disk.

        Returns:
            ProjectState if exists, None otherwise.
        """
        state_path = self.get_state_path(platform_id)
        if not state_path.exists():
            return None

        with state_path.open("r") as f:
            data = json.load(f)

        return ProjectState.model_validate(data)

    def save_state(self, state: ProjectState) -> Path:
        """Save project state to disk.

        Returns:
            Path to the saved state file.
        """
        state.touch()
        project_dir = self.get_project_dir(state.platform_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        state_path = self.get_state_path(state.platform_id)

        with state_path.open("w") as f:
            json.dump(self._serialize_state(state), f, indent=2, default=str)

        return state_path

    def _serialize_state(self, state: ProjectState) -> dict[str, Any]:
        """Serialize state to JSON-compatible dict."""
        data = state.model_dump()
        data["created_at"] = state.created_at.isoformat()
        data["updated_at"] = state.updated_at.isoformat()
        for deployment in data.get("deployments", []):
            if isinstance(deployment.get("deployed_at"), datetime):
                deployment["deployed_at"] = deployment["deployed_at"].isoformat()
        return data

    def create_project(
        self,
        platform_id: str,
        platform_name: str,
    ) -> ProjectState:
        """Create a new project with initial state.

        Args:
            platform_id: Platform identifier.
            platform_name: Full platform name.

        Returns:
            New ProjectState instance.
        """
        state = ProjectState(
            platform_id=platform_id,
            platform_name=platform_name,
        )

        project_dir = self.get_project_dir(platform_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        self.save_state(state)
        return state

    def mark_generated(
        self,
        platform_id: str,
        assets: list[str],
    ) -> ProjectState:
        """Mark project as generated with list of assets.

        Args:
            platform_id: Platform identifier.
            assets: List of generated asset filenames.

        Returns:
            Updated ProjectState.

        Raises:
            ValueError: If project does not exist.
        """
        state = self.load_state(platform_id)
        if state is None:
            raise ValueError(f"Project '{platform_id}' does not exist")

        state.generated_assets = assets
        state.step = WorkflowStep.GENERATED
        self.save_state(state)
        return state

    def add_deployment(
        self,
        platform_id: str,
        theme: str,
        files: dict[str, str],
    ) -> ProjectState:
        """Record a deployment to a theme.

        Args:
            platform_id: Platform identifier.
            theme: Theme name.
            files: Mapping of asset type to deployed path.

        Returns:
            Updated ProjectState.

        Raises:
            ValueError: If project does not exist.
        """
        state = self.load_state(platform_id)
        if state is None:
            raise ValueError(f"Project '{platform_id}' does not exist")

        deployment = DeploymentInfo(
            theme=theme,
            deployed_at=datetime.now(UTC),
            files=files,
        )
        state.deployments.append(deployment)
        state.step = WorkflowStep.DEPLOYED
        self.save_state(state)
        return state

    def list_projects(self) -> list[tuple[str, ProjectState]]:
        """List all projects in the output directory.

        Returns:
            List of (platform_id, state) tuples.
        """
        projects: list[tuple[str, ProjectState]] = []
        images_dir = self.output_dir / "assets" / "images"
        if not images_dir.exists():
            return projects

        for item in images_dir.iterdir():
            if item.is_dir():
                state = self.load_state(item.name)
                if state is not None:
                    projects.append((item.name, state))

        return sorted(projects, key=lambda x: x[1].updated_at, reverse=True)

    def delete_project(self, platform_id: str) -> bool:
        """Delete a project and all its files.

        Returns:
            True if project was deleted, False if it didn't exist.
        """
        import shutil

        project_dir = self.get_project_dir(platform_id)
        if not project_dir.exists():
            return False

        shutil.rmtree(project_dir)
        return True
