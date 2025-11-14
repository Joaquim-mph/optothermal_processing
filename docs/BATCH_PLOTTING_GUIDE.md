# Batch Plotting Guide

**Version 3.3** | **Complete User Guide**

## Overview

The batch plotter (`batch-plot` command) is an optimized tool for generating multiple plots from a single Python process, eliminating the overhead of spawning separate processes for each plot.

### Key Features

✨ **Performance**:
- 🚀 **3-15x faster** than individual subprocess calls
- 📦 **Single process execution** - eliminates Python startup overhead
- 🔄 **Automatic caching** - loads history once, reuses for all plots
- ⚡ **Parallel execution** - multi-worker support for large batches

✨ **Convenience**:
- 📊 **Progress tracking** - real-time progress bars with Rich
- 📝 **YAML configuration** - cleaner than bash scripts
- 🎯 **Preview mode** - dry-run to see what will be generated
- 💾 **Data caching** - LRU eviction with file modification tracking

## Performance Comparison

### Test Case: 30 Plots (Alisson67)

| Method | Time | Speedup |
|--------|------|---------|
| **Bash script** (30 separate `python` calls) | ~90-150s | 1x baseline |
| **Batch sequential** (single process) | ~37s | **3-4x faster** |
| **Batch parallel** (4 workers) | ~10-15s | **8-12x faster** |

### Why is it faster?

**Old approach (bash script):**
- 30 separate Python processes
- Each process:
  - Python interpreter startup: ~200-500ms
  - Import numpy, matplotlib, polars: ~500-1000ms
  - Load history parquet: ~100-300ms
  - Generate plot: ~100-2000ms
- **Total overhead**: ~25-55 seconds just for startup and imports!

**New approach (batch-plot command):**
- Single Python process
- Imports done once: ~1 second
- History loaded once: ~0.3 seconds
- Only plot generation time varies
- **Overhead eliminated**: ~25-55 seconds saved!

### Cache Performance

- **Hit rate**: 48-60% (typical for 30-plot batches)
- **Time saved**: ~5 seconds from cached Parquet reads
- **Memory usage**: ~200-400 MB (default 100-item cache)

## Installation

The batch plotter is already included in the project. No additional dependencies needed beyond the standard requirements.

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Verify command is available
python3 process_and_analyze.py batch-plot --help
```

## Quick Start

### 1. Create a YAML configuration file

```yaml
---
# config/batch_plots/my_plots.yaml
chip: 67
chip_group: "Alisson"  # Optional, defaults to "Alisson"

# Common parameters (optional)
defaults:
  legend_by: irradiated_power

# Plot specifications
plots:
  # IVg plot
  - type: plot-ivg
    seq: 2

  # ITS photoresponse
  - type: plot-its
    seq: "4-7"
    tag: "405nm_neg_gate"
```

### 2. Run the batch plotter

```bash
# Sequential mode (best for <10 plots)
python3 process_and_analyze.py batch-plot config/batch_plots/my_plots.yaml

# Parallel mode (best for >10 plots, 4+ core CPU)
python3 process_and_analyze.py batch-plot config/batch_plots/my_plots.yaml --parallel 4

# Dry run (preview what will be executed)
python3 process_and_analyze.py batch-plot config/batch_plots/my_plots.yaml --dry-run
```

## Configuration Format

### Supported Plot Types

| Type | Description | Required Parameters | Optional Parameters |
|------|-------------|---------------------|---------------------|
| `plot-its` | Current vs time overlay | `seq` | `tag`, `legend_by` |
| `plot-its-sequential` | Sequential ITS plot | `seq` | `tag`, `legend_by` |
| `plot-its-suite` | ITS suite (3 plots in 1) | `seq` | `tag`, `legend_by`, `photoresponse_x` |
| `plot-ivg` | Gate voltage sweep | `seq` | `tag` |
| `plot-transconductance` | Transconductance (gm) | `seq` | `method`, `window`, `polyorder`, `tag` |
| `plot-vvg` | Drain voltage sweep | `seq` | `tag` |
| `plot-vt` | Voltage vs time | `seq` | `tag` |

**See Also:** [ITS_SUITE_PLOTTING.md](ITS_SUITE_PLOTTING.md) for the unified ITS suite feature

### Sequence Specifications

The `seq` parameter supports multiple formats:

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

### Extra Parameters

Plot-specific parameters can be added directly to the plot definition:

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
    legend_by: wavelength  # "wavelength", "vg", "led_voltage", "irradiated_power", "datetime"
```

