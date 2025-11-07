# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based data processing and visualization pipeline for optothermal semiconductor device characterization. The codebase processes raw measurement CSV files from lab equipment (Keithley sourcemeter, laser control, temperature sensors), stages them into optimized Parquet format, builds experiment histories, and generates publication-quality scientific plots.

**Key Technologies:**
- Python 3.11+ (uses zoneinfo for timezone handling)
- Polars (primary dataframe library, NOT pandas)
- Pydantic v2+ (data validation)
- Typer + Rich (modern CLI with beautiful terminal output)
- Matplotlib + scienceplots (publication-quality figures)
- Textual (terminal UI framework)

## Environment Setup

```bash
# Activate virtual environment (ALWAYS do this first)
source .venv/bin/activate

# Install dependencies (use uv if available, or pip)
uv pip install -r requirements.txt
# OR
pip install -r requirements.txt

# Verify installation
python3 process_and_analyze.py --help
```

## Key Commands

### Quick Start

```bash
# Complete pipeline (staging + history generation)
python3 process_and_analyze.py full-pipeline

# View chip history
python3 process_and_analyze.py show-history 67

# Generate plots
python3 process_and_analyze.py plot-its 67 --seq 52,57,58
python3 process_and_analyze.py plot-ivg 67 --auto
```

### Data Processing Pipeline

```bash
# Stage raw CSVs to Parquet (with parallel processing)
python3 process_and_analyze.py stage-all

# Stage with schema validation (strict mode - fails on errors)
python3 process_and_analyze.py stage-all --strict

# Build experiment histories for all chips
python3 process_and_analyze.py build-all-histories

# Validate manifest schema and data quality
python3 process_and_analyze.py validate-manifest

# Inspect manifest with filtering
python3 process_and_analyze.py inspect-manifest --chip 67

# View chip experiment history
python3 process_and_analyze.py show-history 67 --proc IVg --light dark --limit 20
```

### Derived Metrics Pipeline (New in v3.0)

```bash
# Extract all derived metrics (CNP, photoresponse) from measurements
python3 process_and_analyze.py derive-all-metrics

# Include laser calibration power extraction (enabled by default)
python3 process_and_analyze.py derive-all-metrics --calibrations

# Extract metrics for specific chip or procedure
python3 process_and_analyze.py derive-all-metrics --chip 75
python3 process_and_analyze.py derive-all-metrics --procedures IVg,VVg

# Preview what would be extracted (dry run)
python3 process_and_analyze.py derive-all-metrics --dry-run

# Force re-extraction (overwrite existing metrics)
python3 process_and_analyze.py derive-all-metrics --force

# Enrich chip histories with derived metrics (RECOMMENDED UNIFIED COMMAND)
python3 process_and_analyze.py enrich-history 75        # Single chip
python3 process_and_analyze.py enrich-history -a        # All chips
python3 process_and_analyze.py enrich-history 67,81,75  # Multiple chips
python3 process_and_analyze.py enrich-history -a --calibrations-only  # Only add power data

# Alternative: Link calibrations only (advanced users)
python3 process_and_analyze.py link-calibrations
```

### Plotting Commands

```bash
# ITS (current vs time) plots
python3 process_and_analyze.py plot-its 67 --seq 52,57,58
python3 process_and_analyze.py plot-its 67 --auto --vg -0.4  # Auto-select with filters
python3 process_and_analyze.py plot-its-presets  # List available presets

# IVg (gate voltage sweep) plots
python3 process_and_analyze.py plot-ivg 67 --seq 2,8,14
python3 process_and_analyze.py plot-ivg 67 --auto

# Transconductance (gm = dI/dVg) plots
python3 process_and_analyze.py plot-transconductance 67 --seq 2,8,14

# VVg (drain-source voltage vs gate voltage) plots
python3 process_and_analyze.py plot-vvg 67 --seq 2,8,14
python3 process_and_analyze.py plot-vvg 67 --auto

# Vt (voltage vs time) plots
python3 process_and_analyze.py plot-vt 67 --seq 10,20,30

# CNP (Charge Neutrality Point / Dirac point) evolution plots
python3 process_and_analyze.py plot-cnp-time 81

# Photoresponse plots (vs power, wavelength, gate voltage, or time)
python3 process_and_analyze.py plot-photoresponse 81 power
python3 process_and_analyze.py plot-photoresponse 81 wavelength --vg -0.4
python3 process_and_analyze.py plot-photoresponse 81 gate_voltage --wl 660
python3 process_and_analyze.py plot-photoresponse 81 time

# Laser calibration plots
python3 process_and_analyze.py plot-laser-calibration 67
```

