"""Command-line interface for retro-asset-gen.

This CLI provides a multi-step workflow for generating retro gaming
platform assets:

1. candidates - Generate N candidate images for devices and logos
2. list       - List generated candidates for review
3. select     - Select preferred device and logo variants
4. finalize   - Create final asset pack from selections
5. deploy     - Deploy assets to a theme folder
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import get_settings
from .deployer import Deployer, DeploymentError
from .generator import AssetGenerator
from .state import StateManager, WorkflowStep
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


def get_state_manager() -> StateManager:
    """Get the state manager instance."""
    settings = get_settings()
    return StateManager(settings.output_dir)


def print_workflow_status(step: WorkflowStep) -> None:
    """Print current workflow step status."""
    steps = [
        ("1. Candidates", WorkflowStep.INITIALIZED, WorkflowStep.CANDIDATES_GENERATED),
        ("2. Selection", WorkflowStep.CANDIDATES_GENERATED, WorkflowStep.SELECTION_MADE),
        ("3. Finalize", WorkflowStep.SELECTION_MADE, WorkflowStep.FINALIZED),
        ("4. Deploy", WorkflowStep.FINALIZED, WorkflowStep.DEPLOYED),
    ]

    status_line = []
    for name, before_step, after_step in steps:
        if step.value == after_step.value or (
            step == WorkflowStep.DEPLOYED and after_step == WorkflowStep.DEPLOYED
        ):
            status_line.append(f"[green]{name} [/green]")
        elif step.value == before_step.value:
            status_line.append(f"[yellow]{name} [/yellow]")
        else:
            # Check if we're past this step
            step_order = [
                WorkflowStep.INITIALIZED,
                WorkflowStep.CANDIDATES_GENERATED,
                WorkflowStep.SELECTION_MADE,
                WorkflowStep.FINALIZED,
                WorkflowStep.DEPLOYED,
            ]
            current_idx = step_order.index(step)
            after_idx = step_order.index(after_step)
            if current_idx >= after_idx:
                status_line.append(f"[green]{name} [/green]")
            else:
                status_line.append(f"[dim]{name}[/dim]")

    console.print(" -> ".join(status_line))


# =============================================================================
# CANDIDATES COMMAND
# =============================================================================


@app.command()
def candidates(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier (e.g., 'amigacd32')",
    ),
    platform_name: str = typer.Argument(
        ...,
        help="Full platform name (e.g., 'Commodore Amiga CD32')",
    ),
    year: int | None = typer.Argument(
        None,
        help="Release year (e.g., 1993)",
    ),
    vendor: str | None = typer.Argument(
        None,
        help="Vendor/manufacturer (e.g., 'Commodore')",
    ),
    devices: int = typer.Option(
        3,
        "--devices",
        "-d",
        help="Number of device candidates to generate",
        min=1,
        max=10,
    ),
    logos: int = typer.Option(
        3,
        "--logos",
        "-l",
        help="Number of logo candidates to generate",
        min=1,
        max=10,
    ),
    delay: float = typer.Option(
        3.0,
        "--delay",
        help="Delay between API calls in seconds",
    ),
    skip_verify: bool = typer.Option(
        False,
        "--skip-verify",
        help="Skip reference image verification",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing project",
    ),
) -> None:
    """Generate candidate images for a platform.

    This creates N device images and N logo images that you can
    review and select from before finalizing.
    """
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("[dim]Make sure GEMINI_API_KEY is set in environment or .env file[/dim]")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)

    # Check if project exists
    if state_manager.project_exists(platform_id) and not force:
        console.print(f"[yellow]Project '{platform_id}' already exists.[/yellow]")
        console.print("Use --force to overwrite or choose a different platform_id.")
        raise typer.Exit(1)

    # Print header
    info = Table.grid(padding=1)
    info.add_column(style="bold cyan", justify="right")
    info.add_column()
    info.add_row("Platform ID:", platform_id)
    info.add_row("Platform Name:", platform_name)
    info.add_row("Year:", str(year) if year else "N/A")
    info.add_row("Vendor:", vendor or "N/A")
    info.add_row("Device candidates:", str(devices))
    info.add_row("Logo candidates:", str(logos))
    info.add_row("Output:", str(settings.output_dir / platform_id))

    console.print(Panel(info, title="[bold]Generating Candidates[/bold]"))

    # Create project
    if force and state_manager.project_exists(platform_id):
        state_manager.delete_project(platform_id)

    state = state_manager.create_project(
        platform_id=platform_id,
        platform_name=platform_name,
        year=year,
        vendor=vendor,
        device_count=devices,
        logo_count=logos,
    )

    # Create generator and verify references
    generator = AssetGenerator(settings, state_manager, console)

    if not skip_verify and not generator.verify_references():
        console.print("[red]Cannot proceed without all reference images.[/red]")
        raise typer.Exit(1)

    # Generate candidates
    console.print()
    result = generator.generate_candidates(state, delay_between=delay)

    # Print summary
    console.print()
    console.print(Panel("[bold green]Candidates Generated[/bold green]"))
    console.print()
    console.print(f"[bold]Devices:[/bold] {len(result.devices_generated)} generated")
    console.print(f"[bold]Logos:[/bold] {len(result.logos_generated)} generated")

    if result.errors:
        console.print()
        console.print("[bold red]Errors:[/bold red]")
        for name, error in result.errors:
            console.print(f"  [red]✗[/red] {name}: {error}")

    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Review candidates in: {settings.output_dir / platform_id / 'candidates'}")
    console.print(f"  2. Run: retro-asset-gen list {platform_id}")
    console.print(f"  3. Run: retro-asset-gen select {platform_id} --device N --logo N")


# =============================================================================
# LIST COMMAND
# =============================================================================


@app.command("list")
def list_candidates(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier",
    ),
) -> None:
    """List generated candidates for a platform."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)
    state = state_manager.load_state(platform_id)

    if state is None:
        console.print(f"[red]Project '{platform_id}' not found.[/red]")
        raise typer.Exit(1)

    # Print project info
    console.print(Panel(f"[bold]{state.platform_name}[/bold] ({platform_id})"))
    print_workflow_status(state.step)
    console.print()

    # List device candidates
    devices_dir = state_manager.get_devices_dir(platform_id)
    console.print("[bold cyan]Device Candidates:[/bold cyan]")

    if state.candidates.devices:
        for i, filename in enumerate(state.candidates.devices, 1):
            path = devices_dir / filename
            selected = " [green]SELECTED[/green]" if state.selection.device == i else ""
            exists = " [dim](file exists)[/dim]" if path.exists() else " [red](missing)[/red]"
            console.print(f"  {i}. {filename}{selected}{exists}")
    else:
        console.print("  [dim]No candidates generated yet[/dim]")

    console.print()

    # List logo candidates
    logos_dir = state_manager.get_logos_dir(platform_id)
    console.print("[bold cyan]Logo Candidates:[/bold cyan]")

    if state.candidates.logos:
        for i, filename in enumerate(state.candidates.logos, 1):
            path = logos_dir / filename
            selected = " [green]SELECTED[/green]" if state.selection.logo == i else ""
            exists = " [dim](file exists)[/dim]" if path.exists() else " [red](missing)[/red]"
            console.print(f"  {i}. {filename}{selected}{exists}")
    else:
        console.print("  [dim]No candidates generated yet[/dim]")

    # Print paths for viewing
    console.print()
    console.print("[bold]View candidates:[/bold]")
    console.print(f"  Devices: {devices_dir}")
    console.print(f"  Logos:   {logos_dir}")

    # Print next steps based on state
    console.print()
    if state.step == WorkflowStep.CANDIDATES_GENERATED:
        console.print("[bold]Next step:[/bold]")
        console.print(f"  retro-asset-gen select {platform_id} --device N --logo N")
    elif state.step == WorkflowStep.SELECTION_MADE:
        console.print("[bold]Next step:[/bold]")
        console.print(f"  retro-asset-gen finalize {platform_id}")


