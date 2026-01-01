"""Deploy generated asset packs to theme folders.

This module handles copying generated assets to their target
theme directories according to theme configuration.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from .state import ProjectState, StateManager
from .theme_config import ThemeConfig, ThemesConfig


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""

    success: bool
    theme: str
    platform_id: str
    files_deployed: dict[str, Path]
    errors: list[str]


class DeploymentError(Exception):
    """Error during deployment."""

    pass


class Deployer:
    """Deploys generated asset packs to theme folders."""

    # Asset files in the output directory
    ASSET_FILES = {
        "device": "device.png",
        "logo_dark_color": "logo_dark_color.png",
        "logo_dark_black": "logo_dark_black.png",
        "logo_light_color": "logo_light_color.png",
        "logo_light_white": "logo_light_white.png",
    }

    def __init__(
        self,
        state_manager: StateManager,
        themes_config: ThemesConfig,
        console: Console | None = None,
    ) -> None:
        """Initialize deployer.

        Args:
            state_manager: State manager instance.
            themes_config: Themes configuration.
            console: Optional Rich console for output.
        """
        self.state_manager = state_manager
        self.themes_config = themes_config
        self.console = console or Console()

    def validate_deployment(
        self,
        state: ProjectState,
        theme_config: ThemeConfig,
    ) -> list[str]:
        """Validate that deployment can proceed.

        Args:
            state: Project state.
            theme_config: Theme configuration.

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []

        # Check project is generated
        step_value = state.step.value if hasattr(state.step, 'value') else state.step
        if step_value not in ("generated", "deployed"):
            errors.append(
                f"Project must be generated before deployment. "
                f"Current step: {step_value}"
            )

        # Check project directory exists
        project_dir = self.state_manager.get_project_dir(state.platform_id)
        if not project_dir.exists():
            errors.append(f"Project directory does not exist: {project_dir}")
            return errors

        # Check all required files exist
        for _asset_type, filename in self.ASSET_FILES.items():
            file_path = project_dir / filename
            if not file_path.exists():
                errors.append(f"Missing asset: {filename}")

        # Check theme base path exists
        theme_base = Path(theme_config.base_path)
        if not theme_base.exists():
            errors.append(f"Theme base path does not exist: {theme_base}")

        return errors

    def deploy(
        self,
        platform_id: str,
        theme_name: str,
        dry_run: bool = False,
        overwrite: bool = True,
    ) -> DeploymentResult:
        """Deploy generated assets to a theme.

        Args:
            platform_id: Platform identifier.
            theme_name: Name of the theme to deploy to.
            dry_run: If True, only simulate deployment.
            overwrite: If True, overwrite existing files.

        Returns:
            DeploymentResult with details of the operation.

        Raises:
            DeploymentError: If deployment cannot proceed.
        """
        # Load project state
        state = self.state_manager.load_state(platform_id)
        if state is None:
            raise DeploymentError(f"Project '{platform_id}' does not exist")

        # Get theme configuration
        theme_config = self.themes_config.get_theme(theme_name)
        if theme_config is None:
            available = ", ".join(self.themes_config.list_themes())
            raise DeploymentError(
                f"Theme '{theme_name}' not found. Available themes: {available}"
            )

        # Validate
        errors = self.validate_deployment(state, theme_config)
        if errors:
            return DeploymentResult(
                success=False,
                theme=theme_name,
                platform_id=platform_id,
                files_deployed={},
                errors=errors,
            )

        # Get paths
        project_dir = self.state_manager.get_project_dir(platform_id)
        target_dir = theme_config.get_assets_path(platform_id)

        files_deployed: dict[str, Path] = {}
        deploy_errors: list[str] = []

        if not dry_run:
            # Create target directory
            target_dir.mkdir(parents=True, exist_ok=True)

        # Copy each file
        for asset_type, filename in self.ASSET_FILES.items():
            source_path = project_dir / filename
            target_path = theme_config.get_file_path(platform_id, asset_type)

            if not source_path.exists():
                deploy_errors.append(f"Source file missing: {source_path}")
                continue

            if target_path.exists() and not overwrite:
                deploy_errors.append(f"Target exists (no overwrite): {target_path}")
                continue

            if not dry_run:
                try:
                    # Ensure parent directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_path)
                    files_deployed[asset_type] = target_path
                except OSError as e:
                    deploy_errors.append(f"Failed to copy {filename}: {e}")
            else:
                # In dry run, just record what would be deployed
                files_deployed[asset_type] = target_path

        # Record deployment in state (only if not dry run and successful)
        if not dry_run and not deploy_errors:
            self.state_manager.add_deployment(
                platform_id,
                theme_name,
                {k: str(v) for k, v in files_deployed.items()},
            )

        return DeploymentResult(
            success=len(deploy_errors) == 0,
            theme=theme_name,
            platform_id=platform_id,
            files_deployed=files_deployed,
            errors=deploy_errors,
        )

    def list_deployments(self, platform_id: str) -> list[dict[str, str | dict[str, str]]]:
        """List all deployments for a project.

        Args:
            platform_id: Platform identifier.

        Returns:
            List of deployment info dicts.
        """
        state = self.state_manager.load_state(platform_id)
        if state is None:
            return []

        return [
            {
                "theme": d.theme,
                "deployed_at": d.deployed_at.isoformat(),
                "files": d.files,
            }
            for d in state.deployments
        ]