### Configuration Management

```bash
# View current configuration
python3 process_and_analyze.py config-show

# Initialize config file
python3 process_and_analyze.py config-init

# Validate configuration
python3 process_and_analyze.py config-validate

# Use with overrides
python3 process_and_analyze.py --verbose --output-dir /tmp/test plot-its 67 --auto
```

### Terminal UI (For Lab Users)

```bash
# Launch interactive TUI for non-technical users
python3 tui_app.py
```

### Command Discovery

```bash
# List all available commands
python3 process_and_analyze.py --help

# List plugins with metadata
python3 process_and_analyze.py list-plugins

# List commands by group
python3 process_and_analyze.py list-plugins --group plotting
```

## Architecture

### Data Flow

The pipeline follows a four-stage data processing architecture:

**Stage 1: Raw Data** (`data/01_raw/`)
- Raw CSV files from lab equipment
- Organized by date or experiment folder
- Naming convention: `{ChipGroup}{ChipNumber}_{FileIndex}.csv` (e.g., `Alisson67_015.csv`)
- Each CSV has structured header with `#Parameters:`, `#Metadata:`, and `#Data:` sections

**Stage 2: Staged Data** (`data/02_stage/`)
- Parquet files organized by procedure type (`raw_measurements/{proc}/`)
- `manifest.parquet`: Authoritative metadata table (one row per measurement)
- Schema-validated using Pydantic models (`src/models/manifest.py`)
- Parallel processing using multiprocessing pool (configurable workers)
- Run IDs: deterministic SHA-1 hash of `(path|timestamp_utc)` for idempotency
- `chip_histories/`: Per-chip Parquet histories with sequential experiment numbers

**Stage 3: Derived Metrics** (`data/03_derived/`) **[New in v3.0]**
- `_metrics/metrics.parquet`: Extracted derived metrics (CNP, photoresponse, etc.)
- `chip_histories_enriched/`: Chip histories with derived metrics joined as columns
- Contains laser calibration power associations (irradiated power values)
- Built by `derive-all-metrics` command from staged measurements

**Stage 2.5: Chip Histories** (`data/02_stage/chip_histories/`)
- Per-chip Parquet histories with sequential experiment numbers
- Built from manifest.parquet, filtered by chip_number/chip_group
- **Includes `parquet_path` column** pointing to staged measurement data
- Used by plotting functions to select experiments and load data efficiently
- Located under staging directory as metadata summaries of staged data

### Module Organization

**Core Processing** (`src/core/`)
- `stage_raw_measurements.py`: Main staging pipeline (CSV → Parquet + manifest)
- `schema_validator.py`: **Schema validation engine (validates CSV against procedures.yml)**
- `history_builder.py`: Chip history generation from manifest
- `utils.py`: Common utilities, numeric coercion, light detection, Parquet reading with `read_measurement_parquet()`
- `stage_utils.py`: Validation helpers, type coercion for staging
- `parser.py`: CSV header parsing (legacy, still used for compatibility)
- `timeline.py`: Day timeline builder for TUI (legacy)

**Data Models** (`src/models/`)
- `manifest.py`: Pydantic schema for manifest.parquet rows (authoritative metadata schema)
- `parameters.py`: Staging configuration parameters
- `config.py`: TUI configuration state

