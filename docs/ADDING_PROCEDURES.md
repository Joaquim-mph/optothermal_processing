# Adding New Measurement Procedures

This guide explains how to add new measurement procedures to the optothermal processing pipeline.

## Overview

The pipeline uses a **schema-driven architecture** where measurement procedures are defined declaratively in `config/procedures.yml`. The staging pipeline automatically reads these schemas and validates raw CSV files against them - no code changes required for basic data processing!

## Quick Workflow

```bash
# 1. Add procedure schema to config/procedures.yml
# 2. Run the pipeline
python3 process_and_analyze.py full-pipeline

# 3. Validate
python3 process_and_analyze.py validate-manifest
python3 process_and_analyze.py show-history <chip> --proc YourNewProcedure
```

---

## Step 1: Define Procedure Schema

Edit `config/procedures.yml` and add your new procedure under the `procedures:` section:

```yaml
procedures:
  YourNewProcedure:
    Parameters:
      # Parameters from the "# Parameters:" section of your CSV headers
      Chip number: int
      Chip group name: str
      Laser wavelength: float        # Strips units: "450nm" → 450
      Laser voltage: float
      VDS: float
      VG: float
      Sampling time (excluding Keithley): float
      Step time: float
      # ... add all parameters your CSV files contain

    Metadata:
      # Runtime metadata from "# Metadata:" section
      Start time: datetime           # REQUIRED for all procedures
      # ... any other metadata fields

    Data:
      # Data columns from the CSV table (after "# Data:" line)
      t (s): float                   # Time column
      I (A): float                   # Current
      V (V): float                   # Voltage
      # ... all data columns in your measurement files
```

### Type Mappings

| YAML Type | Python Type | Notes |
|-----------|-------------|-------|
| `int` | int | Integer values |
| `float` | float | Automatically strips units (e.g., "120s" → 120, "450nm" → 450) |
| `float_no_unit` | float | For floats that shouldn't have units stripped |
| `float64` | float | Alias for float |
| `str` | str | String values |
| `bool` | bool | Boolean values |
| `datetime` | datetime | Timestamps (various formats supported) |

### Important Notes

1. **`Start time` is REQUIRED** in Metadata for all procedures - used for timeline ordering
2. **Match CSV headers exactly** - field names must match what's in your CSV files (case-sensitive)
3. **Include all fields** - staging will warn if CSV files have fields not in schema
4. **Common parameter patterns:**
   - Chip identification: `Chip number`, `Chip group name`, `Sample`
   - Laser settings: `Laser wavelength`, `Laser voltage`, `Laser toggle`
   - Bias voltages: `VDS`, `VG`, `VG start`, `VG end`, `VG step`
   - Timing: `Sampling time (excluding Keithley)`, `Step time`, `Burn-in time`
   - Metadata: `Procedure version`, `Information`, `Show more`, `Chained execution`

---

## Step 2: Run the Staging Pipeline

Once you've added your schema, the staging pipeline automatically handles everything:

```bash
# Activate virtual environment
source .venv/bin/activate

# Full pipeline (RECOMMENDED)
python3 process_and_analyze.py full-pipeline

# This runs:
# 1. stage-all: Process all CSV files, validate against schemas, create Parquet files
# 2. build-all-histories: Generate per-chip history files including new procedure data
```

### What Happens Automatically

The staging pipeline (`src/core/stage_raw_measurements.py`):

1. **Discovers CSVs** recursively under `data/01_raw/`
2. **Parses headers** to extract procedure name, parameters, metadata
3. **Validates** against your `procedures.yml` schema
4. **Type-casts** all fields according to schema types
5. **Normalizes** column names and units
6. **Enriches** data with derived fields:
   - `run_id`: Deterministic hash for idempotency
   - `with_light`: Boolean from laser settings
   - `wavelength_nm`, `laser_voltage_V`: Normalized values
   - Voltage parameters: `vds_v`, `vg_fixed_v`, sweep ranges, etc.
7. **Writes Parquet** files organized by procedure: `data/02_stage/raw_measurements/proc=YourNewProcedure/...`
8. **Updates manifest**: `data/02_stage/raw_measurements/_manifest/manifest.parquet`

### Staging Options

```bash
# Stage with custom settings
python3 process_and_analyze.py stage-all \
  --raw-root data/01_raw \
  --stage-root data/02_stage/raw_measurements \
  --procedures-yaml config/procedures.yml \
  --workers 8 \
  --force  # Overwrite existing runs

# Build histories after staging
python3 process_and_analyze.py build-all-histories
```

---

## Step 3: Validate and Inspect

After staging, validate that your new procedure data was processed correctly:

