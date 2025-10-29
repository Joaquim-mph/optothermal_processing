"""
Example implementation of the CLI Plugin System.

This file demonstrates how the plugin system would work with real code examples.
NOT meant to be run directly - see CLI_PLUGIN_SYSTEM.md for integration.
"""

# =============================================================================
# Example 1: Basic Plugin Decorator Usage
# =============================================================================

from src.cli.plugin_system import cli_command
import typer
from pathlib import Path
from rich.console import Console

console = Console()


# Simple command with minimal configuration
@cli_command(
    name="quick-stats",
    group="utilities"
)
def quick_stats_command(
    chip_number: int = typer.Argument(..., help="Chip number")
):
    """Quick statistics for a chip (auto-extracted description)."""
    console.print(f"[cyan]Fetching stats for chip {chip_number}...[/cyan]")
    # Implementation
    console.print("[green]✓ Done![/green]")


# Command with full metadata
@cli_command(
    name="export-json",
    group="export",
    description="Export chip history to JSON format",
    aliases=["json-export", "to-json"],
    priority=10  # Higher priority = shown first in help
)
def export_json_command(
    chip_number: int = typer.Argument(...),
    output: Path = typer.Option(Path("export.json"), "--output", "-o"),
    pretty: bool = typer.Option(True, "--pretty/--compact"),
):
    """
    Export chip history to JSON format with optional pretty-printing.

    Examples:
        python process_and_analyze.py export-json 67
        python process_and_analyze.py export-json 67 -o data.json --compact
        python process_and_analyze.py to-json 67  # Using alias
    """
    import json
    console.print(f"[cyan]Exporting chip {chip_number} to JSON...[/cyan]")

    # Mock data
    data = {
        "chip_number": chip_number,
        "experiments": [
            {"seq": 1, "proc": "IVg", "date": "2025-10-01"},
            {"seq": 2, "proc": "It", "date": "2025-10-02"},
        ]
    }

    with open(output, 'w') as f:
        if pretty:
            json.dump(data, f, indent=2)
        else:
            json.dump(data, f)

    console.print(f"[green]✓ Exported to {output}[/green]")


# =============================================================================
# Example 2: Migrating Existing Command to Plugin System
# =============================================================================

# BEFORE: Original command without decorator
# def show_history_command(chip_number: int, ...):
#     """Display chip experiment history"""
#     pass

# AFTER: With plugin decorator
@cli_command(
    name="show-history",
    group="history",
    description="Display chip experiment history"  # Optional, extracted from docstring
)
def show_history_command(
    chip_number: int = typer.Argument(...),
    chip_group: str = typer.Option("Alisson", "--group", "-g"),
    limit: int = typer.Option(None, "--limit", "-n"),
):
    """
    Display the complete experiment history for a specific chip.

    Shows a beautiful, paginated view of all experiments with details.
    """
    console.print(f"[cyan]Loading history for {chip_group}{chip_number}...[/cyan]")
    # Implementation here
    console.print("[green]✓ History displayed[/green]")


# =============================================================================
# Example 3: Command Module with Multiple Commands
# =============================================================================

# This demonstrates how a full command module would look after migration

"""Export commands - data export utilities."""

@cli_command(name="export-csv", group="export")
def export_csv_command(
    chip_number: int = typer.Argument(...),
    output: Path = typer.Option(Path("export.csv"), "--output", "-o"),
):
    """Export chip history to CSV format."""
    console.print(f"[cyan]Exporting to CSV: {output}[/cyan]")
    # Implementation
    console.print("[green]✓ CSV export complete[/green]")


@cli_command(name="export-excel", group="export")
def export_excel_command(
    chip_number: int = typer.Argument(...),
    output: Path = typer.Option(Path("export.xlsx"), "--output", "-o"),
):
    """Export chip history to Excel format."""
    console.print(f"[cyan]Exporting to Excel: {output}[/cyan]")
    # Implementation
    console.print("[green]✓ Excel export complete[/green]")


@cli_command(
    name="export-all-formats",
    group="export",
    description="Export chip history to all formats (CSV, JSON, Excel)"
)
def export_all_formats_command(
    chip_number: int = typer.Argument(...),
    output_dir: Path = typer.Option(Path("exports"), "--output-dir", "-o"),
):
    """Export chip history to multiple formats simultaneously."""
    console.print(f"[cyan]Exporting to all formats in {output_dir}...[/cyan]")
    # Implementation calls export_csv, export_json, export_excel
    console.print("[green]✓ All exports complete[/green]")


# =============================================================================
# Example 4: Third-Party Plugin
# =============================================================================

"""
Third-party plugin example: Custom FFT analysis

File: ~/.optothermal/plugins/custom_fft/commands.py
"""