**Plotting** (`src/plotting/`)
- `its.py`: Current vs time plots (photoresponse) - **reads from staged Parquet via `parquet_path`**
- `ivg.py`: Gate voltage sweep plots
- `vvg.py`: Drain-source voltage vs gate voltage plots
- `vt.py`: Voltage vs time plots
- `transconductance.py`: dI/dVg calculations (Savitzky-Golay filtering)
- `cnp_time.py`: CNP (Dirac point) evolution over time
- `photoresponse.py`: Photoresponse vs power/wavelength/gate/time
- `laser_calibration.py`: Laser calibration curve plots
- `its_presets.py`: Predefined ITS plot configurations
- `plot_utils.py`: Baseline interpolation, shared utilities
- `overlays.py`: Multi-experiment overlay logic
- `styles.py`: scienceplots styling configuration
- **IMPORTANT**: All plotting uses `read_measurement_parquet()` from `src/core/utils.py`

**Derived Metrics** (`src/derived/`) **[New in v3.0]**
- `metric_pipeline.py`: Main pipeline for extracting derived metrics
- `extractors/`: Individual metric extractors (CNP, photoresponse, calibration matching)
- `registry.py`: Plugin registry for auto-discovery of extractors
- `models.py`: Pydantic models for metric metadata
- Supports parallel extraction and incremental updates

**CLI** (`src/cli/`)
- `main.py`: Typer app with plugin discovery system
- `plugin_system.py`: **Auto-discovery and registration of commands via `@cli_command` decorator**
- `config.py`: **Configuration management layer (Pydantic-based)**
- `commands/`: Individual command modules (auto-discovered by plugin system)
  - `data_pipeline.py`: Full pipeline orchestration
  - `history.py`: History viewing and generation
  - `stage.py`: Staging commands and validation
  - `derived_metrics.py`: Derived metrics extraction commands
  - `plot_its.py`: ITS plotting with presets
  - `plot_ivg.py`: IVg plotting
  - `plot_vvg.py`: VVg plotting
  - `plot_vt.py`: Vt plotting
  - `plot_transconductance.py`: Transconductance plotting
  - `plot_cnp.py`: CNP evolution plotting
  - `plot_photoresponse.py`: Photoresponse analysis plotting
  - `plot_laser_calibration.py`: Laser calibration plotting
  - `config.py`: Configuration management commands
  - `utilities.py`: Utility commands (list-plugins, etc.)
- `helpers.py`: Shared CLI utilities (seq parsing, output setup, Rich displays)
- `history_utils.py`: History filtering logic shared by CLI and TUI
- **Note**: `process_and_analyze.py` in project root is a thin wrapper

**TUI** (`src/tui/`)
- Textual-based terminal interface for non-technical lab users
- `app.py`: Main PlotterApp with wizard-style workflow
- `screens/`: Navigation screens (chip selector, config forms, preview)
- `config_manager.py`: Recent configurations persistence (JSON-based)

### Configuration Files

**`config/procedures.yml`**
- Schema definitions for all measurement procedures (IVg, IV, IVgT, It, ITt, LaserCalibration, Tt)
- Specifies expected Parameters, Metadata, and Data columns with types
- **ManifestColumns section** (optional): YAML-driven manifest column extraction
- **Config section** (optional): Procedure-specific behavior (light detection, etc.)
- Used by staging pipeline for validation, type casting, and dynamic manifest generation
- **Modify this file to add new procedures** - no Python code changes needed!
- **See**: `docs/YAML_DRIVEN_MANIFEST.md` for complete documentation

**`config/chip_params.yaml`**
- Chip-specific metadata (chip_group, expected_procs, voltage ranges, wavelengths)
- Global defaults: timezone (`America/Santiago`), parallel workers (6), polars threads (1)
- Staging behavior: force_overwrite, only_yaml_data flags

