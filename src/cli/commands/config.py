#!/usr/bin/env python3
"""
Configuration management commands for the CLI.

Provides commands to:
- Display current configuration (show-config)
- Initialize config file (init-config)
- Validate configuration (validate-config)
- Reset to defaults (reset-config)
"""

import json
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.cli.config import CLIConfig, load_config_with_precedence
from src.cli.plugin_system import cli_command


console = Console()


@cli_command(name="config-show", description="Display current configuration settings")
def show_config_command(
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file to display (default: auto-detect)"
    ),
    show_sources: bool = typer.Option(
        True,
        "--show-sources/--no-sources",
        help="Show source of each setting"
    )
):
    """
    Display current configuration in a formatted table.

    Shows all configuration fields with their current values,
    and optionally the source of each setting (default/env/file/override).
    """
    # Load config with precedence
    try:
        config = load_config_with_precedence(config_file=config_file)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Create table
    table = Table(
        title="Current Configuration",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Setting", style="bold", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Type", style="dim")
    if show_sources:
        table.add_column("Source", style="yellow")
    table.add_column("Status", style="blue")

    # Add rows for each field
    for field_name, field_info in CLIConfig.model_fields.items():
        value = getattr(config, field_name)
        field_type = field_info.annotation.__name__ if hasattr(field_info.annotation, '__name__') else str(field_info.annotation)

        # Format value
        if isinstance(value, Path):
            value_str = str(value)
            status = "✓ exists" if value.exists() else "⚠ will create"
        elif isinstance(value, bool):
            value_str = "✓ enabled" if value else "✗ disabled"
            status = ""
        else:
            value_str = str(value)
            status = ""

        # Get source
        if show_sources:
            source = config.get_field_source(field_name)
            source_emoji = {
                "default": "📋 default",
                "env": "🌍 environment",
                "file": "📄 file",
                "override": "⚙️  override"
            }.get(source, source)
            table.add_row(field_name, value_str, field_type, source_emoji, status)
        else:
            table.add_row(field_name, value_str, field_type, status)

    console.print(table)

    # Show which config files are active
    console.print("\n[bold]Configuration Files:[/bold]")
    user_config = Path.home() / ".optothermal_cli_config.json"
    project_config = Path.cwd() / ".optothermal_cli_config.json"

    if user_config.exists():
        console.print(f"  ✓ User config: [cyan]{user_config}[/cyan]")
    else:
        console.print(f"  ✗ User config: [dim]{user_config} (not found)[/dim]")

    if project_config.exists() and project_config != user_config:
        console.print(f"  ✓ Project config: [cyan]{project_config}[/cyan]")
    else:
        console.print(f"  ✗ Project config: [dim]{project_config} (not found)[/dim]")

    if config_file:
        console.print(f"  ✓ Specified config: [cyan]{config_file}[/cyan]")

    console.print("\n[dim]Tip: Use 'config-init' to create a config file[/dim]")