@cli_command(
    name="fft-analysis",
    group="custom",
    description="FFT analysis of photoresponse data",
    priority=-10  # Third-party plugins have lower priority
)
def fft_analysis_command(
    chip_number: int = typer.Argument(...),
    seq: str = typer.Option(..., "--seq", "-s", help="Seq numbers (e.g., '52,57,58')"),
    window: str = typer.Option("hann", "--window", help="Window function (hann, hamming, blackman)"),
):
    """
    Perform FFT analysis on ITS photoresponse data.

    Analyzes frequency components in the photoresponse signal.

    Examples:
        python process_and_analyze.py fft-analysis 67 --seq 52,57,58
        python process_and_analyze.py fft-analysis 67 --seq 52-60 --window hamming
    """
    from scipy.fft import fft, fftfreq
    import numpy as np

    console.print(f"[cyan]Running FFT analysis on chip {chip_number}...[/cyan]")
    console.print(f"[dim]Window: {window}, Seq: {seq}[/dim]")

    # Implementation would load ITS data and perform FFT
    # This is a mock example

    console.print("[green]✓ FFT analysis complete[/green]")
    console.print("[yellow]Results:[/yellow] Dominant frequency: 0.5 Hz")


# =============================================================================
# Example 5: Experimental Commands
# =============================================================================

"""Experimental features that can be disabled in production."""

@cli_command(
    name="ml-predict",
    group="experimental",
    description="[EXPERIMENTAL] ML-based degradation prediction"
)
def ml_predict_command(
    chip_number: int = typer.Argument(...),
    model: Path = typer.Option(..., "--model", "-m", help="Path to trained model"),
):
    """
    [EXPERIMENTAL] Predict device degradation using ML model.

    WARNING: This is an experimental feature under active development.
    Results should not be used for critical decisions.

    Examples:
        python process_and_analyze.py ml-predict 67 --model models/degradation_v1.pkl
    """
    console.print("[yellow]⚠ EXPERIMENTAL FEATURE[/yellow]")
    console.print(f"[cyan]Loading model: {model}[/cyan]")

    # Mock ML prediction
    console.print("[green]Prediction: 85% confidence of stable operation for 6 months[/green]")


@cli_command(
    name="auto-calibrate",
    group="experimental",
    description="[EXPERIMENTAL] Automatic equipment calibration"
)
def auto_calibrate_command(
    equipment: str = typer.Argument(..., help="Equipment ID"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute"),
):
    """
    [EXPERIMENTAL] Automatically calibrate measurement equipment.

    WARNING: Only use with --dry-run unless you know what you're doing!

    Examples:
        python process_and_analyze.py auto-calibrate keithley-2400 --dry-run
        python process_and_analyze.py auto-calibrate keithley-2400 --execute  # CAREFUL!
    """
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]")
    else:
        console.print("[red]⚠ LIVE MODE - Equipment will be modified![/red]")

    console.print(f"[cyan]Calibrating {equipment}...[/cyan]")
    # Implementation
    console.print("[green]✓ Calibration complete[/green]")


# =============================================================================
# Example 6: Utility Command to List Plugins
# =============================================================================

@cli_command(
    name="list-plugins",
    group="utilities",
    description="List all available command plugins",
    aliases=["plugins", "list-commands"]
)
def list_plugins_command(
    group: str = typer.Option(None, "--group", "-g", help="Filter by group"),
    show_disabled: bool = typer.Option(False, "--show-disabled", help="Include disabled commands"),
):
    """
    List all available command plugins with their metadata.

    Examples:
        python process_and_analyze.py list-plugins
        python process_and_analyze.py list-plugins --group plotting
        python process_and_analyze.py plugins --show-disabled
    """
    from src.cli.plugin_system import list_available_commands, get_command_groups
    from rich.table import Table

    console.print()
    console.print("[bold cyan]Available Command Plugins[/bold cyan]")
    console.print()

    commands = list_available_commands(group)

    # Create table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Command", style="yellow", width=25)
    table.add_column("Group", style="magenta", width=15)
    table.add_column("Description", style="white", width=50)
    table.add_column("Aliases", style="dim", width=20)

    for cmd in commands:
        aliases_str = ", ".join(cmd.aliases) if cmd.aliases else "—"
        table.add_row(
            cmd.name,
            cmd.group,
            cmd.description[:47] + "..." if len(cmd.description) > 50 else cmd.description,
            aliases_str
        )

    console.print(table)
    console.print()

    # Summary
    groups = get_command_groups()
    console.print(f"[cyan]Total commands:[/cyan] {len(commands)}")
    console.print(f"[cyan]Command groups:[/cyan] {', '.join(groups)}")
    console.print()

    if group:
        console.print(f"[dim]Filtered by group: {group}[/dim]")


