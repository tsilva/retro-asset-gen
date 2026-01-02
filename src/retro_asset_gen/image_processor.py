"""Image processing utilities for resizing and transparency."""

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import imagequant  # type: ignore[import-untyped]
from PIL import Image


@dataclass
class QuantizeResult:
    """Result of PNG quantization."""

    original_size: int
    quantized_size: int
    reduction_pct: float
    method: str  # "imagequant" or "skipped"


def quantize_png(
    image_path: Path,
    quality: str = "65-80",
) -> QuantizeResult:
    """
    Quantize a PNG image using libimagequant for smaller file sizes.

    Args:
        image_path: Path to the PNG image to quantize
        quality: Quality range (e.g., "65-80") - uses max value

    Returns:
        QuantizeResult with size information
    """
    original_size = image_path.stat().st_size

    # Parse quality range (e.g., "65-80" -> min=65, max=80)
    try:
        if "-" in quality:
            min_q, max_q = map(int, quality.split("-"))
        else:
            min_q, max_q = int(quality), int(quality)
    except ValueError:
        min_q, max_q = 65, 80

    try:
        # Open image
        img: Image.Image = Image.open(image_path)

        # Convert to RGBA if not already
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Quantize using libimagequant
        quantized_img = imagequant.quantize_pil_image(
            img,
            dithering_level=1.0,
            max_colors=256,
            min_quality=min_q,
            max_quality=max_q,
        )

        # Save quantized image
        quantized_img.save(image_path, "PNG", optimize=True)

        quantized_size = image_path.stat().st_size
        reduction_pct = (1 - quantized_size / original_size) * 100

        return QuantizeResult(
            original_size=original_size,
            quantized_size=quantized_size,
            reduction_pct=reduction_pct,
            method="imagequant",
        )
    except Exception:
        # Quantization can fail for some images
        return QuantizeResult(
            original_size=original_size,
            quantized_size=original_size,
            reduction_pct=0.0,
            method="skipped",
        )


@dataclass
class AlphaMatteStats:
    """Statistics from alpha matte processing."""

    actual_bg: tuple[int, int, int]
    transparent_pct: float
    edges_pct: float
    opaque_pct: float


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    """Get image width and height."""
    with Image.open(image_path) as img:
        return cast(tuple[int, int], img.size)


