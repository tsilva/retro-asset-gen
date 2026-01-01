"""Command-line interface for retro-asset-gen.

This CLI generates retro gaming platform assets from user-provided reference images.
Output matches the COLORFUL theme structure for direct copying.

Workflow:
1. Place reference images in .input/<platform_id>/
   - platform.jpg (or .png) - photo of the console/device
   - logo.png (or .jpg) - the platform logo
2. Run: retro-asset-gen generate <platform_id> "<platform_name>"
3. Copy output to theme: cp -r .output/assets/ /path/to/theme/
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import get_settings
from .generator import AssetGenerator
from .theme_config import (
    ThemeConfigError,
    create_default_themes_config,
    load_themes_config,
)

app = typer.Typer(
    name="retro-asset-gen",
    help="Generate retro gaming platform assets using Gemini AI",
    add_completion=False,
)
console = Console()


# =============================================================================
# GENERATE COMMAND
# =============================================================================


@app.command()
def generate(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier (e.g., 'amigacd32')",
    ),
    platform_name: str = typer.Argument(
        ...,
        help="Full platform name (e.g., 'Commodore Amiga CD32')",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing assets",
    ),
) -> None:
    """Generate platform assets from reference images.

    Reference images must be placed in .input/<platform_id>/:
    - platform.jpg (or .png) - photo of the console/device
    - logo.png (or .jpg) - the platform logo

    Output matches theme structure for direct copying:
    - .output/assets/images/devices/<platform_id>.png
    - .output/assets/images/logos/*/platform_id>.png

    Example:
        retro-asset-gen generate amigacd32 "Commodore Amiga CD32"
    """
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("[dim]Make sure GEMINI_API_KEY is set in .env file[/dim]")
        raise typer.Exit(1) from None

    # Check if device already exists (unless force)
    device_path = settings.output_dir / "assets" / "images" / "devices" / f"{platform_id}.png"
    if device_path.exists() and not force:
        console.print(f"[yellow]Assets for '{platform_id}' already exist.[/yellow]")
        console.print("Use --force to regenerate.")
        raise typer.Exit(1)

    # Verify reference images exist
    generator = AssetGenerator(settings, console)
    missing = generator.verify_references(platform_id)

    if missing:
        console.print("[red]Missing reference images:[/red]")
        for m in missing:
            console.print(f"  [red]✗[/red] {m}")
        console.print()
        input_dir = settings.get_input_dir(platform_id)
        console.print(f"[bold]Please add reference images to:[/bold] {input_dir}")
        console.print("  - platform.jpg (or .png) - photo of the console")
        console.print("  - logo.png (or .jpg) - the platform logo")
        raise typer.Exit(1)

    # Print header
    info = Table.grid(padding=1)
    info.add_column(style="bold cyan", justify="right")
    info.add_column()
    info.add_row("Platform ID:", platform_id)
    info.add_row("Platform Name:", platform_name)
    info.add_row("Input:", str(settings.get_input_dir(platform_id)))
    info.add_row("Output:", str(settings.output_dir / "assets" / "images"))

    console.print(Panel(info, title="[bold]Generating Assets[/bold]"))

    # Generate assets
    result = generator.generate(platform_id, platform_name)

    # Print summary
    console.print()
    if result.success:
        console.print(Panel("[bold green]Generation Complete[/bold green]"))
        console.print()

        table = Table(title="Generated Files")
        table.add_column("File", style="cyan")
        table.add_column("Dimensions", justify="right")

        for asset in result.assets:
            rel_path = asset.output_path.relative_to(settings.output_dir)
            table.add_row(
                str(rel_path),
                f"{asset.dimensions[0]}x{asset.dimensions[1]}",
            )
        console.print(table)

        console.print()
        console.print("[bold]To deploy, copy assets to your theme:[/bold]")
        console.print(f"  cp -r {settings.output_dir}/assets/ /path/to/theme/")
    else:
        console.print(Panel("[bold red]Generation Failed[/bold red]"))
        console.print()
        for name, error in result.errors:
            console.print(f"  [red]✗[/red] {name}: {error}")
        raise typer.Exit(1)


# =============================================================================
# LIST COMMAND
# =============================================================================


@app.command(name="list")
def list_platforms() -> None:
    """List generated platforms."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    devices_dir = settings.output_dir / "assets" / "images" / "devices"
    if not devices_dir.exists():
        console.print("[dim]No platforms generated yet.[/dim]")
        return

    platforms = sorted([f.stem for f in devices_dir.glob("*.png")])

    if not platforms:
        console.print("[dim]No platforms generated yet.[/dim]")
        return

    table = Table(title="Generated Platforms")
    table.add_column("Platform ID", style="cyan")
    table.add_column("Device")
    table.add_column("Logos")

    logos_base = settings.output_dir / "assets" / "images" / "logos"

    for platform_id in platforms:
        device_exists = (devices_dir / f"{platform_id}.png").exists()
        logo_count = sum(
            1 for d in ["Dark - Black", "Dark - Color", "Light - Color", "Light - White"]
            if (logos_base / d / f"{platform_id}.png").exists()
        )
        table.add_row(
            platform_id,
            "[green]✓[/green]" if device_exists else "[red]✗[/red]",
            f"{logo_count}/4",
        )

    console.print(table)


# =============================================================================
# THEMES COMMAND
# =============================================================================


@app.command()
def themes(
    init: bool = typer.Option(
        False,
        "--init",
        help="Create a default themes.yaml configuration",
    ),
) -> None:
    """List available themes or create default configuration."""
    if init:
        config_path = Path.cwd() / "themes.yaml"
        if config_path.exists():
            console.print(f"[yellow]themes.yaml already exists:[/yellow] {config_path}")
            if not typer.confirm("Overwrite?"):
                raise typer.Exit(0)

        create_default_themes_config(config_path)
        console.print(f"[green]Created:[/green] {config_path}")
        console.print()
        console.print("Edit this file to configure your theme paths.")
        return

    try:
        themes_config = load_themes_config()
    except ThemeConfigError as e:
        console.print(f"[red]Theme config error:[/red] {e}")
        console.print()
        console.print("Create a themes.yaml with: retro-asset-gen themes --init")
        raise typer.Exit(1) from None

    theme_names = themes_config.list_themes()

    if not theme_names:
        console.print("[dim]No themes configured.[/dim]")
        return

    table = Table(title="Available Themes")
    table.add_column("Name", style="cyan")
    table.add_column("Base Path")

    for name in theme_names:
        theme = themes_config.get_theme(name)
        if theme:
            table.add_row(name, theme.base_path)

    console.print(table)


# =============================================================================
# CONFIG COMMAND
# =============================================================================


@app.command()
def config() -> None:
    """Show current configuration."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("API URL", settings.gemini_api_url)
    api_key_display = f"{settings.gemini_api_key[:8]}..." if settings.gemini_api_key else "Not set"
    table.add_row("API Key", api_key_display)
    if settings.enable_google_search:
        google_status = "[green]Enabled[/green]"
    else:
        google_status = "[dim]Disabled[/dim]"
    table.add_row("Google Search", google_status)
    table.add_row("Input Dir", str(settings.input_dir))
    table.add_row("Output Dir", str(settings.output_dir))
    table.add_row("Device Size", f"{settings.device_width}x{settings.device_height}")
    table.add_row("Logo Size", f"{settings.logo_width}x{settings.logo_height}")

    console.print(table)


if __name__ == "__main__":
    app()
