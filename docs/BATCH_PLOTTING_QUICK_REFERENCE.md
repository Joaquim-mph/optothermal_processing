# Batch Plotting Quick Reference

**Version**: 3.3 | **Last Updated**: January 2025

---

## Command Syntax

```bash
python3 process_and_analyze.py batch-plot [OPTIONS] CONFIG_FILE
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--parallel` | `-p` | Number of parallel workers | Sequential |
| `--dry-run` | `-n` | Preview without executing | False |
| `--verbose` | `-v` | Detailed execution info | False |
| `--help` | | Show help message | |

---

## Common Commands

### Basic Usage

```bash
# Sequential mode (best for <10 plots)
python3 process_and_analyze.py batch-plot config/batch_plots/my_config.yaml

# Parallel mode with 4 workers (best for >10 plots)
python3 process_and_analyze.py batch-plot config/batch_plots/my_config.yaml --parallel 4

# Preview what will be executed
python3 process_and_analyze.py batch-plot config/batch_plots/my_config.yaml --dry-run

# Get help
python3 process_and_analyze.py batch-plot --help
```

### Performance-Optimized

```bash
# Auto-detect CPU cores and use N-1 workers (macOS)
CORES=$(sysctl -n hw.ncpu)
python3 process_and_analyze.py batch-plot config/batch_plots/large_batch.yaml --parallel $((CORES - 1))

# Auto-detect CPU cores and use N-1 workers (Linux)
CORES=$(nproc)
python3 process_and_analyze.py batch-plot config/batch_plots/large_batch.yaml --parallel $((CORES - 1))
```

---

## YAML Configuration Templates

### Minimal Template

```yaml
chip: 67
plots:
  - type: plot-its
    seq: "1-10"
```

### Standard Template

```yaml
chip: 67
chip_group: "Alisson"
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-its
    seq: "52-58"
    tag: "photoresponse"

  - type: plot-ivg
    seq: 2
```

### Complete Template

```yaml
---
chip: 67
chip_group: "Alisson"
output_base: "plots/chip67"  # Optional, not currently used

defaults:
  legend_by: irradiated_power

plots:
  # IVg characterization
  - type: plot-ivg
    seq: 2

  # Transconductance with custom parameters
  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7

  # Photoresponse overlay
  - type: plot-its
    seq: "52-58"
    tag: "365nm_photoresponse"
    legend_by: irradiated_power

  # Sequential plot (separate panels)
  - type: plot-its-sequential
    seq: "52-58"
    tag: "365nm_sequential"

  # VVg sweep
  - type: plot-vvg
    seq: "10-15"

  # Voltage vs time
  - type: plot-vt
    seq: [20, 21, 22]
```

---

## Plot Type Reference

### ITS Suite (Unified ITS Analysis) 🆕

**NEW in v3.3**: Generate overlay, sequential, and photoresponse plots with one entry!

```yaml
- type: plot-its-suite
  seq: "52-58"
  tag: "405nm_photoresponse"
  legend_by: irradiated_power  # Optional
  photoresponse_x: power       # Optional: power, wavelength, time, gate_voltage
```

**Generates 3 plots**:
1. ITS overlay (all on one plot)
2. ITS sequential (separate panels)
3. Photoresponse vs power (or wavelength/time/gate_voltage)

**Prerequisites for power legends**:
```bash
# Get calibrated power values in legends
python3 process_and_analyze.py derive-all-metrics --calibrations
python3 process_and_analyze.py enrich-history 67  # Your chip number
```

**Advanced options**:
```yaml
- type: plot-its-suite
  seq: "52-58"
  tag: "405nm_analysis"
  photoresponse_x: wavelength  # X-axis for photoresponse
  filter_wavelength: 405       # Filter photoresponse data
  filter_vg: -0.4              # Filter by gate voltage
  axtype: loglog               # Axis scaling: linear, loglog, semilogx, semilogy
```

