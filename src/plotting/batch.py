"""
Batch plotting engine for efficient multi-plot generation.

This module provides optimized batch plotting with:
- Single process execution (eliminates subprocess overhead)
- Cached chip history loading (load once, reuse for all plots)
- Optional parallelization using ProcessPoolExecutor
- Integrated data caching for Parquet files

Performance:
- Sequential: 3-5x faster than subprocess execution
- Parallel: 10-15x faster for large batches (>10 plots)
"""

from __future__ import annotations

import os
import time
import sys
import io
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend (batch plotting saves to files, never displays)

import yaml
import polars as pl
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# Import caching module and enable immediately if available
try:
    from src.core.data_cache import enable_parquet_caching, cache_stats
    CACHE_AVAILABLE = True
    # Enable caching at import time (before plotting modules import)
    enable_parquet_caching()
except ImportError:
    CACHE_AVAILABLE = False

# Import plotting modules after caching is enabled
from src.plotting.its import plot_its_overlay, plot_its_sequential
from src.plotting.ivg import plot_ivg_sequence
from src.plotting.transconductance import (
    plot_ivg_transconductance,
    plot_ivg_transconductance_savgol,
)
from src.plotting.vvg import plot_vvg_sequence
from src.plotting.vt import plot_vt_overlay, plot_vt_sequential
from src.plotting import its_photoresponse
from src.plotting.photoresponse import plot_photoresponse
from src.plotting.config import PlotConfig

# Import CLI utilities
from src.cli.helpers import parse_seq_list


# ============================================================================
# Global state (loaded once, reused across plots)
# ============================================================================
_cached_histories: dict[int, pl.DataFrame] = {}
_plot_config: PlotConfig | None = None
_chip_group: str | None = None  # Track chip group for folder prefix

# Two consoles with different purposes:
# - console: general messages, affected by suppress_output() (uses lazy sys.stdout)
# - _progress_console: progress bars only, immune to suppress_output() (pinned to real stdout)
console = Console()
_progress_console = Console(file=sys.__stdout__)


# ============================================================================
# Output suppression utilities
# ============================================================================
@contextmanager
def suppress_output(allow_errors: bool = True):
    """
    Context manager to suppress stdout/stderr during plotting.

    This prevents noisy output from plotting functions (theme messages,
    file save messages, etc.) from interfering with the progress bar.

    Parameters
    ----------
    allow_errors : bool
        If True, still allow error/warning messages through
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        # Redirect to StringIO buffers
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        yield
    finally:
        # Restore original streams
        captured_stderr = sys.stderr.getvalue()
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        # Show captured errors/warnings if allowed
        if allow_errors and captured_stderr:
            # Only show actual errors/warnings, not info messages
            for line in captured_stderr.split('\n'):
                if line and ('error' in line.lower() or 'warning' in line.lower()):
                    console.print(f"[dim]{line}[/dim]")


@contextmanager
def null_context():
    """Null context manager that does nothing."""
    yield


# ============================================================================
# Data structures
# ============================================================================
@dataclass
class PlotSpec:
    """Specification for a single plot."""

    type: str
    chip: int
    seq: str | list[int]
    tag: str | None = None
    legend_by: str = "irradiated_power"
    extra_args: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable representation."""
        seq_str = ",".join(map(str, self.seq)) if isinstance(self.seq, list) else str(self.seq)
        tag_str = f" ({self.tag})" if self.tag else ""
        return f"{self.type:25s} chip={self.chip} seq={seq_str:15s}{tag_str}"