# =============================================================================
# SELECT COMMAND
# =============================================================================


@app.command()
def select(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier",
    ),
    device: int | None = typer.Option(
        None,
        "--device",
        "-d",
        help="Device candidate number to select (1-based)",
    ),
    logo: int | None = typer.Option(
        None,
        "--logo",
        "-l",
        help="Logo candidate number to select (1-based)",
    ),
) -> None:
    """Select preferred device and logo candidates.

    You must select both a device and a logo before finalizing.
    """
    if device is None and logo is None:
        console.print("[red]Please specify --device and/or --logo to select.[/red]")
        raise typer.Exit(1)

    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)
    state = state_manager.load_state(platform_id)

    if state is None:
        console.print(f"[red]Project '{platform_id}' not found.[/red]")
        raise typer.Exit(1)

    if state.step == WorkflowStep.INITIALIZED:
        console.print("[red]Candidates have not been generated yet.[/red]")
        console.print(f"Run: retro-asset-gen candidates {platform_id} ...")
        raise typer.Exit(1)

    try:
        state = state_manager.update_selection(
            platform_id,
            device=device,
            logo=logo,
        )
    except ValueError as e:
        console.print(f"[red]Selection error:[/red] {e}")
        raise typer.Exit(1) from None

    console.print("[green]Selection updated:[/green]")
    if device is not None:
        console.print(f"  Device: {device} ({state.candidates.devices[device - 1]})")
    if logo is not None:
        console.print(f"  Logo: {logo} ({state.candidates.logos[logo - 1]})")

    # Show current full selection
    console.print()
    console.print("[bold]Current selection:[/bold]")
    if state.selection.device:
        console.print(
            f"  Device: {state.selection.device} "
            f"({state.candidates.devices[state.selection.device - 1]})"
        )
    else:
        console.print("  Device: [yellow]not selected[/yellow]")

    if state.selection.logo:
        console.print(
            f"  Logo: {state.selection.logo} "
            f"({state.candidates.logos[state.selection.logo - 1]})"
        )
    else:
        console.print("  Logo: [yellow]not selected[/yellow]")

    # Next step
    if state.selection.device and state.selection.logo:
        console.print()
        console.print("[bold]Next step:[/bold]")
        console.print(f"  retro-asset-gen finalize {platform_id}")


