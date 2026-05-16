# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python data processing and visualization pipeline for optothermal semiconductor device characterization. Processes raw measurement CSVs from lab equipment (Keithley sourcemeter, laser control, temperature sensors), stages them into Parquet format, builds experiment histories, and generates publication-quality scientific plots.

**Key Technologies:** Python 3.11+, Polars (NOT pandas), Pydantic v2+, Typer + Rich CLI, Matplotlib + scienceplots, Numba (accelerated fitting)

## Environment Setup

```bash
source .venv/bin/activate
pip install -e .              # Editable install, registers `biotite` command
pip install -e ".[dev]"       # Include pytest
pip install -e ".[jupyter]"   # Include Jupyter/IPython
```

## Entry Points

The package provides one console entry point via `pyproject.toml`:

| Command | Entry point | Description |
|---|---|---|
| `biotite` | `src.cli.main:main` | Typer CLI (data processing, plotting, validation) |

## Essential Commands

```bash
# Full pipeline: staging + history generation
biotite full-pipeline

# Staging and history
biotite stage-all              # CSV -> Parquet
biotite build-all-histories     # Manifest -> chip histories
biotite derive-all-metrics      # Extract CNP, photoresponse, etc.
biotite enrich-history 75       # Join derived metrics into history

# Viewing data
biotite show-history 67 --proc IVg --light dark
biotite show-history 67 --format json  # Also: csv, table

# Plotting (all follow: plot-{type} CHIP --seq N,N,N or --auto)
biotite plot-its 67 --seq 52,57,58
biotite plot-ivg 67 --auto
biotite plot-its 67 --seq 52,57 --conductance --absolute

# Batch plotting from YAML config
biotite batch-plot config/batch_plots/alisson67_plots.yaml

# Validation
biotite validate-manifest
biotite list-plugins
```

### Testing

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/test_config.py::test_function_name -v
python3 -c "from src.cli.main import app; print('CLI imports OK')"
```

## Architecture

### Data Flow (4 stages)

```
data/01_raw/          Raw CSVs from lab equipment
    |                 Named: {ChipGroup}{ChipNumber}_{FileIndex}.csv
    v                 CSV has #Parameters:, #Metadata:, #Data: sections
data/02_stage/
  raw_measurements/   Parquet files by procedure type
  _manifest/          manifest.parquet (one row per measurement, source of truth)
  chip_histories/     Per-chip Parquet with sequential experiment numbers
    |                 Includes parquet_path column pointing to staged data
    v
data/03_derived/
  _metrics/           metrics.parquet (CNP, photoresponse, relaxation times)
  chip_histories_enriched/  Histories + derived metric columns
