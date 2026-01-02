"""Prompt templates for Nano Banana Pro image generation.

These prompts use user-provided reference images for accurate reproduction.
"""

from dataclasses import dataclass


@dataclass
class AssetPrompts:
    """Prompt templates optimized for Nano Banana Pro (Gemini 3 Pro Image).

    These prompts are designed to work with user-provided reference images
    to generate accurate platform assets.
    """

    @staticmethod
    def device(platform_name: str) -> str:
        """Generate prompt for device/console image.

        The user provides a reference image (platform.jpg) showing the actual hardware.
        This prompt instructs the model to recreate it in the target style.
        """
        return f"""Generate a photorealistic product image of the {platform_name} gaming console/computer based on the reference image provided.

The reference image shows the actual {platform_name} hardware. Reproduce this EXACTLY in a clean studio product shot style.

ACCURACY REQUIREMENTS:
- Match the reference image EXACTLY - same shape, colors, ports, buttons, vents, and all design elements
- The {platform_name} must be instantly recognizable and historically accurate
- Include all iconic visual elements visible in the reference

STYLE REQUIREMENTS:
- 3/4 perspective angle showing the front and one side (similar to reference if applicable)
- Clean professional studio lighting with soft shadows
- Photorealistic 3D product render quality
- Device centered in frame, filling approximately 70-80% of the image width
- No text overlays, watermarks, or annotations
- No controllers unless they are permanently attached to the unit
- No cables or accessories

CRITICAL BACKGROUND REQUIREMENT:
- Solid bright fluorescent green background, exact color hex #00FF00 (RGB 0,255,0)
- SHARP HARD EDGES between the device and the green background - NO blur, NO feathering, NO gradients, NO shadows bleeding into background
- The green background must be perfectly uniform with ZERO variation
- This is for chroma key extraction - clean edges are essential"""

    @staticmethod
    def logo(platform_name: str) -> str:
        """Generate prompt for logo image.

        The user provides a reference image (logo.png) showing the actual logo.
        This prompt instructs the model to recreate it cleanly.
        """
        return f"""Reproduce the {platform_name} logo exactly as shown in the reference image.

The reference image shows the official {platform_name} logo. Recreate this EXACTLY.

CRITICAL ACCURACY REQUIREMENTS:
- Match the reference logo EXACTLY - same typography, colors, layout, and graphical elements
- Use the EXACT colors from the reference logo
- Use the EXACT typography/font from the reference logo
- Include ALL elements (symbols, emblems, text) exactly as shown
- The logo must be IDENTICAL to the reference

RENDERING REQUIREMENTS:
- Text must be crisp, sharp, and perfectly legible
- Vector-quality clean edges with no artifacts
- Colors should be vibrant and match the reference exactly

LAYOUT REQUIREMENTS:
- Wide banner format (21:9 aspect ratio)
- Logo horizontally and vertically centered
- Generous padding around the logo (logo should fill about 60-70% of width)
- Clean minimalist presentation

CRITICAL BACKGROUND REQUIREMENT:
- Solid bright fluorescent green background, exact color hex #00FF00 (RGB 0,255,0)
- SHARP HARD EDGES between the logo and the green background - NO blur, NO feathering, NO gradients, NO anti-aliasing at edges
- The green background must be perfectly uniform with ZERO variation
- This is for chroma key extraction - clean edges are essential"""


@dataclass
class AssetType:
    """Asset type configuration."""

    name: str
    aspect_ratio: str
    image_size: str
    target_width: int
    target_height: int
    bg_type: str | None  # None for device (no transparency), "light" for logo
    output_filename: str


def get_device_type(
    width: int = 2160,
    height: int = 2160,
) -> AssetType:
    """Get device asset type configuration."""
    return AssetType(
        name="device",
        aspect_ratio="1:1",
        image_size="2K",
        target_width=width,
        target_height=height,
        bg_type="dark",  # Dark bg (#25283B) for alpha extraction
        output_filename="device.png",
    )


def get_logo_type(
    width: int = 1920,
    height: int = 510,
) -> AssetType:
    """Get logo asset type configuration."""
    return AssetType(
        name="logo",
        aspect_ratio="21:9",
        image_size="2K",
        target_width=width,
        target_height=height,
        bg_type="light",  # White bg for alpha extraction
        output_filename="logo.png",
    )