# =============================================================================
# FINALIZE COMMAND
# =============================================================================


@app.command()
def finalize(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier",
    ),
) -> None:
    """Finalize selected candidates into the final asset pack.

    This creates the final device.png and all logo variants from
    the selected candidates.
    """
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)
    state = state_manager.load_state(platform_id)

    if state is None:
        console.print(f"[red]Project '{platform_id}' not found.[/red]")
        raise typer.Exit(1)

    if state.selection.device is None or state.selection.logo is None:
        console.print("[red]Both device and logo must be selected before finalizing.[/red]")
        console.print()
        console.print("[bold]Current selection:[/bold]")
        console.print(f"  Device: {state.selection.device or '[yellow]not selected[/yellow]'}")
        console.print(f"  Logo: {state.selection.logo or '[yellow]not selected[/yellow]'}")
        console.print()
        console.print(f"Run: retro-asset-gen select {platform_id} --device N --logo N")
        raise typer.Exit(1)

    console.print(Panel(f"[bold]Finalizing {state.platform_name}[/bold]"))
    console.print()
    device_name = state.candidates.devices[state.selection.device - 1]
    logo_name = state.candidates.logos[state.selection.logo - 1]
    console.print(f"[bold]Selected device:[/bold] {device_name}")
    console.print(f"[bold]Selected logo:[/bold] {logo_name}")

    generator = AssetGenerator(settings, state_manager, console)

    try:
        result = generator.finalize(state)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Print summary
    console.print()
    console.print(Panel("[bold green]Finalization Complete[/bold green]"))
    console.print()

    final_dir = state_manager.get_final_dir(platform_id)
    console.print(f"[bold]Final assets:[/bold] {final_dir}")
    console.print()

    if result.assets:
        table = Table(title="Generated Files")
        table.add_column("File", style="cyan")
        table.add_column("Dimensions", justify="right")
        table.add_column("Alpha", justify="center")

        for asset in result.assets:
            table.add_row(
                asset.output_path.name,
                f"{asset.dimensions[0]}x{asset.dimensions[1]}",
                "[green]Yes[/green]" if asset.has_alpha else "[dim]No[/dim]",
            )
        console.print(table)

    if result.errors:
        console.print()
        console.print("[bold red]Errors:[/bold red]")
        for name, error in result.errors:
            console.print(f"  [red]✗[/red] {name}: {error}")

    console.print()
    console.print("[bold]Next step:[/bold]")
    console.print(f"  retro-asset-gen deploy {platform_id} --theme colorful")


# =============================================================================
# DEPLOY COMMAND
# =============================================================================