# =============================================================================
# Example 7: Command with Class-Based Plugin
# =============================================================================

"""
Advanced: Class-based command plugin with lifecycle hooks.
Useful for complex commands with setup/teardown logic.
"""

from typing import Optional

@cli_command(
    name="batch-process",
    group="pipeline",
    description="Batch process multiple chips with progress tracking"
)
class BatchProcessCommand:
    """
    Class-based command plugin with lifecycle hooks.

    This pattern is useful for commands that need:
    - Shared state across methods
    - Setup/teardown logic
    - Complex validation
    - Progress tracking
    """

    def __init__(self):
        self.progress = None
        self.results = []

    def __call__(
        self,
        chips: str = typer.Argument(..., help="Comma-separated chip numbers (e.g., '67,72,81')"),
        operation: str = typer.Option("stage", "--operation", "-o", help="Operation to perform"),
    ):
        """
        Batch process multiple chips.

        Examples:
            python process_and_analyze.py batch-process 67,72,81
            python process_and_analyze.py batch-process 67,72,81 --operation history
        """
        chip_list = [int(c.strip()) for c in chips.split(",")]

        console.print(f"[cyan]Batch processing {len(chip_list)} chips...[/cyan]")
        console.print(f"[dim]Operation: {operation}[/dim]")
        console.print()

        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing...", total=len(chip_list))

            for chip in chip_list:
                progress.update(task, description=f"Processing chip {chip}...")
                self._process_chip(chip, operation)
                progress.advance(task)

        console.print()
        console.print(f"[green]✓ Batch processing complete![/green]")
        self._show_summary()

    def _process_chip(self, chip: int, operation: str):
        """Process a single chip."""
        # Mock processing
        import time
        time.sleep(0.1)
        self.results.append({"chip": chip, "status": "success"})

    def _show_summary(self):
        """Show summary of batch processing."""
        from rich.table import Table

        table = Table(title="Batch Results")
        table.add_column("Chip", style="cyan")
        table.add_column("Status", style="green")

        for result in self.results:
            table.add_row(str(result["chip"]), result["status"])

        console.print(table)


# =============================================================================
# Example 8: Configuration-Aware Command
# =============================================================================

"""
Command that reads plugin configuration for custom behavior.
"""

