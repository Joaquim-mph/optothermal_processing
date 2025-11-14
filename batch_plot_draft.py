#!/usr/bin/env python3
"""
Batch plot processor for efficient multi-plot generation.

Usage:
    python batch_plot.py alisson67_plots.yaml --parallel 4
    python batch_plot.py alisson67_plots.yaml --sequential
"""

from __future__ import annotations
import yaml
from pathlib import Path
from typing import Any, Dict, List
import time
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import polars as pl
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

app = typer.Typer()
console = Console()


@dataclass
class PlotSpec:
    """Specification for a single plot."""
    type: str
    chip: int
    seq: str | list[int]
    tag: str | None = None
    legend_by: str = "irradiated_power"
    extra_args: dict[str, Any] | None = None

    def to_cli_command(self) -> list[str]:
        """Convert to CLI command arguments."""
        cmd = ["python", "process_and_analyze.py", self.type, str(self.chip)]
        
        # Handle seq parameter
        if isinstance(self.seq, list):
            seq_str = ",".join(map(str, self.seq))
        else:
            seq_str = str(self.seq)
        cmd.extend(["--seq", seq_str])
        
        # Add legend_by
        if self.legend_by:
            cmd.extend(["--legend", self.legend_by])
        
        # Add extra arguments
        if self.extra_args:
            for key, val in self.extra_args.items():
                cmd.append(f"--{key}")
                if val is not True:  # Don't add value for boolean flags
                    cmd.append(str(val))
        
        return cmd

    def __str__(self) -> str:
        """Human-readable representation."""
        seq_str = ",".join(map(str, self.seq)) if isinstance(self.seq, list) else self.seq
        tag_str = f" ({self.tag})" if self.tag else ""
        return f"{self.type} chip={self.chip} seq={seq_str}{tag_str}"


def load_batch_config(config_path: Path) -> tuple[int, List[PlotSpec]]:
    """Load batch configuration from YAML file."""
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    chip = config["chip"]
    defaults = config.get("defaults", {})
    
    plot_specs = []
    for plot_def in config["plots"]:
        plot_type = plot_def.pop("type")
        seq = plot_def.pop("seq")
        tag = plot_def.pop("tag", None)
        legend_by = plot_def.pop("legend_by", defaults.get("legend_by", "irradiated_power"))
        
        # Remaining keys are extra arguments
        extra_args = plot_def if plot_def else None
        
        spec = PlotSpec(
            type=plot_type,
            chip=chip,
            seq=seq,
            tag=tag,
            legend_by=legend_by,
            extra_args=extra_args
        )
        plot_specs.append(spec)
    
    return chip, plot_specs


def execute_plot_direct(spec: PlotSpec) -> tuple[PlotSpec, float, bool]:
    """
    Execute a single plot by importing and calling the function directly.
    This avoids subprocess overhead.
    
    Returns:
        Tuple of (spec, execution_time, success)
    """
    import sys
    from pathlib import Path
    
    # Add project root to path if needed
    # sys.path.insert(0, str(Path(__file__).parent))
    
    start = time.time()
    success = False
    
    try:
        # Import the necessary modules
        from src.core.history import load_chip_history
        from src.plotting.its import plot_its_overlay, plot_its_sequential
        from src.plotting.ivg import plot_ivg_overlay, plot_transconductance_overlay
        from src.plotting.config import PlotConfig
        
        # Load chip data once
        history = load_chip_history(spec.chip)
        base_dir = Path(".") / "data" / "staged"
        config = PlotConfig()
        
        # Parse sequence
        if isinstance(spec.seq, list):
            seq_list = spec.seq
        elif "-" in str(spec.seq):
            start_seq, end_seq = map(int, str(spec.seq).split("-"))
            seq_list = list(range(start_seq, end_seq + 1))
        else:
            seq_list = [int(spec.seq)]
        
        # Filter dataframe
        df = history.filter(pl.col("seq").is_in(seq_list))
        
        if len(df) == 0:
            console.print(f"[yellow]No data found for {spec}[/yellow]")
            return spec, time.time() - start, False
        
        # Generate tag if not provided
        tag = spec.tag or f"seq_{'_'.join(map(str, seq_list))}"
        
        # Execute appropriate plot function
        if spec.type == "plot-its":
            plot_its_overlay(df, base_dir, tag, legend_by=spec.legend_by, config=config)
            success = True
            
        elif spec.type == "plot-its-sequential":
            plot_its_sequential(df, base_dir, tag, legend_by=spec.legend_by, config=config)
            success = True
            
        elif spec.type == "plot-ivg":
            from src.plotting.ivg import plot_ivg_overlay
            # Need to filter for IVg procedures
            df_ivg = df.filter(pl.col("proc") == "IVg")
            if len(df_ivg) > 0:
                plot_ivg_overlay(df_ivg, base_dir, tag, config=config)
                success = True
                
        elif spec.type == "plot-transconductance":
            from src.plotting.ivg import plot_transconductance_overlay
            df_ivg = df.filter(pl.col("proc") == "IVg")
            if len(df_ivg) > 0:
                extra = spec.extra_args or {}
                plot_transconductance_overlay(
                    df_ivg, 
                    base_dir, 
                    tag,
                    method=extra.get("method", "savgol"),
                    window=extra.get("window", 21),
                    polyorder=extra.get("polyorder", 7),
                    config=config
                )
                success = True
        else:
            console.print(f"[red]Unknown plot type: {spec.type}[/red]")
            
    except Exception as e:
        console.print(f"[red]Error executing {spec}: {e}[/red]")
        import traceback
        traceback.print_exc()
    
    elapsed = time.time() - start
    return spec, elapsed, success


