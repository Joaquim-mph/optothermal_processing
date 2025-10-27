#!/usr/bin/env python3
"""
Main CLI application entry point.

Aggregates all commands from the different command modules and
provides a single unified Typer app for the data processing pipeline.
"""

import typer

# Import command functions from command modules
from src.cli.commands.data_pipeline import (
    full_pipeline_command,
)
from src.cli.commands.history import (
    show_history_command,
    build_history_command,
    build_all_histories_command,
)
from src.cli.commands.plot_its import plot_its_command, list_presets_command
from src.cli.commands.plot_ivg import plot_ivg_command
from src.cli.commands.plot_transconductance import plot_transconductance_command
from src.cli.commands.stage import (
    stage_all_command,
    validate_manifest_command,
    inspect_manifest_command,
    staging_stats_command,
)

# Create the main Typer app
app = typer.Typer(
    name="process_and_analyze",
    help="Complete data processing and analysis pipeline for semiconductor device characterization",
    add_completion=False
)

# Register data pipeline commands
app.command(name="full-pipeline")(full_pipeline_command)

# Register history commands
app.command(name="show-history")(show_history_command)
app.command(name="build-history")(build_history_command)
app.command(name="build-all-histories")(build_all_histories_command)

# Register plotting commands
app.command(name="plot-its")(plot_its_command)
app.command(name="plot-its-presets")(list_presets_command)
app.command(name="plot-ivg")(plot_ivg_command)
app.command(name="plot-transconductance")(plot_transconductance_command)

# Register staging commands
app.command(name="stage-all")(stage_all_command)
app.command(name="validate-manifest")(validate_manifest_command)
app.command(name="inspect-manifest")(inspect_manifest_command)
app.command(name="staging-stats")(staging_stats_command)


def main():
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
