"""Prompt templates for Gemini image generation."""

from dataclasses import dataclass


@dataclass
class AssetPrompts:
    """Prompt templates for different asset types."""

    @staticmethod
    def build_context(year: str | None, vendor: str | None) -> str:
        """Build context string from year and vendor."""
        parts = []
        if year:
            parts.append(f"Released in {year}.")
        if vendor:
            parts.append(f"Made by {vendor}.")
        return " " + " ".join(parts) if parts else ""

    @staticmethod
    def device(platform_name: str, context: str) -> str:
        return f"""I am providing a reference image showing how device images should look for a gaming frontend theme. Study this reference carefully - note the style, composition, lighting, and presentation.

Now generate a NEW image for the '{platform_name}' gaming system.{context}

IMPORTANT - Use your knowledge of this platform's hardware:
- Research what you know about '{platform_name}' - its actual physical appearance, design, and distinctive features
- The device should be RECOGNIZABLE to fans as the authentic hardware from that era
- Include distinctive design elements that made this system iconic (color scheme, shape, ports, buttons, etc.)
- Accuracy to the real hardware is paramount - do not invent or guess at the design

Requirements matching the reference format:
- Show the complete hardware unit (console/computer) from a similar 3/4 perspective angle
- Use the same clean studio lighting style
- Place on a solid dark charcoal gray background (exact hex #25283B) - NOT transparent
- Photorealistic 3D product render style matching the reference
- No text overlays, no logos, no controllers (unless built-in to the device)
- Device should be centered and fill a similar proportion of the frame
- Match the overall visual quality and presentation of the reference image"""

    @staticmethod
    def logo_dark_color(platform_name: str, context: str) -> str:
        return f"""I am providing a reference logo image from a gaming frontend theme. Study this reference carefully - note the typography style, color usage, positioning, and overall design language. Pay attention to the wide banner aspect ratio.

Now generate a NEW logo for '{platform_name}'.{context}

IMPORTANT - Use your knowledge of this platform's branding:
- Research what you know about '{platform_name}' - its official logo, brand colors, typography, and design language
- The logo should be RECOGNIZABLE to fans of this platform as authentic to the original branding
- Use the correct official brand colors (e.g., Commodore's red/blue, Nintendo's red, Sega's blue, etc.)
- Use typography that matches or evokes the original logo style from that era
- If the platform had an iconic logo mark or symbol, include it appropriately

Requirements matching the reference format:
- Recreate the platform's authentic branding adapted to this frontend's banner format
- CRITICAL: Use EXACTLY solid color background hex #25283B (RGB 37,40,59) - uniform solid color, no gradients
- Logo should be horizontally centered, vertically centered
- IMPORTANT: Match the wide banner format of the reference (text/logo centered in a wide rectangle)
- Clean vector-style appearance matching the reference quality
- No 3D effects unless the original brand used them
- No hardware imagery - text/logo only
- Match the visual weight and proportions shown in the reference"""

    @staticmethod
    def logo_dark_black(platform_name: str, context: str) -> str:
        return f"""I am providing a reference logo image from a gaming frontend theme. Study this reference - it shows a monochrome/white version of a platform logo on a dark background in a wide banner format.

Now generate a NEW monochrome logo for '{platform_name}'.{context}

IMPORTANT - Use your knowledge of this platform's branding:
- Research what you know about '{platform_name}' - its official logo, typography, and design language
- The logo should be RECOGNIZABLE to fans as authentic to the original branding, rendered in monochrome
- Use typography that matches or evokes the original logo style from that era
- If the platform had an iconic logo mark or symbol, include it appropriately

Requirements matching the reference format:
- Recreate the platform's authentic branding in WHITE/LIGHT GRAY monochrome
- CRITICAL: Use EXACTLY solid color background hex #25283B (RGB 37,40,59) - uniform solid color, no gradients
- Logo should be horizontally centered, vertically centered
- IMPORTANT: Match the wide banner format of the reference
- Same layout and typography as the color version, but rendered in white/light gray only
- Clean vector-style appearance matching the reference quality
- No color - strictly monochrome white/gray on dark background
- Match the visual weight and proportions shown in the reference"""

    @staticmethod
    def logo_light_color(platform_name: str, context: str) -> str:
        return f"""I am providing a reference logo image from a gaming frontend theme. Study this reference - it shows a colored platform logo on a light/white background in a wide banner format.

Now generate a NEW colored logo for '{platform_name}'.{context}

IMPORTANT - Use your knowledge of this platform's branding:
- Research what you know about '{platform_name}' - its official logo, brand colors, typography, and design language
- The logo should be RECOGNIZABLE to fans of this platform as authentic to the original branding
- Use the correct official brand colors (e.g., Commodore's red/blue, Nintendo's red, Sega's blue, etc.)
- Use typography that matches or evokes the original logo style from that era
- If the platform had an iconic logo mark or symbol, include it appropriately

Requirements matching the reference format:
- Recreate the platform's authentic branding adapted to this frontend's banner format
- CRITICAL: Use EXACTLY solid white background hex #FFFFFF (RGB 255,255,255) - uniform solid color, no gradients
- Logo should be horizontally centered, vertically centered
- IMPORTANT: Match the wide banner format of the reference
- Clean vector-style appearance matching the reference quality
- Colors should be vibrant and match the original branding
- Match the visual weight and proportions shown in the reference"""

    @staticmethod
    def logo_light_white(platform_name: str, context: str) -> str:
        return f"""I am providing a reference logo image from a gaming frontend theme. Study this reference - it shows a monochrome/black version of a platform logo on a light background in a wide banner format.

Now generate a NEW monochrome logo for '{platform_name}'.{context}

IMPORTANT - Use your knowledge of this platform's branding:
- Research what you know about '{platform_name}' - its official logo, typography, and design language
- The logo should be RECOGNIZABLE to fans as authentic to the original branding, rendered in monochrome
- Use typography that matches or evokes the original logo style from that era
- If the platform had an iconic logo mark or symbol, include it appropriately

Requirements matching the reference format:
- Recreate the platform's authentic branding in BLACK/DARK GRAY monochrome
- CRITICAL: Use EXACTLY solid white background hex #FFFFFF (RGB 255,255,255) - uniform solid color, no gradients
- Logo should be horizontally centered, vertically centered
- IMPORTANT: Match the wide banner format of the reference
- Same layout and typography as the color version, but rendered in black/dark gray only
- Clean vector-style appearance matching the reference quality
- No color - strictly monochrome black/gray on white background
- Match the visual weight and proportions shown in the reference"""


