# CLI Module Architecture Documentation

## Table of Contents

1. [Overview](#overview)
2. [Module Structure](#module-structure)
3. [Architecture Design](#architecture-design)
4. [Entry Point: main.py](#entry-point-mainpy)
5. [Configuration Management](#configuration-management)
6. [Helper Modules](#helper-modules)
7. [Command Groups](#command-groups)
8. [Design Patterns](#design-patterns)
9. [User Experience Features](#user-experience-features)
10. [Error Handling](#error-handling)
11. [Extension Guide](#extension-guide)

---

## Overview

The `src/cli` module provides a comprehensive command-line interface for the optothermal processing pipeline. Built on [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/), it offers an ergonomic, visually appealing terminal experience for data processing, history management, and scientific plotting.

**Key Characteristics:**
- **Modern architecture**: Modular command organization with clean separation of concerns
- **Rich terminal UI**: Beautiful tables, progress bars, panels, and color-coded output
- **Parquet-native**: Optimized for the modern staging pipeline (CSV → Parquet)
- **Validation-first**: Validates inputs before expensive operations
- **User-friendly**: Helpful error messages, hints, and preview modes

---

## Module Structure

```
src/cli/
├── __init__.py                    # Empty module marker
├── main.py                        # CLI entry point and command aggregator
├── helpers.py                     # Shared plotting helpers
├── history_utils.py               # History filtering and summarization
└── commands/                      # Command implementations
    ├── __init__.py
    ├── data_pipeline.py           # Full pipeline orchestration
    ├── history.py                 # History viewing and generation
    ├── stage.py                   # Staging commands
    ├── plot_its.py                # ITS plotting commands
    ├── plot_ivg.py                # IVg plotting
    └── plot_transconductance.py   # Transconductance plotting
```

**File Responsibilities:**
- **`main.py`**: Aggregates all commands into a single Typer app
- **`helpers.py`**: Reusable plotting utilities (seq parsing, output dir setup, Rich displays)
- **`history_utils.py`**: History filtering logic shared by CLI and TUI
- **`commands/*.py`**: Individual command implementations organized by domain

---

## Architecture Design

### 1. Command Registration Pattern

The CLI uses a **centralized registration** pattern where `main.py` imports all command functions and registers them with kebab-case names:

```python
# main.py
from src.cli.commands.data_pipeline import full_pipeline_command
from src.cli.commands.history import show_history_command, build_history_command
from src.cli.commands.plot_its import plot_its_command

app = typer.Typer(name="process_and_analyze", help="...")

# Register with kebab-case names
app.command(name="full-pipeline")(full_pipeline_command)
app.command(name="show-history")(show_history_command)
app.command(name="plot-its")(plot_its_command)
```

**Benefits:**
- Single source of truth for available commands
- Consistent naming convention (kebab-case)
- Easy to add/remove commands
- Clear command namespace

### 2. Thin Wrapper Entry Point

The project root contains `process_and_analyze.py` as a **thin wrapper** that simply imports and runs the CLI:

```python
# process_and_analyze.py (root)
from src.cli.main import main

if __name__ == "__main__":
    main()
```

This allows running the CLI as:
```bash
python process_and_analyze.py <command>
```

### 3. Modular Command Structure

Each command module follows a consistent structure:

```python
def command_name(
    # Required positional arguments
    chip_number: int = typer.Argument(..., help="..."),

    # Optional flags with sensible defaults
    option1: str = typer.Option("default", "--option1", "-o1", help="..."),
    option2: bool = typer.Option(False, "--option2", help="..."),
):
    """
    Command docstring (shown in --help).

    Examples:
        command examples here
    """
    # 1. Input validation
    # 2. Rich console output
    # 3. Core logic execution
    # 4. Success/error reporting
```

### 4. Shared Helper Functions

Common operations are extracted into reusable helpers to ensure consistency:

- **`helpers.py`**: Plotting-specific utilities (seq parsing, file naming, Rich displays)
- **`history_utils.py`**: History filtering logic (shared by CLI and TUI)

This **DRY principle** ensures:
- Consistent behavior across commands
- Easier testing and maintenance
- Reduced code duplication

---

## Entry Point: main.py

**Purpose**: Aggregates all command functions into a single Typer application.

### Key Components

```python
# Import all command functions
from src.cli.commands.data_pipeline import full_pipeline_command
from src.cli.commands.history import (
    show_history_command,
    build_history_command,
    build_all_histories_command,
)
from src.cli.commands.plot_its import (
    plot_its_command,
    list_presets_command,
    plot_its_sequential_command
)
# ... more imports

# Create main app
app = typer.Typer(
    name="process_and_analyze",
    help="Complete data processing and analysis pipeline",
    add_completion=False  # Disable shell completion
)

# Register commands
app.command(name="full-pipeline")(full_pipeline_command)
app.command(name="show-history")(show_history_command)
app.command(name="plot-its")(plot_its_command)
# ... more registrations

def main():
    """Main entry point for the CLI application."""
    app()
```

**Design Notes:**
- Commands are registered with **kebab-case** names for CLI convention
- Command functions retain **snake_case** names for Python convention
- `add_completion=False` disables automatic shell completion generation
- The `main()` function is called from `process_and_analyze.py` wrapper

---

## Configuration Management

The CLI module includes a comprehensive configuration management system that provides flexible, validated settings with multiple configuration sources and proper precedence handling.

### Overview

**Location**: `src/cli/config.py`

**Purpose**: Centralized configuration with support for:
- Environment variables (`CLI_*` prefix)
- JSON configuration files (user and project-level)
- Command-line overrides
- Validated defaults with Pydantic

### Configuration Priority

Configuration values are resolved in the following order (highest to lowest priority):

1. **Command-line overrides** - Explicit flags like `--output-dir`, `--verbose`
2. **Specified config file** - Via `--config path/to/config.json`
3. **Project config** - `./.optothermal_cli_config.json` in current directory
4. **User config** - `~/.optothermal_cli_config.json` in home directory
5. **Environment variables** - `CLI_VERBOSE`, `CLI_OUTPUT_DIR`, etc.
6. **Defaults** - Hardcoded sensible defaults

### Configuration Fields

The `CLIConfig` Pydantic model includes:

**Directory Paths:**
- `raw_data_dir`: Raw CSV files (default: `data/01_raw`)
- `stage_dir`: Staged Parquet files (default: `data/02_stage`)
- `history_dir`: Chip history files (default: `data/02_stage/chip_histories`)
- `output_dir`: Plot outputs (default: `figs`)

**Behavior Settings:**
- `verbose`: Enable verbose logging (default: `False`)
- `dry_run`: Preview mode without execution (default: `False`)

**Processing Settings:**
- `parallel_workers`: Number of worker processes (default: `4`, range: 1-16)
- `cache_enabled`: Enable caching (default: `True`)
- `cache_ttl`: Cache time-to-live in seconds (default: `300`)

**Plot Settings:**
- `default_plot_format`: Output format (default: `"png"`, choices: png, pdf, svg, jpg)
- `plot_dpi`: Plot resolution (default: `300`, range: 72-600)

### Global Config Access

Commands access the global configuration using the singleton pattern:

```python
from src.cli.main import get_config

def my_command(output_dir: Optional[Path] = None):
    config = get_config()

    # Use config default if not specified
    if output_dir is None:
        output_dir = config.output_dir
        if config.verbose:
            console.print(f"[dim]Using output_dir from config: {output_dir}[/dim]")
```

**Key Functions:**
- `get_config()`: Returns cached global configuration instance
- `set_config(config)`: Sets global configuration (useful for testing)
- `load_config_with_precedence()`: Loads config with proper priority handling

### Configuration Commands

**`config-show`** - Display current configuration
```bash
# Show configuration with sources
python process_and_analyze.py config-show

# Hide source information
python process_and_analyze.py config-show --no-sources
```

**`config-init`** - Initialize configuration file
```bash
# Create default config in home directory
python process_and_analyze.py config-init

# Create config with specific output location
python process_and_analyze.py config-init --output my_config.json

# Use a preset profile
python process_and_analyze.py config-init --profile development
python process_and_analyze.py config-init --profile production
```

**`config-validate`** - Validate configuration
```bash
# Validate current configuration
python process_and_analyze.py config-validate

# Validate and attempt to fix issues
python process_and_analyze.py config-validate --fix
```

**`config-reset`** - Reset to defaults
```bash
# Reset with confirmation and backup
python process_and_analyze.py config-reset

# Skip confirmation
python process_and_analyze.py config-reset --yes

# Reset without creating backup
python process_and_analyze.py config-reset --yes --no-backup
```

### Configuration Profiles

Predefined profiles for common use cases:

**Development Profile**
```python
ConfigProfile.development()
# verbose=True, dry_run=True, parallel_workers=2, cache_enabled=False
```

**Production Profile**
```python
ConfigProfile.production()
# parallel_workers=8, cache_enabled=True, cache_ttl=600
```

**Testing Profile**
```python
ConfigProfile.testing()
# Uses temporary directories, verbose=True, parallel_workers=1
```

**High Quality Profile**
```python
ConfigProfile.high_quality()
# default_plot_format="pdf", plot_dpi=600
```

### Global Options

The CLI provides global options that apply to all commands via the Typer callback:

```bash
# Enable verbose output for any command
python process_and_analyze.py --verbose plot-its 67 --auto

# Override output directory globally
python process_and_analyze.py --output-dir /tmp/plots plot-its 67 --seq 52,57,58

# Use custom config file
python process_and_analyze.py --config my_config.json full-pipeline

# Dry-run mode (show what would happen)
python process_and_analyze.py --dry-run full-pipeline
```

### Environment Variables

All configuration fields can be set via environment variables:

```bash
# Set environment variables (CLI_ prefix)
export CLI_VERBOSE=true
export CLI_OUTPUT_DIR=/data/plots
export CLI_PARALLEL_WORKERS=8
export CLI_DEFAULT_PLOT_FORMAT=pdf

# Run commands (automatically use environment config)
python process_and_analyze.py plot-its 67 --auto
```

### Configuration File Format

Example `~/.optothermal_cli_config.json`:

```json
{
  "raw_data_dir": "data/01_raw",
  "stage_dir": "data/02_stage",
  "history_dir": "data/02_stage/chip_histories",
  "output_dir": "figs",
  "verbose": false,
  "dry_run": false,
  "parallel_workers": 8,
  "cache_enabled": true,
  "cache_ttl": 600,
  "default_plot_format": "png",
  "plot_dpi": 300,
  "config_version": "1.0.0"
}
```

### Validation Features

The configuration system includes comprehensive validation:

**Path Validation:**
- Relative paths automatically resolved to absolute paths
- Directories auto-created if missing during validation
- Write permission checks for output directories

**Field Validation:**
- `plot_format`: Must be one of: png, pdf, svg, jpg
- `parallel_workers`: Range 1-16
- `plot_dpi`: Range 72-600
- `cache_ttl`: Non-negative integer

**Runtime Validation:**
- Pydantic enforces types at runtime (prevents invalid assignments)
- Helpful error messages for validation failures

### Integration with Commands

All commands have been updated to support configuration:

**Before (Hardcoded):**
```python
def plot_its_command(
    output_dir: Path = typer.Option(Path("figs"), ...),
    history_dir: Path = typer.Option(Path("data/02_stage/chip_histories"), ...),
):
    # Fixed paths
```

**After (Config-aware):**
```python
def plot_its_command(
    output_dir: Optional[Path] = typer.Option(None, help="... (default: from config)"),
    history_dir: Optional[Path] = typer.Option(None, help="... (default: from config)"),
):
    config = get_config()
    if output_dir is None:
        output_dir = config.output_dir
    if history_dir is None:
        history_dir = config.history_dir
```

### Benefits

1. **Flexibility**: Users can configure once, use everywhere
2. **Consistency**: Same settings across all commands by default
3. **Overridable**: Can override any setting per-command when needed
4. **Type-Safe**: Pydantic validation prevents invalid configurations
5. **Discoverable**: `config-show` displays all settings with sources
6. **Portable**: Project-specific configs for different environments

---

## Helper Modules

### helpers.py - Plotting Helpers

**Purpose**: Provides reusable utilities for plotting commands to ensure consistent behavior.

#### Key Functions

##### 1. `parse_seq_list(seq_str: str) -> list[int]`

Parses comma-separated sequence numbers with range support.

**Features:**
- Single numbers: `"52,57,58"` → `[52, 57, 58]`
- Ranges: `"89-92"` → `[89, 90, 91, 92]`
- Combined: `"89-92,95,100-102"` → `[89, 90, 91, 92, 95, 100, 101, 102]`
- Automatic deduplication and sorting
- Helpful error messages

**Usage:**
```python
seq_numbers = parse_seq_list("89-92,95,100-105")
# Returns: [89, 90, 91, 92, 95, 100, 101, 102, 103, 104, 105]
```

##### 2. `generate_plot_tag(seq_numbers: list[int], custom_tag: str | None) -> str`

Generates unique, deterministic filename tags based on selected experiments.

**Logic:**
- **Short lists (≤5)**: `seq_52_57_58`
- **Long lists (>5)**: `seq_89_90_91_plus114_a3c4f2` (first 3 + count + hash)
- **Custom tag**: Appends custom tag if provided

**Benefits:**
- Prevents accidental overwrites
- Same experiments always generate same filename
- Readable for small sets, compact for large sets

##### 3. `setup_output_dir(output_dir: Path, chip: int, chip_group: str) -> Path`

Creates chip-specific output subdirectories.

**Pattern:** `output_dir/{chip_group}{chip}/`

**Example:**
```python
output_dir = setup_output_dir(Path("figs"), 67, "Alisson")
# Creates and returns: figs/Alisson67/
```

##### 4. `auto_select_experiments(...) -> list[int]`

Auto-selects experiments from chip history based on procedure type and filters.

**Parameters:**
- `chip`, `proc`, `history_dir`, `chip_group`
- `filters`: Optional dict with keys `vg`, `vds`, `wavelength`, `date`

**Example:**
```python
# Auto-select all ITS experiments with VG=-0.4V
seq_numbers = auto_select_experiments(
    chip=67,
    proc="It",  # ITS experiments
    history_dir=Path("data/02_stage/chip_histories"),
    chip_group="Alisson",
    filters={"vg": -0.4}
)
```

##### 5. Rich Display Functions

Beautiful terminal output using Rich library:

- **`display_experiment_list(experiments: pl.DataFrame, title: str)`**
  - Shows experiment table with colors and formatting

- **`display_plot_settings(settings: dict)`**
  - Displays plot configuration in a bordered panel

- **`display_plot_success(output_file: Path)`**
  - Success message with output file path

**Example Output:**
```
┌─ Plot Settings ─────────────────────┐
│ Legend by: led_voltage              │
│ Padding: 5.00%                      │
│ Baseline: Fixed at 60.0 s           │
│ Output dir: figs/                   │
└─────────────────────────────────────┘
```

### history_utils.py - History Filtering

**Purpose**: Shared history filtering and summarization logic for CLI and TUI.

#### Key Components

##### 1. `HistoryFilterError` Exception

Custom exception with exit codes for graceful CLI exits.

```python
class HistoryFilterError(Exception):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code
```

**Exit codes:**
- `0`: Graceful exit (e.g., no experiments found with filter)
- `1`: Error condition (e.g., invalid filter syntax)

##### 2. `filter_history(...) -> Tuple[pl.DataFrame, List[str]]`

Applies filters to history DataFrame with validation.

**Filters:**
- `proc_filter`: Procedure type (e.g., "IVg", "It")
- `light_filter`: Light status with aliases
  - Light: `"light"`, `"l"`, `"💡"`
  - Dark: `"dark"`, `"d"`, `"🌙"`
  - Unknown: `"unknown"`, `"u"`, `"?"`, `"❗"`
- `limit`: Keep last N experiments (tail)
- `strict`: Raise error if no results (default True)

**Returns:** `(filtered_df, applied_filters)`

**Example:**
```python
filtered, filters = filter_history(
    df,
    proc_filter="IVg",
    light_filter="light",
    limit=10,
    strict=True
)
# Returns: (filtered_df, ["proc=IVg", "light=light", "limit=10"])
```

##### 3. `summarize_history(df: pl.DataFrame) -> Dict[str, object]`

Generates summary statistics for history displays.

**Returns:**
```python
{
    "total": 145,
    "date_range": "2025-10-01 to 2025-10-15",
    "num_days": 8,
    "proc_counts": [("IVg", 45), ("It", 100)],
    "light_counts": {"light": 80, "dark": 60, "unknown": 5}
}
```

---

## Command Groups

### 1. Data Pipeline Commands (data_pipeline.py)

#### `full-pipeline` - Complete Pipeline Orchestration

**Purpose**: Runs the complete modern pipeline: staging + history generation.

**Architecture:**
```
full-pipeline
    ├─> stage-all (Stage CSV → Parquet)
    └─> build-all-histories (Generate histories from manifest)
```

**Key Features:**
- Orchestrates multi-step pipeline
- Shows progress for each step with Rich panels
- Catches and reports errors gracefully
- Displays final summary with next steps

**Example:**
```bash
python process_and_analyze.py full-pipeline
python process_and_analyze.py full-pipeline --workers 16 --force
```

**Implementation Pattern:**
```python
def full_pipeline_command(...):
    # Step 1: Display header
    console.print(Panel.fit("Complete Data Processing Pipeline", ...))

    # Step 2: Run staging
    try:
        stage_all_command(...)
    except SystemExit as e:
        if e.code != 0:
            console.print("[red]✗ Staging failed[/red]")
            raise typer.Exit(1)

    # Step 3: Run history generation
    try:
        build_all_histories_command(...)
    except SystemExit as e:
        if e.code != 0:
            console.print("[red]✗ History failed[/red]")
            raise typer.Exit(1)

    # Step 4: Display success summary
    console.print(Panel.fit("✓ Pipeline Complete!", ...))
```

### 2. History Commands (history.py)

#### `show-history` - Display Chip Timeline

**Purpose**: Beautiful, paginated view of chip experiment history.

**Features:**
- Rich table display with date grouping
- Light status indicators (💡 🌙 ❗)
- Filtering by procedure, light status, limit
- Summary statistics (date range, procedure counts, light breakdown)
- Visual date separators for readability

**Example:**
```bash
python process_and_analyze.py show-history 67
python process_and_analyze.py show-history 67 --proc IVg --limit 20
python process_and_analyze.py show-history 67 --light dark --limit 10
```

**UI Example:**
```
┌─ Alisson67 Experiment History ─────────────────┐
│ Total experiments: 145                          │
└────────────────────────────────────────────────┘

 Timeline        │ Procedures      │ Light Status
─────────────────┼─────────────────┼──────────────
 Date Range:     │ IVg:      45    │ 💡 Light:  80
 2025-10-01 to   │ It:      100    │ 🌙 Dark:   60
 2025-10-15      │                 │ ❗ Unknown: 5
 Days: 8         │                 │

 💡 │ Seq │ Date       │ Time     │ Proc │ Description
────┼─────┼────────────┼──────────┼──────┼──────────────────
 💡 │  52 │ 2025-10-01 │ 14:30:21 │ It   │ VG=-0.4V λ=365nm
 💡 │  53 │ 2025-10-01 │ 14:45:12 │ It   │ VG=-0.4V λ=530nm
────┼─────┼────────────┼──────────┼──────┼──────────────────
 🌙 │  54 │ 2025-10-02 │ 09:15:43 │ It   │ VG=-0.6V dark
```

#### `build-history` - Single Chip History

**Purpose**: Build history for a specific chip from manifest.

**Flow:**
1. Load manifest.parquet
2. Filter by chip_number and chip_group
3. Sort chronologically
4. Assign sequential experiment numbers
5. Save as chip_histories/{chip_name}_history.parquet

**Example:**
```bash
python process_and_analyze.py build-history 67
python process_and_analyze.py build-history 72 --group Alisson
```

#### `build-all-histories` - Batch History Generation

**Purpose**: Discover all chips in manifest and generate histories.

**Features:**
- Auto-discovers unique chips from manifest
- Filters by chip_group if specified
- Min experiments threshold
- Progress spinner during processing
- Summary table of generated files

**Example:**
```bash
python process_and_analyze.py build-all-histories
python process_and_analyze.py build-all-histories --group Alisson --min-experiments 10
```

### 3. Staging Commands (stage.py)

#### `stage-all` - CSV to Parquet Staging

**Purpose**: Stage raw CSVs to Parquet with schema validation and manifest tracking.

**Architecture:**
```
stage-all
    ├─> Discover CSV files recursively
    ├─> Parse headers (Parameters, Metadata, Data)
    ├─> Validate against procedures.yml schema
    ├─> Generate deterministic run_id (SHA-1)
    ├─> Write partitioned Parquet (proc=X/date=Y/file.parquet)
    └─> Update manifest.parquet (atomic append)
```

**Key Features:**
- **Parallel processing**: ProcessPoolExecutor with configurable workers
- **Schema validation**: Pydantic models enforce data types
- **Idempotent**: Same CSV always generates same run_id
- **Progress display**: Rich progress bar or spinner (verbose mode)
- **Reject handling**: Failed files logged to _rejects/

**Example:**
```bash
# Clean output (progress bar)
python process_and_analyze.py stage-all

# Detailed file-by-file progress
python process_and_analyze.py stage-all --verbose

# Custom paths and parallel processing
python process_and_analyze.py stage-all -r data/01_raw -s data/02_stage/raw_measurements -w 16

# Force overwrite and strict schema
python process_and_analyze.py stage-all --force --only-yaml-data
```

**Implementation Highlights:**

1. **Progress Display Toggle:**
```python
if not verbose:
    # Show clean progress bar
    with Progress(...) as progress:
        # Redirect stdout to capture staging output
        sys.stdout = ProgressCapture(progress, task)
        run_staging_pipeline(params)
else:
    # Show detailed file-by-file output
    run_staging_pipeline(params)
```

2. **Summary Statistics:**
```python
# Read manifest to show procedure breakdown
manifest_df = pl.read_parquet(params.manifest)
proc_counts = manifest_df.group_by("proc").agg(pl.count().alias("count"))
# Display in Rich panel
```

#### `validate-manifest` - Schema and Quality Checks

**Purpose**: Comprehensive manifest validation with detailed reporting.

**Checks:**
- Duplicate run_id detection
- Pydantic schema validation
- Required field completeness
- Summary statistics by procedure
- Optional detailed statistics

**Example:**
```bash
python process_and_analyze.py validate-manifest
python process_and_analyze.py validate-manifest --details
```

**Output:**
```
┌─ Manifest Validation ──────────────────────────┐
│ ✓ No duplicate run_ids                         │
│ ✓ Schema validation passed                     │
│                                                 │
│ Required Fields                                │
│   run_id         125,432  0   100.0%           │
│   source_file    125,432  0   100.0%           │
│   proc           125,432  0   100.0%           │
│                                                 │
│ Total Measurements: 125,432                    │
│   └─ IVg: 45,231                               │
│   └─ It: 80,201                                │
└────────────────────────────────────────────────┘
```

#### `inspect-manifest` - Browse Manifest Data

**Purpose**: Interactive manifest exploration with filtering.

**Filters:**
- `--proc`: Procedure type
- `--chip`: Chip number
- `--limit`: Number of rows

**Example:**
```bash
python process_and_analyze.py inspect-manifest
python process_and_analyze.py inspect-manifest --proc IVg --chip 67 -n 50
```

#### `staging-stats` - Disk Usage and Statistics

**Purpose**: Show staging directory statistics and disk usage.

**Displays:**
- Directory tree with sizes
- File counts per partition
- Procedure distribution
- Manifest summary

**Example:**
```bash
python process_and_analyze.py staging-stats
```

### 4. Plotting Commands

All plotting commands follow a **consistent workflow pattern**:

1. **Input Mode Selection**: `--seq`, `--auto`, or `--interactive`
2. **Validation**: Verify seq numbers exist in history
3. **History Loading**: Load chip history with parquet_path column
4. **Filtering**: Apply optional filters (vg, wavelength, date, vds)
5. **Preview/Dry-run**: Optional modes to check before plotting
6. **Plotting**: Call plotting functions from `src/plotting/`
7. **Success Display**: Show output file path

#### `plot-its` - ITS Overlay Plots

**Purpose**: Generate current vs time overlay plots with baseline correction.

**Features:**
- **Preset configurations**: `dark`, `light_power_sweep`, `light_spectral`, `custom`
- **Baseline modes**: `fixed`, `auto`, `none`
- **Legend grouping**: `led_voltage`, `wavelength`, `vg`
- **Auto-detection**: Dark vs light experiments
- **Filters**: `--vg`, `--wavelength`, `--date`
- **Preview/Dry-run**: Check before generating

**Example:**
```bash
# Basic plot
python process_and_analyze.py plot-its 67 --seq 52,57,58

# With preset
python process_and_analyze.py plot-its 67 --seq 52,57,58 --preset dark

# Auto-select with filters
python process_and_analyze.py plot-its 67 --auto --vg -0.4 --wavelength 365

# Range notation
python process_and_analyze.py plot-its 81 --seq 89-117

# Dry run to check filename
python process_and_analyze.py plot-its 67 --seq 52,57,58 --dry-run
```

**Preset System:**

Presets defined in `src/plotting/its_presets.py`:
```python
PRESETS = {
    "dark": ITSPlotPreset(
        name="dark",
        description="Dark measurements (no LED)",
        baseline_mode="none",
        plot_start_time=20.0,
        legend_by="vg",
        ...
    ),
    "light_power_sweep": ITSPlotPreset(
        name="light_power_sweep",
        description="LED power sweep at fixed wavelength",
        baseline_mode="auto",
        baseline_auto_divisor=2.0,
        legend_by="led_voltage",
        check_duration_mismatch=True,
        ...
    ),
}
```

**Dark Detection:**

```python
def _all_its_are_dark(meta: pl.DataFrame) -> bool:
    """Auto-detect if all ITS are dark measurements."""
    # Check Laser toggle column
    if "Laser toggle" in meta.columns:
        if all(not toggle for toggle in meta["Laser toggle"]):
            return True

    # Check laser voltage
    if "Laser voltage" in meta.columns:
        if all(v == 0 or v is None for v in meta["Laser voltage"]):
            return True

    return False
```

#### `plot-its-sequential` - Sequential ITS Plots

**Purpose**: Concatenated time-series plot (experiments follow each other).

**Features:**
- No baseline correction (raw data)
- Different color per experiment
- Optional boundary markers
- Legend by datetime, wavelength, vg, or led_voltage

**Example:**
```bash
python process_and_analyze.py plot-its-sequential 81 --seq 93,94,95,96
python process_and_analyze.py plot-its-sequential 81 --seq 93-96 --legend wavelength
python process_and_analyze.py plot-its-sequential 81 --auto --no-boundaries
```

#### `plot-its-presets` - List Available Presets

**Purpose**: Display all ITS plot presets with descriptions and configurations.

**Example:**
```bash
python process_and_analyze.py plot-its-presets
```

#### `plot-ivg` - IVg Sequence Plots

**Purpose**: Current vs gate voltage curves in chronological order.

**Example:**
```bash
python process_and_analyze.py plot-ivg 67 --seq 2,8,14
python process_and_analyze.py plot-ivg 67 --auto --vds 0.1
python process_and_analyze.py plot-ivg 67 --seq 10-20 --date 2025-10-15
```

#### `plot-transconductance` - Transconductance (gm) Plots

**Purpose**: Compute and plot dI/dVg from IVg measurements.

**Methods:**
- `gradient`: numpy.gradient (default, matches PyQtGraph)
- `savgol`: Savitzky-Golay filter (smoother)

**Example:**
```bash
python process_and_analyze.py plot-transconductance 67 --seq 2,8,14
python process_and_analyze.py plot-transconductance 67 --seq 2,8,14 --method savgol --window 11
python process_and_analyze.py plot-transconductance 67 --auto --vds 0.1
```

**Validation:**
```python
# CRITICAL: Verify ALL experiments are IVg type
if "proc" in history.columns:
    non_ivg = history.filter(pl.col("proc") != "IVg")
    if non_ivg.height > 0:
        console.print("[red]Error: Transconductance requires IVg experiments![/red]")
        raise typer.Exit(1)
```

---

## Design Patterns

### 1. Validation-First Pattern

All commands validate inputs **before** expensive operations:

```python
def plot_command(...):
    # 1. Parse inputs
    seq_numbers = parse_seq_list(seq)

    # 2. Validate experiments exist (fast - only reads history)
    valid, errors = validate_experiments_exist(seq_numbers, ...)
    if not valid:
        console.print("[red]Validation failed[/red]")
        raise typer.Exit(1)

    # 3. Dry-run mode: exit after validation
    if dry_run:
        output_file = calculate_output_filename(...)
        console.print(f"Would create: {output_file}")
        raise typer.Exit(0)

    # 4. Expensive operations (load data, plot)
    history = load_history_for_plotting(...)
    generate_plot(history, ...)
```

**Benefits:**
- Fast feedback on typos/errors
- No wasted computation
- Clear error messages

### 2. Progressive Enhancement Pattern

Commands support multiple modes with increasing detail:

1. **Dry-run**: Fastest, just validation + filename preview
2. **Preview**: Validation + metadata loading + experiment display (no plotting)
3. **Normal**: Full execution with plot generation

```python
# Dry-run: Exit after validation
if dry_run:
    console.print("Dry run - would create:", output_file)
    raise typer.Exit(0)

# Load data (needed for preview and normal modes)
history = load_history_for_plotting(...)

# Preview: Exit after showing what will be plotted
if preview:
    display_experiment_list(history)
    console.print("Preview - no files generated")
    raise typer.Exit(0)

# Normal: Actually generate plot
generate_plot(history, ...)
```

### 3. Rich Console Pattern

Consistent use of Rich for beautiful terminal output:

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def command(...):
    # Header panel
    console.print(Panel.fit(
        "[bold cyan]Command Title[/bold cyan]",
        border_style="cyan"
    ))

    # Progress/status
    console.print("[cyan]Loading data...[/cyan]")
    console.print("[green]✓[/green] Loaded successfully")

    # Data display in table
    table = Table(title="Results")
    table.add_column("Column1", style="cyan")
    table.add_column("Column2", style="yellow")
    # ... add rows
    console.print(table)

    # Success panel
    console.print(Panel.fit(
        "[bold green]✓ Success![/bold green]",
        border_style="green"
    ))
```

**Standard Colors:**
- Cyan: Headers, informational
- Green: Success, confirmations
- Yellow: Warnings
- Red: Errors
- Dim: Less important info
- Magenta: Special highlights

### 4. Error Context Pattern

Errors include helpful hints and next steps:

```python
if not history_file.exists():
    console.print(f"[red]Error:[/red] History file not found: {history_file}")
    console.print(f"\n[yellow]Hint:[/yellow] Run [cyan]build-all-histories[/cyan] first")
    console.print(f"Available files in {history_dir}:")
    for f in sorted(history_dir.glob("*_history.parquet")):
        console.print(f"  • {f.name}")
    raise typer.Exit(1)
```

**Components:**
- **Error message**: What went wrong
- **Hint**: How to fix it
- **Context**: Relevant information (available files, valid options)
- **Exit code**: 0 for graceful exits, 1 for errors

### 5. Parquet Path Aliasing Pattern

Plotting commands handle both legacy and modern history formats:

```python
# Modern history has parquet_path, legacy has source_file
if "parquet_path" in history.columns:
    # Prefer parquet_path (fast staged Parquet)
    history = history.drop("source_file") if "source_file" in history.columns else history
    history = history.rename({"parquet_path": "source_file"})
elif "source_file" not in history.columns:
    # Neither column exists - error
    console.print("[red]Error:[/red] History missing data paths")
    raise typer.Exit(1)

# Now history has source_file pointing to either:
# - Staged Parquet (modern, fast)
# - Raw CSV (legacy, slower)
```

---

## User Experience Features

### 1. Input Flexibility

**Multiple input modes:**
- `--seq`: Explicit list with range support (`"52,57,58"` or `"89-117"`)
- `--auto`: Auto-select all experiments of type
- `--interactive`: TUI selector (deprecated, to be updated)

**Filters stack with auto-select:**
```bash
# Auto-select all ITS experiments with VG=-0.4V
python process_and_analyze.py plot-its 67 --auto --vg -0.4
```

### 2. Smart Filename Generation

Filenames prevent overwrites while being readable:

```python
# Short lists: readable
seq_52_57_58

# Long lists: compact with hash
seq_89_90_91_plus114_a3c4f2

# With custom tag
seq_52_57_58_my_experiment
```

**Deterministic**: Same experiments always generate same filename.

### 3. Progress Feedback

**Clean mode (default):**
```
Staging files ━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:05
```

**Verbose mode:**
```
[1] ACCEPT IVg from Alisson67_015.csv
[2] ACCEPT It from Alisson67_016.csv
[3] ACCEPT IVg from Alisson67_017.csv
...
```

### 4. Configuration Display

Before expensive operations, show what will happen:

```
┌─ Plot Settings ─────────────────────────────┐
│ Legend by: led_voltage                      │
│ Padding: 5.00%                              │
│ Baseline: Fixed at 60.0 s                  │
│ Duration check: Enabled (±10% tolerance)    │
│ Output directory: figs/                     │
└─────────────────────────────────────────────┘
```

### 5. Helpful Suggestions

Commands suggest next steps:

```
┌─ Pipeline Complete! ────────────────────────┐
│                                              │
│ Outputs:                                     │
│   • Staged data: data/02_stage              │
│   • Manifest: manifest.parquet              │
│   • Histories: chip_histories/              │
│                                              │
│ Next steps:                                  │
│   • show-history <chip> - View timeline     │
│   • plot-its - Generate plots               │
│   • validate-manifest - Check data quality  │
└──────────────────────────────────────────────┘
```

### 6. Light Status Icons

Visual indicators for experiment lighting:
- 💡 Light (laser ON)
- 🌙 Dark (laser OFF)
- ❗ Unknown (manual review needed)

---

## Error Handling

### 1. Early Validation

Validate inputs before expensive operations:

```python
# 1. Check file exists (fast)
if not history_file.exists():
    console.print("[red]Error:[/red] File not found")
    raise typer.Exit(1)

# 2. Validate seq numbers (fast)
valid, errors = validate_experiments_exist(seq_numbers, ...)
if not valid:
    for error in errors:
        console.print(f"[red]✗[/red] {error}")
    raise typer.Exit(1)

# 3. Expensive operations (only after validation)
history = load_history_for_plotting(...)
```

### 2. Graceful Exit Codes

```python
# Error condition (invalid input)
raise typer.Exit(1)

# Graceful exit (no data matching filter)
raise typer.Exit(0)
```

### 3. Context-Rich Errors

```python
except FileNotFoundError:
    console.print(f"[red]Error:[/red] File not found: {path}")
    console.print(f"[yellow]Hint:[/yellow] Run 'stage-all' first")
    raise typer.Exit(1)

except ValueError as e:
    console.print(f"[red]Error:[/red] {e}")
    console.print(f"[yellow]Valid options:[/yellow] ...")
    raise typer.Exit(1)
```

### 4. Pipeline Error Propagation

Multi-step commands catch and report sub-command failures:

```python
def full_pipeline_command(...):
    try:
        stage_all_command(...)
    except SystemExit as e:
        if e.code != 0:
            console.print("[red]✗ Staging failed, aborting pipeline[/red]")
            raise typer.Exit(1)

    try:
        build_all_histories_command(...)
    except SystemExit as e:
        if e.code != 0:
            console.print("[red]✗ History generation failed[/red]")
            raise typer.Exit(1)
```

---

## Extension Guide

### Adding a New Command

1. **Create command module** in `src/cli/commands/`:

```python
# src/cli/commands/my_command.py
import typer
from pathlib import Path
from rich.console import Console

console = Console()

def my_command(
    arg1: int = typer.Argument(..., help="Required argument"),
    opt1: str = typer.Option("default", "--opt1", "-o", help="Optional flag"),
):
    """
    Brief description of command.

    Examples:
        command examples here
    """
    # 1. Validate inputs
    console.print("[cyan]Validating...[/cyan]")

    # 2. Core logic
    console.print("[cyan]Processing...[/cyan]")

    # 3. Report results
    console.print("[green]✓ Success![/green]")
```

2. **Register in main.py**:

```python
# main.py
from src.cli.commands.my_command import my_command

app.command(name="my-command")(my_command)
```

3. **Test**:

```bash
python process_and_analyze.py my-command --help
python process_and_analyze.py my-command <args>
```

### Adding a Helper Function

1. **Choose appropriate module**:
   - `helpers.py`: Plotting-related helpers
   - `history_utils.py`: History filtering/summarization
   - Create new module if needed

2. **Follow naming conventions**:
   - `snake_case` for functions
   - Type hints for all parameters and returns
   - Docstrings with examples

3. **Import in commands**:

```python
from src.cli.helpers import my_helper_function
```

### Best Practices

1. **Use Rich for all output** (not print)
2. **Validate early** before expensive operations
3. **Provide helpful error messages** with hints
4. **Use consistent colors** (cyan=info, green=success, red=error, yellow=warning)
5. **Include examples** in docstrings
6. **Support dry-run/preview** for expensive commands
7. **Use Typer.Option** with short flags (`-o`) for common options
8. **Exit with appropriate codes** (0=success/graceful, 1=error)

---

## Summary

The `src/cli` module provides a **production-quality CLI** with:

- **Clean architecture**: Modular commands, centralized registration
- **Beautiful UX**: Rich tables, panels, progress bars, colors
- **Robust validation**: Early checks, helpful errors, dry-run modes
- **Parquet-native**: Optimized for modern staging pipeline
- **Extensible design**: Easy to add new commands and helpers

**Key Design Principles:**
1. Validate early, fail fast
2. Provide context-rich errors
3. Use progressive enhancement (dry-run → preview → execute)
4. Maintain consistent visual language
5. Extract reusable helpers (DRY)
6. Support flexible input modes

The CLI is the primary interface for **power users and scripting**, while the TUI (`src/tui/`) provides a **guided experience for lab users**.