def resize_image(
    image_path: Path,
    target_width: int,
    target_height: int,
) -> tuple[int, int, int, int]:
    """
    Resize image to exact dimensions.

    Returns:
        Tuple of (original_width, original_height, new_width, new_height)
    """
    with Image.open(image_path) as img:
        original_size = img.size

        if original_size == (target_width, target_height):
            return (*original_size, *original_size)

        resized = img.resize(
            (target_width, target_height),
            Image.Resampling.LANCZOS,
        )
        resized.save(image_path, "PNG")

        return (*original_size, target_width, target_height)


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Calculate Euclidean distance in RGB space."""
    return math.sqrt(
        (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2
    )


def _clamp(val: float, min_val: int = 0, max_val: int = 255) -> int:
    """Clamp value to range."""
    return max(min_val, min(max_val, int(round(val))))


def make_background_transparent(
    image_path: Path,
    bg_type: str,
    bg_dark: tuple[int, int, int] = (37, 40, 59),
    bg_light: tuple[int, int, int] = (255, 255, 255),
    pure_bg_threshold: int = 15,
    pure_fg_threshold: int = 80,
) -> AlphaMatteStats:
    """
    Remove background color and apply alpha matting with color decontamination.

    Args:
        image_path: Path to the image to process
        bg_type: "dark" or "light" background type
        bg_dark: RGB tuple for dark background color
        bg_light: RGB tuple for light background color
        pure_bg_threshold: Below this distance = fully transparent
        pure_fg_threshold: Above this distance = fully opaque

    Returns:
        AlphaMatteStats with processing statistics
    """
    _ = bg_dark if bg_type == "dark" else bg_light  # reserved for future use

    img = Image.open(image_path).convert("RGBA")
    pixels = img.load()
    assert pixels is not None, "Failed to load image pixels"
    width, height = img.size

    # Sample corner pixels to detect actual background color
    corners: list[tuple[int, int, int]] = [
        cast(tuple[int, int, int, int], pixels[0, 0])[:3],
        cast(tuple[int, int, int, int], pixels[width - 1, 0])[:3],
        cast(tuple[int, int, int, int], pixels[0, height - 1])[:3],
        cast(tuple[int, int, int, int], pixels[width - 1, height - 1])[:3],
    ]

    # Use most common corner color as actual background
    actual_bg: tuple[int, int, int] = Counter(corners).most_common(1)[0][0]
    bg_r, bg_g, bg_b = actual_bg

    fully_transparent = 0
    partially_transparent = 0
    fully_opaque = 0

    for y in range(height):
        for x in range(width):
            pixel = cast(tuple[int, int, int, int], pixels[x, y])
            r, g, b, a = pixel
            dist = _color_distance((r, g, b), actual_bg)

            if dist <= pure_bg_threshold:
                # Pure background - fully transparent
                pixels[x, y] = (r, g, b, 0)
                fully_transparent += 1

            elif dist >= pure_fg_threshold:
                # Pure foreground - fully opaque
                pixels[x, y] = (r, g, b, 255)
                fully_opaque += 1

            else:
                # Edge pixel - graduated alpha with color decontamination
                alpha_float = (dist - pure_bg_threshold) / (
                    pure_fg_threshold - pure_bg_threshold
                )
                alpha = _clamp(alpha_float * 255)

                # Color decontamination: remove background color contribution
                # Original: C = alpha * Foreground + (1-alpha) * Background
                # Solve: F = (C - (1-alpha)*B) / alpha
                if alpha_float > 0.01:
                    new_r = _clamp((r - (1 - alpha_float) * bg_r) / alpha_float)
                    new_g = _clamp((g - (1 - alpha_float) * bg_g) / alpha_float)
                    new_b = _clamp((b - (1 - alpha_float) * bg_b) / alpha_float)
                else:
                    new_r, new_g, new_b = r, g, b

                pixels[x, y] = (new_r, new_g, new_b, alpha)
                partially_transparent += 1

    img.save(image_path, "PNG")

    total = width * height
    return AlphaMatteStats(
        actual_bg=actual_bg,
        transparent_pct=fully_transparent / total * 100,
        edges_pct=partially_transparent / total * 100,
        opaque_pct=fully_opaque / total * 100,
    )


def has_alpha_channel(image_path: Path) -> bool:
    """Check if image has alpha channel."""
    with Image.open(image_path) as img:
        return img.mode in ("RGBA", "LA", "PA")


def chroma_key_transparency(
    image_path: Path,
    tolerance: int = 100,
) -> None:
    """
    Remove green screen background using chroma key.

    Detects green-dominant pixels (G > R and G > B by threshold) and makes them transparent.
    Works with varying shades of green background.

    Args:
        image_path: Path to the image to process
        tolerance: How much greener G must be than R and B (default 50)
    """
    img = Image.open(image_path).convert("RGBA")
    pixels = img.load()
    assert pixels is not None, "Failed to load image pixels"
    width, height = img.size

    for y in range(height):
        for x in range(width):
            pixel = cast(tuple[int, int, int, int], pixels[x, y])
            r, g, b, a = pixel

            # Detect green-dominant pixels (green screen)
            # G channel must be significantly higher than R and B
            is_green = g > r + 30 and g > b + 30 and g > 100

            if is_green:
                pixels[x, y] = (r, g, b, 0)  # Fully transparent

    img.save(image_path, "PNG")


def convert_to_monochrome(
    source_path: Path,
    output_path: Path,
    target_color: tuple[int, int, int],
) -> None:
    """
    Convert a transparent PNG to monochrome while preserving alpha.

    Takes the luminance of each pixel and applies the target color,
    preserving the original alpha channel.

    Args:
        source_path: Path to source image (RGBA with transparency)
        output_path: Path to save the monochrome result
        target_color: RGB tuple for the monochrome color (e.g., white or black)
    """
    img = Image.open(source_path).convert("RGBA")
    pixels = img.load()
    assert pixels is not None, "Failed to load image pixels"
    width, height = img.size

    target_r, target_g, target_b = target_color

    for y in range(height):
        for x in range(width):
            pixel = cast(tuple[int, int, int, int], pixels[x, y])
            r, g, b, a = pixel

            if a > 0:
                # Apply target color, preserve alpha
                pixels[x, y] = (target_r, target_g, target_b, a)

    img.save(output_path, "PNG")


def create_logo_variants_theme_structure(
    source_color_logo: Path,
    platform_id: str,
    logos_dark_black_dir: Path,
    logos_dark_color_dir: Path,
    logos_light_color_dir: Path,
    logos_light_white_dir: Path,
) -> dict[str, Path]:
    """
    Create all logo variants matching theme directory structure.

    The source logo is already in logos_light_color_dir as {platform_id}.png.
    This creates the other 3 variants in their respective directories.

    Args:
        source_color_logo: Path to the color logo with transparency
        platform_id: Platform identifier for filenames
        logos_dark_black_dir: Directory for Dark - Black logos
        logos_dark_color_dir: Directory for Dark - Color logos
        logos_light_color_dir: Directory for Light - Color logos
        logos_light_white_dir: Directory for Light - White logos

    Returns:
        Dict mapping variant name to output path (excludes source which is already saved)
    """
    variants: dict[str, Path] = {}
    filename = f"{platform_id}.png"

    img = Image.open(source_color_logo)

    # Dark - Color: copy of the color logo
    dark_color_path = logos_dark_color_dir / filename
    img.save(dark_color_path, "PNG")
    variants["Dark - Color"] = dark_color_path

    # Dark - Black: white monochrome for dark backgrounds
    dark_black_path = logos_dark_black_dir / filename
    convert_to_monochrome(source_color_logo, dark_black_path, (255, 255, 255))
    variants["Dark - Black"] = dark_black_path

    # Light - White: black monochrome for light backgrounds
    light_white_path = logos_light_white_dir / filename
    convert_to_monochrome(source_color_logo, light_white_path, (0, 0, 0))
    variants["Light - White"] = light_white_path

    img.close()
    return variants