## Common Use Cases

### Use Case 1: Daily Analysis Workflow

After collecting new data, generate analysis plots in one command:

```bash
# Stage new data
python3 process_and_analyze.py stage-all

# Build histories
python3 process_and_analyze.py build-all-histories

# Generate plots (batch mode)
python3 process_and_analyze.py batch-plot config/batch_plots/daily_analysis.yaml --parallel 4
```

**Configuration:**
```yaml
# config/batch_plots/daily_analysis.yaml
chip: 67
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-ivg
    seq: 2
  - type: plot-its
    seq: "latest-10"  # Last 10 experiments
```

### Use Case 2: Chip Characterization

Standard characterization plots for device baseline:

```yaml
# config/batch_plots/characterization.yaml
chip: 67
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-ivg
    seq: 2
    tag: "baseline_ivg"

  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7
    tag: "transconductance"
```

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/characterization.yaml
```

### Use Case 3: Wavelength Scan Analysis

Compare photoresponse across different wavelengths:

```yaml
# config/batch_plots/wavelength_scan.yaml
chip: 67
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-its
    seq: "4-7"
    tag: "405nm"

  - type: plot-its
    seq: "27-30"
    tag: "385nm"

  - type: plot-its
    seq: "38-44"
    tag: "365nm"
```

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/wavelength_scan.yaml --parallel 2
```

## Performance Tips

### When to use sequential mode

- **Small batches** (<10 plots): Sequential mode has less overhead
- **Simple plots**: Fast-generating plots don't benefit much from parallelization
- **Limited CPU cores**: Single-core machines should use sequential

### When to use parallel mode

- **Large batches** (>10 plots): Parallelization overhead is amortized
- **Complex plots**: ITS sequential plots with long traces benefit greatly
- **Multi-core CPUs**: Use `--parallel 2-4` on typical 4+ core machines

### Optimal parallel worker count

```bash
# Check CPU core count
sysctl -n hw.ncpu  # macOS
nproc              # Linux

# Rule of thumb: Use cores - 1 to keep system responsive
# 4-core CPU → --parallel 2 or --parallel 3
# 8-core CPU → --parallel 4 or --parallel 6
```

### Memory considerations

Each parallel worker loads plotting libraries and data. If you have limited RAM:
- Reduce `--parallel` workers
- Use sequential mode
- Close other applications

## Examples

### Example 1: Quick test with 2 plots

```yaml
---
# test_batch.yaml
chip: 67

plots:
  - type: plot-ivg
    seq: 2

  - type: plot-its
    seq: "4-7"
    tag: "quick_test"
```

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/test_batch.yaml
```

### Example 2: Full chip analysis (30+ plots)

```yaml
---
# full_chip_67.yaml
chip: 67

defaults:
  legend_by: irradiated_power

plots:
  # IVg baseline
  - type: plot-ivg
    seq: 2

  # Transconductance
  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7

  # UV wavelength scans
  - type: plot-its
    seq: "4-7"
    tag: "405nm_neg_gate"

  - type: plot-its
    seq: "9-12"
    tag: "405nm_neg_gate_2"

  # ... more plots ...
```

```bash
# Use parallel mode for large batches
python3 process_and_analyze.py batch-plot config/batch_plots/full_chip_67.yaml --parallel 4
```

### Example 3: Wavelength comparison

```yaml
---
# wavelength_comparison.yaml
chip: 67

plots:
  # 405 nm
  - type: plot-its
    seq: "4-7"
    tag: "405nm"
    legend_by: irradiated_power

  # 385 nm
  - type: plot-its
    seq: "27-30"
    tag: "385nm"
    legend_by: irradiated_power

  # 365 nm
  - type: plot-its
    seq: "38-44"
    tag: "365nm"
    legend_by: irradiated_power
```

## Migrating from Bash Scripts

If you have an existing bash script with many `python process_and_analyze.py` calls:

### Step 1: Extract plot commands

```bash
# Example bash script line
python process_and_analyze.py plot-its 67 --seq 4-7 --legend irradiated_power
```

### Step 2: Convert to YAML

```yaml
plots:
  - type: plot-its
    seq: "4-7"
    # legend_by in defaults, so omitted here
