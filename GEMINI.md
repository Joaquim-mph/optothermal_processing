# GEMINI.md - Biotite Project Context

This file provides essential context and instructions for working with the **Biotite** codebase, a data processing and visualization pipeline for optothermal semiconductor device characterization.

## Project Overview

- **Purpose:** Automate the transition from raw lab measurement CSVs (Keithley, laser, temperature) to publication-quality scientific plots and derived metrics.
- **Core Architecture:** A 4-stage data pipeline:
    1. **Raw (01_raw):** Original CSV files.
    2. **Staged (02_stage):** Schema-validated Parquet files and a central `manifest.parquet`.
    3. **Derived (03_derived):** Extracted metrics (CNP, photoresponse) and enriched histories.
    4. **Plots (figs/):** Final figures organized by chip and procedure.
- **Tech Stack:**
    - **Language:** Python 3.11+
    - **Data Processing:** **Polars** (High performance, NO pandas)
    - **Validation:** **Pydantic v2**
    - **CLI/TUI:** Typer, Rich, Textual
    - **Scientific:** Matplotlib (+ scienceplots), NumPy, SciPy, Numba

## Key Commands

### Environment & Setup
```bash
source .venv/bin/activate
pip install -e ".[dev]"       # Editable install with dev dependencies
```

### Data Pipeline
```bash
biotite full-pipeline         # Run staging + history generation
biotite stage-all             # CSV -> Parquet (Standardized staging)
biotite build-all-histories   # Generate chip histories from manifest
biotite derive-all-metrics    # Extract CNP, photoresponse, etc.
biotite validate-manifest     # Run schema and quality checks
```

### Plotting & Visualization
```bash
biotite plot-its CHIP --auto  # Generate ITS (Current vs Time) plots
biotite plot-ivg CHIP --auto  # Generate IVg (Gate Sweep) plots
biotite plot-its-suite CHIP   # Generate multiple ITS-related plots
biotite-tui                   # Launch interactive terminal UI
```

### Testing
```bash
pytest tests/ -v              # Run all tests
```

## Architecture & Module Map

- `src/core/`: The "Engine". Staging (`stage_raw_measurements.py`), history building (`history_builder.py`), and the formal `pipeline.py`.
- `src/models/`: Pydantic schemas. `manifest.py` is the source of truth for all metadata fields.
- `src/cli/`: Typer CLI. Uses a plugin system in `commands/` via the `@cli_command` decorator.
- `src/plotting/`: Specific plot implementations (its, ivg, vvg, etc.). Uses `PlotConfig` for styling and output paths.
- `src/derived/`: Extraction logic for scientific metrics. Extractors in `extractors/` are auto-discovered.
- `src/tui/`: Textual-based interactive wizard.
- `config/`: YAML configurations for procedures (`procedures.yml`), chips (`chip_params.yaml`), and plugins.

## Development Mandates & Conventions

### 1. Data Processing
- **NEVER use pandas.** Use Polars exclusively (`.filter()`, `.select()`, `.with_columns()`).
- **Parquet is the Source of Truth.** Do not read raw CSVs for analysis.
- **Data Loading:** Always use `read_measurement_parquet(path)` from `src/core/utils.py`. It automatically joins metadata from the manifest.

### 2. CLI Extension
- **Plugin System:** To add a new command, create a file in `src/cli/commands/` and use the `@cli_command` decorator. It will be auto-discovered. No changes to `main.py` are required.

### 3. Plotting Style
- **No Grids:** Never call `plt.grid(True)` or `ax.grid(True)`.
- **Output Paths:** Use `PlotConfig` to maintain the chip-first directory hierarchy (`figs/ChipName/Proc/...`).
- **Standard Names:** Use procedure names from `procedures.yml` (e.g., `It`), not plotting aliases.

### 4. Data Models
- **Manifest integrity:** `src/models/manifest.py` defines every field in the manifest. All changes to data structure must start here.

## Reference Documentation
- `README.md`: High-level overview and installation.
- `CLAUDE.md`: Concise technical guide for AI assistants.
- `docs/ARCHITECTURE/*.md`: Deep dives into specific subsystems.
- `docs/guides/*.md`: Step-by-step guides for adding metrics, procedures, or plots.