@cli_command(
    name="validate-setup",
    group="utilities",
    description="Validate installation and configuration"
)
def validate_setup_command(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Validate that the system is properly configured.

    Checks:
    - Required dependencies installed
    - Data directories exist
    - Plugin configuration is valid
    - Command groups are properly registered

    Examples:
        python process_and_analyze.py validate-setup
        python process_and_analyze.py validate-setup --verbose
    """
    from src.cli.plugin_system import load_plugin_config, list_available_commands
    from rich.panel import Panel

    console.print()
    console.print(Panel.fit("[bold cyan]System Validation[/bold cyan]", border_style="cyan"))
    console.print()

    # Check plugin configuration
    console.print("[cyan]Checking plugin configuration...[/cyan]")
    try:
        config = load_plugin_config()
        console.print("[green]✓[/green] Plugin config loaded")
        if verbose:
            console.print(f"[dim]  Enabled groups: {config['enabled_groups']}[/dim]")
            console.print(f"[dim]  Disabled commands: {config['disabled_commands']}[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Plugin config error: {e}")

    # Check registered commands
    console.print("[cyan]Checking registered commands...[/cyan]")
    commands = list_available_commands()
    console.print(f"[green]✓[/green] {len(commands)} commands registered")

    # Check data directories
    console.print("[cyan]Checking data directories...[/cyan]")
    from pathlib import Path
    dirs = [
        Path("data/01_raw"),
        Path("data/02_stage"),
        Path("config"),
    ]
    for d in dirs:
        if d.exists():
            console.print(f"[green]✓[/green] {d}")
        else:
            console.print(f"[yellow]⚠[/yellow] {d} (missing)")

    # Check dependencies
    console.print("[cyan]Checking dependencies...[/cyan]")
    required = ["polars", "typer", "rich", "matplotlib", "scipy"]
    for pkg in required:
        try:
            __import__(pkg)
            console.print(f"[green]✓[/green] {pkg}")
        except ImportError:
            console.print(f"[red]✗[/red] {pkg} (not installed)")

    console.print()
    console.print(Panel.fit("[bold green]✓ Validation Complete[/bold green]", border_style="green"))
    console.print()


# =============================================================================
# Example 9: Full Command Module (Complete Example)
# =============================================================================

"""
This is what a complete command module would look like after migration.
File: src/cli/commands/analysis.py
"""

# --- File: src/cli/commands/analysis.py ---

"""
Advanced analysis commands for semiconductor device characterization.

Provides specialized analysis tools beyond standard plotting:
- Statistical analysis
- Trend detection
- Anomaly detection
- Comparative analysis
"""

from typing import Optional, List
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import polars as pl

from src.cli.plugin_system import cli_command
from src.cli.helpers import parse_seq_list, load_history_for_plotting

console = Console()


@cli_command(
    name="analyze-trends",
    group="analysis",
    description="Analyze parameter trends over time",
    priority=50
)
def analyze_trends_command(
    chip_number: int = typer.Argument(..., help="Chip number"),
    parameter: str = typer.Option(..., "--parameter", "-p", help="Parameter to analyze (VG, VDS, etc.)"),
    chip_group: str = typer.Option("Alisson", "--group", "-g"),
    history_dir: Path = typer.Option(Path("data/02_stage/chip_histories"), "--history-dir"),
):
    """
    Analyze trends in measurement parameters over time.

    Detects:
    - Linear trends (improvement/degradation)
    - Step changes (sudden shifts)
    - Cyclical patterns

    Examples:
        python process_and_analyze.py analyze-trends 67 --parameter VG
        python process_and_analyze.py analyze-trends 67 -p VDS --group Alisson
    """
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Trend Analysis: {chip_group}{chip_number}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    console.print(f"[cyan]Analyzing parameter:[/cyan] {parameter}")
    console.print(f"[cyan]Loading data...[/cyan]")

    # Mock analysis
    console.print()
    console.print("[green]✓ Analysis complete[/green]")
    console.print()

    # Mock results
    results = Table(title="Trend Analysis Results")
    results.add_column("Metric", style="cyan")
    results.add_column("Value", style="yellow")

    results.add_row("Trend Direction", "Stable")
    results.add_row("Linear Slope", "0.002 V/day")
    results.add_row("R² Score", "0.95")
    results.add_row("Anomalies Detected", "2")

    console.print(results)
    console.print()


@cli_command(
    name="compare-chips",
    group="analysis",
    description="Compare characteristics across multiple chips"
)
def compare_chips_command(
    chips: str = typer.Argument(..., help="Comma-separated chip numbers (e.g., '67,72,81')"),
    metric: str = typer.Option("all", "--metric", "-m", help="Metric to compare"),
    chip_group: str = typer.Option("Alisson", "--group", "-g"),
):
    """
    Compare characteristics across multiple chips.

    Metrics:
    - IVg characteristics (threshold voltage, on/off ratio)
    - Photoresponse (responsivity, response time)
    - Stability (drift over time)

    Examples:
        python process_and_analyze.py compare-chips 67,72,81
        python process_and_analyze.py compare-chips 67,72,81 --metric photoresponse
    """
    chip_list = [int(c.strip()) for c in chips.split(",")]

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Chip Comparison[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    console.print(f"[cyan]Comparing {len(chip_list)} chips:[/cyan] {', '.join(map(str, chip_list))}")
    console.print(f"[cyan]Metric:[/cyan] {metric}")
    console.print()

    # Mock comparison
    comparison = Table(title="Chip Comparison Results")
    comparison.add_column("Chip", style="cyan")
    comparison.add_column("Threshold Voltage", style="yellow")
    comparison.add_column("On/Off Ratio", style="yellow")
    comparison.add_column("Responsivity", style="yellow")

    for chip in chip_list:
        comparison.add_row(
            f"{chip_group}{chip}",
            "−0.35 V",
            "10⁵",
            "0.42 A/W"
        )

    console.print(comparison)
    console.print()
    console.print("[green]✓ Comparison complete[/green]")
    console.print()


# --- End of src/cli/commands/analysis.py ---


# =============================================================================
# Example 10: Main.py with Plugin Discovery
# =============================================================================

"""
This is what main.py would look like with the plugin system.
Compare to the current 40+ lines of manual imports/registrations.
"""

# --- File: src/cli/main.py (NEW VERSION) ---

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
# This single line replaces 40+ lines of imports and registrations!
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

# --- End of src/cli/main.py ---


# =============================================================================
# Summary
# =============================================================================

"""
These examples demonstrate:

1. Basic decorator usage (@cli_command)
2. Migration of existing commands (minimal changes)
3. Multiple commands per module
4. Third-party plugins
5. Experimental features (can be disabled)
6. Utility commands (list-plugins)
7. Class-based plugins with lifecycle hooks
8. Configuration-aware commands
9. Complete command module structure
10. Simplified main.py (40 lines → 10 lines)

Key Benefits:
- No main.py changes when adding commands
- Configuration-driven command availability
- Third-party extension support
- Clean separation of concerns
- Easy to test individual commands
- Backward compatible with existing commands

See CLI_PLUGIN_SYSTEM.md for full architecture documentation.
"""
