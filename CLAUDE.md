# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Linting
uv run ruff check src/

# Type checking
uv run mypy src/

# Run tests
uv run pytest
```

## Workflow

The CLI generates platform assets from user-provided reference images.

### Step 1: Prepare Reference Images

Create an input directory with reference images:

```
.input/<platform_id>/
├── platform.jpg  (or .png) - photo of the console/device
└── logo.png      (or .jpg) - the platform logo
```

Example:
```
.input/amigacd32/
├── platform.jpg  # Photo of the Amiga CD32 console
└── logo.png      # Amiga CD32 logo
```

### Step 2: Generate Assets

```bash
uv run retro-asset-gen generate <platform_id> "<platform_name>"

# Example:
uv run retro-asset-gen generate amigacd32 "Commodore Amiga CD32"

# Options:
#   --force    Overwrite existing assets
```

### Step 3: Deploy to Theme

```bash
uv run retro-asset-gen deploy

# Options:
#   <platform_id>     Deploy only this platform (omit for all)
#   --theme, -t       Theme name from themes.yaml (default: colorful)
#   --dry-run, -n     Show what would be copied without copying

# Examples:
uv run retro-asset-gen deploy                    # Deploy all platforms
uv run retro-asset-gen deploy amigacd32          # Deploy single platform
uv run retro-asset-gen deploy -n                 # Dry run
```

### Additional Commands

```bash
# List generated platforms
uv run retro-asset-gen list

# Manage themes
uv run retro-asset-gen themes           # List themes
uv run retro-asset-gen themes --init    # Create themes.yaml

# Show configuration
uv run retro-asset-gen config
```

## Architecture

This CLI tool generates retro gaming platform assets (device images and logos) using **Nano Banana Pro** (Gemini 3 Pro Image). Assets are styled to match the Pegasus Frontend COLORFUL theme.

### Key Features (Nano Banana Pro)

- **Google Search integration**: Model uses web search for accurate platform/brand knowledge
- **Reference image support**: Uses user-provided images for accurate reproduction
- **Accurate text rendering**: Reliable reproduction of logo text and typography
- **High resolution**: 2K output support

### Module Responsibilities

- **cli.py**: Typer-based CLI with `generate`, `list`, and utility commands. Entry point is `app`.
- **generator.py**: `AssetGenerator` handles image generation using Gemini API and user references.
- **config.py**: Pydantic Settings for configuration via environment variables and `.env` file.
- **prompts.py**: Prompt templates optimized for Nano Banana Pro.
- **gemini_client.py**: `GeminiClient` handles Nano Banana Pro API requests with Google Search support.
- **image_processor.py**: Post-processing with resize, alpha matting, and PNG quantization.
- **theme_config.py**: Loads and validates theme configuration from `themes.yaml`.

### Directory Structure

**Input (user-provided references):**
```
.input/<platform_id>/
├── platform.jpg    # Reference photo of the console
└── logo.png        # Reference logo image
```

**Output (matches COLORFUL theme structure):**
```
output/
└── assets/
    └── images/
        ├── devices/
        │   └── <platform_id>.png
        └── logos/
            ├── Dark - Black/
            │   └── <platform_id>.png
            ├── Dark - Color/
            │   └── <platform_id>.png
            ├── Light - Color/
            │   └── <platform_id>.png
            └── Light - White/
                └── <platform_id>.png
```

### Asset Types Generated

| Location | Dimensions | Description |
|----------|------------|-------------|
| devices/<platform_id>.png | 2160x2160 | Device/console image |
| logos/Light - Color/<platform_id>.png | 1920x510 | Color logo (transparent) |
| logos/Dark - Color/<platform_id>.png | 1920x510 | Color logo (transparent) |
| logos/Dark - Black/<platform_id>.png | 1920x510 | White monochrome logo |
| logos/Light - White/<platform_id>.png | 1920x510 | Black monochrome logo |

## Configuration

### Environment Variables

Requires `GEMINI_API_KEY` in `.env` or environment.

Optional:
- `RETRO_INPUT_DIR` - Input directory for references (default: `.input`)
- `RETRO_OUTPUT_DIR` - Output directory (default: `output`)
- `RETRO_QUANTIZE` - Enable PNG quantization (default: `true`)
- `RETRO_QUANTIZE_QUALITY` - Quantization quality range (default: `65-80`)

### themes.yaml

Theme configuration file in project root. Used by the `themes` command:

```yaml
themes:
  colorful:
    base_path: "/path/to/theme"
    assets_dir: "assets/images/{platform_id}"
    files:
      device: "device.png"
      logo_dark_color: "logo_dark_color.png"
      # ...
```

Create with: `retro-asset-gen themes --init`

## LLM Agent Workflow

For an LLM agent working through the workflow:

1. **Prepare references** - place `platform.jpg` and `logo.png` in `.input/<platform_id>/`
2. **Run `generate`** - generates device and logo images with variants
3. **Read output images** - use the Read tool to visually inspect generated PNGs
4. **Run `deploy`** - copies assets to theme folder

Each step is atomic and observable. Use `list` to check generated platforms.
