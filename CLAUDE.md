# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based data processing and visualization pipeline for optothermal semiconductor device characterization. The codebase processes raw measurement CSV files from lab equipment (Keithley sourcemeter, laser control, temperature sensors), stages them into optimized Parquet format, builds experiment histories, and generates publication-quality scientific plots.

## Key Commands

### Environment Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Data Processing Pipeline

```bash
# Full pipeline (RECOMMENDED: stage + histories in one command)
python process_and_analyze.py full-pipeline

# OR run steps individually:

# Stage raw CSVs to Parquet (with parallel processing)
python process_and_analyze.py stage-all --raw-root data/01_raw --stage-root data/02_stage/raw_measurements

# Build experiment histories for all chips from manifest
python process_and_analyze.py build-all-histories --manifest data/02_stage/raw_measurements/_manifest/manifest.parquet

# Validate manifest schema and data quality
python process_and_analyze.py validate-manifest --manifest data/02_stage/raw_measurements/_manifest/manifest.parquet

# Inspect manifest with filtering
python process_and_analyze.py inspect-manifest --manifest data/02_stage/raw_measurements/_manifest/manifest.parquet --chip 67

# View chip history
python process_and_analyze.py show-history 67 --history-dir data/03_history
```

### Plotting Commands

```bash
# Generate ITS (current vs time) overlay plots
python process_and_analyze.py plot-its --metadata-csv <path> --chip-number 67

# List available ITS presets
python process_and_analyze.py plot-its-presets

# Generate IVg (gate voltage sweep) plots
python process_and_analyze.py plot-ivg --chip-number 67

# Generate transconductance plots (dI/dVg from IVg data)
python process_and_analyze.py plot-transconductance --chip-number 67
```

### Terminal UI (For Lab Users)

```bash
# Launch interactive TUI for non-technical users
python tui_app.py
```

## Architecture

### Data Flow

The pipeline follows a three-stage data processing architecture:

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

**Stage 3: History Files** (`data/03_history/`)
- Per-chip Parquet histories with sequential experiment numbers
- Built from manifest.parquet, filtered by chip_number/chip_group
- **Includes `parquet_path` column** pointing to staged measurement data
- Used by plotting functions to select experiments and load data efficiently

### Module Organization

**Core Processing** (`src/core/`)
- `parser.py`: CSV header parsing, procedure detection
- `utils.py`: Common utilities, numeric coercion, light detection
- `timeline.py`: Day timeline builder for TUI experiment selection
- `history_builder.py`: Chip history generation from manifest

**Staging Layer** (`src/staging/`)
- `stage_raw_measurements.py`: Main staging pipeline (CSV → Parquet + manifest)
- `stage_utils.py`: Validation helpers, type coercion
- Uses `config/procedures.yml` for schema validation
- Uses `config/chip_params.yaml` for chip-specific settings

**Data Models** (`src/models/`)
- `manifest.py`: Pydantic schema for manifest.parquet rows
- `parameters.py`: Staging configuration parameters
- `config.py`: TUI configuration state

**Plotting** (`src/plotting/`)
- `its.py`: Current vs time plots (photoresponse)
- `ivg.py`: Gate voltage sweep plots
- `transconductance.py`: dI/dVg calculations (Savitzky-Golay filtering)
- `styles.py`: scienceplots styling configuration
- `plot_utils.py`: Baseline interpolation, shared utilities
- `overlays.py`: Multi-experiment overlay logic
- **Now reads from staged Parquet files** via `parquet_path` in chip histories
- Use `read_measurement_parquet()` from `src/core/utils.py` for efficient loading

**CLI** (`src/cli/`)
- `main.py`: Typer app aggregating all commands (actual CLI implementation)
- `commands/`: Individual command modules (data_pipeline, history, plot_*, stage)
- `helpers.py`: Shared CLI utilities
- Note: `process_and_analyze.py` in project root is just a thin wrapper importing `src/cli/main.py`

**TUI** (`src/tui/`)
- Textual-based terminal interface for lab users
- `app.py`: Main PlotterApp
- `screens/`: Wizard-style navigation (chip selector, config forms, preview)
- `config_manager.py`: Recent configurations persistence

### Configuration Files

**`config/procedures.yml`**
- Schema definitions for all measurement procedures (IVg, IV, IVgT, It, ITt, LaserCalibration, Tt)
- Specifies expected Parameters, Metadata, and Data columns with types
- Used by staging pipeline for validation and type casting

**`config/chip_params.yaml`**
- Chip-specific metadata (chip_group, expected_procs, voltage ranges, wavelengths)
- Global defaults: timezone (`America/Santiago`), parallel workers (6), polars threads (1)
- Staging behavior: force_overwrite, only_yaml_data flags

### Key Concepts

**Parquet-Based Pipeline**
- **All data is Parquet**: Raw CSVs → Staged Parquet → History Parquet → Plotting
- **Fast & efficient**: Parquet files are 10-100x faster than CSV
- **Schema-validated**: Types checked during staging, no parsing errors in plotting
- **Single source of truth**: Staged Parquet files referenced by `parquet_path` in histories
- Plotting functions use `read_measurement_parquet()` from `src/core/utils.py`

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

## Development Workflow

1. **Adding New Procedure Types**: Update `config/procedures.yml` with schema, then staging pipeline auto-validates
2. **Adding Plots**: Create new module in `src/plotting/`, add command in `src/cli/commands/`, register in `src/cli/main.py`
3. **Testing Staging**: Use `stage-all --dry-run` (if implemented) or test on small dataset, then `validate-manifest`
4. **Modifying Schema**: Update `src/models/manifest.py` (Pydantic), bump `schema_version`, handle migrations

## Notes

- Python 3.11+ required (uses zoneinfo for timezone handling)
- Polars is primary dataframe library (not pandas)
- matplotlib with scienceplots for publication-quality figures
- Git describe used for extraction_version tracking (`v{major}.{minor}.{patch}+g{commit_hash}[-dirty]`)

## Legacy vs Modern Pipeline

**Modern Pipeline (CURRENT - Use this):**
- `full-pipeline`: Runs staging → history generation
- `stage-all`: CSV → Parquet with Pydantic validation
- `build-all-histories`: Generate histories from `manifest.parquet`
- Uses `data/02_stage/raw_measurements/_manifest/manifest.parquet` as source of truth

**Legacy Pipeline (DEPRECATED):**
- `parse-all`: CSV headers → metadata CSV files
- `chip-histories`: Generate histories from metadata folder
- Functions in `src/core/parser.py` and `src/core/timeline.py`
- Still present in codebase but superseded by staging system
- Legacy code in `src/legacy/` is fully deprecated
