"""Main asset generation orchestration.

This module handles generating platform assets from user-provided reference images.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from rich.console import Console

from .config import Settings
from .gemini_client import GeminiAPIError, GeminiClient
from .image_processor import (
    AlphaMatteStats,
    create_logo_variants_theme_structure,
    get_image_dimensions,
    has_alpha_channel,
    make_background_transparent,
    quantize_png,
    resize_image,
)
from .prompts import AssetPrompts, get_device_type, get_logo_type


def save_as_png(image_data: bytes, output_path: Path) -> None:
    """Save image data as PNG, converting from any format if necessary."""
    img: Image.Image = Image.open(io.BytesIO(image_data))
    # Convert to RGB/RGBA as needed
    if img.mode == "RGBA":
        pass  # Keep RGBA
    elif img.mode in ("RGB", "L", "P"):
        img = img.convert("RGB")
    else:
        img = img.convert("RGB")
    img.save(output_path, "PNG")


@dataclass
class GeneratedAsset:
    """Information about a generated asset."""

    asset_type: str
    output_path: Path
    dimensions: tuple[int, int]
    has_alpha: bool
    alpha_stats: AlphaMatteStats | None = None


@dataclass
class GenerationResult:
    """Result of generating platform assets."""

    platform_id: str
    assets: list[GeneratedAsset] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return True if at least some assets were generated."""
        return len(self.assets) > 0