**`config/cli_plugins.yaml`**
- Controls which CLI command groups are enabled/disabled
- Supports `enabled_groups` (e.g., `[pipeline, history, staging, plotting]` or `[all]`)
- Supports `disabled_commands` for specific commands

### Key Concepts

**Parquet-Based Pipeline**
- **All data is Parquet**: Raw CSVs → Staged Parquet → History Parquet → Plotting
- **Fast & efficient**: Parquet files are 10-100x faster than CSV
- **Schema-validated**: Types checked during staging, no parsing errors in plotting
- **Single source of truth**: Staged Parquet files referenced by `parquet_path` in histories
- Plotting functions use `read_measurement_parquet()` from `src/core/utils.py`

**Schema Validation & Evolution**
- **Automatic validation**: Every CSV validated against `config/procedures.yml` during staging
- **Optional columns support**: Mark columns as `required: false` for backward compatibility
- **Schema evolution**: Add new columns without breaking old data (nulls filled automatically)
- **Validation modes**:
  - Default: Warns on missing optional columns, continues processing
  - Strict (`--strict`): Fails on missing required columns, critical parameters
- **Validation output**: ERROR (fails in strict), WARN (logged), INFO (informational)
- **Consistent schemas**: All parquet files have same columns (old data has typed nulls for new fields)
- **See**: `docs/SCHEMA_VALIDATION_GUIDE.md` for complete documentation

**Light Detection**
- Primary: Laser voltage < 0.1V = dark (🌙), >= 0.1V = light (💡)
- Fallback: VL column in measurement data
- Unknown (❗) triggers warning for manual review