def execute_plot_subprocess(spec: PlotSpec) -> tuple[PlotSpec, float, bool]:
    """
    Execute a single plot using subprocess (fallback method).
    
    Returns:
        Tuple of (spec, execution_time, success)
    """
    import subprocess
    
    start = time.time()
    cmd = spec.to_cli_command()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        success = result.returncode == 0
        if not success:
            console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
            console.print(f"[red]{result.stderr}[/red]")
    except subprocess.TimeoutExpired:
        console.print(f"[red]Timeout: {spec}[/red]")
        success = False
    except Exception as e:
        console.print(f"[red]Error: {spec}: {e}[/red]")
        success = False
    
    elapsed = time.time() - start
    return spec, elapsed, success


@app.command()
def main(
    config_file: Path = typer.Argument(..., help="YAML configuration file"),
    parallel: int = typer.Option(None, "--parallel", "-p", help="Number of parallel workers (default: sequential)"),
    method: str = typer.Option("direct", "--method", "-m", help="Execution method: 'direct' or 'subprocess'"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be executed without running"),
):
    """
    Execute batch plot generation from YAML configuration.
    
    Examples:
        # Sequential execution (fastest for small batches)
        python batch_plot.py config.yaml
        
        # Parallel execution with 4 workers
        python batch_plot.py config.yaml --parallel 4
        
        # Dry run to see what will be executed
        python batch_plot.py config.yaml --dry-run
    """
    
    if not config_file.exists():
        console.print(f"[red]Config file not found: {config_file}[/red]")
        raise typer.Exit(1)
    
    # Load configuration
    console.print(f"[cyan]Loading configuration from {config_file}...[/cyan]")
    chip, plot_specs = load_batch_config(config_file)
    
    console.print(f"[green]✓ Loaded {len(plot_specs)} plot specifications for chip {chip}[/green]\n")
    
    # Dry run
    if dry_run:
        console.print("[yellow]DRY RUN - Commands that would be executed:[/yellow]\n")
        for i, spec in enumerate(plot_specs, 1):
            console.print(f"{i:3d}. {spec}")
        return
    
    # Choose execution function
    execute_func = execute_plot_direct if method == "direct" else execute_plot_subprocess
    
    # Execute plots
    start_time = time.time()
    results = []
    
    if parallel and parallel > 1:
        # Parallel execution
        console.print(f"[cyan]Executing {len(plot_specs)} plots with {parallel} workers...[/cyan]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Generating plots...", total=len(plot_specs))
            
            with ProcessPoolExecutor(max_workers=parallel) as executor:
                futures = {executor.submit(execute_func, spec): spec for spec in plot_specs}
                
                for future in as_completed(futures):
                    spec, elapsed, success = future.result()
                    results.append((spec, elapsed, success))
                    
                    status = "[green]✓[/green]" if success else "[red]✗[/red]"
                    progress.update(task, advance=1, description=f"{status} {spec} ({elapsed:.1f}s)")
    
    else:
        # Sequential execution
        console.print(f"[cyan]Executing {len(plot_specs)} plots sequentially...[/cyan]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Generating plots...", total=len(plot_specs))
            
            for spec in plot_specs:
                spec_result, elapsed, success = execute_func(spec)
                results.append((spec_result, elapsed, success))
                
                status = "[green]✓[/green]" if success else "[red]✗[/red]"
                progress.update(task, advance=1, description=f"{status} {spec} ({elapsed:.1f}s)")
    
    # Summary
    total_time = time.time() - start_time
    successful = sum(1 for _, _, success in results if success)
    failed = len(results) - successful
    
    console.print("\n" + "="*70)
    console.print(f"[bold]Batch Plot Summary[/bold]")
    console.print("="*70)
    console.print(f"Total plots:     {len(results)}")
    console.print(f"[green]Successful:      {successful}[/green]")
    if failed > 0:
        console.print(f"[red]Failed:          {failed}[/red]")
    console.print(f"Total time:      {total_time:.1f}s")
    console.print(f"Average time:    {total_time/len(results):.1f}s per plot")
    
    if parallel and parallel > 1:
        speedup = sum(t for _, t, _ in results) / total_time
        console.print(f"[cyan]Parallel speedup: {speedup:.1f}x[/cyan]")
    
    console.print("="*70 + "\n")
    
    if failed > 0:
        console.print("[yellow]Failed plots:[/yellow]")
        for spec, elapsed, success in results:
            if not success:
                console.print(f"  • {spec}")


if __name__ == "__main__":
    app()
