"""Command-line interface for retro-asset-gen."""


import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Settings, get_settings
from .generator import AssetGenerator, GenerationReport

app = typer.Typer(
    name="retro-asset-gen",
    help="Generate retro gaming platform assets using Gemini AI",
    add_completion=False,
)
console = Console()


def print_header(
    platform_id: str,
    platform_name: str,
    year: str | None,
    vendor: str | None,
    settings: Settings,
) -> None:
    """Print generation header."""
    info = Table.grid(padding=1)
    info.add_column(style="bold cyan", justify="right")
    info.add_column()

    info.add_row("Platform ID:", platform_id)
    info.add_row("Platform Name:", platform_name)
    info.add_row("Year:", year or "N/A")
    info.add_row("Vendor:", vendor or "N/A")
    info.add_row("Reference:", settings.reference_platform)
    info.add_row("Output:", str(settings.output_dir / platform_id))

    console.print(Panel(info, title="[bold]COLORFUL Theme Asset Generator[/bold]"))

    api_info = Table.grid(padding=1)
    api_info.add_column(style="dim")
    api_info.add_column(style="dim")
    api_info.add_row(
        "Device:",
        f"aspectRatio=1:1, imageSize=2K -> {settings.device_width}x{settings.device_height}",
    )
    logo_dims = f"{settings.logo_width}x{settings.logo_height}"
    api_info.add_row(
        "Logos:",
        f"aspectRatio=21:9, imageSize=2K -> {logo_dims} + transparent bg",
    )
    console.print(api_info)


def print_report(report: GenerationReport) -> None:
    """Print generation report."""
    console.print()
    console.print(Panel("[bold green]Generation Complete[/bold green]"))
    console.print()
    console.print(f"[bold]Output directory:[/bold] {report.output_dir}")
    console.print()

    if report.assets:
        table = Table(title="Generated Files")
        table.add_column("File", style="cyan")
        table.add_column("Dimensions", justify="right")
        table.add_column("Alpha", justify="center")

        for asset in report.assets:
            table.add_row(
                asset.output_path.name,
                f"{asset.dimensions[0]}x{asset.dimensions[1]}",
                "✓" if asset.has_alpha else "✗",
            )
        console.print(table)

    if report.errors:
        console.print()
        console.print("[bold red]Errors:[/bold red]")
        for name, error in report.errors:
            console.print(f"  [red]✗[/red] {name}: {error}")

    # Print installation paths
    console.print()
    console.print("[bold]Installation paths:[/bold]")
    settings = get_settings()
    install_map = [
        ("device.png", f"devices/{report.platform_id}.png"),
        ("logo_dark_color.png", f"logos/Dark - Color/{report.platform_id}.png"),
        ("logo_dark_black.png", f"logos/Dark - Black/{report.platform_id}.png"),
        ("logo_light_color.png", f"logos/Light - Color/{report.platform_id}.png"),
        ("logo_light_white.png", f"logos/Light - White/{report.platform_id}.png"),
    ]
    for src, dst in install_map:
        console.print(f"  {src:25} -> {settings.theme_base / dst}")


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
    year: str | None = typer.Argument(
        None,
        help="Release year (e.g., '1993')",
    ),
    vendor: str | None = typer.Argument(
        None,
        help="Vendor/manufacturer (e.g., 'Commodore')",
    ),
    delay: float = typer.Option(
        3.0,
        "--delay",
        "-d",
        help="Delay between API calls in seconds",
    ),
    skip_verify: bool = typer.Option(
        False,
        "--skip-verify",
        help="Skip reference image verification",
    ),
) -> None:
    """Generate platform assets for the COLORFUL theme."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("[dim]Make sure GEMINI_API_KEY is set in environment or .env file[/dim]")
        raise typer.Exit(1) from None

    print_header(platform_id, platform_name, year, vendor, settings)

    generator = AssetGenerator(settings, console)

    if not skip_verify and not generator.verify_references():
        console.print("[red]Cannot proceed without all reference images.[/red]")
        raise typer.Exit(1)

    report = generator.generate(
        platform_id=platform_id,
        platform_name=platform_name,
        year=year,
        vendor=vendor,
        delay_between=delay,
    )

    print_report(report)

    if report.errors:
        raise typer.Exit(1)


@app.command()
def verify() -> None:
    """Verify reference images exist."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    console.print("[bold]Checking reference images...[/bold]")
    console.print(f"[dim]Theme base: {settings.theme_base}[/dim]")
    console.print(f"[dim]Reference platform: {settings.reference_platform}[/dim]")
    console.print()

    paths = settings.get_reference_paths()
    all_ok = True

    for name, path in paths.items():
        if path.exists():
            console.print(f"[green]✓[/green] {name}: {path}")
        else:
            console.print(f"[red]✗[/red] {name}: {path}")
            all_ok = False

    if all_ok:
        console.print("\n[green]All reference images found![/green]")
    else:
        console.print("\n[red]Some reference images are missing.[/red]")
        raise typer.Exit(1)


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
    table.add_row("Output Dir", str(settings.output_dir))
    table.add_row("Theme Base", str(settings.theme_base))
    table.add_row("Reference Platform", settings.reference_platform)
    table.add_row("Device Size", f"{settings.device_width}x{settings.device_height}")
    table.add_row("Logo Size", f"{settings.logo_width}x{settings.logo_height}")
    table.add_row("Alpha BG Threshold", str(settings.alpha_bg_threshold))
    table.add_row("Alpha FG Threshold", str(settings.alpha_fg_threshold))
    table.add_row("Dark BG Color", str(settings.bg_dark))
    table.add_row("Light BG Color", str(settings.bg_light))

    console.print(table)


if __name__ == "__main__":
    app()
