# Plotting Function Implementation Guide

**Last Updated:** October 31, 2025
**Applies to:** v3.0+

This guide provides step-by-step instructions and code templates for implementing plotting functions for each measurement procedure in the pipeline. It follows the project's established architecture and patterns from existing implementations (ITS, IVg, transconductance, CNP, photoresponse).

## Table of Contents

1. [Overview & Architecture](#overview--architecture)
2. [Configuration System Integration](#configuration-system-integration)
3. [Procedure Categories](#procedure-categories)
4. [Implementation Checklist](#implementation-checklist)
5. [Step-by-Step Instructions](#step-by-step-instructions)
6. [Procedure-Specific Templates](#procedure-specific-templates)
7. [Configuration Compliance Checklist](#configuration-compliance-checklist)

---

## Overview & Architecture

### Key Principles

The project uses a **separation of concerns** architecture:

- **Plotting logic** (`src/plotting/`) - Pure plotting functions, no CLI dependencies
- **CLI commands** (`src/cli/commands/`) - User interface using Typer, calls plotting functions
- **Helpers** (`src/cli/helpers.py`) - Shared utilities for seq parsing, filtering, display
- **Data access** (`src/core/utils.py`) - `read_measurement_parquet()` for loading staged data

### Data Flow

```
User runs CLI command
    ↓
CLI validates inputs & loads chip history (Parquet)
    ↓
Filters history by procedure & user criteria (seq, date, etc.)
    ↓
Calls plotting function with filtered history DataFrame
    ↓
Plotting function loads measurement data via parquet_path
    ↓
Generates matplotlib figure(s)
    ↓
Saves to output directory (figs/{chip}/)
    ↓
CLI displays success message
```

### Existing Implementations

**Reference these files as templates:**
- **Time-series (I vs t)**: `src/plotting/its.py` + `src/cli/commands/plot_its.py`
- **Voltage sweep (I vs Vg)**: `src/plotting/ivg.py` + `src/cli/commands/plot_ivg.py`
- **Derivative plot**: `src/plotting/transconductance.py` + `src/cli/commands/plot_transconductance.py`
- **Laser calibration**: `src/plotting/laser_calibration.py` + `src/cli/commands/plot_laser_calibration.py`

---

## Configuration System Integration

### Overview

**All plotting commands MUST support the persistent configuration system** introduced in the CLI refactor. This allows users to set default paths and options once, then use them across all commands.

### Configuration Architecture

**Configuration Sources (priority order):**
1. **Command-line arguments** - Explicit `--output-dir` or `--history-dir` flags
2. **Specified config file** - `--config my-config.json`
3. **Project config** - `./.optothermal_cli_config.json`
4. **User config** - `~/.optothermal_cli_config.json`
5. **Environment variables** - `CLI_OUTPUT_DIR`, `CLI_HISTORY_DIR`, etc.
6. **Built-in defaults** - Hardcoded in `src/cli/config.py`

### Key Configuration Fields for Plotting

```python
# From src/cli/config.py
class CLIConfig(BaseModel):
    # Directories
    output_dir: Path = Path("figs")
    history_dir: Path = Path("data/02_stage/chip_histories")

    # Behavior
    verbose: bool = False
    dry_run: bool = False

    # Plot settings
    default_plot_format: Literal["png", "pdf", "svg", "jpg"] = "png"
    plot_dpi: int = 300
```

### Required Pattern for CLI Commands

**CRITICAL**: All plotting commands must follow this pattern:

```python
@cli_command(...)
def plot_{procedure_name}_command(
    chip_number: int = typer.Argument(...),
    # ... other arguments ...
    history_dir: Optional[Path] = typer.Option(
        None,  # ✅ MUST be None, not a hardcoded default
        "--history-dir",
        help="Chip history directory (default: from config)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,  # ✅ MUST be None, not a hardcoded default
        "--output",
        "-o",
        help="Output directory (default: from config)"
    ),
):
    """Command docstring."""

    # ✅ STEP 1: Load config at the very start
    from src.cli.main import get_config
    config = get_config()

    # ✅ STEP 2: Apply config defaults with verbose logging
    if output_dir is None:
        output_dir = config.output_dir
        if config.verbose:
            console.print(f"[dim]Using output directory from config: {output_dir}[/dim]")

    if history_dir is None:
        history_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    # ✅ STEP 3: Use setup_output_dir helper (handles config value)
    output_dir = setup_output_dir(chip_number, chip_group, output_dir)

    # ✅ STEP 4: Set FIG_DIR before calling plotting function
    from src.plotting import {procedure_name}
    {procedure_name}.FIG_DIR = output_dir

    # Now call plotting function...
```

### Common Mistakes to Avoid

❌ **WRONG - Hardcoded default:**
```python
history_dir: Path = typer.Option(
    Path("data/02_stage/chip_histories"),  # ❌ Don't do this!
    "--history-dir"
)
```

❌ **WRONG - Not loading config:**
```python
def plot_something_command(...):
    # Missing config loading!
    if output_dir is None:
        output_dir = Path("figs")  # ❌ Hardcoded fallback
```

❌ **WRONG - Not setting FIG_DIR:**
```python
# Plotting function saves to hardcoded FIG_DIR
output_file = plot_something(selected, Path("."), tag)  # ❌ Wrong output location
```

✅ **CORRECT Pattern:**
```python
history_dir: Optional[Path] = typer.Option(None, "--history-dir",
    help="Chip history directory (default: from config)")

# Load config
config = get_config()
if history_dir is None:
    history_dir = config.history_dir
    if config.verbose:
        console.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

# Set module FIG_DIR before plotting
from src.plotting import procedure_module
procedure_module.FIG_DIR = output_dir
```

### Testing Configuration Support

After implementing a new plotting command, test configuration support:

```bash
# 1. Test with built-in defaults
python process_and_analyze.py plot-{procedure} 67 --auto

# 2. Test with verbose mode (shows config values)
python process_and_analyze.py --verbose plot-{procedure} 67 --auto

# 3. Test with global output override
python process_and_analyze.py --output-dir /tmp/plots plot-{procedure} 67 --auto

# 4. Test with custom config file
python process_and_analyze.py config-init --profile production
python process_and_analyze.py plot-{procedure} 67 --auto

# 5. Test with explicit command-line override
python process_and_analyze.py plot-{procedure} 67 --auto --output /custom/path
```

### Debugging Configuration Issues

If your command doesn't respect config:

1. **Check parameter type**: Must be `Optional[Path] = None`, not `Path = Path(...)`
2. **Check config loading**: Add `from src.cli.main import get_config` at start of function
3. **Check verbose output**: Run with `--verbose` to see which config is used
4. **Check FIG_DIR**: Ensure plotting module's `FIG_DIR` is set before calling plot function
5. **Check helper signature**: `setup_output_dir(chip, group, output_dir)` - note parameter order!

---

## Procedure Categories

Procedures are grouped by plot type for easier implementation:

### Category 1: Time-Series Electrical (like ITS/It)
**Procedures**: `ITt`, `It2`, `Vt`
- **X-axis**: Time (s)
- **Y-axis**: Current (A) or Voltage (V)
- **Features**: Laser ON/OFF phases, temperature data, baseline correction
- **Template**: Based on `its.py`

### Category 2: Voltage Sweeps (like IVg)
**Procedures**: `IVgT`, `VVg`
- **X-axis**: Gate voltage (V)
- **Y-axis**: Current (A) or Drain-source voltage (V)
- **Features**: Light/dark comparison, temperature data (IVgT)
- **Template**: Based on `ivg.py`

### Category 3: Time-Series with Stepped Parameter
**Procedures**: `ItVg`, `ItWl`
- **X-axis**: Time (s) within each step
- **Y-axis**: Current (A)
- **Features**: Multiple subplots or curves for each parameter step
- **Template**: Hybrid of `its.py` + multi-curve logic

### Category 4: Optical Calibration/Power
**Procedures**: `LaserCalibration`, `Pt`, `Pwl`
- **X-axis**: Laser voltage (V), Time (s), or Wavelength (nm)
- **Y-axis**: Optical power (W or mW)
- **Features**: Calibration curves, stability plots
- **Template**: Simpler than electrical, focus on clarity

### Category 5: Thermal Characterization
**Procedures**: `Tt`
- **X-axis**: Time (s)
- **Y-axis**: Temperature (°C)
- **Features**: Plate vs ambient temperature, ramp profiles
- **Template**: Based on time-series pattern

---

## Implementation Checklist

For each procedure, follow this checklist:

### Phase 1: Planning (10 min)
- [ ] Identify procedure category (time-series, sweep, optical, thermal)
- [ ] Review `docs/PROCEDURES.md` for measurement details
- [ ] Check `config/procedures.yml` for data columns
- [ ] Choose reference implementation (its.py, ivg.py, etc.)

### Phase 2: Plotting Module (1-2 hours)
- [ ] Create `src/plotting/{procedure_name}.py`
- [ ] Import dependencies (matplotlib, polars, numpy, utils)
- [ ] Define main plotting function with standard signature
- [ ] Load measurement data using `read_measurement_parquet()`
- [ ] Handle column name normalization (upper/lower case variants)
- [ ] Apply plot style with `set_plot_style()`
- [ ] Implement procedure-specific logic (baseline, segmentation, etc.)
- [ ] Add axis labels, title, legend
- [ ] Save figure with consistent naming
- [ ] Add docstrings and type hints

### Phase 3: CLI Command (30-45 min)
- [ ] Create `src/cli/commands/plot_{procedure_name}.py`
- [ ] Use `@cli_command` decorator (auto-discovery!)
- [ ] Define Typer command with standard options
- [ ] **CRITICAL: Set `history_dir` and `output_dir` parameters to `Optional[Path] = None`**
- [ ] **CRITICAL: Load config at start with `get_config()`**
- [ ] **CRITICAL: Apply config defaults with verbose logging**
- [ ] Load chip history from Parquet
- [ ] Filter by procedure type
- [ ] Parse seq numbers or auto-select
- [ ] Apply metadata filters (VDS, date, wavelength, etc.)
- [ ] Setup output directory with `setup_output_dir(chip, group, output_dir)`
- [ ] **CRITICAL: Set plotting module's `FIG_DIR = output_dir` before calling plot function**
- [ ] Call plotting function
- [ ] Display success with `display_plot_success()`

### Phase 4: Testing & Refinement (30 min)
- [ ] Test with real data: `python3 process_and_analyze.py plot-{name} <chip> --auto`
- [ ] Verify plot quality (labels, legends, colors)
- [ ] Test filtering options (--seq, --vds, --date)
- [ ] **Test configuration support:**
  - [ ] Test with `--verbose` flag (should show config values)
  - [ ] Test with global `--output-dir` override
  - [ ] Test with custom `--config` file
  - [ ] Test with explicit command `--output` flag (should override config)
- [ ] Check edge cases (empty data, missing columns)
- [ ] Update CLAUDE.md if needed

---

## Step-by-Step Instructions

### Step 1: Create Plotting Module

**File**: `src/plotting/{procedure_name}.py`

```python
"""
{Procedure Name} plotting functions.

Brief description of what this procedure measures.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import polars as pl
from typing import Optional

from src.core.utils import read_measurement_parquet
from src.plotting.plot_utils import get_chip_label  # if needed

# Configuration
FIG_DIR = Path("figs")


def plot_{procedure_name}(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    # Add procedure-specific options here
) -> Path:
    """
    Generate {procedure name} plot.

    Parameters
    ----------
    df : pl.DataFrame
        Chip history DataFrame filtered to {ProcedureName} experiments
    base_dir : Path
        Base directory for loading measurement Parquet files
    tag : str
        Tag for output filename (typically chip identifier)

    Returns
    -------
    Path
        Path to saved plot file

    Examples
    --------
    >>> history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")
    >>> proc_data = history.filter(pl.col("proc") == "{ProcedureName}")
    >>> output = plot_{procedure_name}(proc_data, Path("."), "Alisson67")
    """
    # Apply plot style
    from src.plotting.styles import set_plot_style
    set_plot_style("prism_rain")  # or "default"

    # Filter and sort
    data = df.filter(pl.col("proc") == "{ProcedureName}").sort("seq")
    if data.height == 0:
        print("[warn] No {ProcedureName} experiments to plot")
        return None

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Iterate through experiments
    for row in data.iter_rows(named=True):
        # Load measurement data from staged Parquet
        parquet_path = Path(row["parquet_path"])
        if not parquet_path.exists():
            print(f"[warn] Missing file: {parquet_path}")
            continue

        measurement = read_measurement_parquet(parquet_path)

        # Normalize column names (handle case variations)
        col_map = {}
        if "t (s)" in measurement.columns:
            col_map["t (s)"] = "t"
        elif "Time (s)" in measurement.columns:
            col_map["Time (s)"] = "t"
        # Add more column normalizations as needed

        if col_map:
            measurement = measurement.rename(col_map)

        # Verify required columns exist
        required_cols = {"t", "I"}  # Adjust based on procedure
        if not required_cols <= set(measurement.columns):
            print(f"[warn] Missing columns in {parquet_path.name}: {required_cols - set(measurement.columns)}")
            continue

        # Extract data for plotting
        x = measurement["t"].to_numpy()
        y = measurement["I"].to_numpy()

        # Create label from metadata
        seq = int(row["seq"])
        wavelength = row.get("wavelength_nm")
        light_status = "light" if row.get("with_light", False) else "dark"
        label = f"seq {seq}: {wavelength:.0f}nm ({light_status})"

        # Plot
        ax.plot(x, y, label=label, linewidth=1.5)

    # Styling
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (A)")
    ax.set_title(f"{tag} — {ProcedureName}")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # Save figure
    output_dir = FIG_DIR / tag
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{procedure_name}_{tag}.png"

    fig.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)

    print(f"[info] Saved {output_file}")
    return output_file
```

### Step 2: Create CLI Command

**File**: `src/cli/commands/plot_{procedure_name}.py`

```python
"""
CLI command for {ProcedureName} plotting.
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
import polars as pl

from src.cli.plugin_system import cli_command
from src.cli.helpers import (
    parse_seq_list,
    setup_output_dir,
    auto_select_experiments,
    validate_experiments_exist,
    display_plot_success,
    display_experiment_list,
)
from src.plotting.{procedure_name} import plot_{procedure_name}

console = Console()


@cli_command(
    name="plot-{procedure-name}",  # Use kebab-case!
    group="plotting",
    description="Generate {ProcedureName} plots"
)
def plot_{procedure_name}_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Comma-separated seq numbers (e.g., '1,2,3' or '10-20')"
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        "-a",
        help="Auto-select all {ProcedureName} experiments"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    # Add procedure-specific filters
    vds: Optional[float] = typer.Option(
        None,
        "--vds",
        help="Filter by VDS voltage (V)"
    ),
    wavelength: Optional[float] = typer.Option(
        None,
        "--wavelength",
        "-wl",
        help="Filter by laser wavelength (nm)"
    ),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        help="Filter by date (YYYY-MM-DD)"
    ),
    history_dir: Optional[Path] = typer.Option(
        None,  # ✅ MUST be None for config support
        "--history-dir",
        help="Chip history directory (default: from config)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,  # ✅ MUST be None for config support
        "--output",
        "-o",
        help="Output directory (default: from config)"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Preview experiments without plotting"
    ),
):
    """
    Generate {ProcedureName} plots.

    Examples:
        # Plot specific experiments
        plot-{procedure-name} 67 --seq 1,2,3

        # Auto-select all experiments
        plot-{procedure-name} 67 --auto

        # Filter by wavelength
        plot-{procedure-name} 67 --auto --wavelength 450

        # Preview what will be plotted
        plot-{procedure-name} 67 --auto --preview
    """
    # Build chip identifier
    chip_name = f"{chip_group}{chip_number}"

    # ✅ Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    if output_dir is None:
        output_dir = config.output_dir
        if config.verbose:
            console.print(f"[dim]Using output directory from config: {output_dir}[/dim]")

    if history_dir is None:
        history_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    # Load chip history
    history_file = history_dir / f"{chip_name}_history.parquet"
    if not history_file.exists():
        console.print(f"[red]✗[/red] History file not found: {history_file}")
        console.print("[yellow]→[/yellow] Run: python3 process_and_analyze.py build-all-histories")
        raise typer.Exit(1)

    history = pl.read_parquet(history_file)

    # Filter to procedure type
    proc_history = history.filter(pl.col("proc") == "{ProcedureName}")
    if proc_history.height == 0:
        console.print(f"[red]✗[/red] No {ProcedureName} experiments found for {chip_name}")
        available = history["proc"].unique().to_list()
        console.print(f"[yellow]Available procedures:[/yellow] {', '.join(available)}")
        raise typer.Exit(1)

    # Get seq numbers
    if auto:
        # Auto-select with filters
        filters = {}
        if vds is not None:
            filters["vds"] = vds
        if wavelength is not None:
            filters["wavelength"] = wavelength
        if date is not None:
            filters["date"] = date

        seq_numbers = auto_select_experiments(
            chip_number,
            "{ProcedureName}",
            chip_group,
            history_dir,
            filters
        )
    elif seq:
        seq_numbers = parse_seq_list(seq)
    else:
        console.print("[red]✗[/red] Must specify --seq or --auto")
        raise typer.Exit(1)

    # Validate seq numbers exist
    validate_experiments_exist(proc_history, seq_numbers, "{ProcedureName}")

    # Filter to selected experiments
    selected = proc_history.filter(pl.col("seq").is_in(seq_numbers))

    # Display experiment list
    console.print()
    display_experiment_list(selected, f"{ProcedureName} Experiments")

    # Preview mode: stop here
    if preview:
        console.print("\n[cyan]Preview mode - no plots generated[/cyan]")
        return

    # ✅ Setup output directory (config already loaded earlier)
    output_dir = setup_output_dir(chip_number, chip_group, output_dir)

    # ✅ Set output directory for plotting module
    from src.plotting import {procedure_name}
    {procedure_name}.FIG_DIR = output_dir

    # Generate plot
    console.print(f"\n[cyan]Generating {ProcedureName} plot...[/cyan]")
    plot_tag = chip_name

    output_file = plot_{procedure_name}(
        selected,
        Path("."),  # Base dir not used since we have parquet_paths
        plot_tag
    )

    if output_file:
        display_plot_success(output_file)
```

### Step 3: Test Your Implementation

```bash
# Activate environment
source .venv/bin/activate

# Verify command is discovered
python3 process_and_analyze.py --help | grep plot-{procedure-name}

# Test with preview mode
python3 process_and_analyze.py plot-{procedure-name} 67 --auto --preview

# Generate actual plot
python3 process_and_analyze.py plot-{procedure-name} 67 --auto

# Test with filters
python3 process_and_analyze.py plot-{procedure-name} 67 --seq 1,2,3 --wavelength 450

# ✅ Test configuration support
python3 process_and_analyze.py --verbose plot-{procedure-name} 67 --auto  # Shows config values
python3 process_and_analyze.py --output-dir /tmp/plots plot-{procedure-name} 67 --auto  # Global override
python3 process_and_analyze.py plot-{procedure-name} 67 --auto --output /custom/path  # Command override
python3 process_and_analyze.py config-show  # View current config
```

---

## Procedure-Specific Templates

Below are specific implementation plans for each procedure, organized by category.

### Category 1: Time-Series Electrical

#### ITt (Current vs Time with Temperature)

**Description**: Like `It` but includes PT100 temperature data throughout.

**Data Columns** (from procedures.yml):
- `t (s)`: Time
- `I (A)`: Current
- `VL (V)`: Laser voltage
- `Plate T (degC)`: Plate temperature
- `Ambient T (degC)`: Ambient temperature
- `Clock (ms)`: Clock time

**Key Features**:
- Laser ON/OFF phases (use `Laser ON+OFF period` parameter)
- Temperature overlay or separate subplot
- Baseline correction (similar to ITS)

**Plot Design**:
```python
# Option 1: Dual y-axis (current + temperature)
fig, ax1 = plt.subplots(figsize=(12, 6))
ax1.plot(t, I, 'b-', label='Current')
ax1.set_ylabel('Current (A)', color='b')
ax2 = ax1.twinx()
ax2.plot(t, plate_temp, 'r--', label='Plate T')
ax2.plot(t, ambient_temp, 'orange', linestyle=':', label='Ambient T')
ax2.set_ylabel('Temperature (°C)', color='r')

# Option 2: Two subplots (stacked)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
ax1.plot(t, I)
ax2.plot(t, plate_temp, label='Plate')
ax2.plot(t, ambient_temp, label='Ambient')
```

**Implementation Hints**:
- Reuse baseline correction logic from `its.py`
- Use laser voltage (`VL (V)`) to detect ON/OFF phases
- Consider temperature ramping (check `T step start time` parameter)

---

#### It2 (3-Phase Current vs Time)

**Description**: Like `It` but with separately configurable phase durations.

**Data Columns**: Same as `It`
- `t (s)`: Time
- `I (A)`: Current
- `VL (V)`: Laser voltage
- `Plate T (degC)`, `Ambient T (degC)`, `Clock (ms)`

**Key Differences from It**:
- Parameters: `Phase 1 duration (laser OFF)`, `Phase 2 duration (laser ON)`, `Phase 3 duration (laser OFF)`
- Asymmetric phase lengths

**Plot Design**:
```python
# Annotate phase boundaries
phase1_end = phase1_duration
phase2_end = phase1_duration + phase2_duration

ax.axvline(phase1_end, color='gray', linestyle='--', alpha=0.5, label='Phase 1→2')
ax.axvline(phase2_end, color='gray', linestyle='--', alpha=0.5, label='Phase 2→3')

# Shade laser ON region
ax.axvspan(phase1_end, phase2_end, alpha=0.15, color='yellow', label='Laser ON')
```

**Implementation Hints**:
- Extract phase durations from parameters
- Use same baseline correction as ITS
- Optionally overlay all three phases from multiple experiments

---

#### Vt (Voltage vs Time)

**Description**: Measures drain-source voltage over time while sourcing current.

**Data Columns**:
- `t (s)`: Time
- `VDS (V)`: Drain-source voltage (measured)
- `VL (V)`: Laser voltage
- `Plate T (degC)`, `Ambient T (degC)`, `Clock (ms)`

**Key Features**:
- Y-axis is voltage instead of current
- Otherwise similar to ITt/It2

**Plot Design**:
```python
ax.plot(t, vds, label=f'seq {seq}')
ax.set_ylabel('$V_{DS}$ (V)')
ax.set_xlabel('Time (s)')
```

**Implementation Hints**:
- Nearly identical to ITt template
- Change y-axis label to voltage
- No baseline correction needed (voltage measurement)

---

### Category 2: Voltage Sweeps

#### IVgT (Current vs Vg with Temperature)

**Description**: Like `IVg` but with PT100 temperature data.

**Data Columns**:
- `Vg (V)`: Gate voltage
- `I (A)`: Current
- `Plate T (degC)`: Plate temperature
- `Ambient T (degC)`: Ambient temperature
- `Clock (ms)`: Clock time

**Key Features**:
- Transfer characteristic sweep
- Temperature monitoring during sweep
- Light/dark comparison

**Plot Design**:
```python
# Option 1: Just I vs Vg (ignore temperature in plot)
ax.plot(vg, I * 1e6, label=f'seq {seq} ({light_status})')
ax.set_ylabel('$I_{DS}$ (μA)')

# Option 2: Color-code by temperature
scatter = ax.scatter(vg, I * 1e6, c=plate_temp, cmap='coolwarm', s=10)
plt.colorbar(scatter, label='Plate T (°C)')
```

**Implementation Hints**:
- Start with `ivg.py` as template
- Add temperature to legend or use color mapping
- Can reuse `segment_voltage_sweep()` from `plot_utils.py`

---

#### VVg (Vds vs Vg)

**Description**: Measures drain-source voltage while sweeping gate at constant current.

**Data Columns**:
- `Vg (V)`: Gate voltage (swept)
- `VDS (V)`: Drain-source voltage (measured)
- `t (s)`: Time per point
- `Plate T (degC)`, `Ambient T (degC)`, `Clock (ms)`

**Key Features**:
- Resistance characterization (VDS at constant IDS)
- Gate voltage sweep (similar structure to IVg)
- Temperature monitoring

**Plot Design**:
```python
ax.plot(vg, vds, label=f'seq {seq}')
ax.set_xlabel('$V_G$ (V)')
ax.set_ylabel('$V_{DS}$ (V)')
ax.set_title('Voltage Transfer Characteristic')
```

**Implementation Hints**:
- Use `ivg.py` structure
- Y-axis is voltage instead of current
- Can compute resistance: R = VDS / IDS (if IDS is in parameters)

---

### Category 3: Time-Series with Stepped Parameter

#### ItVg (Current vs Time at Stepped Vg)

**Description**: Steps gate voltage and records current transients at each step.

**Data Columns**:
- `t (s)`: Time
- `I (A)`: Current
- `Vg (V)`: Gate voltage (stepped)

**Key Features**:
- Multiple gate voltage steps per experiment
- Each step produces a time series
- Optional laser burn-in before first step

**Plot Design Option 1 - All on one plot**:
```python
# Color-code by Vg
unique_vg = np.unique(vg)
for vg_val in unique_vg:
    mask = (vg == vg_val)
    ax.plot(t[mask], I[mask], label=f'Vg = {vg_val:.2f}V')
```

**Plot Design Option 2 - Subplots per Vg**:
```python
n_steps = len(unique_vg)
fig, axes = plt.subplots(n_steps, 1, figsize=(10, 3*n_steps), sharex=True)
for i, vg_val in enumerate(unique_vg):
    mask = (vg == vg_val)
    axes[i].plot(t[mask], I[mask])
    axes[i].set_ylabel(f'I @ Vg={vg_val:.2f}V')
```

**Implementation Hints**:
- Segment data by gate voltage value
- Reset time axis per segment (t = t - t[0])
- Consider overlaying multiple experiments for comparison

---

#### ItWl (Current vs Time at Stepped Wavelength)

**Description**: Steps through wavelengths and records current transients.

**Data Columns**:
- `t (s)`: Time
- `I (A)`: Current
- `wl (nm)`: Wavelength (stepped)

**Key Features**:
- Wavelength sweep (Bentham TLS120Xe)
- Burn-in period with lamp off
- Spectral response characterization

**Plot Design**:
```python
# Similar to ItVg but with wavelength
unique_wl = np.unique(wl)
for wl_val in unique_wl:
    mask = (wl == wl_val)
    ax.plot(t[mask], I[mask], label=f'λ = {wl_val:.0f}nm')
ax.set_xlabel('Time (s)')
ax.set_ylabel('Current (A)')
ax.legend(title='Wavelength')
```

**Implementation Hints**:
- Very similar structure to ItVg
- Use wavelength for legend instead of Vg
- Consider spectral response plot: I_peak vs wavelength

---

### Category 4: Optical Calibration/Power

#### LaserCalibration (Power vs Laser Voltage)

**Description**: Calibration curve relating laser PSU voltage to optical power.

**Data Columns**:
- `VL (V)`: Laser voltage (swept)
- `Power (W)`: Measured optical power

**Metadata**:
- `Sensor model`: Power meter model
- Parameters include `Optical fiber`, `Laser wavelength`

**Plot Design**:
```python
ax.plot(vl, power * 1e3, marker='o', linestyle='-', markersize=4)
ax.set_xlabel('Laser Voltage (V)')
ax.set_ylabel('Optical Power (mW)')
ax.set_title(f'Laser Calibration - {wavelength:.0f}nm ({fiber})')
ax.grid(True, alpha=0.3)
```

**Implementation Hints**:
- Simpler than electrical measurements
- Include wavelength and fiber in legend/title
- Consider fitting a curve (polynomial or exponential)
- Multiple calibrations on one plot for comparison

---

#### Pt (Power vs Time)

**Description**: Optical power stability over time with laser ON/OFF sequence.

**Data Columns**:
- `t (s)`: Time
- `P (W)`: Optical power
- `VL (V)`: Laser voltage

**Key Features**:
- 3-phase sequence (OFF-ON-OFF)
- Power stability and warm-up characterization

**Plot Design**:
```python
ax.plot(t, P * 1e3, linewidth=1.5)
ax.set_xlabel('Time (s)')
ax.set_ylabel('Optical Power (mW)')

# Shade laser ON region
laser_on_mask = vl > 0.1
t_on_start = t[laser_on_mask][0] if any(laser_on_mask) else None
t_on_end = t[laser_on_mask][-1] if any(laser_on_mask) else None
if t_on_start and t_on_end:
    ax.axvspan(t_on_start, t_on_end, alpha=0.15, color='yellow', label='Laser ON')
```

**Implementation Hints**:
- Similar structure to ITS/ITt
- Use laser voltage to identify ON/OFF phases
- Consider stability metrics (std dev during ON phase)

---

#### Pwl (Power vs Wavelength)

**Description**: Spectral power distribution from wavelength sweep.

**Data Columns**:
- `Wavelength (nm)`: Wavelength (swept)
- `Power (W)`: Measured optical power
- `Time (s)`: Time per point

**Key Features**:
- Spectral characterization of light source
- Bentham TLS120Xe monochromator sweep

**Plot Design**:
```python
ax.plot(wavelength, power * 1e3, marker='o', linestyle='-', markersize=4)
ax.set_xlabel('Wavelength (nm)')
ax.set_ylabel('Optical Power (mW)')
ax.set_title('Spectral Power Distribution')
ax.grid(True, alpha=0.3)
```

**Implementation Hints**:
- Very straightforward X-Y plot
- Consider log scale if power varies significantly
- Overlay multiple sweeps for comparison
- Identify peaks automatically (scipy.signal.find_peaks)

---

### Category 5: Thermal Characterization

#### Tt (Temperature vs Time)

**Description**: Temperature ramp profile for thermal characterization.

**Data Columns**:
- `Time (s)`: Time
- `Plate Temperature (degC)`: Hotplate temperature
- `Ambient Temperature (degC)`: Ambient temperature
- `Clock`: System clock (ms)

**Key Features**:
- Temperature ramp (start → end)
- Step-wise or continuous ramping
- No electrical measurement

**Plot Design**:
```python
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(time, plate_temp, label='Plate', linewidth=2)
ax.plot(time, ambient_temp, label='Ambient', linewidth=1.5, linestyle='--')
ax.set_xlabel('Time (s)')
ax.set_ylabel('Temperature (°C)')
ax.set_title(f'Temperature Profile - {tag}')
ax.legend()
ax.grid(True, alpha=0.3)

# Mark target temperature if available
target_temp = row.get("Target T")
if target_temp:
    ax.axhline(target_temp, color='red', linestyle=':', label=f'Target: {target_temp}°C')
```

**Implementation Hints**:
- Simple time-series plot
- Clearly distinguish plate vs ambient
- Consider thermal lag analysis (time to reach target)
- Overlay multiple ramps for repeatability

---

## Advanced Features (Optional)

### Multi-Experiment Overlays

For comparing multiple experiments (e.g., different wavelengths, temperatures):

```python
# Group by parameter
wavelengths = data["wavelength_nm"].unique().sort()
for wl in wavelengths:
    subset = data.filter(pl.col("wavelength_nm") == wl)
    # Plot all experiments at this wavelength with same color
    color = cmap(wl / max(wavelengths))
    for row in subset.iter_rows(named=True):
        # ... plot with color
```

### Interactive Selection

For procedures with many experiments, add interactive selector:

```python
interactive: bool = typer.Option(
    False,
    "--interactive",
    "-i",
    help="Launch interactive experiment selector"
)

if interactive:
    from src.interactive_selector import interactive_select_experiments
    seq_numbers = interactive_select_experiments(proc_history)
```

### Export Data

Add option to export plotted data to CSV:

```python
export_csv: bool = typer.Option(
    False,
    "--export-csv",
    help="Export plotted data to CSV"
)

if export_csv:
    export_path = output_dir / f"{procedure_name}_{tag}_data.csv"
    selected.write_csv(export_path)
    console.print(f"[green]✓[/green] Data exported: {export_path}")
```

### Statistical Analysis

Add summary statistics for thermal/optical stability:

```python
# For Pt or Tt procedures
mean_power = np.mean(power_during_on_phase)
std_power = np.std(power_during_on_phase)
stability_pct = (std_power / mean_power) * 100

ax.text(0.02, 0.98,
        f'Stability: ±{stability_pct:.2f}%\nMean: {mean_power*1e3:.2f} mW',
        transform=ax.transAxes, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
```

---

## Summary Priority List

Based on typical usage, implement in this order:

### High Priority (Most Used)
1. **ITt** - Critical for temperature-dependent measurements
2. **It2** - Variant of It, frequently used
3. **IVgT** - IVg with temperature is common

### Medium Priority
4. **ItVg** - Gate voltage stepping useful for optimization
5. **Vt** - Voltage measurement variant
6. **VVg** - Resistance characterization
7. **Tt** - Thermal validation

### Lower Priority (Calibration/Utility)
8. **LaserCalibration** - Infrequent, but important for setup
9. **Pt** - Power stability checks
10. **ItWl** - Wavelength sweeps (specialized)
11. **Pwl** - Spectral characterization (specialized)

---

## Quick Reference Table

| Procedure | Category | X-Axis | Y-Axis | Template | Complexity |
|-----------|----------|--------|--------|----------|------------|
| ITt | Time-series | Time (s) | Current (A) | its.py | Medium |
| It2 | Time-series | Time (s) | Current (A) | its.py | Low |
| Vt | Time-series | Time (s) | Voltage (V) | its.py | Low |
| IVgT | Sweep | Vg (V) | Current (A) | ivg.py | Low |
| VVg | Sweep | Vg (V) | Vds (V) | ivg.py | Low |
| ItVg | Stepped | Time (s) | Current (A) | its.py + multi | High |
| ItWl | Stepped | Time (s) | Current (A) | its.py + multi | High |
| LaserCalibration | Optical | VL (V) | Power (W) | Simple XY | Low |
| Pt | Optical | Time (s) | Power (W) | its.py | Low |
| Pwl | Optical | λ (nm) | Power (W) | Simple XY | Low |
| Tt | Thermal | Time (s) | Temp (°C) | its.py | Low |

---

## Getting Help

- **Reference implementations**: `src/plotting/its.py`, `src/plotting/ivg.py`
- **Plot utilities**: `src/plotting/plot_utils.py`
- **CLI helpers**: `src/cli/helpers.py`
- **Data loading**: `src/core/utils.py` → `read_measurement_parquet()`
- **Procedure schemas**: `config/procedures.yml`
- **Measurement details**: `docs/PROCEDURES.md`

**When stuck:**
1. Start with the simplest version (basic X-Y plot)
2. Add features incrementally (legend, filters, styling)
3. Test with real data frequently
4. Copy patterns from existing implementations

---

## Configuration Compliance Checklist

Use this checklist to verify your new plotting command supports the configuration system correctly:

### ✅ Parameter Definitions
- [ ] `history_dir` parameter is `Optional[Path] = None` (not `Path = Path(...)`)
- [ ] `output_dir` parameter is `Optional[Path] = None` (not `Path = Path(...)`)
- [ ] Help text says "(default: from config)" for both parameters

### ✅ Config Loading (at start of function)
- [ ] `from src.cli.main import get_config` import exists
- [ ] `config = get_config()` called before using paths
- [ ] `if output_dir is None: output_dir = config.output_dir`
- [ ] `if history_dir is None: history_dir = config.history_dir`
- [ ] Verbose logging: `if config.verbose: console.print(...)`

### ✅ Helper Function Usage
- [ ] `setup_output_dir(chip_number, chip_group, output_dir)` called with correct parameter order
- [ ] NOT using conditional `if output_dir is None: ... else: ...` pattern (deprecated)

### ✅ Plotting Module Integration
- [ ] Import plotting module: `from src.plotting import {procedure_name}`
- [ ] Set FIG_DIR before plotting: `{procedure_name}.FIG_DIR = output_dir`
- [ ] Call happens BEFORE calling the plot function

### ✅ Testing
- [ ] Tested with `--verbose` flag (shows "Using ... from config")
- [ ] Tested with global `--output-dir` override
- [ ] Tested with command-specific `--output` override
- [ ] Tested with `config-init` and custom config file
- [ ] All tests produce output in expected directory

### ✅ Reference Implementation
If you're unsure, compare your implementation with these verified examples:
- `src/cli/commands/plot_its.py` (lines 248-260 for config loading)
- `src/cli/commands/plot_laser_calibration.py` (lines 198-210 for config loading)
- `src/cli/commands/plot_ivg.py` (for another working example)

### Common Errors and Fixes

| Error | Symptom | Fix |
|-------|---------|-----|
| Plots go to wrong directory | Config ignored | Set `{module}.FIG_DIR = output_dir` before plotting |
| `--verbose` shows nothing | No config loading | Add `config = get_config()` at function start |
| TypeError with paths | Wrong parameter type | Change `Path = Path(...)` to `Optional[Path] = None` |
| `setup_output_dir` error | Wrong parameter order | Use `(chip, group, output_dir)` not `(output_dir, chip, group)` |

Good luck! 🚀