class AssetGenerator:
    """Generates platform assets using Gemini API and user-provided references."""

    def __init__(
        self,
        settings: Settings,
        console: Console | None = None,
    ):
        """Initialize the asset generator.

        Args:
            settings: Application settings.
            console: Optional Rich console for output.
        """
        self.settings = settings
        self.console = console or Console()
        self.client = GeminiClient(
            api_key=settings.gemini_api_key,
            api_url=settings.gemini_api_url,
            enable_google_search=settings.enable_google_search,
        )

    def verify_references(self, platform_id: str) -> list[str]:
        """Verify reference images exist for a platform.

        Returns list of missing references (empty if all present).
        """
        return self.settings.verify_input_references(platform_id)

    def generate(
        self,
        platform_id: str,
        platform_name: str,
    ) -> GenerationResult:
        """Generate all assets for a platform.

        Uses reference images from .input/<platform_id>/:
        - platform.jpg/png - reference for device generation
        - logo.png/jpg - reference for logo generation

        Args:
            platform_id: Platform identifier (e.g., 'amigacd32')
            platform_name: Full platform name (e.g., 'Commodore Amiga CD32')

        Returns:
            GenerationResult with generated assets and any errors.
        """
        result = GenerationResult(platform_id=platform_id)

        # Get reference paths
        platform_ref = self.settings.get_platform_reference(platform_id)
        logo_ref = self.settings.get_logo_reference(platform_id)

        if not platform_ref or not logo_ref:
            missing = self.verify_references(platform_id)
            for m in missing:
                result.errors.append(("references", m))
            return result

        # Create output directories matching theme structure
        base_dir = self.settings.output_dir / "assets" / "images"
        devices_dir = base_dir / "devices"
        logos_dark_black_dir = base_dir / "logos" / "Dark - Black"
        logos_dark_color_dir = base_dir / "logos" / "Dark - Color"
        logos_light_color_dir = base_dir / "logos" / "Light - Color"
        logos_light_white_dir = base_dir / "logos" / "Light - White"

        for d in [devices_dir, logos_dark_black_dir, logos_dark_color_dir,
                  logos_light_color_dir, logos_light_white_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Generate device image
        self.console.print("\n[bold cyan]Generating device image...[/bold cyan]")
        device_asset = self._generate_device(
            platform_name=platform_name,
            platform_id=platform_id,
            reference_path=platform_ref,
            output_dir=devices_dir,
        )
        if device_asset:
            result.assets.append(device_asset)
        else:
            result.errors.append(("device", "Failed to generate device image"))

        # Generate logo image (to temp location, then create variants)
        self.console.print("\n[bold cyan]Generating logo image...[/bold cyan]")
        logo_asset = self._generate_logo(
            platform_name=platform_name,
            platform_id=platform_id,
            reference_path=logo_ref,
            output_dir=logos_light_color_dir,  # Base goes to Light - Color
        )
        if logo_asset:
            result.assets.append(logo_asset)

            # Generate logo variants from the base logo
            self.console.print("\n[bold cyan]Creating logo variants...[/bold cyan]")
            try:
                variants = create_logo_variants_theme_structure(
                    source_color_logo=logo_asset.output_path,
                    platform_id=platform_id,
                    logos_dark_black_dir=logos_dark_black_dir,
                    logos_dark_color_dir=logos_dark_color_dir,
                    logos_light_color_dir=logos_light_color_dir,
                    logos_light_white_dir=logos_light_white_dir,
                )
                for variant_name, variant_path in variants.items():
                    dimensions = get_image_dimensions(variant_path)
                    has_alpha = has_alpha_channel(variant_path)
                    result.assets.append(GeneratedAsset(
                        asset_type=variant_name,
                        output_path=variant_path,
                        dimensions=dimensions,
                        has_alpha=has_alpha,
                    ))
                    self.console.print(
                        f"  [green]✓[/green] {variant_path.relative_to(self.settings.output_dir)} "
                        f"({dimensions[0]}x{dimensions[1]})"
                    )
            except Exception as e:
                result.errors.append(("logo_variants", str(e)))
                self.console.print(f"  [red]✗[/red] Logo variants error: {e}")
        else:
            result.errors.append(("logo", "Failed to generate logo image"))

        # Quantize all generated PNGs if enabled
        if self.settings.enable_quantization and result.assets:
            self.console.print("\n[bold cyan]Quantizing images...[/bold cyan]")
            total_original = 0
            total_quantized = 0

            for asset in result.assets:
                qr = quantize_png(
                    asset.output_path,
                    quality=self.settings.quantization_quality,
                )
                total_original += qr.original_size
                total_quantized += qr.quantized_size

                if qr.method == "pngquant" and qr.reduction_pct > 0:
                    self.console.print(
                        f"  [green]✓[/green] {asset.output_path.name} "
                        f"({self._format_size(qr.original_size)} → "
                        f"{self._format_size(qr.quantized_size)}, "
                        f"-{qr.reduction_pct:.0f}%)"
                    )

            if total_original > 0:
                total_reduction = (1 - total_quantized / total_original) * 100
                self.console.print(
                    f"  [dim]Total: {self._format_size(total_original)} → "
                    f"{self._format_size(total_quantized)} (-{total_reduction:.0f}%)[/dim]"
                )

        return result

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"

    def _generate_device(
        self,
        platform_name: str,
        platform_id: str,
        reference_path: Path,
        output_dir: Path,
    ) -> GeneratedAsset | None:
        """Generate device image using reference.

        Args:
            platform_name: Platform name for prompt
            platform_id: Platform identifier for filename
            reference_path: Path to reference platform image
            output_dir: Output directory

        Returns:
            GeneratedAsset if successful, None otherwise
        """
        device_type = get_device_type(
            width=self.settings.device_width,
            height=self.settings.device_height,
        )
        output_path = output_dir / f"{platform_id}.png"
        prompt = AssetPrompts.device(platform_name)

        try:
            result = self.client.generate_image_with_reference(
                prompt=prompt,
                reference_image_path=reference_path,
                aspect_ratio=device_type.aspect_ratio,
                image_size=device_type.image_size,
            )

            # Save image as PNG (converting if necessary)
            save_as_png(result.image_data, output_path)

            if result.text_response and len(result.text_response) < 200:
                self.console.print(f"  [dim]Note: {result.text_response}[/dim]")

            # Resize to exact dimensions
            orig_w, orig_h, new_w, new_h = resize_image(
                output_path,
                device_type.target_width,
                device_type.target_height,
            )
            if (orig_w, orig_h) != (new_w, new_h):
                self.console.print(
                    f"  [dim]Resized: {orig_w}x{orig_h} -> {new_w}x{new_h}[/dim]"
                )

            dimensions = get_image_dimensions(output_path)
            self.console.print(
                f"  [green]✓[/green] {output_path.name} "
                f"({dimensions[0]}x{dimensions[1]})"
            )

            return GeneratedAsset(
                asset_type="device",
                output_path=output_path,
                dimensions=dimensions,
                has_alpha=False,
            )

        except GeminiAPIError as e:
            self.console.print(f"  [red]✗[/red] API error: {e}")
            return None
        except Exception as e:
            self.console.print(f"  [red]✗[/red] Error: {e}")
            return None

    def _generate_logo(
        self,
        platform_name: str,
        platform_id: str,
        reference_path: Path,
        output_dir: Path,
    ) -> GeneratedAsset | None:
        """Generate logo image using reference.

        Args:
            platform_name: Platform name for prompt
            platform_id: Platform identifier for filename
            reference_path: Path to reference logo image
            output_dir: Output directory

        Returns:
            GeneratedAsset if successful, None otherwise
        """
        logo_type = get_logo_type(
            width=self.settings.logo_width,
            height=self.settings.logo_height,
        )
        output_path = output_dir / f"{platform_id}.png"
        prompt = AssetPrompts.logo(platform_name)

        try:
            result = self.client.generate_image_with_reference(
                prompt=prompt,
                reference_image_path=reference_path,
                aspect_ratio=logo_type.aspect_ratio,
                image_size=logo_type.image_size,
            )

            # Save image as PNG (converting if necessary)
            save_as_png(result.image_data, output_path)

            if result.text_response and len(result.text_response) < 200:
                self.console.print(f"  [dim]Note: {result.text_response}[/dim]")

            # Resize to exact dimensions
            orig_w, orig_h, new_w, new_h = resize_image(
                output_path,
                logo_type.target_width,
                logo_type.target_height,
            )
            if (orig_w, orig_h) != (new_w, new_h):
                self.console.print(
                    f"  [dim]Resized: {orig_w}x{orig_h} -> {new_w}x{new_h}[/dim]"
                )

            # Apply transparency (white background -> transparent)
            if logo_type.bg_type:
                make_background_transparent(
                    output_path,
                    bg_type=logo_type.bg_type,
                    bg_dark=self.settings.bg_dark,
                    bg_light=self.settings.bg_light,
                    pure_bg_threshold=self.settings.alpha_bg_threshold,
                    pure_fg_threshold=self.settings.alpha_fg_threshold,
                )

            dimensions = get_image_dimensions(output_path)
            has_alpha = has_alpha_channel(output_path)
            self.console.print(
                f"  [green]✓[/green] {output_path.name} "
                f"({dimensions[0]}x{dimensions[1]})"
            )

            return GeneratedAsset(
                asset_type="logo",
                output_path=output_path,
                dimensions=dimensions,
                has_alpha=has_alpha,
            )

        except GeminiAPIError as e:
            self.console.print(f"  [red]✗[/red] API error: {e}")
            return None
        except Exception as e:
            self.console.print(f"  [red]✗[/red] Error: {e}")
            return None
