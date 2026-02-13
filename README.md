# Optothermal Processing

A Python-based data processing and visualization pipeline for optothermal semiconductor device characterization.

## Overview

This pipeline processes raw measurement CSV files from lab equipment (Keithley sourcemeter, laser control, temperature sensors), stages them into optimized Parquet format, builds experiment histories, and generates publication-quality scientific plots.

## Features

- **Modern Data Pipeline**: CSV → Parquet staging with schema validation
- **Experiment History Management**: Track and organize experiments by chip
- **Derived Metrics Extraction**: Automatic CNP, photoresponse, and laser power extraction
- **Publication-Quality Plotting**: ITS, IVg, VVg, CNP, photoresponse, and more with scienceplots styling
- **Parallel Processing**: Multi-core data staging and metric extraction
- **Terminal UI**: User-friendly TUI for non-technical lab users
- **Plugin Architecture**: Extensible CLI with auto-discovery of commands

## Quick Start

### Installation

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install as editable package (recommended)
pip install -e .

# Optional extras
pip install -e ".[dev]"       # Testing (pytest)
pip install -e ".[jupyter]"   # Jupyter/IPython support
```

### Basic Usage

After installation, two commands are available system-wide:

```bash
# CLI: data processing and plotting
biotite full-pipeline
biotite derive-all-metrics
biotite show-history 67
biotite plot-its 67 --seq 52,57,58
biotite plot-ivg 67 --auto
biotite plot-cnp-time 81
biotite plot-photoresponse 81 power

# TUI: interactive terminal UI for lab users
biotite-tui
```

Legacy script entry points (`python process_and_analyze.py`, `python tui_app.py`) still work for backward compatibility.

### List Available Commands

```bash
# See all available commands
biotite --help

# List plugins with metadata
biotite list-plugins

# List commands by group
biotite list-plugins --group plotting
```

### Configuration Management

The CLI supports persistent configuration via JSON config files, eliminating the need to specify paths and options repeatedly.

```bash
# Create a new configuration file
biotite config-init

# View current configuration
biotite config-show

# Use global options across all commands
biotite --verbose full-pipeline
biotite --output-dir /custom/path plot-its 67 --auto
biotite --config my-config.json stage-all
```

**Configuration Sources (priority order):**
1. Command-line arguments
2. Specified config file (`--config`)
3. Project config (`./.optothermal_cli_config.json`)
4. User config (`~/.optothermal_cli_config.json`)
5. Environment variables (`CLI_*`)
6. Built-in defaults

**Quick Start with Profiles:**

```bash
# Initialize with preset configuration
biotite config-init --profile production

# Available profiles:
#   - development: Fast iteration with low quality plots
#   - production: High quality plots for publication
#   - testing: Dry run mode for validation
#   - high_quality: Maximum quality settings
```

See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for complete configuration documentation.

## Data Flow

```
1. Raw Data (data/01_raw/)
   ├─ CSV files from lab equipment
   └─ Naming: {ChipGroup}{ChipNumber}_{FileIndex}.csv

2. Staged Data (data/02_stage/)
   ├─ Parquet files (fast, schema-validated)
   ├─ manifest.parquet (metadata index)
   └─ chip_histories/ (per-chip timelines)

3. Derived Metrics (data/03_derived/)
   ├─ metrics.parquet (CNP, photoresponse, etc.)
   └─ chip_histories_enriched/ (with metrics joined)

4. Plots (figs/)
   └─ Publication-quality PNG figures
