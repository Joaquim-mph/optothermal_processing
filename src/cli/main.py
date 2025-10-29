#!/usr/bin/env python3
"""
Main CLI application entry point with plugin system.

Commands are auto-discovered from the commands/ directory using
the @cli_command decorator. No manual registration required.
"""

import typer
from pathlib import Path
from src.cli.plugin_system import discover_commands

# Create the main Typer app
app = typer.Typer(
    name="process_and_analyze",
    help="Complete data processing and analysis pipeline for semiconductor device characterization",
    add_completion=False
)

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
