# Retro Asset Generator

Generate platform assets (device images and logos) for the Pegasus Frontend COLORFUL theme using Google's Gemini image generation API.

## Features

- **Reference-based generation**: Uses existing SNES assets as style reference
- **Branding-aware prompts**: Instructs AI to use knowledge of platform's authentic branding
- **API-enforced parameters**: Uses `imageConfig` for aspect ratio and resolution control
- **Alpha matting**: Clean transparent backgrounds with color decontamination (no jagged edges)
- **Auto-resize**: Ensures exact output dimensions match theme requirements
- **Rich CLI**: Beautiful terminal output with progress tracking

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Gemini API key
- Existing COLORFUL theme with SNES reference assets

## Installation

```bash
# Clone the repository
git clone https://github.com/tsilva/retro-asset-gen.git
cd retro-asset-gen

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

## Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Gemini API key:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```

3. Optionally configure output paths in `.env`:
   ```bash
   RETRO_OUTPUT_DIR=/path/to/output
   RETRO_THEME_BASE=/path/to/theme/assets/images
   ```

## Usage

### Generate Assets

```bash
# Using uv
uv run retro-asset-gen generate <platform_id> "<platform_name>" [year] [vendor]

# Or if installed globally
retro-asset-gen generate <platform_id> "<platform_name>" [year] [vendor]
```

### Examples

```bash
# Single platform
uv run retro-asset-gen generate amigacd32 "Amiga CD32" 1993 Commodore

# Without optional parameters
uv run retro-asset-gen generate n64 "Nintendo 64"

# With custom delay between API calls
uv run retro-asset-gen generate c128 "Commodore 128" 1985 Commodore --delay 5
```

### Other Commands

```bash
# Verify reference images exist
uv run retro-asset-gen verify

# Show current configuration
uv run retro-asset-gen config

# Get help
uv run retro-asset-gen --help
uv run retro-asset-gen generate --help
```

## Output

Assets are generated to `{RETRO_OUTPUT_DIR}/{platform_id}/`:

| File | Dimensions | Description |
|------|------------|-------------|
| `device.png` | 2160x2160 | 3D render of console/computer |
| `logo_dark_color.png` | 1920x510 | Color logo, transparent bg |
| `logo_dark_black.png` | 1920x510 | White monochrome logo, transparent bg |
| `logo_light_color.png` | 1920x510 | Color logo, transparent bg |
| `logo_light_white.png` | 1920x510 | Black monochrome logo, transparent bg |

## Installation to Theme

After reviewing generated assets, copy to COLORFUL theme:

```bash
PLATFORM=amigacd32
THEME=/Volumes/RETRO/frontends/Pegasus_mac/themes/COLORFUL/assets/images
TEMP=/Volumes/RETRO/temp_platform_assets/$PLATFORM

cp "$TEMP/device.png" "$THEME/devices/$PLATFORM.png"
cp "$TEMP/logo_dark_color.png" "$THEME/logos/Dark - Color/$PLATFORM.png"
cp "$TEMP/logo_dark_black.png" "$THEME/logos/Dark - Black/$PLATFORM.png"
cp "$TEMP/logo_light_color.png" "$THEME/logos/Light - Color/$PLATFORM.png"
cp "$TEMP/logo_light_white.png" "$THEME/logos/Light - White/$PLATFORM.png"
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Your Gemini API key |
| `GEMINI_API_URL` | No | Override API endpoint |
| `RETRO_OUTPUT_DIR` | No | Output directory for generated assets |
| `RETRO_THEME_BASE` | No | Theme path for reference images |

## Project Structure

```
retro-asset-gen/
├── src/retro_asset_gen/
│   ├── __init__.py
│   ├── cli.py           # Typer CLI interface
│   ├── config.py        # Pydantic settings management
│   ├── gemini_client.py # Gemini API client
│   ├── generator.py     # Main generation orchestration
│   ├── image_processor.py # Image resize and alpha matting
│   └── prompts.py       # Prompt templates
├── pyproject.toml       # Project configuration
├── .env.example         # Example environment variables
└── README.md
```

## How It Works

1. **Reference Image**: Loads corresponding SNES asset as style reference
2. **API Request**: Sends reference + prompt to Gemini with `imageConfig` parameters
3. **Resize**: Ensures exact target dimensions using Pillow
4. **Alpha Matte**: For logos, applies background removal with:
   - Corner pixel sampling to detect actual background color
   - Graduated alpha based on color distance from background
   - Color decontamination to remove background bleed from edge pixels

## API Parameters

| Asset Type | aspectRatio | imageSize | Final Size |
|------------|-------------|-----------|------------|
| Device | 1:1 | 2K | 2160x2160 |
| Logos | 21:9 | 2K | 1920x510 |

Note: Logo target ratio (3.76:1) has no exact API match; 21:9 (2.33:1) is closest.

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run linting
uv run ruff check src/

# Run type checking
uv run mypy src/

# Run tests
uv run pytest
```

## License

MIT