```

## Key Commands

### Data Processing

- `full-pipeline` - Run complete pipeline (staging + histories)
- `stage-all` - Stage raw CSVs to Parquet with validation
- `build-all-histories` - Generate chip histories from manifest
- `derive-all-metrics` - Extract CNP, photoresponse, laser power (v3.0)

### History Management

- `show-history` - Display chip experiment timeline
- `build-history` - Build history for specific chip
- `enrich-history` - Add derived metrics to chip history (v3.0)

### Plotting

- `plot-its` - Current vs time overlay plots
- `plot-its-sequential` - Sequential ITS plots
- `plot-ivg` - Gate voltage sweep plots
- `plot-vvg` - Drain-source voltage vs gate voltage plots
- `plot-vt` - Voltage vs time plots
- `plot-transconductance` - Transconductance (gm = dI/dVg) plots
- `plot-cnp-time` - CNP (Dirac point) evolution over time (v3.0)
- `plot-photoresponse` - Photoresponse vs power/wavelength/gate/time (v3.0)
- `plot-laser-calibration` - Laser calibration curves (v3.0)

### Data Validation

- `validate-manifest` - Schema and quality checks
- `inspect-manifest` - Browse manifest contents
- `staging-stats` - Disk usage and statistics

## Plugin System

The CLI uses an extensible plugin architecture that makes adding new commands simple.

### Adding New Commands

1. Create your command in `src/cli/commands/`
2. Add the `@cli_command()` decorator
3. Done! No need to modify `main.py`

**Example:**

```python
# src/cli/commands/my_module.py
from src.cli.plugin_system import cli_command
import typer

@cli_command(
    name="export-csv",
    group="export",
    description="Export chip history to CSV"
)
def export_csv_command(
    chip_number: int = typer.Argument(...),
    output: Path = typer.Option(Path("export.csv"), "--output", "-o"),
):
    """Export chip history to CSV format."""
    # Your implementation here
    pass
```

The command will be automatically discovered and registered! ✨

### Command Groups

Commands are organized into groups:

- `pipeline` - Full pipeline orchestration
- `history` - History viewing and generation
- `staging` - Data staging and validation
- `plotting` - All plotting commands
- `utilities` - Helper commands

### Configuration

Control which commands are available via `config/cli_plugins.yaml`:

```yaml
# Enable all commands
enabled_groups:
  - all

# Or enable specific groups
enabled_groups:
  - pipeline
  - history
  - staging
  - plotting

# Disable specific commands
disabled_commands:
  - experimental-feature
  - beta-command
```

See [`docs/CLI_PLUGIN_SYSTEM.md`](docs/CLI_PLUGIN_SYSTEM.md) for complete documentation.

## Architecture

### Module Organization

```
src/
├── cli/                    # Command-line interface
│   ├── plugin_system.py   # Plugin discovery and registration
│   ├── commands/          # Command implementations
│   └── helpers.py         # Shared utilities
├── core/                  # Core processing logic
│   ├── stage_raw_measurements.py
│   ├── history_builder.py
│   └── utils.py
├── plotting/              # Plotting functions
│   ├── its.py
│   ├── ivg.py
│   └── transconductance.py
├── models/                # Data models (Pydantic)
│   ├── manifest.py
│   └── parameters.py
└── tui/                   # Terminal user interface
```

### Key Technologies

- **Typer** - Modern CLI framework
- **Rich** - Beautiful terminal output
- **Polars** - Fast dataframe operations
- **Pydantic** - Data validation
- **Matplotlib + scienceplots** - Publication-quality plots
- **Textual** - Terminal UI framework

## Configuration

### Procedure Schemas

Define measurement schemas in `config/procedures.yml`:

```yaml
IVg:
  Parameters:
    VG: float64
    VDS: float64
  Metadata:
    Laser wavelength: float64
  Data:
    VG: float64
    ID: float64
```

### Chip Parameters

Chip-specific settings in `config/chip_params.yaml`:

```yaml
chips:
  67:
    chip_group: Alisson
    expected_procs: [IVg, It]
    wavelengths: [365, 405, 530, 660]
```

### CLI Plugins

Control command availability in `config/cli_plugins.yaml`:

```yaml
enabled_groups:
  - all

