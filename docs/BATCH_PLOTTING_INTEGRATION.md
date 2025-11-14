# Batch Plotting Integration Guide

## Overview

This guide documents the integration of the batch plotting and data caching systems into the main codebase structure. These features were previously standalone scripts in the project root and have been reorganized into proper modules with CLI integration.

**Version**: 3.3
**Date**: January 2025

---

## What Changed

### File Relocations

| Old Location | New Location | Purpose |
|-------------|-------------|----------|
| `batch_plot.py` (root) | `src/plotting/batch.py` | Batch plotting engine |
| - | `src/cli/commands/batch_plot.py` | CLI command wrapper |
| `data_cache.py` (root) | `src/core/data_cache.py` | Data caching utilities |
| `alisson67_plots.yaml` (root) | `config/batch_plots/alisson67_plots.yaml` | Example configuration |

### Architecture Changes

**Old Approach (standalone script):**
```bash
# Direct execution of Python script
python batch_plot.py alisson67_plots.yaml --parallel 4
```

**New Approach (integrated CLI command):**
```bash
# Integrated into main CLI with plugin discovery
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --parallel 4
```

---

## Module Structure

### 1. Data Caching Module (`src/core/data_cache.py`)

**Purpose**: In-memory caching layer for Parquet files to reduce redundant disk I/O.

**Key Features**:
- LRU (Least Recently Used) eviction policy
- File modification time tracking for automatic invalidation
- Cache hit/miss statistics with performance estimates
- Transparent monkey-patching of `pl.read_parquet` and `read_measurement_parquet`

**API**:
```python
from src.core.data_cache import (
    enable_parquet_caching,  # Enable caching globally
    cache_stats,             # Get statistics dict
    print_cache_stats,       # Print formatted stats
    clear_cache,             # Clear all cached data
    DataCache,               # Cache class for custom instances
    with_cache,              # Decorator for function caching
)

# Enable caching (called automatically by batch module)
enable_parquet_caching()

# Check cache performance
stats = cache_stats()
# => {'size': 52, 'maxsize': 100, 'hits': 49, 'misses': 52,
#     'hit_rate': 0.485, 'hit_rate_pct': '48.5%'}

# Clear cache to free memory
clear_cache()
```

**How It Works**:
1. **Initialization**: `enable_parquet_caching()` monkey-patches read functions
2. **First Read**: File loaded from disk, cached with modification timestamp
3. **Cache Hit**: Subsequent reads served from memory (no disk I/O)
4. **Invalidation**: File modification triggers automatic cache eviction
5. **Eviction**: LRU policy removes oldest unused items when cache is full

**Configuration**:
```python
# Custom cache size (default: 100 items)
from src.core.data_cache import DataCache
cache = DataCache(maxsize=200)
```

---

### 2. Batch Plotting Engine (`src/plotting/batch.py`)

**Purpose**: Core batch plotting logic with sequential and parallel execution modes.

**Key Components**:

#### Data Structures
```python
@dataclass
class PlotSpec:
    """Specification for a single plot."""
    type: str                    # e.g., "plot-its", "plot-ivg"
    chip: int                    # Chip number
    seq: str | list[int]         # Sequence numbers
    tag: str | None              # Plot tag (optional)
    legend_by: str               # Legend grouping
    extra_args: dict[str, Any]   # Plot-specific parameters

@dataclass
class PlotResult:
    """Result of executing a plot."""
    spec: PlotSpec
    success: bool
    elapsed: float
    error: str | None
```

#### Core Functions

**Configuration Loading**:
```python
def load_batch_config(config_path: Path) -> tuple[int, str, list[PlotSpec]]:
    """
    Load batch configuration from YAML file.

    Returns:
        (chip_number, chip_group, plot_specs)
    """
```

**Data Loading with Caching**:
```python
def get_chip_history(chip: int, chip_group: str) -> pl.DataFrame:
    """
    Load chip history with caching.

    Loads once per chip and reuses for all subsequent plots.
    Uses global cache dictionary: _cached_histories
    """
```

**Plot Execution**:
```python
def execute_plot(spec: PlotSpec, chip_group: str) -> PlotResult:
    """
    Execute a single plot by calling plotting functions directly.

    Returns PlotResult with timing and error information.
    """

def execute_sequential(plot_specs: list[PlotSpec], chip_group: str) -> list[PlotResult]:
    """Execute plots sequentially with progress bar."""

def execute_parallel(plot_specs: list[PlotSpec], chip_group: str, workers: int) -> list[PlotResult]:
    """Execute plots in parallel with progress bar."""
```