@cli_command(name="config-init", description="Initialize a configuration file")
def init_config_command(
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output location (default: ~/.optothermal_cli_config.json)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing config file"
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use a profile as base (development/production/testing/high_quality)"
    )
):
    """
    Generate a configuration file with current settings or a profile.

    Creates a JSON config file that can be edited to customize behavior.
    """
    # Determine output location
    if output is None:
        output = Path.home() / ".optothermal_cli_config.json"
    else:
        output = Path(output)

    # Check if file exists
    if output.exists() and not force:
        console.print(f"[yellow]Config file already exists: {output}[/yellow]")
        console.print("[dim]Use --force to overwrite[/dim]")
        raise typer.Exit(1)

    # Get base config
    if profile:
        from src.cli.config import ConfigProfile
        profile_lower = profile.lower()
        if profile_lower == "development":
            config = ConfigProfile.development()
        elif profile_lower == "production":
            config = ConfigProfile.production()
        elif profile_lower == "testing":
            config = ConfigProfile.testing()
        elif profile_lower == "high_quality":
            config = ConfigProfile.high_quality()
        else:
            console.print(f"[red]Unknown profile: {profile}[/red]")
            console.print("[dim]Available profiles: development, production, testing, high_quality[/dim]")
            raise typer.Exit(1)
        console.print(f"[green]Using profile: {profile}[/green]")
    else:
        config = CLIConfig()

    # Save config
    try:
        config.save(output, pretty=True)
        console.print(f"[green]✓[/green] Configuration file created: [cyan]{output}[/cyan]")
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")
        raise typer.Exit(1)

    # Display instructions
    panel = Panel(
        f"""[bold]Configuration file created successfully![/bold]

Location: [cyan]{output}[/cyan]

You can now:
  1. Edit the file to customize settings
  2. Run [bold]config-show[/bold] to verify changes
  3. Run [bold]config-validate[/bold] to check validity

All commands will automatically use this configuration.

[dim]Example edits:[/dim]
  • Set [yellow]verbose: true[/yellow] for detailed output
  • Change [yellow]parallel_workers[/yellow] to match your CPU cores
  • Customize [yellow]output_dir[/yellow] for plot outputs
""",
        title="✓ Config Initialized",
        border_style="green",
        box=box.ROUNDED
    )
    console.print(panel)


@cli_command(name="config-validate", description="Validate current configuration")
def validate_config_command(
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file to validate (default: auto-detect)"
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Attempt to fix issues automatically"
    )
):
    """
    Validate current configuration and check for issues.

    Checks:
    - All paths are accessible
    - Value ranges are valid
    - Write permissions for output directories
    - Config file format (if using file)
    """
    issues = []
    warnings = []

    console.print("[bold]Validating configuration...[/bold]\n")

    # Try to load config
    try:
        config = load_config_with_precedence(config_file=config_file)
        console.print("[green]✓[/green] Configuration loaded successfully")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load configuration: {e}")
        issues.append(f"Config loading error: {e}")
        # Can't continue without config
        console.print(f"\n[red]Validation failed with {len(issues)} error(s)[/red]")
        raise typer.Exit(1)

    # Check path fields
    console.print("\n[bold]Checking paths...[/bold]")
    for field_name in ["raw_data_dir", "stage_dir", "history_dir", "output_dir"]:
        path = getattr(config, field_name)

        if not path.exists():
            if fix:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    console.print(f"[green]✓[/green] Created {field_name}: {path}")
                except Exception as e:
                    console.print(f"[red]✗[/red] Cannot create {field_name}: {e}")
                    issues.append(f"Cannot create {field_name}: {e}")
            else:
                console.print(f"[yellow]⚠[/yellow] {field_name} does not exist: {path}")
                warnings.append(f"{field_name} will be created on first use")
        else:
            # Check write permissions
            if not os.access(path, os.W_OK):
                console.print(f"[red]✗[/red] No write permission for {field_name}: {path}")
                issues.append(f"No write permission for {field_name}")
            else:
                console.print(f"[green]✓[/green] {field_name}: {path}")

    # Check field values
    console.print("\n[bold]Checking field values...[/bold]")

    # parallel_workers
    if 1 <= config.parallel_workers <= 16:
        console.print(f"[green]✓[/green] parallel_workers: {config.parallel_workers}")
    else:
        console.print(f"[red]✗[/red] parallel_workers out of range: {config.parallel_workers}")
        issues.append(f"parallel_workers must be between 1 and 16")

    # plot_dpi
    if 72 <= config.plot_dpi <= 600:
        console.print(f"[green]✓[/green] plot_dpi: {config.plot_dpi}")
    else:
        console.print(f"[red]✗[/red] plot_dpi out of range: {config.plot_dpi}")
        issues.append(f"plot_dpi must be between 72 and 600")

    # plot_format
    valid_formats = ["png", "pdf", "svg", "jpg"]
    if config.default_plot_format in valid_formats:
        console.print(f"[green]✓[/green] default_plot_format: {config.default_plot_format}")
    else:
        console.print(f"[red]✗[/red] invalid plot format: {config.default_plot_format}")
        issues.append(f"default_plot_format must be one of: {', '.join(valid_formats)}")

    # cache_ttl
    if config.cache_ttl >= 0:
        console.print(f"[green]✓[/green] cache_ttl: {config.cache_ttl}")
    else:
        console.print(f"[red]✗[/red] cache_ttl cannot be negative: {config.cache_ttl}")
        issues.append(f"cache_ttl must be >= 0")

    # Check config files
    console.print("\n[bold]Checking config files...[/bold]")
    user_config = Path.home() / ".optothermal_cli_config.json"
    project_config = Path.cwd() / ".optothermal_cli_config.json"

    for cfg_path, name in [(user_config, "User config"), (project_config, "Project config")]:
        if cfg_path.exists():
            try:
                with open(cfg_path, 'r') as f:
                    json.load(f)
                console.print(f"[green]✓[/green] {name}: {cfg_path}")
            except json.JSONDecodeError as e:
                console.print(f"[red]✗[/red] {name} has invalid JSON: {e}")
                issues.append(f"{name} is not valid JSON")
        else:
            console.print(f"[dim]○[/dim] {name}: not present")

    # Summary
    console.print()
    if issues:
        console.print(f"[red]✗ Validation failed with {len(issues)} error(s):[/red]")
        for issue in issues:
            console.print(f"  • {issue}")
        raise typer.Exit(1)
    elif warnings:
        console.print(f"[yellow]⚠ Validation passed with {len(warnings)} warning(s):[/yellow]")
        for warning in warnings:
            console.print(f"  • {warning}")
        console.print("\n[green]Configuration is valid[/green]")
    else:
        console.print("[green]✓ Validation passed - configuration is perfect![/green]")