**See**: [ITS_SUITE_PLOTTING.md](ITS_SUITE_PLOTTING.md) for complete guide

---

### ITS (Current vs Time)

**Overlay Mode**:
```yaml
- type: plot-its
  seq: "52-58"           # Range or list
  tag: "photoresponse"   # Optional tag
  legend_by: irradiated_power  # Legend grouping
```

**Sequential Mode** (separate panels):
```yaml
- type: plot-its-sequential
  seq: "52-58"
  tag: "sequential_view"
```

**Legend Options**:
- `irradiated_power` (default)
- `wavelength`
- `vg`
- `led_voltage`
- `datetime`

### IVg (Gate Voltage Sweep)

```yaml
- type: plot-ivg
  seq: 2                 # Single or multiple
  tag: "characterization"  # Optional
```

### Transconductance (gm = dI/dVg)

**Gradient Method**:
```yaml
- type: plot-transconductance
  seq: 2
  method: gradient       # Simple numerical derivative
```

**Savitzky-Golay Filter**:
```yaml
- type: plot-transconductance
  seq: 2
  method: savgol         # Smoothed derivative
  window: 21             # Window length (odd number)
  polyorder: 7           # Polynomial order
```

### VVg (Drain-Source Voltage vs Gate Voltage)

```yaml
- type: plot-vvg
  seq: "10-15"
  tag: "voltage_sweep"
```

### Vt (Voltage vs Time)

```yaml
- type: plot-vt
  seq: [20, 21, 22]
  tag: "time_series"
```

---

## Sequence Specifications

### Single Experiment

```yaml
seq: 52
```

### Range (Inclusive)

```yaml
seq: "52-58"    # Experiments 52, 53, 54, 55, 56, 57, 58
```

### Explicit List

```yaml
seq: [52, 57, 58, 65]
```

### Comma-Separated String

```yaml
seq: "52,57,58,65"
```

---

## Performance Guidelines

### When to Use Sequential Mode

✅ **Best for:**
- Small batches (<10 plots)
- Fast-generating plots
- Single-core machines
- Minimal memory overhead

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/small_batch.yaml
```

### When to Use Parallel Mode

✅ **Best for:**
- Large batches (>10 plots)
- Complex plots (ITS with long traces)
- Multi-core CPUs (4+ cores)
- Maximum throughput

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/large_batch.yaml --parallel 4
```

### Optimal Worker Count

| CPU Cores | Recommended Workers | Notes |
|-----------|-------------------|-------|
| 2 cores | 1 (sequential) | Limited benefit from parallelization |
| 4 cores | 2-3 | Sweet spot for typical laptop |
| 8 cores | 4-6 | Good balance of speed and overhead |
| 16+ cores | 8-12 | Diminishing returns beyond 8 workers |

**Formula**: `workers = max(1, cpu_cores - 1)`

---

## Common Workflows

### 1. Initial Chip Characterization

```yaml
# characterization.yaml
chip: 67
defaults:
  legend_by: irradiated_power

plots:
  # Baseline IVg
  - type: plot-ivg
    seq: 2

  # Transconductance analysis
  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7
```

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/characterization.yaml
```

### 2. Wavelength Scan

```yaml
# wavelength_scan.yaml
chip: 67
defaults:
  legend_by: wavelength

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

### 3. Full Chip Analysis (30+ plots)

```bash
# Use example configuration
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --parallel 4

# Expected output:
# ✓ Loaded 30 plot specifications
# Execution mode: Parallel
# Workers: 4
# Caching: Enabled (automatic)
#
# [Progress: ████████████████████ 30/30]
#
# Total: 30 plots, 12.3s (10.2x speedup)
```

---

## Troubleshooting

### Error: "Chip history file not found"

```
FileNotFoundError: Chip history file not found: data/02_stage/chip_histories/Alisson67_history.parquet
```