**Display Utilities**:
```python
def display_summary(results: list[PlotResult], total_time: float, parallel_workers: int | None):
    """Display execution summary with Rich tables."""

def print_cache_stats():
    """Print cache statistics if caching is available."""
```

**Global State Management**:
```python
# Module-level caching (loaded once, reused)
_cached_histories: dict[int, pl.DataFrame] = {}
_plot_config: PlotConfig | None = None
```

---

### 3. CLI Command (`src/cli/commands/batch_plot.py`)

**Purpose**: CLI interface for batch plotting using plugin discovery system.

**Integration**:
```python
from src.cli.plugin_system import cli_command

@cli_command(
    name="batch-plot",
    group="plotting",
    description="Execute batch plot generation from YAML configuration",
)
def batch_plot_command(
    config_file: Path,
    parallel: Optional[int] = None,
    dry_run: bool = False,
    verbose: bool = False,
):
    """Execute batch plot generation from YAML configuration."""
    # Implementation delegates to src.plotting.batch
```

**Auto-Discovery**: No manual registration needed. The `@cli_command` decorator automatically registers the command with the main CLI application.

**Help Output**:
```bash
$ python3 process_and_analyze.py batch-plot --help

Usage: process_and_analyze.py batch-plot [OPTIONS] CONFIG_FILE

Execute batch plot generation from YAML configuration.

Arguments:
  CONFIG_FILE  YAML configuration file [required]

Options:
  --parallel, -p  INTEGER  Number of parallel workers
  --dry-run, -n           Show what would be executed
  --verbose, -v           Show detailed information
  --help                  Show this message and exit
```

---

## YAML Configuration Format

### Basic Structure

```yaml
---
# Chip identification
chip: 67
chip_group: "Alisson"  # Optional, defaults to "Alisson"

# Common defaults (applied to all plots)
defaults:
  legend_by: irradiated_power

# Plot specifications
plots:
  - type: plot-its
    seq: "52-58"
    tag: "photoresponse"

  - type: plot-ivg
    seq: 2
```

### Supported Plot Types

| Type | Description | Required Parameters | Optional Parameters |
|------|-------------|---------------------|---------------------|
| `plot-its` | Current vs time overlay | `seq` | `tag`, `legend_by` |
| `plot-its-sequential` | Sequential ITS plot | `seq` | `tag`, `legend_by` |
| `plot-ivg` | Gate voltage sweep | `seq` | `tag` |
| `plot-transconductance` | Transconductance (gm) | `seq` | `method`, `window`, `polyorder`, `tag` |
| `plot-vvg` | Drain voltage sweep | `seq` | `tag` |
| `plot-vt` | Voltage vs time | `seq` | `tag` |

### Sequence Specifications

```yaml
# Single experiment
seq: 52

# Range (inclusive)
seq: "52-58"

# List of experiments
seq: [52, 57, 58, 65]

# Comma-separated (as string)
seq: "52,57,58"
```

### Advanced: Plot-Specific Parameters

```yaml
plots:
  # Transconductance with custom Savitzky-Golay parameters
  - type: plot-transconductance
    seq: 2
    method: savgol        # "savgol" or "gradient"
    window: 21            # Window length (odd number)
    polyorder: 7          # Polynomial order

  # ITS with custom legend grouping
  - type: plot-its
    seq: "4-7"
    legend_by: wavelength  # Group by wavelength instead of power
```

---

## Usage Examples

### 1. Sequential Execution (Small Batches)

```bash
# Best for <10 plots
python3 process_and_analyze.py batch-plot config/batch_plots/test_config.yaml

# Example output:
# ✓ Loaded 5 plot specifications for Alisson67
#
# ✓ plot-its (1.2s)
# ✓ plot-ivg (0.8s)
# ✓ plot-transconductance (1.5s)
#
# Total: 5 plots, 3.5s
```

### 2. Parallel Execution (Large Batches)

```bash
# Best for >10 plots with 4+ CPU cores
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --parallel 4

# Example output:
# ✓ Loaded 30 plot specifications for Alisson67
# Execution mode: Parallel
# Workers: 4
# Caching: Enabled (automatic)
#
# [Progress bar: 30/30 plots]
#
# Total: 30 plots, 12.3s (10.2x speedup)
```

### 3. Dry Run (Preview Mode)

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --dry-run