```

### Module Structure

- **`src/core/`** - Staging pipeline, schema validation, history builder, pipeline orchestration, utilities
  - `utils.py`: `read_measurement_parquet()` -- the single function all plotting code uses to load data
  - `pipeline.py`: Formal pipeline builder with error handling, rollback, checkpointing
  - `history_detection.py`: `load_chip_history()` for picking enriched vs. plain history
- **`src/models/`** - Pydantic schemas (manifest rows, staging params)
- **`src/plotting/`** - One module per plot type (its, ivg, vvg, vt, transconductance, cnp_time, photoresponse, laser_calibration, plus `*_presets`, `its_relaxation_*`, `consecutive_sweep_diff`, `overlays`, `ivg_by_sample`). `transforms.py` for resistance/conductance conversions
- **`src/derived/`** - Metric extraction pipeline. Extractors in `extractors/` are auto-discovered via `registry.py`. Numba-accelerated algorithms in `algorithms/`
- **`src/cli/`** - Typer CLI with plugin auto-discovery (`@cli_command` decorator). Commands in `commands/` are auto-registered
- **`scripts/`** - Ad-hoc per-paper analysis scripts (cross-chip overlays, photoresponse comparisons). See `scripts/CATALOG.md`. When writing new ones, use the `photoresponse-analysis` skill.
- **`pyproject.toml`** - Package config with the `biotite` entry point

### Configuration Files

- **`config/procedures.yml`** - Schema definitions for all measurement procedures. Modify this to add new procedures (no Python changes needed). See `docs/guides/ADDING_PROCEDURES.md`
- **`config/chip_params.yaml`** - Chip metadata, global defaults (timezone: `America/Santiago`, workers: 6)
- **`config/cli_plugins.yaml`** - Enable/disable CLI command groups
- **`config/batch_plots/`** - YAML configs for batch plot generation
- **`config/pipelines/`** - Pipeline presets (`full-pipeline.yml`, `quick-staging.yml`, `chip-specific.yml`)

## Critical Rules

### Always Use Polars, Never pandas
Different API: `.filter()` not `.query()`, `.select()` not `[]`. See `src/core/utils.py` for patterns.

### Parquet is Source of Truth
Never read CSV files directly in new code. Use `read_measurement_parquet()` from `src/core/utils.py`. History Parquet files contain `parquet_path` pointing to staged data.

### Plotting Style
- **NO GRIDS** -- never call `plt.grid(True)` or `ax.grid(True)`
- Use `PlotConfig` for output paths (chip-first hierarchy: `figs/Encap81/It/Dark_It/`)
- Use data procedure names (`procedure="It"`), not plotting aliases (`procedure="ITS"`)
- Only create output directories during save (`create_dirs=True` on `config.get_output_path()`)
- Auto-detect illumination subcategories from metadata (`has_light` -> subfolder)
- **Default output format is PDF** (`PlotConfig.format = "pdf"`). `get_output_path` only appends an extension when the caller's filename has no suffix -- pass `"foo.png"` to force PNG.
- `set_plot_style(theme_or_config)` is polymorphic: accepts a theme name string OR a `PlotConfig`. Pass the config to get `palette`, `font_family`, `font_weight`, `legend_*`, and `show_grid` wired into rcParams.
- Add a new palette -> register it in `src/plotting/shared/styles.py::PALETTES` and add to `PlotConfig.palette` Literal. Add a new font family -> register the matplotlib name in `styles.py::_FONT_FAMILY_NAMES` and add to `PlotConfig.font_family` Literal. Bundled fonts: drop any `.ttf` under `assets/` (recursive); auto-registered via `_register_bundled_fonts`.
- Forward a new field CLIConfig->PlotConfig: add an `Optional[T] = None` field on `CLIConfig` (prefix `plot_`) and one row in `PlotConfig._CLI_OVERRIDE_FIELDS`. None means "use PlotConfig default" -- avoids drift.

### Resistance/Conductance Transforms
- `--resistance` flag on VVg/Vt plots (R = V/I, requires `ids_v` in metadata)
- `--conductance` flag on IVg/It plots (G = I/V, requires `vds_v` in metadata)
- `--absolute` for unsigned values. Filename suffixes: `_R` or `_G`
- Implementation in `src/plotting/transforms.py`

## Development Patterns

### Adding a CLI Command

Create file in `src/cli/commands/` with `@cli_command` decorator -- auto-discovered, no `main.py` changes:

```python
from src.cli.plugin_system import cli_command
import typer

@cli_command(name="my-command", group="plotting", description="Brief description")
def my_command(chip_number: int = typer.Argument(..., help="Chip number")):
    """Docstring."""
    pass
```

### Adding a Plot Type

1. Create `src/plotting/my_proc.py` using `read_measurement_parquet()` to load data
2. Create `src/cli/commands/plot_my_proc.py` with `@cli_command`
3. Reference implementations: `src/plotting/its.py` (time-series), `src/plotting/ivg.py` (sweeps)
4. See `docs/guides/PLOTTING_IMPLEMENTATION_GUIDE.md` for templates
5. Tests that call `set_plot_style` should use the `_restore_rcparams` autouse fixture pattern from `tests/test_set_plot_style_config.py` -- snapshots/restores `mpl.rcParams` per test (theme application leaks otherwise).

### Adding a Derived Metric Extractor

1. Create `src/derived/extractors/my_metric.py` with `@register_extractor` class
2. Import in `extractors/__init__.py` for auto-discovery
3. For CPU-heavy work, use Numba `@jit(nopython=True)` with NumPy arrays (not Polars)
4. See `docs/guides/ADDING_NEW_METRICS_GUIDE.md`

### Adding a New Procedure Type

1. Add schema to `config/procedures.yml` (Parameters, Metadata, Data sections with types)
2. Run staging -- pipeline auto-validates. No Python changes needed

### Modifying Data Schema

1. Update `src/models/manifest.py` (Pydantic model)
2. Bump `schema_version`
3. Handle migrations for existing fields
4. Validate: `biotite validate-manifest`

## Key Concepts

- **Run IDs**: Deterministic `SHA1(normalized_path|timestamp_utc)[:16]` for idempotent staging
- **Light detection**: Laser voltage < 0.1V = dark, >= 0.1V = light; fallback to VL column
- **Timezone**: Raw timestamps are Unix epoch, localized to `America/Santiago`, stored as UTC
- **Config priority**: CLI flags > config file > env vars (`CLI_*` prefix) > defaults
- **Sequential > parallel** for metric extraction (Parquet I/O is fast; parallel overhead dominates)
- **Measurement column names**: IVg/Vt sweeps use `Vg (V)` (lowercase g), not `VG (V)`. Time-series It uses `I (A)`, `t (s)`, `VL (V)`.

## Legacy (Do Not Use)

`parse-all`, `chip-histories`, `src/core/parser.py`, `src/core/timeline.py` are deprecated. Always use the modern pipeline: `stage-all` -> `build-all-histories` -> `derive-all-metrics`.
