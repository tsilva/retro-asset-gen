# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

**See [README.md](README.md) for usage instructions, workflow, and configuration.**

## Development Commands

```bash
uv sync                      # Install dependencies
uv sync --all-extras         # Install with dev dependencies
uv run ruff check src/       # Linting
uv run mypy src/             # Type checking
uv run pytest                # Run tests
```

## Module Responsibilities

- **cli.py**: Typer-based CLI with `generate`, `list`, `deploy`, and utility commands. Entry point is `app`.
- **generator.py**: `AssetGenerator` handles image generation using Gemini API and user references.
- **config.py**: Pydantic Settings for configuration via environment variables and `.env` file.
- **prompts.py**: Prompt templates optimized for Nano Banana Pro.
- **gemini_client.py**: `GeminiClient` handles Nano Banana Pro API requests with Google Search support.
- **image_processor.py**: Post-processing with resize, alpha matting, and PNG quantization.
- **theme_config.py**: Loads and validates theme configuration from `themes.yaml`.

## LLM Agent Workflow

For an LLM agent working through the workflow:

1. **Prepare references** - place `platform.jpg` and `logo.png` in `.input/<platform_id>/`
2. **Run `generate`** - generates device and logo images with variants
3. **Read output images** - use the Read tool to visually inspect generated PNGs
4. **Run `deploy`** - copies assets to theme folder

Each step is atomic and observable. Use `list` to check generated platforms.