@dataclass
class AssetType:
    """Asset type configuration."""

    name: str
    prompt_fn: callable
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
    """Get list of all asset types to generate."""
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
            name="Logo - Dark Color",
            prompt_fn=AssetPrompts.logo_dark_color,
            reference_key="logo_dark_color",
            aspect_ratio="21:9",
            image_size="2K",
            target_width=logo_width,
            target_height=logo_height,
            bg_type="dark",
            output_filename="logo_dark_color.png",
        ),
        AssetType(
            name="Logo - Dark Black",
            prompt_fn=AssetPrompts.logo_dark_black,
            reference_key="logo_dark_black",
            aspect_ratio="21:9",
            image_size="2K",
            target_width=logo_width,
            target_height=logo_height,
            bg_type="dark",
            output_filename="logo_dark_black.png",
        ),
        AssetType(
            name="Logo - Light Color",
            prompt_fn=AssetPrompts.logo_light_color,
            reference_key="logo_light_color",
            aspect_ratio="21:9",
            image_size="2K",
            target_width=logo_width,
            target_height=logo_height,
            bg_type="light",
            output_filename="logo_light_color.png",
        ),
        AssetType(
            name="Logo - Light White",
            prompt_fn=AssetPrompts.logo_light_white,
            reference_key="logo_light_white",
            aspect_ratio="21:9",
            image_size="2K",
            target_width=logo_width,
            target_height=logo_height,
            bg_type="light",
            output_filename="logo_light_white.png",
        ),
    ]
