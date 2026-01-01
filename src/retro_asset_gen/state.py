"""State management for multi-step asset generation workflow.

This module handles persisting and loading state between CLI commands,
enabling the interactive workflow where users generate candidates,
select favorites, finalize packs, and deploy to themes.
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
    CANDIDATES_GENERATED = "candidates_generated"
    SELECTION_MADE = "selection_made"
    FINALIZED = "finalized"
    DEPLOYED = "deployed"


class CandidateInfo(BaseModel):
    """Information about generated candidate images."""

    devices: list[str] = Field(default_factory=list)
    logos: list[str] = Field(default_factory=list)


class SelectionInfo(BaseModel):
    """User's selection of preferred variants."""

    device: int | None = None
    logo: int | None = None


class DeploymentInfo(BaseModel):
    """Information about deployment to themes."""

    theme: str
    deployed_at: datetime
    files: dict[str, str] = Field(default_factory=dict)


class ProjectState(BaseModel):
    """Complete state for a platform asset generation project."""

    platform_id: str
    platform_name: str
    year: int | None = None
    vendor: str | None = None

    step: WorkflowStep = WorkflowStep.INITIALIZED
    candidates: CandidateInfo = Field(default_factory=CandidateInfo)
    selection: SelectionInfo = Field(default_factory=SelectionInfo)
    deployments: list[DeploymentInfo] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    device_count: int = 3
    logo_count: int = 3

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
        """Get the project directory for a platform.

        Args:
            platform_id: Platform identifier.

        Returns:
            Path to the project directory.
        """
        return self.output_dir / platform_id

    def get_state_path(self, platform_id: str) -> Path:
        """Get the state file path for a platform.

        Args:
            platform_id: Platform identifier.

        Returns:
            Path to the state.json file.
        """
        return self.get_project_dir(platform_id) / self.STATE_FILENAME

    def get_candidates_dir(self, platform_id: str) -> Path:
        """Get the candidates directory for a platform.

        Args:
            platform_id: Platform identifier.

        Returns:
            Path to the candidates directory.
        """
        return self.get_project_dir(platform_id) / "candidates"

    def get_devices_dir(self, platform_id: str) -> Path:
        """Get the device candidates directory.

        Args:
            platform_id: Platform identifier.

        Returns:
            Path to the devices subdirectory.
        """
        return self.get_candidates_dir(platform_id) / "devices"

    def get_logos_dir(self, platform_id: str) -> Path:
        """Get the logo candidates directory.

        Args:
            platform_id: Platform identifier.

        Returns:
            Path to the logos subdirectory.
        """
        return self.get_candidates_dir(platform_id) / "logos"

    def get_selected_dir(self, platform_id: str) -> Path:
        """Get the selected variants directory.

        Args:
            platform_id: Platform identifier.

        Returns:
            Path to the selected directory.
        """
        return self.get_project_dir(platform_id) / "selected"

    def get_final_dir(self, platform_id: str) -> Path:
        """Get the finalized assets directory.

        Args:
            platform_id: Platform identifier.

        Returns:
            Path to the final directory.
        """
        return self.get_project_dir(platform_id) / "final"

    def project_exists(self, platform_id: str) -> bool:
        """Check if a project exists.

        Args:
            platform_id: Platform identifier.

        Returns:
            True if project state file exists.
        """
        return self.get_state_path(platform_id).exists()

    def load_state(self, platform_id: str) -> ProjectState | None:
        """Load project state from disk.

        Args:
            platform_id: Platform identifier.

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

        Args:
            state: Project state to save.

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
        """Serialize state to JSON-compatible dict.

        Args:
            state: Project state to serialize.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        data = state.model_dump()
        # Convert datetime objects to ISO format strings
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
        year: int | None = None,
        vendor: str | None = None,
        device_count: int = 3,
        logo_count: int = 3,
    ) -> ProjectState:
        """Create a new project with initial state.

        Args:
            platform_id: Platform identifier.
            platform_name: Full platform name.
            year: Optional release year.
            vendor: Optional vendor/manufacturer.
            device_count: Number of device candidates to generate.
            logo_count: Number of logo candidates to generate.

        Returns:
            New ProjectState instance.
        """
        state = ProjectState(
            platform_id=platform_id,
            platform_name=platform_name,
            year=year,
            vendor=vendor,
            device_count=device_count,
            logo_count=logo_count,
        )

        # Create directory structure
        project_dir = self.get_project_dir(platform_id)
        devices_dir = self.get_devices_dir(platform_id)
        logos_dir = self.get_logos_dir(platform_id)
        selected_dir = self.get_selected_dir(platform_id)
        final_dir = self.get_final_dir(platform_id)

        for directory in [project_dir, devices_dir, logos_dir, selected_dir, final_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.save_state(state)
        return state

    def update_candidates(
        self,
        platform_id: str,
        devices: list[str] | None = None,
        logos: list[str] | None = None,
    ) -> ProjectState:
        """Update candidate information after generation.

        Args:
            platform_id: Platform identifier.
            devices: List of device candidate filenames.
            logos: List of logo candidate filenames.

        Returns:
            Updated ProjectState.

        Raises:
            ValueError: If project does not exist.
        """
        state = self.load_state(platform_id)
        if state is None:
            raise ValueError(f"Project '{platform_id}' does not exist")

        if devices is not None:
            state.candidates.devices = devices
        if logos is not None:
            state.candidates.logos = logos

        state.step = WorkflowStep.CANDIDATES_GENERATED
        self.save_state(state)
        return state

    def update_selection(
        self,
        platform_id: str,
        device: int | None = None,
        logo: int | None = None,
    ) -> ProjectState:
        """Update user's selection.

        Args:
            platform_id: Platform identifier.
            device: Selected device index (1-based).
            logo: Selected logo index (1-based).

        Returns:
            Updated ProjectState.

        Raises:
            ValueError: If project does not exist or selection is invalid.
        """
        state = self.load_state(platform_id)
        if state is None:
            raise ValueError(f"Project '{platform_id}' does not exist")

        if device is not None:
            if device < 1 or device > len(state.candidates.devices):
                raise ValueError(
                    f"Invalid device selection: {device}. "
                    f"Must be between 1 and {len(state.candidates.devices)}"
                )
            state.selection.device = device

        if logo is not None:
            if logo < 1 or logo > len(state.candidates.logos):
                raise ValueError(
                    f"Invalid logo selection: {logo}. "
                    f"Must be between 1 and {len(state.candidates.logos)}"
                )
            state.selection.logo = logo

        # Only update step if both selections are made
        if state.selection.device is not None and state.selection.logo is not None:
            state.step = WorkflowStep.SELECTION_MADE

        self.save_state(state)
        return state

    def mark_finalized(self, platform_id: str) -> ProjectState:
        """Mark project as finalized.

        Args:
            platform_id: Platform identifier.

        Returns:
            Updated ProjectState.

        Raises:
            ValueError: If project does not exist.
        """
        state = self.load_state(platform_id)
        if state is None:
            raise ValueError(f"Project '{platform_id}' does not exist")

        state.step = WorkflowStep.FINALIZED
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
        if not self.output_dir.exists():
            return projects

        for item in self.output_dir.iterdir():
            if item.is_dir():
                state = self.load_state(item.name)
                if state is not None:
                    projects.append((item.name, state))

        return sorted(projects, key=lambda x: x[1].updated_at, reverse=True)

    def delete_project(self, platform_id: str) -> bool:
        """Delete a project and all its files.

        Args:
            platform_id: Platform identifier.

        Returns:
            True if project was deleted, False if it didn't exist.
        """
        import shutil

        project_dir = self.get_project_dir(platform_id)
        if not project_dir.exists():
            return False

        shutil.rmtree(project_dir)
        return True