@cli_command(name="config-reset", description="Reset configuration to defaults")
def reset_config_command(
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Config file to reset (default: ~/.optothermal_cli_config.json)"
    ),
    confirm: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt"
    ),
    backup: bool = typer.Option(
        True,
        "--backup/--no-backup",
        help="Create backup before resetting"
    )
):
    """
    Reset configuration file to default values.

    Creates a backup before resetting (unless --no-backup is used).
    """
    # Determine which config file to reset
    if config_file is None:
        config_file = Path.home() / ".optothermal_cli_config.json"
    else:
        config_file = Path(config_file)

    # Check if file exists
    if not config_file.exists():
        console.print(f"[yellow]Config file does not exist: {config_file}[/yellow]")
        console.print("[dim]Nothing to reset. Use 'config-init' to create one.[/dim]")
        raise typer.Exit(0)

    # Confirm
    if not confirm:
        console.print(f"[yellow]This will reset: {config_file}[/yellow]")
        if backup:
            console.print("[dim]A backup will be created[/dim]")
        response = typer.confirm("Are you sure you want to continue?")
        if not response:
            console.print("[dim]Reset cancelled[/dim]")
            raise typer.Exit(0)

    # Create backup
    if backup:
        backup_file = config_file.with_suffix(".json.backup")
        try:
            shutil.copy2(config_file, backup_file)
            console.print(f"[green]✓[/green] Backup created: [cyan]{backup_file}[/cyan]")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create backup: {e}")
            console.print("[dim]Reset cancelled[/dim]")
            raise typer.Exit(1)

    # Reset to defaults
    try:
        default_config = CLIConfig()
        default_config.save(config_file, pretty=True)
        console.print(f"[green]✓[/green] Configuration reset to defaults: [cyan]{config_file}[/cyan]")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to reset config: {e}")
        if backup:
            console.print(f"[dim]Backup available at: {backup_file}[/dim]")
        raise typer.Exit(1)

    # Success message
    panel = Panel(
        f"""[bold]Configuration has been reset to defaults[/bold]

Original file backed up to:
  [cyan]{backup_file if backup else 'N/A (no backup)'}[/cyan]

Reset file:
  [cyan]{config_file}[/cyan]

Run [bold]config-show[/bold] to see the default settings.
""",
        title="✓ Reset Complete",
        border_style="green",
        box=box.ROUNDED
    )
    console.print(panel)


# Import os at module level for validate command
import os
