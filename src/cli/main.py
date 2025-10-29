#!/usr/bin/env python3
"""
Main CLI application entry point with plugin system.

Commands are auto-discovered from the commands/ directory using
the @cli_command decorator. No manual registration required.
"""

import typer
from pathlib import Path
from typing import Optional

from src.cli.plugin_system import discover_commands
from src.cli.config import CLIConfig, load_config_with_precedence


# Global configuration singleton
_config: Optional[CLIConfig] = None


def get_config() -> CLIConfig:
    """
    Get or create global config instance.

    Returns the cached config if available, otherwise loads with precedence:
    1. Project config (./.optothermal_cli_config.json)
    2. User config (~/.optothermal_cli_config.json)
    3. Environment variables (CLI_*)
    4. Defaults

    Returns:
        CLIConfig: Global configuration instance
    """
    global _config
    if _config is None:
        _config = load_config_with_precedence()
    return _config


def set_config(config: CLIConfig) -> None:
    """
    Set global config instance.

    Useful for testing and command-line overrides.

    Args:
        config: CLIConfig instance to use globally
    """
    global _config
    _config = config


# Create the main Typer app
app = typer.Typer(
    name="process_and_analyze",
    help="Complete data processing and analysis pipeline for semiconductor device characterization",
    add_completion=False
)


@app.callback()
def global_options(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output for all commands"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Override output directory for plots"
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Use specific config file"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would happen without executing"
    ),
):
    """
    Global options applied to all commands.

    These options override configuration from files and environment variables.
    """
    # Load base config with specified file (if any)
    config = load_config_with_precedence(config_file=config_file)

    # Apply overrides from command-line options
    overrides = {}
    if verbose:
        overrides["verbose"] = verbose
    if output_dir is not None:
        overrides["output_dir"] = output_dir
    if dry_run:
        overrides["dry_run"] = dry_run

    # Create merged config and set as global
    if overrides:
        config = config.merge_with(**overrides)

    set_config(config)


# Auto-discover and register all command plugins
discover_commands(
    app,
    commands_dir=Path("src/cli/commands"),
    config_path=Path("config/cli_plugins.yaml"),
    verbose=False  # Set to True for debugging
)


def main():
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
