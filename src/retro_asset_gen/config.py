"""Configuration management using Pydantic Settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Configuration
    gemini_api_key: str = Field(description="Gemini API key (required)")
    gemini_api_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent",
        description="Gemini API endpoint",
    )

    # Output Configuration
    output_dir: Path = Field(
        default=Path("/Volumes/RETRO/temp_platform_assets"),
        alias="RETRO_OUTPUT_DIR",
        description="Output directory for generated assets",
    )

    # Theme Configuration
    theme_base: Path = Field(
        default=Path("/Volumes/RETRO/frontends/Pegasus_mac/themes/COLORFUL/assets/images"),
        alias="RETRO_THEME_BASE",
        description="Theme base path for reference images",
    )

    # Reference Platform
    reference_platform: str = Field(
        default="snes",
        description="Reference platform for style matching",
    )

    # Image Dimensions
    device_width: int = Field(default=2160, description="Device image width")
    device_height: int = Field(default=2160, description="Device image height")
    logo_width: int = Field(default=1920, description="Logo image width")
    logo_height: int = Field(default=510, description="Logo image height")

    # Alpha Matte Thresholds
    alpha_bg_threshold: int = Field(
        default=15,
        description="Below this distance = fully transparent",
    )
    alpha_fg_threshold: int = Field(
        default=80,
        description="Above this distance = fully opaque",
    )

    # Background Colors
    bg_dark: tuple[int, int, int] = Field(
        default=(37, 40, 59),
        description="Dark background color RGB (#25283B)",
    )
    bg_light: tuple[int, int, int] = Field(
        default=(255, 255, 255),
        description="Light background color RGB (#FFFFFF)",
    )

    @property
    def ref_device_path(self) -> Path:
        return self.theme_base / "devices" / f"{self.reference_platform}.png"

    @property
    def ref_logo_dark_black_path(self) -> Path:
        return self.theme_base / "logos" / "Dark - Black" / f"{self.reference_platform}.png"

    @property
    def ref_logo_dark_color_path(self) -> Path:
        return self.theme_base / "logos" / "Dark - Color" / f"{self.reference_platform}.png"

    @property
    def ref_logo_light_color_path(self) -> Path:
        return self.theme_base / "logos" / "Light - Color" / f"{self.reference_platform}.png"

    @property
    def ref_logo_light_white_path(self) -> Path:
        return self.theme_base / "logos" / "Light - White" / f"{self.reference_platform}.png"

    def get_reference_paths(self) -> dict[str, Path]:
        """Return all reference image paths."""
        return {
            "device": self.ref_device_path,
            "logo_dark_black": self.ref_logo_dark_black_path,
            "logo_dark_color": self.ref_logo_dark_color_path,
            "logo_light_color": self.ref_logo_light_color_path,
            "logo_light_white": self.ref_logo_light_white_path,
        }

    def verify_references(self) -> list[str]:
        """Verify all reference images exist. Returns list of missing paths."""
        missing = []
        for name, path in self.get_reference_paths().items():
            if not path.exists():
                missing.append(f"{name}: {path}")
        return missing


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
