"""Main asset generation orchestration.

This module handles generating candidate images and finalizing
selected variants into complete asset packs.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from .config import Settings
from .gemini_client import GeminiAPIError, GeminiClient
from .image_processor import (
    AlphaMatteStats,
    create_logo_variants,
    get_image_dimensions,
    has_alpha_channel,
    make_background_transparent,
    resize_image,
)
from .prompts import AssetPrompts, get_asset_types
from .state import ProjectState, StateManager, WorkflowStep


@dataclass
class GeneratedAsset:
    """Information about a generated asset."""

    asset_type: str
    output_path: Path
    dimensions: tuple[int, int]
    has_alpha: bool
    alpha_stats: AlphaMatteStats | None = None


@dataclass
class CandidateGenerationResult:
    """Result of generating candidate images."""

    platform_id: str
    devices_generated: list[str]
    logos_generated: list[str]
    errors: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class FinalizationResult:
    """Result of finalizing selected assets."""

    platform_id: str
    assets: list[GeneratedAsset]
    errors: list[tuple[str, str]] = field(default_factory=list)


class AssetGenerator:
    """Generates platform assets using Gemini API."""

    def __init__(
        self,
        settings: Settings,
        state_manager: StateManager,
        console: Console | None = None,
    ):
        """Initialize the asset generator.

        Args:
            settings: Application settings.
            state_manager: State manager for persistence.
            console: Optional Rich console for output.
        """
        self.settings = settings
        self.state_manager = state_manager
        self.console = console or Console()
        self.client = GeminiClient(
            api_key=settings.gemini_api_key,
            api_url=settings.gemini_api_url,
            enable_google_search=settings.enable_google_search,
        )

    def verify_references(self) -> bool:
        """Verify all reference images exist."""
        self.console.print("[bold]Verifying reference images...[/bold]")
        missing = self.settings.verify_references()
        if missing:
            self.console.print("[red]Missing reference images:[/red]")
            for path in missing:
                self.console.print(f"  [red]✗[/red] {path}")
            return False
        self.console.print("[green]All reference images found.[/green]")
        return True

    def generate_candidates(
        self,
        state: ProjectState,
        delay_between: float = 3.0,
    ) -> CandidateGenerationResult:
        """Generate candidate images for user selection.

        Args:
            state: Project state with platform info and counts.
            delay_between: Delay between API calls in seconds.

        Returns:
            CandidateGenerationResult with generated files and any errors.
        """
        devices_dir = self.state_manager.get_devices_dir(state.platform_id)
        logos_dir = self.state_manager.get_logos_dir(state.platform_id)

        # Ensure directories exist
        devices_dir.mkdir(parents=True, exist_ok=True)
        logos_dir.mkdir(parents=True, exist_ok=True)

        context = AssetPrompts.build_context(
            str(state.year) if state.year else None,
            state.vendor,
        )
        reference_paths = self.settings.get_reference_paths()

        asset_types = get_asset_types(
            device_width=self.settings.device_width,
            device_height=self.settings.device_height,
            logo_width=self.settings.logo_width,
            logo_height=self.settings.logo_height,
        )

        # Find device and logo asset types
        device_type = next((t for t in asset_types if t.name == "Device"), None)
        logo_type = next((t for t in asset_types if t.name == "Logo"), None)

        if not device_type or not logo_type:
            raise RuntimeError("Could not find Device or Logo asset types")

        devices_generated: list[str] = []
        logos_generated: list[str] = []
        errors: list[tuple[str, str]] = []

        total_count = state.device_count + state.logo_count
        current = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Generating {total_count} candidates...",
                total=total_count,
            )

            # Generate device candidates
            for i in range(1, state.device_count + 1):
                progress.update(
                    task,
                    description=f"[cyan]Device {i}/{state.device_count}...",
                )

                filename = f"device_{i:03d}.png"
                output_path = devices_dir / filename

                try:
                    self._generate_single_asset(
                        asset_type=device_type,
                        platform_name=state.platform_name,
                        context=context,
                        reference_path=reference_paths[device_type.reference_key],
                        output_path=output_path,
                    )
                    devices_generated.append(filename)
                    self.console.print(
                        f"  [green]✓[/green] Generated: {filename}"
                    )
                except GeminiAPIError as e:
                    errors.append((f"device_{i}", str(e)))
                    self.console.print(f"  [red]✗[/red] Device {i} error: {e}")
                except Exception as e:
                    errors.append((f"device_{i}", str(e)))
                    self.console.print(f"  [red]✗[/red] Device {i} error: {e}")

                current += 1
                progress.update(task, completed=current)

                if current < total_count and delay_between > 0:
                    time.sleep(delay_between)

            # Generate logo candidates
            for i in range(1, state.logo_count + 1):
                progress.update(
                    task,
                    description=f"[cyan]Logo {i}/{state.logo_count}...",
                )

                filename = f"logo_{i:03d}.png"
                output_path = logos_dir / filename

                try:
                    self._generate_single_asset(
                        asset_type=logo_type,
                        platform_name=state.platform_name,
                        context=context,
                        reference_path=reference_paths[logo_type.reference_key],
                        output_path=output_path,
                    )
                    logos_generated.append(filename)
                    self.console.print(
                        f"  [green]✓[/green] Generated: {filename}"
                    )
                except GeminiAPIError as e:
                    errors.append((f"logo_{i}", str(e)))
                    self.console.print(f"  [red]✗[/red] Logo {i} error: {e}")
                except Exception as e:
                    errors.append((f"logo_{i}", str(e)))
                    self.console.print(f"  [red]✗[/red] Logo {i} error: {e}")

                current += 1
                progress.update(task, completed=current)

                if current < total_count and delay_between > 0:
                    time.sleep(delay_between)

        # Update state with generated candidates
        self.state_manager.update_candidates(
            state.platform_id,
            devices=devices_generated,
            logos=logos_generated,
        )

        return CandidateGenerationResult(
            platform_id=state.platform_id,
            devices_generated=devices_generated,
            logos_generated=logos_generated,
            errors=errors,
        )

    def _generate_single_asset(
        self,
        asset_type: object,  # AssetType from prompts.py
        platform_name: str,
        context: str,
        reference_path: Path,
        output_path: Path,
    ) -> None:
        """Generate a single asset image.

        Args:
            asset_type: Asset type configuration.
            platform_name: Platform name for prompt.
            context: Context string for prompt.
            reference_path: Path to reference image.
            output_path: Where to save the generated image.
        """
        # Type narrowing for mypy
        from .prompts import AssetType
        if not isinstance(asset_type, AssetType):
            raise TypeError("asset_type must be an AssetType")

        prompt = asset_type.prompt_fn(platform_name, context)

        # Generate image
        result = self.client.generate_image_with_reference(
            prompt=prompt,
            reference_image_path=reference_path,
            aspect_ratio=asset_type.aspect_ratio,
            image_size=asset_type.image_size,
        )

        # Save image
        with open(output_path, "wb") as f:
            f.write(result.image_data)

        if result.text_response and len(result.text_response) < 200:
            self.console.print(f"  [dim]Note: {result.text_response}[/dim]")

        # Resize to exact dimensions
        orig_w, orig_h, new_w, new_h = resize_image(
            output_path,
            asset_type.target_width,
            asset_type.target_height,
        )
        if (orig_w, orig_h) != (new_w, new_h):
            self.console.print(
                f"  [dim]Resized: {orig_w}x{orig_h} -> {new_w}x{new_h}[/dim]"
            )

        # Apply transparency if needed (for logos)
        if asset_type.bg_type:
            make_background_transparent(
                output_path,
                bg_type=asset_type.bg_type,
                bg_dark=self.settings.bg_dark,
                bg_light=self.settings.bg_light,
                pure_bg_threshold=self.settings.alpha_bg_threshold,
                pure_fg_threshold=self.settings.alpha_fg_threshold,
            )

    def finalize(self, state: ProjectState) -> FinalizationResult:
        """Finalize selected candidates into the final asset pack.

        This copies the selected device and logo to the final directory,
        then generates all logo variants from the selected logo.

        Args:
            state: Project state with selections.

        Returns:
            FinalizationResult with generated assets and any errors.
        """
        if state.selection.device is None or state.selection.logo is None:
            raise ValueError(
                "Both device and logo must be selected before finalizing"
            )

        if state.step == WorkflowStep.INITIALIZED:
            raise ValueError("Candidates must be generated before finalizing")

        devices_dir = self.state_manager.get_devices_dir(state.platform_id)
        logos_dir = self.state_manager.get_logos_dir(state.platform_id)
        selected_dir = self.state_manager.get_selected_dir(state.platform_id)
        final_dir = self.state_manager.get_final_dir(state.platform_id)

        # Ensure directories exist
        selected_dir.mkdir(parents=True, exist_ok=True)
        final_dir.mkdir(parents=True, exist_ok=True)

        assets: list[GeneratedAsset] = []
        errors: list[tuple[str, str]] = []

        # Get selected files
        device_filename = state.candidates.devices[state.selection.device - 1]
        logo_filename = state.candidates.logos[state.selection.logo - 1]

        selected_device = devices_dir / device_filename
        selected_logo = logos_dir / logo_filename

        # Copy to selected directory
        selected_device_dest = selected_dir / "device.png"
        selected_logo_dest = selected_dir / "logo_base.png"

        self.console.print("\n[bold]Copying selected variants...[/bold]")

        try:
            shutil.copy2(selected_device, selected_device_dest)
            self.console.print(f"  [green]✓[/green] Device: {device_filename}")
        except Exception as e:
            errors.append(("device_copy", str(e)))
            self.console.print(f"  [red]✗[/red] Device copy error: {e}")

        try:
            shutil.copy2(selected_logo, selected_logo_dest)
            self.console.print(f"  [green]✓[/green] Logo: {logo_filename}")
        except Exception as e:
            errors.append(("logo_copy", str(e)))
            self.console.print(f"  [red]✗[/red] Logo copy error: {e}")

        # Copy device to final
        self.console.print("\n[bold]Creating final assets...[/bold]")

        final_device = final_dir / "device.png"
        try:
            shutil.copy2(selected_device_dest, final_device)
            dimensions = get_image_dimensions(final_device)
            assets.append(GeneratedAsset(
                asset_type="device",
                output_path=final_device,
                dimensions=dimensions,
                has_alpha=False,
            ))
            self.console.print(
                f"  [green]✓[/green] device.png ({dimensions[0]}x{dimensions[1]})"
            )
        except Exception as e:
            errors.append(("device_final", str(e)))
            self.console.print(f"  [red]✗[/red] Device finalize error: {e}")

        # Generate logo variants
        self.console.print("\n[bold]Creating logo variants...[/bold]")

        try:
            variants = create_logo_variants(
                source_color_logo=selected_logo_dest,
                output_dir=final_dir,
                platform_id=state.platform_id,
            )

            for variant_name, variant_path in variants.items():
                dimensions = get_image_dimensions(variant_path)
                has_alpha = has_alpha_channel(variant_path)
                assets.append(GeneratedAsset(
                    asset_type=variant_name,
                    output_path=variant_path,
                    dimensions=dimensions,
                    has_alpha=has_alpha,
                ))
                self.console.print(
                    f"  [green]✓[/green] {variant_path.name} "
                    f"({dimensions[0]}x{dimensions[1]})"
                )
        except Exception as e:
            errors.append(("logo_variants", str(e)))
            self.console.print(f"  [red]✗[/red] Logo variants error: {e}")

        # Update state to finalized
        if not errors:
            self.state_manager.mark_finalized(state.platform_id)

        return FinalizationResult(
            platform_id=state.platform_id,
            assets=assets,
            errors=errors,
        )

    def regenerate_device(
        self,
        state: ProjectState,
        index: int,
    ) -> bool:
        """Regenerate a specific device candidate.

        Args:
            state: Project state.
            index: 1-based index of the device to regenerate.

        Returns:
            True if successful, False otherwise.
        """
        if index < 1 or index > state.device_count:
            self.console.print(
                f"[red]Invalid device index: {index}. "
                f"Must be between 1 and {state.device_count}[/red]"
            )
            return False

        devices_dir = self.state_manager.get_devices_dir(state.platform_id)
        filename = f"device_{index:03d}.png"
        output_path = devices_dir / filename

        context = AssetPrompts.build_context(
            str(state.year) if state.year else None,
            state.vendor,
        )
        reference_paths = self.settings.get_reference_paths()

        asset_types = get_asset_types(
            device_width=self.settings.device_width,
            device_height=self.settings.device_height,
            logo_width=self.settings.logo_width,
            logo_height=self.settings.logo_height,
        )
        device_type = next((t for t in asset_types if t.name == "Device"), None)

        if not device_type:
            self.console.print("[red]Could not find Device asset type[/red]")
            return False

        self.console.print(f"\n[bold]Regenerating device {index}...[/bold]")

        try:
            self._generate_single_asset(
                asset_type=device_type,
                platform_name=state.platform_name,
                context=context,
                reference_path=reference_paths[device_type.reference_key],
                output_path=output_path,
            )
            self.console.print(f"  [green]✓[/green] Regenerated: {filename}")
            return True
        except Exception as e:
            self.console.print(f"  [red]✗[/red] Error: {e}")
            return False

    def regenerate_logo(
        self,
        state: ProjectState,
        index: int,
    ) -> bool:
        """Regenerate a specific logo candidate.

        Args:
            state: Project state.
            index: 1-based index of the logo to regenerate.

        Returns:
            True if successful, False otherwise.
        """
        if index < 1 or index > state.logo_count:
            self.console.print(
                f"[red]Invalid logo index: {index}. "
                f"Must be between 1 and {state.logo_count}[/red]"
            )
            return False

        logos_dir = self.state_manager.get_logos_dir(state.platform_id)
        filename = f"logo_{index:03d}.png"
        output_path = logos_dir / filename

        context = AssetPrompts.build_context(
            str(state.year) if state.year else None,
            state.vendor,
        )
        reference_paths = self.settings.get_reference_paths()

        asset_types = get_asset_types(
            device_width=self.settings.device_width,
            device_height=self.settings.device_height,
            logo_width=self.settings.logo_width,
            logo_height=self.settings.logo_height,
        )
        logo_type = next((t for t in asset_types if t.name == "Logo"), None)

        if not logo_type:
            self.console.print("[red]Could not find Logo asset type[/red]")
            return False

        self.console.print(f"\n[bold]Regenerating logo {index}...[/bold]")

        try:
            self._generate_single_asset(
                asset_type=logo_type,
                platform_name=state.platform_name,
                context=context,
                reference_path=reference_paths[logo_type.reference_key],
                output_path=output_path,
            )
            self.console.print(f"  [green]✓[/green] Regenerated: {filename}")
            return True
        except Exception as e:
            self.console.print(f"  [red]✗[/red] Error: {e}")
            return False