disabled_commands: []
```

## Documentation

### Core Documentation
- **[CLAUDE.md](CLAUDE.md)** - Complete project overview and commands for AI assistants
- **[CLI_MODULE_ARCHITECTURE.md](docs/CLI_MODULE_ARCHITECTURE.md)** - CLI architecture
- **[CONFIGURATION.md](docs/CONFIGURATION.md)** - Configuration management guide
- **[PYDANTIC_ARCHITECTURE.md](docs/PYDANTIC_ARCHITECTURE.md)** - Data models

### Plugin Systems
- **[CLI_PLUGIN_SYSTEM.md](docs/CLI_PLUGIN_SYSTEM.md)** - CLI plugin system guide

### Derived Metrics (v3.0)
- **[DERIVED_METRICS_ARCHITECTURE.md](docs/DERIVED_METRICS_ARCHITECTURE.md)** - Architecture overview
- **[DERIVED_METRICS_QUICKSTART.md](docs/DERIVED_METRICS_QUICKSTART.md)** - Quick start guide
- **[ADDING_NEW_METRICS_GUIDE.md](docs/ADDING_NEW_METRICS_GUIDE.md)** - Step-by-step extractor guide
- **[CNP_EXTRACTOR_GUIDE.md](docs/CNP_EXTRACTOR_GUIDE.md)** - CNP implementation details

### Data Processing
- **[SCHEMA_VALIDATION_GUIDE.md](docs/SCHEMA_VALIDATION_GUIDE.md)** - Schema validation
- **[YAML_DRIVEN_MANIFEST.md](docs/YAML_DRIVEN_MANIFEST.md)** - Manifest generation
- **[PLOTTING_IMPLEMENTATION_GUIDE.md](docs/PLOTTING_IMPLEMENTATION_GUIDE.md)** - Plotting guide
- **[PROCEDURES.md](docs/PROCEDURES.md)** - Procedure types reference

## Examples

### Process New Data

```bash
# Stage raw CSVs to Parquet
biotite stage-all

# Generate chip histories
biotite build-all-histories

# Or do both in one step
biotite full-pipeline

# Extract derived metrics (CNP, photoresponse, laser power)
biotite derive-all-metrics
```

### Generate Plots

```bash
# ITS overlay with specific experiments
biotite plot-its 67 --seq 52,57,58

# ITS with range notation
biotite plot-its 81 --seq 89-117

# Auto-select all ITS experiments
biotite plot-its 67 --auto

# ITS with filters
biotite plot-its 67 --auto --vg -0.4

# IVg sequence plots
biotite plot-ivg 67 --seq 2,8,14

# VVg (drain-source voltage vs gate voltage)
biotite plot-vvg 67 --seq 2,8,14

# Transconductance
biotite plot-transconductance 67 --seq 2,8,14

# CNP evolution over time
biotite plot-cnp-time 81

# Photoresponse analysis
biotite plot-photoresponse 81 power
biotite plot-photoresponse 81 wavelength --vg -0.4
biotite plot-photoresponse 81 gate_voltage --wl 660
biotite plot-photoresponse 81 time
```

### View History

```bash
# Show complete history
biotite show-history 67

# Filter by procedure
biotite show-history 67 --proc IVg

# Filter by light status
biotite show-history 67 --light dark

# Show last 20 experiments
biotite show-history 67 --limit 20
```

## Development

### Adding a Plotting Command

```python
# 1. Create plotting function in src/plotting/
def plot_my_analysis(history, base_dir, plot_tag):
    # Implementation
    pass

# 2. Create CLI command in src/cli/commands/
@cli_command(name="plot-my-analysis", group="plotting")
def plot_my_analysis_command(chip_number: int, ...):
    """Generate my custom analysis plots."""
    # Load history, call plotting function
    pass

# 3. Done! Command auto-discovered
```

### Adding a Derived Metric Extractor

```python
# 1. Create extractor in src/derived/extractors/
from src.derived.registry import register_extractor
from src.derived.models import DerivedMetric

@register_extractor
class MyMetricExtractor:
    procedures = ["IVg"]  # Which procedures to process

    def extract(self, measurement, metadata):
        # Extract metric from measurement data
        return [DerivedMetric(...)]

# 2. Done! Auto-discovered by derive-all-metrics
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Test CLI imports
python -c "from src.cli.main import app; print('OK')"

# Test command discovery
biotite --help

# Validate manifest
biotite validate-manifest

# Test metric extraction (dry run)
biotite derive-all-metrics --dry-run
```

## Contributing

Contributions welcome! The plugin system makes it easy to add new commands without modifying core files.

1. Fork the repository
2. Create your feature branch
3. Add your command using `@cli_command()` decorator
4. Test with `biotite --help`
5. Submit a pull request

See [CLI_PLUGIN_SYSTEM.md](docs/CLI_PLUGIN_SYSTEM.md) for plugin development guide.

## License

See LICENSE file for details.

## Contact

For questions or support, please open an issue on GitHub.
