"""Image processing utilities for resizing and transparency."""

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


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
        return img.size


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
    width, height = img.size

    # Sample corner pixels to detect actual background color
    corners = [
        pixels[0, 0][:3],
        pixels[width - 1, 0][:3],
        pixels[0, height - 1][:3],
        pixels[width - 1, height - 1][:3],
    ]

    # Use most common corner color as actual background
    actual_bg = Counter(corners).most_common(1)[0][0]
    bg_r, bg_g, bg_b = actual_bg

    fully_transparent = 0
    partially_transparent = 0
    fully_opaque = 0

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
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