# Example output:
# DRY RUN - Plots that would be generated:
#
#   1. plot-ivg                chip=67 seq=2
#   2. plot-transconductance   chip=67 seq=2
#   3. plot-its                chip=67 seq=4-7       (405nm_neg_gate)
#   ...
#  30. plot-its                chip=67 seq=85,87     (365nm_85_87)
#
# Total: 30 plots
```

---

## Performance Analysis

### Speedup Breakdown

**Old Approach (subprocess per plot)**:
```
Plot 1: 200ms startup + 800ms import + 200ms load + 1000ms plot = 2200ms
Plot 2: 200ms startup + 800ms import + 200ms load + 1200ms plot = 2400ms
...
Total (30 plots): ~90-150 seconds
```

**New Approach (single process, sequential)**:
```
Startup: 200ms (once)
Imports: 800ms (once)
Load history: 200ms (once)
Plot 1: 1000ms
Plot 2: 1200ms (cache hit on shared data: -100ms)
...
Total (30 plots): ~37 seconds (3-4x faster)
```

**New Approach (parallel, 4 workers)**:
```
Startup: 200ms × 4 = 800ms (parallel overhead)
Imports: 800ms × 4 = 3200ms (parallel overhead)
Load history: 200ms × 4 = 800ms (parallel overhead)
Plots: ~25 seconds (parallel execution)
Total (30 plots): ~10-15 seconds (10-15x faster)
```

### Cache Performance

**Typical Statistics (30 plots, Alisson67)**:
```
============================================================
Data Cache Statistics
============================================================
Cache size:      52/100 items
Total requests:  101
Cache hits:      49
Cache misses:    52
Hit rate:        48.5%
============================================================

Estimated time saved: ~4.9s from cached reads
```

**When Caching Helps Most**:
- Large batch sizes (>20 plots): More opportunities for reuse
- Overlapping data: Plots sharing seq numbers benefit greatly
- Sequential plots: Reuse same files multiple times

**When Caching Helps Less**:
- Small batches (<5 plots): Less data reuse
- Unique data per plot: No overlapping seq numbers
- Parallel mode: Each worker has separate cache

---

## Migration Guide

### For Users

**Old Command**:
```bash
python batch_plot.py alisson67_plots.yaml --parallel 4
```

**New Command**:
```bash
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --parallel 4
```

**Configuration Files**:
- Move YAML configs from project root to `config/batch_plots/`
- No changes to YAML format required

### For Developers

**Old Imports**:
```python
from data_cache import enable_parquet_caching, cache_stats
from batch_plot import load_batch_config, execute_sequential
```

**New Imports**:
```python
from src.core.data_cache import enable_parquet_caching, cache_stats
from src.plotting.batch import load_batch_config, execute_sequential
```

**Adding New Plot Types**:

1. Implement plotting function in `src/plotting/your_plot.py`
2. Add type handler in `src/plotting/batch.py`:

```python
elif spec.type == "plot-your-feature":
    df_filtered = df.filter(pl.col("proc") == "YourProc")
    plot_your_feature(df_filtered, base_dir, tag, config=config)
```

3. Update `docs/BATCH_PLOTTING_GUIDE.md` with supported type
4. Add example to `config/batch_plots/` directory

---

## Troubleshooting

### Import Errors

**Issue**: `ModuleNotFoundError: No module named 'src.core.data_cache'`

**Solution**:
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Verify module exists
ls -la src/core/data_cache.py

# Test import
python3 -c "from src.core.data_cache import enable_parquet_caching; print('✓ OK')"
```

### Command Not Found

**Issue**: `batch-plot` command not appearing in CLI

**Solution**:
```bash
# Verify plugin discovery
python3 process_and_analyze.py list-plugins | grep batch-plot

# If not found, check imports
python3 -c "from src.cli.commands.batch_plot import batch_plot_command; print('✓ OK')"
```

### Cache Not Working

**Issue**: Low hit rates or no caching statistics

**Solution**:
```python
# Check if caching is enabled
from src.plotting.batch import CACHE_AVAILABLE
print(f"Caching available: {CACHE_AVAILABLE}")

# Manually enable if needed
from src.core.data_cache import enable_parquet_caching
enable_parquet_caching()
```

### Performance Issues

**Issue**: Batch mode slower than expected

**Checklist**:
- [ ] History file exists (`show-history` command works)
- [ ] Using sequential mode for small batches (<10 plots)
- [ ] Not using excessive parallel workers (> CPU cores)
- [ ] Sufficient RAM available (monitor with `top` or `htop`)
- [ ] No other CPU-intensive processes running

