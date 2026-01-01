"""Main asset generation orchestration."""

import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from .config import Settings
from .gemini_client import GeminiAPIError, GeminiClient
from .image_processor import (
    AlphaMatteStats,
    get_image_dimensions,
    has_alpha_channel,
    make_background_transparent,
    resize_image,
)
from .prompts import AssetPrompts, AssetType, get_asset_types


@dataclass
class GeneratedAsset:
    """Information about a generated asset."""

    asset_type: str
    output_path: Path
    dimensions: tuple[int, int]
    has_alpha: bool
    alpha_stats: AlphaMatteStats | None = None


@dataclass
class GenerationReport:
    """Report of all generated assets."""

    platform_id: str
    platform_name: str
    output_dir: Path
    assets: list[GeneratedAsset]
    errors: list[tuple[str, str]]


class AssetGenerator:
    """Generates platform assets using Gemini API."""

    def __init__(
        self,
        settings: Settings,
        console: Console | None = None,
    ):
        self.settings = settings
        self.console = console or Console()
        self.client = GeminiClient(
            api_key=settings.gemini_api_key,
            api_url=settings.gemini_api_url,
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

    def generate(
        self,
        platform_id: str,
        platform_name: str,
        year: str | None = None,
        vendor: str | None = None,
        delay_between: float = 3.0,
    ) -> GenerationReport:
        """
        Generate all assets for a platform.

        Args:
            platform_id: Short platform identifier (e.g., "snes")
            platform_name: Full platform name (e.g., "Super Nintendo")
            year: Optional release year
            vendor: Optional vendor/manufacturer
            delay_between: Delay between API calls in seconds

        Returns:
            GenerationReport with all generated assets
        """
        output_dir = self.settings.output_dir / platform_id
        output_dir.mkdir(parents=True, exist_ok=True)

        context = AssetPrompts.build_context(year, vendor)
        reference_paths = self.settings.get_reference_paths()

        asset_types = get_asset_types(
            device_width=self.settings.device_width,
            device_height=self.settings.device_height,
            logo_width=self.settings.logo_width,
            logo_height=self.settings.logo_height,
        )

        generated: list[GeneratedAsset] = []
        errors: list[tuple[str, str]] = []

        for i, asset_type in enumerate(asset_types, 1):
            self.console.print(
                f"\n[bold cyan][{i}/{len(asset_types)}][/bold cyan] "
                f"Generating {asset_type.name}..."
            )

            try:
                asset = self._generate_asset(
                    asset_type=asset_type,
                    platform_name=platform_name,
                    context=context,
                    reference_path=reference_paths[asset_type.reference_key],
                    output_dir=output_dir,
                )
                generated.append(asset)
                self.console.print(
                    f"  [green]✓[/green] Generated: {asset.output_path.name} "
                    f"({asset.dimensions[0]}x{asset.dimensions[1]})"
                )
                if asset.alpha_stats:
                    self.console.print(
                        f"  [dim]Alpha: bg={asset.alpha_stats.actual_bg}, "
                        f"transparent={asset.alpha_stats.transparent_pct:.1f}%, "
                        f"edges={asset.alpha_stats.edges_pct:.1f}%, "
                        f"opaque={asset.alpha_stats.opaque_pct:.1f}%[/dim]"
                    )
            except GeminiAPIError as e:
                errors.append((asset_type.name, str(e)))
                self.console.print(f"  [red]✗[/red] Error: {e}")
            except Exception as e:
                errors.append((asset_type.name, str(e)))
                self.console.print(f"  [red]✗[/red] Unexpected error: {e}")

            # Delay between requests (except last one)
            if i < len(asset_types) and delay_between > 0:
                time.sleep(delay_between)

        return GenerationReport(
            platform_id=platform_id,
            platform_name=platform_name,
            output_dir=output_dir,
            assets=generated,
            errors=errors,
        )

    def _generate_asset(
        self,
        asset_type: AssetType,
        platform_name: str,
        context: str,
        reference_path: Path,
        output_dir: Path,
    ) -> GeneratedAsset:
        """Generate a single asset."""
        prompt = asset_type.prompt_fn(platform_name, context)
        output_path = output_dir / asset_type.output_filename

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

        # Apply transparency if needed
        alpha_stats = None
        if asset_type.bg_type:
            alpha_stats = make_background_transparent(
                output_path,
                bg_type=asset_type.bg_type,
                bg_dark=self.settings.bg_dark,
                bg_light=self.settings.bg_light,
                pure_bg_threshold=self.settings.alpha_bg_threshold,
                pure_fg_threshold=self.settings.alpha_fg_threshold,
            )

        dimensions = get_image_dimensions(output_path)
        has_alpha = has_alpha_channel(output_path)

        return GeneratedAsset(
            asset_type=asset_type.name,
            output_path=output_path,
            dimensions=dimensions,
            has_alpha=has_alpha,
            alpha_stats=alpha_stats,
        )
