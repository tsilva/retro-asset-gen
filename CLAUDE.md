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

## Multi-Step Workflow

The CLI provides an interactive workflow for generating platform assets. Each step is a separate command, making it easy for an LLM agent to follow:

### Step 1: Generate Candidates

```bash
uv run retro-asset-gen candidates <platform_id> "<platform_name>" [year] [vendor]

# Options:
#   --devices N    Number of device candidates (default: 3)
#   --logos N      Number of logo candidates (default: 3)
#   --force        Overwrite existing project
```

### Step 2: List/Review Candidates

```bash
uv run retro-asset-gen list <platform_id>
```

View the generated images in `output/<platform_id>/candidates/devices/` and `output/<platform_id>/candidates/logos/`.

### Step 3: Select Preferred Variants

```bash
uv run retro-asset-gen select <platform_id> --device N --logo N
```

### Step 4: Finalize Asset Pack

```bash
uv run retro-asset-gen finalize <platform_id>
```

Creates all logo variants from the selected logo base.

### Step 5: Deploy to Theme

```bash
uv run retro-asset-gen deploy <platform_id> --theme colorful
```

### Additional Commands

```bash
# Regenerate a specific candidate
uv run retro-asset-gen regenerate <platform_id> --device N
uv run retro-asset-gen regenerate <platform_id> --logo N

# List all projects
uv run retro-asset-gen projects

# Delete a project
uv run retro-asset-gen delete <platform_id>

# Manage themes
uv run retro-asset-gen themes           # List themes
uv run retro-asset-gen themes --init    # Create themes.yaml

# Utility commands
uv run retro-asset-gen config           # Show configuration
uv run retro-asset-gen verify           # Verify reference images
```

## Architecture

This CLI tool generates retro gaming platform assets (device images and logos) using **Nano Banana Pro** (Gemini 3 Pro Image). Assets are styled to match the Pegasus Frontend COLORFUL theme.

### Key Features (Nano Banana Pro)

- **Google Search integration**: Model uses web search for accurate platform/brand knowledge
- **Accurate text rendering**: Reliable reproduction of logo text and typography
- **Multiple reference images**: Supports up to 14 reference images for style consistency
- **High resolution**: 2K/4K output support

### Module Responsibilities

- **cli.py**: Typer-based CLI with multi-step workflow commands. Entry point is `app`.
- **state.py**: `StateManager` persists project state between commands. Tracks candidates, selections, and workflow step.
- **generator.py**: `AssetGenerator` orchestrates generation - creates candidates, handles regeneration, and finalizes packs.
- **deployer.py**: `Deployer` copies finalized assets to theme folders based on `themes.yaml`.
- **theme_config.py**: Loads and validates theme configuration from `themes.yaml`.
- **gemini_client.py**: `GeminiClient` handles Nano Banana Pro API requests with Google Search support.
- **prompts.py**: Prompt templates optimized for Nano Banana Pro.
- **image_processor.py**: Post-processing with resize and alpha matting.
- **config.py**: Pydantic Settings for configuration via environment variables and `.env` file.

### Project Directory Structure

```
output/<platform_id>/
├── state.json              # Project state (step, selections, metadata)
├── candidates/
│   ├── devices/
│   │   ├── device_001.png
│   │   ├── device_002.png
│   │   └── device_003.png
│   └── logos/
│       ├── logo_001.png
│       ├── logo_002.png
│       └── logo_003.png
├── selected/               # Copies of selected candidates
│   ├── device.png
│   └── logo_base.png
└── final/                  # Finalized assets (ready for deploy)
    ├── device.png
    ├── logo_dark_color.png
    ├── logo_dark_black.png
    ├── logo_light_color.png
    └── logo_light_white.png
```

### Asset Types Generated

| Asset | Dimensions | Aspect Ratio | Alpha |
|-------|------------|--------------|-------|
| device.png | 2160x2160 | 1:1 | No |
| logo_dark_color.png | 1920x510 | 21:9 | Yes |
| logo_dark_black.png | 1920x510 | 21:9 | Yes |
| logo_light_color.png | 1920x510 | 21:9 | Yes |
| logo_light_white.png | 1920x510 | 21:9 | Yes |

## Configuration

### Environment Variables

Requires `GEMINI_API_KEY` in `.env` or environment. Optional: `RETRO_OUTPUT_DIR`, `RETRO_THEME_BASE`.

### themes.yaml

Theme configuration file in project root. Defines deployment targets:

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

1. **Run `candidates`** - generates images to disk
2. **Read candidate images** - use the Read tool to visually inspect PNGs
3. **Analyze quality** - pick best device/logo based on accuracy and quality
4. **Run `select`** - persist choice with indices
5. **Run `finalize`** - create final asset pack
6. **Run `deploy`** - copy to theme folder

Each step is atomic, observable, and recoverable. Use `list` to check current state at any time.