```

### Step 3: Test with dry-run

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/converted_config.yaml --dry-run
```

### Step 4: Run and compare

```bash
# Old way
time bash run_plots.sh

# New way
time python3 process_and_analyze.py batch-plot config/batch_plots/converted_config.yaml
```

**Expected result:** 3-15x speedup depending on batch size and CPU cores!

## Troubleshooting

### Error: "Chip history file not found"

```
FileNotFoundError: Chip history file not found: data/02_stage/chip_histories/Alisson67_history.parquet
Run 'build-all-histories' command first to generate history files.
```

**Solution:**
```bash
python3 process_and_analyze.py build-all-histories
```

### Error: "No experiments found for seq"

```
ValueError: No experiments found for seq=999
```

**Solution:** Check available experiments:
```bash
python3 process_and_analyze.py show-history 67
```

### Warning: "Mixed illumination experiments"

This is normal for sequential plots with both dark and light experiments. The plot is saved to the procedure root folder.

### Performance not as expected

If batch mode is slower than expected:
1. Check if history file exists (avoids repeated generation)
2. Verify you're using sequential mode for small batches
3. Use `--parallel` only for large batches (>10 plots)
4. Close other applications to free up memory

### Quick Verification

```bash
# Verify command is available
python3 process_and_analyze.py list-plugins | grep batch-plot

# Test imports
python3 -c "from src.core.data_cache import enable_parquet_caching; print('✓ OK')"
python3 -c "from src.plotting.batch import load_batch_config; print('✓ OK')"

# Check configuration syntax
python3 process_and_analyze.py batch-plot config/batch_plots/my_config.yaml --dry-run
```

## Advanced Usage

### Custom chip groups

```yaml
chip: 81
chip_group: "Encap"  # Use different chip naming

plots:
  - type: plot-its
    seq: "1-10"
```

### Mixing plot types

```yaml
plots:
  # Characterization
  - type: plot-ivg
    seq: 2

  # Photoresponse
  - type: plot-its
    seq: "10-20"
    tag: "photoresponse_sweep"

  # Time series
  - type: plot-vt
    seq: "30-35"
```

### Parallel execution with custom workers

```bash
# Auto-detect cores and use cores-1 (Linux)
python3 process_and_analyze.py batch-plot config/batch_plots/config.yaml --parallel $(( $(nproc) - 1 ))

# Or on macOS
python3 process_and_analyze.py batch-plot config/batch_plots/config.yaml --parallel $(( $(sysctl -n hw.ncpu) - 1 ))
```

## See Also

### User Documentation
- **[BATCH_PLOTTING_QUICK_REFERENCE.md](BATCH_PLOTTING_QUICK_REFERENCE.md)** - Quick command reference and YAML templates
- **[ITS_SUITE_PLOTTING.md](ITS_SUITE_PLOTTING.md)** - Unified ITS suite (3 plots in 1 command)
- **[DATA_CACHING_GUIDE.md](DATA_CACHING_GUIDE.md)** - Caching internals and performance tuning
- **[BUILDING_BATCH_PLOT_PIPELINES.md](BUILDING_BATCH_PLOT_PIPELINES.md)** - Step-by-step tutorial for building pipelines

### Developer Documentation
- **[BATCH_PLOTTING_INTEGRATION.md](BATCH_PLOTTING_INTEGRATION.md)** - Integration architecture and API reference
- **[PLOTTING_IMPLEMENTATION_GUIDE.md](guides/PLOTTING_IMPLEMENTATION_GUIDE.md)** - Adding new plot types

### Examples & Source Code
- `config/batch_plots/alisson67_plots.yaml` - Example configuration with 30+ plots
- `src/plotting/batch.py` - Batch plotting engine implementation
- `src/core/data_cache.py` - Data caching utilities
- `src/cli/commands/batch_plot.py` - CLI command implementation

### Architecture
- **[CLAUDE.md](../CLAUDE.md)** - Project architecture overview (includes v3.3 batch plotting features)

---

**Last Updated**: January 2025
**Version**: 3.3
**Maintainers**: Optothermal Processing Team