@dataclass
class PlotResult:
    """Result of executing a plot."""

    spec: PlotSpec
    success: bool
    elapsed: float
    error: str | None = None
    plots_generated: int = 0  # Number of plots generated (useful for suite type)
    warnings: list[str] = None  # Captured warnings

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# ============================================================================
# Configuration loading
# ============================================================================
def load_batch_config(config_path: Path) -> tuple[int, str, list[PlotSpec]]:
    """
    Load batch configuration from YAML file.

    Parameters
    ----------
    config_path : Path
        Path to YAML configuration file

    Returns
    -------
    tuple[int, str, list[PlotSpec]]
        Tuple of (chip_number, chip_group, plot_specs)

    Raises
    ------
    FileNotFoundError
        If config file does not exist
    ValueError
        If config file is malformed
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    chip = config["chip"]
    chip_group = config.get("chip_group", "Alisson")
    defaults = config.get("defaults", {})

    plot_specs = []
    for plot_def in config["plots"]:
        plot_type = plot_def.pop("type")
        seq = plot_def.pop("seq")
        tag = plot_def.pop("tag", None)
        legend_by = plot_def.pop("legend_by", defaults.get("legend_by", "irradiated_power"))

        # Remaining keys are extra arguments
        extra_args = plot_def if plot_def else {}

        spec = PlotSpec(
            type=plot_type,
            chip=chip,
            seq=seq,
            tag=tag,
            legend_by=legend_by,
            extra_args=extra_args,
        )
        plot_specs.append(spec)

    return chip, chip_group, plot_specs


# ============================================================================
# Data loading (with caching)
# ============================================================================
def get_chip_history(chip: int, chip_group: str) -> pl.DataFrame:
    """
    Load chip history with caching.

    Loads once per chip and reuses for all subsequent plots.
    Prefers enriched history (with calibrated power) if available.

    Parameters
    ----------
    chip : int
        Chip number
    chip_group : str
        Chip group name (e.g., "Alisson")

    Returns
    -------
    pl.DataFrame
        Chip history dataframe (enriched if available)

    Raises
    ------
    FileNotFoundError
        If chip history file does not exist
    ValueError
        If history is missing required columns
    """
    global _cached_histories

    if chip not in _cached_histories:
        console.print(f"[dim]Loading history for {chip_group}{chip}...[/dim]")
        start = time.time()

        chip_name = f"{chip_group}{chip}"

        # Try enriched history first (has irradiated_power_w for legends)
        enriched_dir = Path("data/03_derived/chip_histories_enriched")
        enriched_file = enriched_dir / f"{chip_name}_history.parquet"

        if enriched_file.exists():
            console.print(f"[green]✓[/green] Using enriched history (with calibrated power)")
            history = pl.read_parquet(enriched_file)
            history_source = "enriched"
        else:
            # Fall back to standard history
            from src.cli.main import get_config
            config = get_config()
            history_dir = config.history_dir

            history_file = history_dir / f"{chip_name}_history.parquet"

            if not history_file.exists():
                raise FileNotFoundError(
                    f"Chip history file not found: {history_file}\n"
                    f"Run 'build-all-histories' command first to generate history files."
                )

            console.print(
                f"[yellow]⚠[/yellow]  Using standard history (enriched not found)\n"
                f"[dim]   → Power legends may not show. Run: enrich-history {chip}[/dim]"
            )
            history = pl.read_parquet(history_file)
            history_source = "standard"

        # Use parquet_path (staged Parquet) if available
        if "parquet_path" in history.columns:
            history = history.drop("source_file") if "source_file" in history.columns else history
            history = history.rename({"parquet_path": "source_file"})
        elif "source_file" not in history.columns:
            raise ValueError(
                f"History for chip {chip} missing both 'parquet_path' and 'source_file' columns"
            )

        _cached_histories[chip] = history
        elapsed = time.time() - start
        console.print(f"[green]✓[/green] Loaded {history.height} experiments in {elapsed:.2f}s\n")

    return _cached_histories[chip]


def get_plot_config(chip_group: str) -> PlotConfig:
    """
    Get plot configuration with chip-specific folder prefix.

    Creates a new config if chip_group changes or first call.

    Parameters
    ----------
    chip_group : str
        Chip group name (e.g., "Alisson") for folder prefix

    Returns
    -------
    PlotConfig
        Plot configuration with chip_subdir_enabled=True and correct prefix
    """
    global _plot_config, _chip_group

    # Create new config if first call or chip_group changed
    if _plot_config is None or _chip_group != chip_group:
        # Enable chip-first hierarchy with chip_group as folder prefix
        _plot_config = PlotConfig(
            chip_subdir_enabled=True,
            chip_folder_prefix=chip_group
        )
        _chip_group = chip_group

    return _plot_config


# ============================================================================
# Plot execution
# ============================================================================
def execute_plot(spec: PlotSpec, chip_group: str, quiet: bool = True) -> PlotResult:
    """
    Execute a single plot by calling plotting functions directly.

    Parameters
    ----------
    spec : PlotSpec
        Plot specification
    chip_group : str
        Chip group name (e.g., "Alisson")
    quiet : bool
        If True, suppress output from plotting functions (default: True)

    Returns
    -------
    PlotResult
        Execution result with timing and error information
    """
    start = time.time()
    plots_generated = 0
    warnings = []

    try:
        # Load chip history (from cache if available)
        # Suppress output if quiet (handles worker reloading case)
        with suppress_output() if quiet else null_context():
            history = get_chip_history(spec.chip, chip_group)

        # Parse sequence list
        if isinstance(spec.seq, list):
            seq_list = spec.seq
        else:
            seq_list = parse_seq_list(str(spec.seq))

        # Filter history by sequence numbers
        df = history.filter(pl.col("seq").is_in(seq_list))

        if df.height == 0:
            return PlotResult(
                spec=spec,
                success=False,
                elapsed=time.time() - start,
                error=f"No experiments found for seq={spec.seq}",
            )

        # Generate tag if not provided
        tag = spec.tag or f"seq_{'_'.join(map(str, seq_list))}"

        # Get plot config with chip group for correct folder prefix
        config = get_plot_config(chip_group)

        # Base directory (current directory, plotting functions handle paths)
        base_dir = Path(".")

        # Execute appropriate plot function with output suppression
        if spec.type == "plot-its":
            with suppress_output() if quiet else null_context():
                plot_its_overlay(df, base_dir, tag, legend_by=spec.legend_by, config=config)
            plots_generated = 1

        elif spec.type == "plot-its-sequential":
            with suppress_output() if quiet else null_context():
                plot_its_sequential(df, base_dir, tag, legend_by=spec.legend_by, config=config)
            plots_generated = 1

        elif spec.type == "plot-ivg":
            # Filter for IVg procedures only
            df_ivg = df.filter(pl.col("proc") == "IVg") if "proc" in df.columns else df
            if df_ivg.height == 0:
                return PlotResult(
                    spec=spec,
                    success=False,
                    elapsed=time.time() - start,
                    error="No IVg experiments found in selection",
                )
            with suppress_output() if quiet else null_context():
                plot_ivg_sequence(df_ivg, base_dir, tag, config=config)
            plots_generated = 1

        elif spec.type == "plot-transconductance":
            # Filter for IVg procedures only
            df_ivg = df.filter(pl.col("proc") == "IVg") if "proc" in df.columns else df
            if df_ivg.height == 0:
                return PlotResult(
                    spec=spec,
                    success=False,
                    elapsed=time.time() - start,
                    error="No IVg experiments found in selection",
                )

            # Extract transconductance parameters
            method = spec.extra_args.get("method", "savgol")
            window = spec.extra_args.get("window", 21)
            polyorder = spec.extra_args.get("polyorder", 7)

            with suppress_output() if quiet else null_context():
                if method == "savgol":
                    plot_ivg_transconductance_savgol(
                        df_ivg,
                        base_dir,
                        tag,
                        window_length=window,
                        polyorder=polyorder,
                        config=config,
                    )
                else:  # gradient
                    plot_ivg_transconductance(df_ivg, base_dir, tag, config=config)
            plots_generated = 1

        elif spec.type == "plot-vvg":
            df_vvg = df.filter(pl.col("proc") == "VVg") if "proc" in df.columns else df
            if df_vvg.height == 0:
                return PlotResult(
                    spec=spec,
                    success=False,
                    elapsed=time.time() - start,
                    error="No VVg experiments found in selection",
                )
            with suppress_output() if quiet else null_context():
                plot_vvg_sequence(df_vvg, base_dir, tag, config=config)
            plots_generated = 1

        elif spec.type == "plot-vt":
            df_vt = df.filter(pl.col("proc") == "Vt") if "proc" in df.columns else df
            if df_vt.height == 0:
                return PlotResult(
                    spec=spec,
                    success=False,
                    elapsed=time.time() - start,
                    error="No Vt experiments found in selection",
                )
            with suppress_output() if quiet else null_context():
                plot_vt_overlay(df_vt, base_dir, tag, config=config)
            plots_generated = 1

        elif spec.type == "plot-its-suite":
            # Unified ITS plotting: generates overlay, sequential, and photoresponse plots
            # This is a convenience type that replaces 3 separate plot entries

            # Filter for It procedures only (ITS measurements)
            df_its = df.filter(pl.col("proc") == "It") if "proc" in df.columns else df
            if df_its.height == 0:
                return PlotResult(
                    spec=spec,
                    success=False,
                    elapsed=time.time() - start,
                    error="No It (ITS) experiments found in selection",
                )

            chip_name = f"{chip_group}{spec.chip}"

            # Suppress output during suite generation
            with suppress_output() if quiet else null_context():
                # 1. Generate ITS overlay plot
                plot_its_overlay(df_its, base_dir, tag, legend_by=spec.legend_by, config=config)
                plots_generated += 1

                # 2. Generate ITS sequential plot (separate panels)
                plot_its_sequential(df_its, base_dir, f"{tag}_seq", legend_by=spec.legend_by, config=config)
                plots_generated += 1

                # 3. Generate photoresponse vs power plot
                # Extract photoresponse plotting parameters
                x_axis = spec.extra_args.get("photoresponse_x", "power")  # power, wavelength, time, gate_voltage
                filter_wavelength = spec.extra_args.get("filter_wavelength", None)
                filter_vg = spec.extra_args.get("filter_vg", None)
                axtype = spec.extra_args.get("axtype", None)

                # Only generate photoresponse if we have light experiments
                df_its_light = df_its.filter(pl.col("has_light") == True) if "has_light" in df_its.columns else df_its
                if df_its_light.height > 0:
                    try:
                        its_photoresponse.plot_its_photoresponse(
                            df_its_light,
                            chip_name,
                            x_axis,
                            filter_wavelength=filter_wavelength,
                            filter_vg=filter_vg,
                            filter_power_range=None,
                            plot_tag=f"{tag}_photoresponse",
                            axtype=axtype,
                            config=config
                        )
                        plots_generated += 1
                    except Exception as e:
                        # Photoresponse plotting may fail if metrics not extracted
                        # Don't fail the whole suite, just capture warning
                        warnings.append(f"Photoresponse plot skipped for {tag}: {str(e)}")

        elif spec.type == "plot-vts-suite":
            # Unified Vt plotting: overlay, sequential, and photoresponse (delta voltage)
            df_vt = df.filter(pl.col("proc") == "Vt") if "proc" in df.columns else df
            if df_vt.height == 0:
                return PlotResult(
                    spec=spec,
                    success=False,
                    elapsed=time.time() - start,
                    error="No Vt experiments found in selection",
                )

            chip_name = f"{chip_group}{spec.chip}"

            baseline_t = spec.extra_args.get("baseline_t", 60.0)
            baseline_mode = spec.extra_args.get("baseline_mode", "fixed")
            baseline_auto_divisor = spec.extra_args.get("baseline_auto_divisor", 2.0)
            plot_start_time = spec.extra_args.get("plot_start_time", None)
            padding = spec.extra_args.get("padding", None)
            resistance = spec.extra_args.get("resistance", False)
            absolute = spec.extra_args.get("absolute", False)

            with suppress_output() if quiet else null_context():
                # 1. Overlay plot
                plot_vt_overlay(
                    df_vt,
                    base_dir,
                    tag,
                    baseline_t=baseline_t,
                    baseline_mode=baseline_mode,
                    baseline_auto_divisor=baseline_auto_divisor,
                    plot_start_time=plot_start_time,
                    legend_by=spec.legend_by,
                    padding=padding,
                    resistance=resistance,
                    absolute=absolute,
                    config=config,
                )
                plots_generated += 1

                # 2. Sequential plot
                plot_vt_sequential(
                    df_vt,
                    base_dir,
                    f"{tag}_seq",
                    plot_start_time=plot_start_time,
                    legend_by=spec.legend_by,
                    padding=padding,
                    resistance=resistance,
                    absolute=absolute,
                    config=config,
                )
                plots_generated += 1

                # 3. Photoresponse vs x (delta voltage)
                x_axis = spec.extra_args.get("photoresponse_x", "power")
                filter_wavelength = spec.extra_args.get("filter_wavelength", None)
                filter_vg = spec.extra_args.get("filter_vg", None)
                filter_power_range = spec.extra_args.get("filter_power_range", None)

                try:
                    plot_photoresponse(
                        df_vt,
                        chip_name,
                        x_variable=x_axis,
                        y_metric="delta_voltage",
                        procedures=["Vt"],
                        filter_wavelength=filter_wavelength,
                        filter_vg=filter_vg,
                        filter_power_range=filter_power_range,
                        plot_tag=f"{tag}_photoresponse",
                        output_procedure="Vt",
                        output_metadata={"has_light": True},
                        filename_prefix=f"{chip_name.lower()}_Vt_photoresponse",
                        config=config,
                    )
                    plots_generated += 1
                except Exception as e:
                    warnings.append(f"Photoresponse plot skipped for {tag}: {str(e)}")

        else:
            return PlotResult(
                spec=spec,
                success=False,
                elapsed=time.time() - start,
                error=f"Unknown plot type: {spec.type}",
            )

        # Success!
        elapsed = time.time() - start
        return PlotResult(
            spec=spec,
            success=True,
            elapsed=elapsed,
            plots_generated=plots_generated,
            warnings=warnings
        )

    except Exception as e:
        elapsed = time.time() - start
        return PlotResult(
            spec=spec,
            success=False,
            elapsed=elapsed,
            error=str(e),
            plots_generated=plots_generated,
            warnings=warnings
        )


# ============================================================================
# Batch execution
# ============================================================================
def execute_sequential(plot_specs: list[PlotSpec], chip_group: str) -> list[PlotResult]:
    """
    Execute plots sequentially with progress bar.

    Parameters
    ----------
    plot_specs : list[PlotSpec]
        List of plot specifications
    chip_group : str
        Chip group name (e.g., "Alisson")

    Returns
    -------
    list[PlotResult]
        List of execution results
    """
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=_progress_console,
    ) as progress:
        task = progress.add_task("[cyan]Generating plots...", total=len(plot_specs))

        for i, spec in enumerate(plot_specs, 1):
            # Update progress with current task
            tag_str = f" ({spec.tag})" if spec.tag else ""
            progress.update(task, description=f"[cyan]Processing:[/cyan] {spec.type}{tag_str}")

            result = execute_plot(spec, chip_group, quiet=True)
            results.append(result)

            # Update progress with completion status
            status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
            plots_info = f" [{result.plots_generated} plots]" if result.plots_generated > 1 else ""
            progress.update(
                task,
                advance=1,
                description=f"{status} {spec.type}{tag_str}{plots_info} ({result.elapsed:.1f}s)"
            )

            # Show warnings immediately if any
            if result.warnings:
                for warning in result.warnings:
                    _progress_console.print(f"  [yellow]⚠[/yellow] {warning}")

    return results


def _worker_init():
    """Silence all output in worker processes to prevent terminal corruption."""
    devnull = open(os.devnull, "w")
    sys.stdout = devnull
    sys.stderr = devnull
    sys.__stdout__ = devnull
    sys.__stderr__ = devnull


def execute_parallel(plot_specs: list[PlotSpec], chip_group: str, workers: int) -> list[PlotResult]:
    """
    Execute plots in parallel with progress bar.

    Parameters
    ----------
    plot_specs : list[PlotSpec]
        List of plot specifications
    chip_group : str
        Chip group name (e.g., "Alisson")
    workers : int
        Number of parallel workers

    Returns
    -------
    list[PlotResult]
        List of execution results
    """
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=_progress_console,
    ) as progress:
        task = progress.add_task("[cyan]Generating plots...", total=len(plot_specs))

        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init) as executor:
            # Submit all tasks (quiet mode enabled for parallel execution)
            futures = {executor.submit(execute_plot, spec, chip_group, True): spec for spec in plot_specs}

            # Collect results as they complete
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                # Update progress with completion status
                status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
                tag_str = f" ({result.spec.tag})" if result.spec.tag else ""
                plots_info = f" [{result.plots_generated} plots]" if result.plots_generated > 1 else ""
                progress.update(
                    task,
                    advance=1,
                    description=f"{status} {result.spec.type}{tag_str}{plots_info} ({result.elapsed:.1f}s)"
                )

                # Show warnings if any
                if result.warnings:
                    for warning in result.warnings:
                        _progress_console.print(f"  [yellow]⚠[/yellow] {warning}")

    return results


# ============================================================================
# Display utilities
# ============================================================================
def display_summary(results: list[PlotResult], total_time: float, parallel_workers: int | None):
    """
    Display execution summary.

    Parameters
    ----------
    results : list[PlotResult]
        Execution results
    total_time : float
        Total execution time in seconds
    parallel_workers : int or None
        Number of parallel workers (None for sequential)
    """
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_plots_generated = sum(r.plots_generated for r in results if r.success)
    total_warnings = sum(len(r.warnings) for r in results if r.warnings)

    # Create summary table
    table = Table(title="Batch Plot Summary", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Plot entries", str(len(results)))
    table.add_row("Files generated", f"[green]{total_plots_generated}[/green]")
    table.add_row("Successful", f"[green]{successful}[/green]")
    if failed > 0:
        table.add_row("Failed", f"[red]{failed}[/red]")
    if total_warnings > 0:
        table.add_row("Warnings", f"[yellow]{total_warnings}[/yellow]")
    table.add_row("Total time", f"{total_time:.1f}s")
    table.add_row("Average time", f"{total_time/len(results):.1f}s per entry")

    if parallel_workers and parallel_workers > 1:
        # Calculate parallel speedup
        sequential_time = sum(r.elapsed for r in results)
        speedup = sequential_time / total_time
        table.add_row("Parallel speedup", f"[cyan]{speedup:.1f}x[/cyan]")
        table.add_row("Workers", str(parallel_workers))

    console.print("\n")
    console.print(table)

    # Show failed plots if any
    if failed > 0:
        console.print("\n[yellow]Failed plots:[/yellow]")
        for result in results:
            if not result.success:
                console.print(f"  • {result.spec}")
                if result.error:
                    console.print(f"    [dim]{result.error}[/dim]")

    # Show summary of warnings
    if total_warnings > 0:
        console.print(f"\n[dim]See warnings above for details ({total_warnings} warnings)[/dim]")


def print_cache_stats():
    """Print cache statistics if caching is available."""
    if not CACHE_AVAILABLE:
        return

    stats = cache_stats()
    console.print("\n" + "=" * 60)
    console.print("Data Cache Statistics")
    console.print("=" * 60)
    console.print(f"Cache size:      {stats['size']}/{stats['maxsize']} items")
    console.print(f"Total requests:  {stats['total_requests']}")
    console.print(f"Cache hits:      {stats['hits']}")
    console.print(f"Cache misses:    {stats['misses']}")
    console.print(f"Hit rate:        {stats['hit_rate_pct']}")
    console.print("=" * 60)

    # Performance estimate
    if stats["total_requests"] > 0:
        # Assume 100ms saved per cache hit (conservative estimate)
        time_saved_seconds = stats["hits"] * 0.1
        console.print(f"\nEstimated time saved: ~{time_saved_seconds:.1f}s from cached reads")
    console.print()
