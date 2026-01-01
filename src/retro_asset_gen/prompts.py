"""Prompt templates for Nano Banana Pro image generation."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class AssetPrompts:
    """Prompt templates optimized for Nano Banana Pro (Gemini 3 Pro Image)."""

    @staticmethod
    def build_context(year: str | None, vendor: str | None) -> str:
        """Build context string from year and vendor."""
        parts = []
        if year:
            parts.append(f"Released in {year}.")
        if vendor:
            parts.append(f"Manufactured by {vendor}.")
        return " " + " ".join(parts) if parts else ""

    @staticmethod
    def device(platform_name: str, context: str) -> str:
        return f"""Generate a photorealistic product image of the {platform_name} gaming console/computer.{context}

USE GOOGLE SEARCH to find the exact appearance of the {platform_name} hardware. The image must be historically accurate and instantly recognizable to fans of retro gaming.

ACCURACY REQUIREMENTS:
- The {platform_name} must look EXACTLY like the real hardware - correct shape, colors, ports, buttons, vents, and all distinctive design elements
- Search for official product photos, press images, and reference materials for the {platform_name}
- Do NOT invent or approximate the design - reproduce the actual hardware faithfully
- Include all iconic visual elements that make this system recognizable

STYLE REQUIREMENTS (match the reference image):
- 3/4 perspective angle showing the front and one side
- Clean professional studio lighting with soft shadows
- Solid dark charcoal background, exact color hex #25283B (RGB 37,40,59)
- Photorealistic 3D product render quality
- Device centered in frame, filling approximately 70-80% of the image width
- No text overlays, watermarks, or annotations
- No controllers unless they are permanently attached to the unit
- No cables or accessories"""

    @staticmethod
    def logo_color(platform_name: str, context: str) -> str:
        return f"""Generate the official logo for {platform_name} in full color.{context}

USE GOOGLE SEARCH to find the authentic {platform_name} logo. This must be the REAL official logo, not an approximation.

CRITICAL ACCURACY REQUIREMENTS:
- Search for "{platform_name} official logo" and reproduce it EXACTLY
- Use the CORRECT brand colors from the official logo
- Use the EXACT typography/font from the original logo
- Include ALL iconic symbols, emblems, or graphical elements from the official branding
- The logo must be INSTANTLY recognizable to fans as the authentic {platform_name} brand
- Do NOT invent or modify the logo design - reproduce it faithfully

RENDERING REQUIREMENTS:
- Text must be crisp, sharp, and perfectly legible
- Render all text exactly as it appears in the official logo
- Vector-quality clean edges with no artifacts
- Colors should be vibrant and match official brand guidelines exactly

LAYOUT REQUIREMENTS:
- Wide banner format (21:9 aspect ratio)
- Logo horizontally and vertically centered
- CRITICAL: Solid pure white background #FFFFFF (RGB 255,255,255) - absolutely uniform, no gradients, no shadows, no texture
- No hardware imagery, controllers, or game screenshots - logo/text only
- Generous padding around the logo (logo should fill about 60-70% of width)
- Clean minimalist presentation"""


@dataclass
class AssetType:
    """Asset type configuration."""

    name: str
    prompt_fn: Callable[[str, str], str]
    reference_key: str
    aspect_ratio: str
    image_size: str
    target_width: int
    target_height: int
    bg_type: str | None  # None for device (no transparency)
    output_filename: str


def get_asset_types(
    device_width: int = 2160,
    device_height: int = 2160,
    logo_width: int = 1920,
    logo_height: int = 510,
) -> list[AssetType]:
    """Get list of asset types to generate (device + single color logo)."""
    return [
        AssetType(
            name="Device",
            prompt_fn=AssetPrompts.device,
            reference_key="device",
            aspect_ratio="1:1",
            image_size="2K",
            target_width=device_width,
            target_height=device_height,
            bg_type=None,
            output_filename="device.png",
        ),
        AssetType(
            name="Logo",
            prompt_fn=AssetPrompts.logo_color,
            reference_key="logo_light_color",  # Use light color ref for style
            aspect_ratio="21:9",
            image_size="2K",
            target_width=logo_width,
            target_height=logo_height,
            bg_type="light",  # White bg for easy alpha extraction
            output_filename="logo_color_source.png",  # Source for all variants
        ),
    ]