@app.command()
def deploy(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier",
    ),
    theme: str = typer.Option(
        ...,
        "--theme",
        "-t",
        help="Theme to deploy to",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deployed without copying",
    ),
    no_overwrite: bool = typer.Option(
        False,
        "--no-overwrite",
        help="Don't overwrite existing files",
    ),
) -> None:
    """Deploy finalized assets to a theme folder.

    The theme must be configured in themes.yaml.
    """
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    try:
        themes_config = load_themes_config()
    except ThemeConfigError as e:
        console.print(f"[red]Theme config error:[/red] {e}")
        console.print()
        console.print("Create a themes.yaml in the project root with your theme configuration.")
        console.print("Run: retro-asset-gen themes --init")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)
    state = state_manager.load_state(platform_id)

    if state is None:
        console.print(f"[red]Project '{platform_id}' not found.[/red]")
        raise typer.Exit(1)

    deployer = Deployer(state_manager, themes_config, console)

    if dry_run:
        console.print("[yellow]DRY RUN - No files will be copied[/yellow]")
        console.print()

    try:
        result = deployer.deploy(
            platform_id=platform_id,
            theme_name=theme,
            dry_run=dry_run,
            overwrite=not no_overwrite,
        )
    except DeploymentError as e:
        console.print(f"[red]Deployment error:[/red] {e}")
        raise typer.Exit(1) from None

    if result.success:
        action = "Would deploy" if dry_run else "Deployed"
        console.print(Panel(f"[bold green]{action} to {theme}[/bold green]"))
        console.print()

        table = Table(title="Deployed Files")
        table.add_column("Asset", style="cyan")
        table.add_column("Path")

        for asset_type, path in result.files_deployed.items():
            table.add_row(asset_type, str(path))

        console.print(table)
    else:
        console.print(Panel("[bold red]Deployment Failed[/bold red]"))
        console.print()
        for error in result.errors:
            console.print(f"  [red]✗[/red] {error}")
        raise typer.Exit(1)


# =============================================================================
# REGENERATE COMMAND
# =============================================================================


@app.command()
def regenerate(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier",
    ),
    device: int | None = typer.Option(
        None,
        "--device",
        "-d",
        help="Device candidate number to regenerate (1-based)",
    ),
    logo: int | None = typer.Option(
        None,
        "--logo",
        "-l",
        help="Logo candidate number to regenerate (1-based)",
    ),
) -> None:
    """Regenerate a specific candidate image.

    Use this if you want to get a new version of a particular
    device or logo without regenerating all candidates.
    """
    if device is None and logo is None:
        console.print("[red]Please specify --device and/or --logo to regenerate.[/red]")
        raise typer.Exit(1)

    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)
    state = state_manager.load_state(platform_id)

    if state is None:
        console.print(f"[red]Project '{platform_id}' not found.[/red]")
        raise typer.Exit(1)

    generator = AssetGenerator(settings, state_manager, console)

    success = True

    if device is not None and not generator.regenerate_device(state, device):
        success = False

    if logo is not None and not generator.regenerate_logo(state, logo):
        success = False

    if not success:
        raise typer.Exit(1)


# =============================================================================
# PROJECTS COMMAND
# =============================================================================


@app.command()
def projects() -> None:
    """List all projects."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)
    project_list = state_manager.list_projects()

    if not project_list:
        console.print("[dim]No projects found.[/dim]")
        console.print()
        console.print("Create a new project with:")
        console.print('  retro-asset-gen candidates <platform_id> "<platform_name>"')
        return

    table = Table(title="Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Step")
    table.add_column("Selection")
    table.add_column("Updated")

    for platform_id, state in project_list:
        selection_str = ""
        if state.selection.device or state.selection.logo:
            dev = state.selection.device or "-"
            logo_sel = state.selection.logo or "-"
            selection_str = f"D:{dev} L:{logo_sel}"

        step_colors = {
            "initialized": "dim",
            "candidates_generated": "yellow",
            "selection_made": "blue",
            "finalized": "green",
            "deployed": "green bold",
        }
        step_style = step_colors.get(state.step.value, "")
        step_display = f"[{step_style}]{state.step.value}[/{step_style}]"

        table.add_row(
            platform_id,
            state.platform_name,
            step_display,
            selection_str,
            state.updated_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


# =============================================================================
# DELETE COMMAND
# =============================================================================


@app.command()
def delete(
    platform_id: str = typer.Argument(
        ...,
        help="Platform identifier",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation",
    ),
) -> None:
    """Delete a project and all its files."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from None

    state_manager = StateManager(settings.output_dir)
    state = state_manager.load_state(platform_id)

    if state is None:
        console.print(f"[red]Project '{platform_id}' not found.[/red]")
        raise typer.Exit(1)

    project_dir = state_manager.get_project_dir(platform_id)

    if not force:
        console.print(f"[yellow]This will delete:[/yellow] {project_dir}")
        console.print()
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    if state_manager.delete_project(platform_id):
        console.print(f"[green]Deleted project '{platform_id}'[/green]")
    else:
        console.print(f"[red]Failed to delete project '{platform_id}'[/red]")
        raise typer.Exit(1)


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
    table.add_column("Assets Dir Pattern")

    for name in theme_names:
        theme = themes_config.get_theme(name)
        if theme:
            table.add_row(name, theme.base_path, theme.assets_dir)

    console.print(table)


# =============================================================================
# VERIFY COMMAND
# =============================================================================


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
