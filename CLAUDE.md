# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Run the CLI
uv run retro-asset-gen generate <platform_id> "<platform_name>" [year] [vendor]

# Linting
uv run ruff check src/

# Type checking
uv run mypy src/

# Run tests
uv run pytest
```

## Architecture

This CLI tool generates retro gaming platform assets (device images and logos) using **Nano Banana Pro** (Gemini 3 Pro Image). Assets are styled to match the Pegasus Frontend COLORFUL theme.

### Key Features (Nano Banana Pro)

- **Google Search integration**: Model uses web search for accurate platform/brand knowledge
- **Accurate text rendering**: Reliable reproduction of logo text and typography
- **Multiple reference images**: Supports up to 14 reference images for style consistency
- **High resolution**: 2K/4K output support

### Module Responsibilities

- **cli.py**: Typer-based CLI with `generate`, `verify`, and `config` commands. Entry point is `app`.
- **generator.py**: `AssetGenerator` orchestrates the generation pipeline - loads references, calls API, resizes, applies alpha matting.
- **gemini_client.py**: `GeminiClient` handles Nano Banana Pro API requests. Supports multiple reference images and Google Search tool for real-world knowledge.
- **prompts.py**: Prompt templates optimized for Nano Banana Pro - instructs model to use Google Search for authentic branding/hardware appearance.
- **image_processor.py**: Post-processing with `resize_image` for exact dimensions and `make_background_transparent` for alpha matting with color decontamination.
- **config.py**: Pydantic Settings for configuration via environment variables and `.env` file.

### Generation Pipeline

1. Load SNES reference image for the asset type (style reference)
2. Send reference + prompt to Nano Banana Pro API with Google Search enabled
3. Model searches for authentic platform appearance/branding
4. Resize result to exact target dimensions
5. For logos: apply alpha matting (corner sampling to detect BG, graduated alpha, color decontamination)

### Asset Types Generated

| Asset | Dimensions | Aspect Ratio | Alpha |
|-------|------------|--------------|-------|
| device.png | 2160x2160 | 1:1 | No |
| logo_dark_color.png | 1920x510 | 21:9 | Yes |
| logo_dark_black.png | 1920x510 | 21:9 | Yes |
| logo_light_color.png | 1920x510 | 21:9 | Yes |
| logo_light_white.png | 1920x510 | 21:9 | Yes |

## Environment Configuration

Requires `GEMINI_API_KEY` in `.env` or environment. Optional: `RETRO_OUTPUT_DIR`, `RETRO_THEME_BASE`.

Google Search is enabled by default (`enable_google_search=True`) for accurate brand/hardware reproduction.
