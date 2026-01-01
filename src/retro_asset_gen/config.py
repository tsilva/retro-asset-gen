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
        default="https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent",
        description="Gemini API endpoint (Nano Banana Pro)",
    )

    # Input Configuration - user provides reference images here
    input_dir: Path = Field(
        default=Path(".input"),
        alias="RETRO_INPUT_DIR",
        description="Input directory for user-provided reference images",
    )

    # Output Configuration
    output_dir: Path = Field(
        default=Path("output"),
        alias="RETRO_OUTPUT_DIR",
        description="Output directory for generated assets",
    )

    # Theme Configuration (for deployment)
    theme_base: Path = Field(
        default=Path("/Volumes/RETRO/frontends/Pegasus_mac/themes/COLORFUL/assets/images"),
        alias="RETRO_THEME_BASE",
        description="Theme base path for deployment",
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

    # Nano Banana Pro Features
    enable_google_search: bool = Field(
        default=True,
        description="Enable Google Search for real-world knowledge of platforms/branding",
    )

    def get_input_dir(self, platform_id: str) -> Path:
        """Get input directory for a platform."""
        return self.input_dir / platform_id

    def get_platform_reference(self, platform_id: str) -> Path | None:
        """Get platform/console reference image path (platform.jpg or platform.png)."""
        input_dir = self.get_input_dir(platform_id)
        for ext in [".jpg", ".jpeg", ".png"]:
            path = input_dir / f"platform{ext}"
            if path.exists():
                return path
        return None

    def get_logo_reference(self, platform_id: str) -> Path | None:
        """Get logo reference image path (logo.png or logo.jpg)."""
        input_dir = self.get_input_dir(platform_id)
        for ext in [".png", ".jpg", ".jpeg"]:
            path = input_dir / f"logo{ext}"
            if path.exists():
                return path
        return None

    def verify_input_references(self, platform_id: str) -> list[str]:
        """Verify input reference images exist for a platform. Returns list of missing."""
        missing = []
        input_dir = self.get_input_dir(platform_id)

        if not input_dir.exists():
            missing.append(f"Input directory: {input_dir}")
            return missing

        if not self.get_platform_reference(platform_id):
            missing.append(f"Platform reference: {input_dir}/platform.(jpg|png)")

        if not self.get_logo_reference(platform_id):
            missing.append(f"Logo reference: {input_dir}/logo.(png|jpg)")

        return missing


def get_settings() -> Settings:
    """Get cached settings instance. Values loaded from environment/.env file."""
    return Settings()  # type: ignore[call-arg]