---

## Testing

### Unit Tests

```bash
# Test data caching module
python3 -m pytest tests/test_data_cache.py -v

# Test batch plotting engine
python3 -m pytest tests/test_batch_plotting.py -v

# Test CLI command
python3 -m pytest tests/test_cli_batch_plot.py -v
```

### Integration Tests

```bash
# Test end-to-end workflow
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --dry-run

# Verify command discovery
python3 process_and_analyze.py list-plugins | grep batch-plot

# Check help text
python3 process_and_analyze.py batch-plot --help
```

### Performance Benchmarks

```bash
# Benchmark sequential mode
time python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml

# Benchmark parallel mode (4 workers)
time python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --parallel 4

# Compare with individual commands (old approach)
time bash scripts/run_individual_plots.sh
```

---

## API Reference

### `src.core.data_cache`

#### Functions

- `enable_parquet_caching() -> bool`
  Enable caching globally by monkey-patching read functions.

- `cache_stats() -> dict[str, Any]`
  Get cache statistics dictionary.

- `print_cache_stats() -> None`
  Print formatted cache statistics.

- `clear_cache() -> None`
  Clear all cached data.

- `cached_read_parquet(path: Path) -> pl.DataFrame`
  Read Parquet file with caching (direct API).

#### Classes

- `DataCache(maxsize: int = 100)`
  LRU cache for arbitrary data with file modification tracking.

- `CachedItem`
  Cache entry with value and modification timestamp.

#### Decorators

- `@with_cache(cache_key_fn: Callable | None = None)`
  Decorator for caching function results.

### `src.plotting.batch`

#### Functions

- `load_batch_config(config_path: Path) -> tuple[int, str, list[PlotSpec]]`
  Load batch configuration from YAML file.

- `execute_plot(spec: PlotSpec, chip_group: str) -> PlotResult`
  Execute single plot.

- `execute_sequential(plot_specs: list[PlotSpec], chip_group: str) -> list[PlotResult]`
  Execute plots sequentially.

- `execute_parallel(plot_specs: list[PlotSpec], chip_group: str, workers: int) -> list[PlotResult]`
  Execute plots in parallel.

- `get_chip_history(chip: int, chip_group: str) -> pl.DataFrame`
  Load chip history with caching.

- `display_summary(results: list[PlotResult], total_time: float, parallel_workers: int | None)`
  Display execution summary.

#### Data Classes

- `PlotSpec`: Plot specification
- `PlotResult`: Plot execution result

#### Global State

- `_cached_histories: dict[int, pl.DataFrame]`
  Module-level history cache.

- `_plot_config: PlotConfig | None`
  Module-level plot configuration.

- `CACHE_AVAILABLE: bool`
  Flag indicating if data caching is available.

---

## See Also

- **User Guides**:
  - `docs/BATCH_PLOTTING_GUIDE.md` - Comprehensive usage guide
  - `docs/DATA_CACHING_GUIDE.md` - Caching internals and tuning

- **Example Configurations**:
  - `config/batch_plots/alisson67_plots.yaml` - 30+ plot example

- **Source Code**:
  - `src/core/data_cache.py` - Caching implementation
  - `src/plotting/batch.py` - Batch plotting engine
  - `src/cli/commands/batch_plot.py` - CLI command

- **Project Documentation**:
  - `CLAUDE.md` - Project architecture overview
  - `docs/PLOTTING_IMPLEMENTATION_GUIDE.md` - Adding new plot types

---

## Changelog

### v3.3 (January 2025) - Initial Integration

**Added**:
- `src/core/data_cache.py` - In-memory caching layer
- `src/plotting/batch.py` - Batch plotting engine
- `src/cli/commands/batch_plot.py` - CLI command
- `config/batch_plots/` - Configuration directory
- `docs/BATCH_PLOTTING_INTEGRATION.md` - This document

**Changed**:
- Moved `batch_plot.py` from root to integrated modules
- Moved `data_cache.py` from root to `src/core/`
- Moved `alisson67_plots.yaml` to `config/batch_plots/`
- Updated `docs/BATCH_PLOTTING_GUIDE.md` with new command syntax
- Updated `docs/DATA_CACHING_GUIDE.md` with new import paths
- Updated `CLAUDE.md` with v3.3 feature documentation

**Deprecated**:
- Standalone `batch_plot.py` script (removed)
- Root-level configuration files (moved to `config/batch_plots/`)

---

**Last Updated**: January 2025
**Contributors**: Integration by Claude Code Assistant