```bash
# 1. Validate manifest schema and data quality
python3 process_and_analyze.py validate-manifest

# 2. Inspect manifest (see all procedures)
python3 process_and_analyze.py inspect-manifest

# 3. View chip history with your new procedure
python3 process_and_analyze.py show-history <chip_number>

# 4. Filter by your specific procedure
python3 process_and_analyze.py show-history <chip_number> --proc YourNewProcedure

# 5. Check with light/dark filtering
python3 process_and_analyze.py show-history <chip_number> --proc YourNewProcedure --light light
```

### Troubleshooting Staging Issues

**Validation errors during staging:**

```bash
# Check staging statistics
python3 process_and_analyze.py staging-stats

# Look at rejected files
ls -la data/02_stage/raw_measurements/_rejects/
cat data/02_stage/raw_measurements/_rejects/<file>.json
```

Common issues:
- **Missing fields**: CSV file has parameters not in schema → Add to `procedures.yml`
- **Type mismatch**: Value can't be cast to schema type → Check CSV values
- **Missing Start time**: Required metadata field missing → Ensure CSV has `Start time` in Metadata
- **Unknown procedure**: CSV has procedure not in YAML → Add procedure definition

---

## Step 4: Access Your Data Programmatically

Your new procedure data is now available throughout the codebase:

### Reading Staged Data

```python
from pathlib import Path
from src.core.utils import read_measurement_parquet
import polars as pl

# Load chip history
history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")

# Filter to your procedure
your_proc_exps = history.filter(pl.col("proc") == "YourNewProcedure")

# Get a specific experiment's parquet_path
parquet_path = your_proc_exps[0, "parquet_path"]

# Load the full measurement data
data = read_measurement_parquet(parquet_path)

# Now you have the full timeseries with all columns
print(data.columns)  # All Data columns + enriched metadata columns
```

### Querying the Manifest

```python
# Load manifest directly
manifest = pl.read_parquet("data/02_stage/raw_measurements/_manifest/manifest.parquet")

# Filter by your procedure
your_proc = manifest.filter(pl.col("proc") == "YourNewProcedure")

# Query by chip
chip_67 = your_proc.filter(pl.col("chip_number") == 67)

# Access metadata
print(chip_67.select(["run_id", "start_dt", "wavelength_nm", "vds_v"]))
```

---

## Step 5: (Optional) Add Custom Plotting

If your procedure needs specialized visualization (like ITS, IVg, transconductance have), create plotting functions:

### 5.1 Create Plotting Module

Create `src/plotting/your_procedure.py`:

```python
"""Plotting functions for YourNewProcedure data."""

from pathlib import Path
import polars as pl
import matplotlib.pyplot as plt
from src.core.utils import read_measurement_parquet
from src.plotting.styles import apply_science_style

def plot_your_procedure(history_df, output_dir, plot_tag, seq_numbers=None):
    """
    Generate plots for YourNewProcedure experiments.

    Parameters
    ----------
    history_df : pl.DataFrame
        Chip history dataframe (filtered to YourNewProcedure)
    output_dir : Path
        Output directory for plots
    plot_tag : str
        Tag for output filename
    seq_numbers : list[int], optional
        Specific seq numbers to plot
    """
    apply_science_style()

    # Filter to requested experiments
    if seq_numbers:
        data = history_df.filter(pl.col("seq").is_in(seq_numbers))
    else:
        data = history_df

    fig, ax = plt.subplots(figsize=(8, 6))

    for row in data.iter_rows(named=True):
        # Load measurement data
        parquet_path = row["parquet_path"]
        measurement = read_measurement_parquet(parquet_path)

        # Extract relevant columns for plotting
        # Adjust based on your procedure's data columns
        t = measurement["t (s)"].to_numpy()
        y = measurement["I (A)"].to_numpy()  # or whatever you want to plot

        # Plot with metadata in label
        label = f"seq {row['seq']}: {row['wavelength_nm']:.0f}nm"
        ax.plot(t, y, label=label)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (A)")
    ax.set_title(f"Your Procedure Analysis - {plot_tag}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Save
    output_file = output_dir / f"your_procedure_{plot_tag}.png"
    fig.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)

    return output_file
```

### 5.2 Create CLI Command

Create `src/cli/commands/plot_your_procedure.py`:

```python
"""CLI command for plotting YourNewProcedure data."""

import typer
from pathlib import Path
from rich.console import Console
from src.cli.plugin_system import cli_command
from src.cli.helpers import (
    parse_seq_list,
    setup_output_dir,
    auto_select_experiments,
    display_plot_success
)
from src.plotting.your_procedure import plot_your_procedure
import polars as pl

console = Console()

@cli_command(
    name="plot-your-procedure",
    group="plotting",
    description="Generate plots for YourNewProcedure measurements"
)
def plot_your_procedure_command(
    chip_number: int = typer.Argument(..., help="Chip number"),
    seq: str = typer.Option(None, "--seq", "-s", help="Comma-separated seq numbers (e.g., '1,2,3')"),
    auto: bool = typer.Option(False, "--auto", "-a", help="Auto-select all experiments"),
    chip_group: str = typer.Option("Alisson", "--chip-group", "-g"),
):
    """
    Generate plots for YourNewProcedure measurements.

    Examples:
        plot-your-procedure 67 --seq 1,2,3
        plot-your-procedure 67 --auto
    """
    # Load history
    history_dir = Path("data/02_stage/chip_histories")
    history_file = history_dir / f"{chip_group}{chip_number}_history.parquet"

    if not history_file.exists():
        console.print(f"[red]✗[/red] History file not found: {history_file}")
        raise typer.Exit(1)

    history = pl.read_parquet(history_file)

    # Filter to your procedure
    proc_history = history.filter(pl.col("proc") == "YourNewProcedure")

    if len(proc_history) == 0:
        console.print(f"[red]✗[/red] No YourNewProcedure experiments found for chip {chip_number}")
        raise typer.Exit(1)

    # Get seq numbers
    if auto:
        seq_numbers = proc_history["seq"].to_list()
    elif seq:
        seq_numbers = parse_seq_list(seq)
    else:
        console.print("[red]✗[/red] Must specify --seq or --auto")
        raise typer.Exit(1)

    # Setup output
    output_dir = setup_output_dir(chip_number, chip_group)
    plot_tag = f"{chip_group}{chip_number}"

    # Generate plot
    console.print(f"[cyan]Generating YourNewProcedure plot...[/cyan]")
    output_file = plot_your_procedure(proc_history, output_dir, plot_tag, seq_numbers)

    display_plot_success(output_file)
```

### 5.3 Test Your Command

```bash
# Your command is auto-discovered!
python3 process_and_analyze.py --help  # Should show plot-your-procedure

# Test it
python3 process_and_analyze.py plot-your-procedure 67 --auto
```

---

## Complete Example: Adding "ItVg" Procedure

Let's walk through a complete example using the existing `ItVg` procedure:

### 1. Schema Definition (already in procedures.yml)

```yaml
procedures:
  ItVg:
    Parameters:
      Irange: float
      NPLC: int
      Burn-in time: float
      Chip number: int
      Chip group name: str
      Laser wavelength: float
      VDS: float
      VG start: float
      VG end: float
      VG step: float
      # ... etc
    Metadata:
      Start time: datetime
    Data:
      t (s): float
      I (A): float
      Vg (V): float
```

### 2. Stage Data

```bash
python3 process_and_analyze.py full-pipeline
```

This automatically:
- Validates ItVg CSV files against the schema
- Creates `data/02_stage/raw_measurements/proc=ItVg/...` Parquet files
- Updates manifest and chip histories

### 3. Access Data

```python
# View in CLI
python3 process_and_analyze.py show-history 67 --proc ItVg

# Load programmatically
import polars as pl
history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")
itvg_exps = history.filter(pl.col("proc") == "ItVg")
```

---

## Summary Checklist

- [ ] Add procedure definition to `config/procedures.yml`
  - [ ] Parameters section with all CSV parameter fields
  - [ ] Metadata section with `Start time` (required)
  - [ ] Data section with all data columns
  - [ ] Correct type annotations (int, float, datetime, str, bool)
- [ ] Run staging pipeline: `python3 process_and_analyze.py full-pipeline`
- [ ] Validate: `python3 process_and_analyze.py validate-manifest`
- [ ] Verify data: `python3 process_and_analyze.py show-history <chip> --proc YourProcedure`
- [ ] (Optional) Create plotting function in `src/plotting/`
- [ ] (Optional) Create CLI command in `src/cli/commands/` with `@cli_command` decorator
- [ ] (Optional) Test plotting: `python3 process_and_analyze.py plot-your-procedure <chip> --auto`

---

## Key Takeaways

1. **Schema-driven**: Just update YAML, no code changes needed for basic processing
2. **Automatic validation**: Staging pipeline validates all CSV files against schemas
3. **Parquet-native**: Data automatically converted to efficient Parquet format
4. **History integration**: New procedures automatically appear in chip histories
5. **Optional plotting**: Custom visualization requires additional coding, but data is accessible without it
6. **Plugin system**: CLI commands are auto-discovered, no need to modify `main.py`

The pipeline is designed to make adding procedures as simple as possible - in most cases, you only need to update the YAML schema!