**Run ID Generation**
- Deterministic: `SHA1(normalized_path|timestamp_utc)[:16]`
- Ensures idempotent staging (re-running doesn't create duplicates)

**Parallel Processing**
- Staging uses ProcessPoolExecutor (default 6 workers)
- Each worker has dedicated Polars threads (default 1)
- Configure via `config/chip_params.yaml` or CLI flags

**Timezone Handling**
- Raw CSV timestamps are Unix epoch (seconds since 1970-01-01)
- Localized to `America/Santiago` during staging
- Converted to UTC for storage in manifest.parquet
- `date_local` field preserves local calendar date for Hive partitioning

## Key Concepts (Continued)

**Derived Metrics Pipeline** **[New in v3.0]**
- **Automated extraction**: Extracts derived quantities (CNP, photoresponse) from measurements
- **Plugin-based extractors**: Auto-discovered metric extractors in `src/derived/extractors/`
- **Incremental updates**: Only processes new/changed measurements (use `--force` to re-extract)
- **Parallel processing**: Multi-worker extraction for performance
- **Laser calibration matching**: Associates light experiments with nearest calibration curves
- **Power interpolation**: Calculates irradiated power from laser voltage and calibration data
- **Enriched histories**: Chip histories with derived metrics joined as columns for plotting
- **See**: `docs/DERIVED_METRICS_ARCHITECTURE.md` for complete documentation

**Adding New Derived Metrics**
1. **Create extractor** in `src/derived/extractors/my_metric.py`:
   ```python
   from src.derived.registry import register_extractor
   from src.derived.models import DerivedMetric

   @register_extractor
   class MyMetricExtractor:
       procedures = ["IVg"]  # Which procedures to process

       def extract(self, measurement: pl.DataFrame, metadata: dict) -> list[DerivedMetric]:
           # Extract metric from measurement data
           return [DerivedMetric(...)]
   ```
2. **Auto-discovered**: No registration needed, just import in `__init__.py`
3. **Test**: `python3 process_and_analyze.py derive-all-metrics --procedures IVg`
4. **See**: `docs/ADDING_NEW_METRICS_GUIDE.md` for step-by-step guide

## Development Workflow

### Adding New CLI Commands (Recommended Approach)

The codebase uses a **plugin system** for automatic command discovery. No need to modify `main.py`!

1. **Create command file** in `src/cli/commands/my_feature.py`
2. **Use the `@cli_command` decorator**:
   ```python
   from src.cli.plugin_system import cli_command
   import typer

   @cli_command(
       name="my-command",
       group="utilities",  # Options: pipeline, history, staging, plotting, utilities
       description="Brief description of what it does"
   )
   def my_command_function(
       chip_number: int = typer.Argument(..., help="Chip number"),
       option: str = typer.Option("default", "--option", "-o")
   ):
       """Detailed docstring for the command."""
       # Implementation here
       pass
   ```
3. **Done!** Command is auto-discovered and registered
4. **Test it**: `python3 process_and_analyze.py my-command --help`

### Adding New Procedure Types

1. **Update `config/procedures.yml`** with schema definition:
   ```yaml
   MyNewProcedure:
     Parameters:
       V1: float64
       V2: float64
     Metadata:
       wavelength: float64
     Data:
       time: float64
       current: float64
   ```
2. **Run staging**: Pipeline auto-validates against new schema
3. **Test**: `python3 process_and_analyze.py validate-manifest`

### Adding New Plotting Commands

**See `docs/PLOTTING_IMPLEMENTATION_GUIDE.md` for comprehensive step-by-step instructions with templates for all procedure types!**

Quick overview:

1. **Create plotting function** in `src/plotting/my_procedure.py`:
   ```python
   from src.core.utils import read_measurement_parquet

   def plot_my_procedure(df: pl.DataFrame, base_dir: Path, tag: str) -> Path:
       """Generate plots for MyProcedure measurements."""
       # Load data from staged Parquet via parquet_path column
       for row in df.iter_rows(named=True):
           parquet_path = Path(row["parquet_path"])
           measurement = read_measurement_parquet(parquet_path)
           # ... plotting logic
       return output_file
   ```

2. **Create CLI command** in `src/cli/commands/plot_my_procedure.py`:
   ```python
   from src.cli.plugin_system import cli_command
   from src.plotting.my_procedure import plot_my_procedure

   @cli_command(name="plot-my-procedure", group="plotting")
   def plot_my_procedure_command(chip_number: int, ...):
       """Generate MyProcedure plots."""
       # Load history, filter by procedure, call plotting function
       pass
   ```

3. **Auto-discovered!** No registration needed - just run `python3 process_and_analyze.py plot-my-procedure --help`

**Reference implementations:**
- Time-series (I vs t): `src/plotting/its.py`
- Voltage sweeps (I vs Vg): `src/plotting/ivg.py`
- Voltage sweeps (V vs Vg): `src/plotting/vvg.py`
- Voltage time-series (V vs t): `src/plotting/vt.py`
- Derivatives: `src/plotting/transconductance.py`
- Derived metrics: `src/plotting/cnp_time.py`, `src/plotting/photoresponse.py`

### Modifying Data Schema

1. **Update `src/models/manifest.py`** (Pydantic model)
2. **Bump `schema_version`** field
3. **Handle migrations** if changing existing fields
4. **Validate**: `python3 process_and_analyze.py validate-manifest`

### Testing

```bash
# Activate environment first
source .venv/bin/activate

# Run all tests with pytest
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_config.py -v

# Run specific test function
python3 -m pytest tests/test_config.py::test_function_name -v

# Test staging on small dataset
python3 process_and_analyze.py stage-all --dry-run  # Preview mode (if implemented)

# Validate after staging
python3 process_and_analyze.py validate-manifest

# Test command imports
python3 -c "from src.cli.main import app; print('✓ CLI imports OK')"

# Test command discovery
python3 process_and_analyze.py list-plugins
```

## Important Notes

### Use Python 3.11+
- Required for zoneinfo timezone handling
- Verify: `python3 --version`

### Always Use Polars (NOT pandas)
- Faster and more memory-efficient
- Different API: use `.filter()` not `.query()`, `.select()` not `[]`
- Refer to `src/core/utils.py` for examples

### Parquet is the Source of Truth
- **NEVER read from CSV files directly** in new code
- Use `read_measurement_parquet()` from `src/core/utils.py`
- History Parquet files contain `parquet_path` pointing to staged data

### Git Version Tracking
- Uses `git describe` for extraction_version tracking
- Format: `v{major}.{minor}.{patch}+g{commit_hash}[-dirty]`
- Embedded in manifest.parquet during staging

### Configuration System
- Uses Pydantic for validation
- Supports environment variables (`CLI_*` prefix), config files, and CLI overrides
- Priority: CLI flags > config file > env vars > defaults
- See `src/cli/config.py` for implementation

### Plugin System
- Commands auto-discovered via `@cli_command` decorator
- Controlled by `config/cli_plugins.yaml`
- No need to modify `main.py` when adding commands
- See `docs/CLI_PLUGIN_SYSTEM.md` for details

## Legacy vs Modern Pipeline

**Modern Pipeline (CURRENT - ALWAYS use this):**
- `full-pipeline`: Runs staging → history generation
- `stage-all`: CSV → Parquet with Pydantic validation
- `build-all-histories`: Generate histories from `manifest.parquet`
- `derive-all-metrics`: Extract derived metrics (CNP, photoresponse) with laser calibration power
- Uses `data/02_stage/raw_measurements/_manifest/manifest.parquet` as source of truth

**Legacy Pipeline (DEPRECATED - DO NOT USE):**
- `parse-all`: CSV headers → metadata CSV files (obsolete)
- `chip-histories`: Generate histories from metadata folder (obsolete)
- Functions in `src/core/parser.py` and `src/core/timeline.py` (kept for compatibility)
- Some legacy functions still used by TUI, but being phased out

**Deprecated Enrichment Commands (Still work, but hidden from help):**
- `enrich-all-histories` → Use: `enrich-history -a`
- `enrich-histories-with-calibrations` → Use: `link-calibrations` or `enrich-history -a --calibrations-only`
- `enrich-history-old` → Use: `enrich-history <chip>`
- These commands still function for backward compatibility but are hidden from `--help` output
- Users are encouraged to migrate to the new unified `enrich-history` command

## Recent Additions & Features

### Version 3.0 - Derived Metrics Pipeline (October 2025)

**New Commands:**
- `derive-all-metrics`: Extract CNP, photoresponse, and laser calibration power
- `enrich-history`: **UNIFIED COMMAND** - Join calibrations and metrics to chip histories
  - Replaces: `enrich-all-histories`, `enrich-histories-with-calibrations` (now hidden)
  - Examples: `enrich-history 75`, `enrich-history -a`, `enrich-history -a --calibrations-only`
- `link-calibrations`: Associate light experiments with laser calibrations (advanced)
  - Renamed from: `enrich-histories-with-calibrations` (kept as hidden alias)
- `plot-cnp-time`: Plot CNP (Dirac point) evolution over time
- `plot-photoresponse`: Plot photoresponse vs power, wavelength, gate voltage, or time
- `plot-laser-calibration`: Visualize laser calibration curves

**New Plotting Support:**
- `plot-vvg`: Drain-source voltage vs gate voltage plots (VVg procedure)
- `plot-vt`: Voltage vs time plots (Vt procedure)

**Workflow:**
1. Stage data: `python3 process_and_analyze.py full-pipeline`
2. Extract metrics: `python3 process_and_analyze.py derive-all-metrics`
3. **Enrich histories: `python3 process_and_analyze.py enrich-history -a`** ⭐ New unified command!
4. Plot derived quantities: `python3 process_and_analyze.py plot-cnp-time 81`

**Documentation:**
- `docs/DERIVED_METRICS_ARCHITECTURE.md`: Complete architecture guide
- `docs/ADDING_NEW_METRICS_GUIDE.md`: Step-by-step guide for adding extractors
- `docs/DERIVED_METRICS_QUICKSTART.md`: Quick start guide
- `docs/CNP_EXTRACTOR_GUIDE.md`: CNP extractor implementation details