**Solution**:
```bash
python3 process_and_analyze.py build-all-histories
```

### Error: "No experiments found for seq"

```
ValueError: No experiments found for seq=999
```

**Solution**: Check available experiments
```bash
python3 process_and_analyze.py show-history 67
```

### Low Performance / Slow Execution

**Checklist**:
1. ✅ History file exists (run `build-all-histories`)
2. ✅ Using sequential for small batches (<10 plots)
3. ✅ Not using excessive workers (> CPU cores)
4. ✅ Sufficient RAM available
5. ✅ No other CPU-intensive processes

### Parallel Mode Slower Than Sequential

**Possible causes**:
- Small batch size (parallelization overhead > benefit)
- Limited CPU cores
- Insufficient RAM (workers swapping to disk)

**Solution**: Use sequential mode for batches <10 plots

---

## Import Examples

### Python API

```python
from pathlib import Path
from src.plotting.batch import (
    load_batch_config,
    execute_sequential,
    execute_parallel,
    display_summary,
)
from src.core.data_cache import enable_parquet_caching, cache_stats

# Enable caching
enable_parquet_caching()

# Load configuration
config_path = Path("config/batch_plots/my_config.yaml")
chip, chip_group, plot_specs = load_batch_config(config_path)

# Execute plots
results = execute_sequential(plot_specs, chip_group)

# Display summary
import time
total_time = sum(r.elapsed for r in results)
display_summary(results, total_time, parallel_workers=None)

# Check cache performance
stats = cache_stats()
print(f"Cache hit rate: {stats['hit_rate_pct']}")
```

### Caching API

```python
from src.core.data_cache import (
    enable_parquet_caching,
    cache_stats,
    clear_cache,
    DataCache,
)

# Enable caching
enable_parquet_caching()

# Get statistics
stats = cache_stats()
print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate_pct']}")

# Clear cache
clear_cache()

# Custom cache instance
cache = DataCache(maxsize=200)
```

---

## File Locations

### Configuration Files
- `config/batch_plots/*.yaml` - Batch plot configurations
- `config/batch_plots/alisson67_plots.yaml` - Example (30+ plots)

### Source Code
- `src/plotting/batch.py` - Batch plotting engine
- `src/core/data_cache.py` - Data caching layer
- `src/cli/commands/batch_plot.py` - CLI command

### Documentation
- `docs/BATCH_PLOTTING_GUIDE.md` - Complete usage guide
- `docs/DATA_CACHING_GUIDE.md` - Caching internals
- `docs/BATCH_PLOTTING_INTEGRATION.md` - Integration details
- `docs/BATCH_PLOTTING_QUICK_REFERENCE.md` - This document

---

## Performance Metrics

### Typical Speedups (30-plot batch)

| Method | Time | Speedup | Notes |
|--------|------|---------|-------|
| Individual subprocesses | 90-150s | 1x | Baseline (old approach) |
| Batch sequential | 20-40s | **3-5x** | Single process, cached history |
| Batch parallel (4 workers) | 8-20s | **10-15x** | Parallel execution + caching |

### Cache Performance (30-plot batch)

| Metric | Typical Value |
|--------|--------------|
| Cache size | 52 items |
| Total requests | 101 |
| Cache hits | 49 (48.5%) |
| Cache misses | 52 (51.5%) |
| Time saved | ~5 seconds |

---

## See Also

- **Main Documentation**: `CLAUDE.md` - Project architecture
- **User Guides**:
  - `docs/BATCH_PLOTTING_GUIDE.md`
  - `docs/DATA_CACHING_GUIDE.md`
- **Developer Guide**: `docs/BATCH_PLOTTING_INTEGRATION.md`
- **Plotting Guide**: `docs/PLOTTING_IMPLEMENTATION_GUIDE.md`

---

**Questions?** Check the full documentation or run:
```bash
python3 process_and_analyze.py batch-plot --help
```
