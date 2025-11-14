# ITS Suite Plotting: Unified ITS Analysis

**Version**: 3.3+ | **Feature**: `plot-its-suite`

## Overview

The `plot-its-suite` plot type is a **unified command** that generates three common ITS plots with a single configuration entry, eliminating repetition in your batch plot configurations.

## Prerequisites

### For Power Legends

To get **power values in legends** (recommended for photoresponse analysis):

```bash
# 1. Extract metrics (including calibration power matching)
python3 process_and_analyze.py derive-all-metrics --calibrations

# 2. Enrich chip history with power data
python3 process_and_analyze.py enrich-history 67  # Replace 67 with your chip number

# Or enrich all chips at once
python3 process_and_analyze.py enrich-history -a
```

**What this does**:
- Matches light experiments with nearest laser calibration curves
- Interpolates irradiated power from LED voltage and calibration data
- Adds `irradiated_power_w` column to history for power legends

### Without Enriched History

The batch plotter will still work, but:
- ⚠️ Power legends will show LED voltage instead of calibrated power
- 💡 You'll see a warning: `"Using standard history (enriched not found)"`
- ✅ All three plots still generate (just legends show voltage, not power)

**To fix**: Run the enrichment commands above.

### What It Does

One `plot-its-suite` entry generates:
1. **ITS Overlay** - All experiments overlaid on one plot
2. **ITS Sequential** - Each experiment in a separate panel
3. **Photoresponse vs Power** - Delta current as a function of irradiated power

### Before and After

#### ❌ Old Way (3 separate entries)

```yaml
plots:
  # 405 nm photoresponse
  - type: plot-its
    seq: "4-7"
    tag: "405nm_neg_gate"

  - type: plot-its-sequential
    seq: "4-7"
    tag: "405nm_neg_gate_seq"

  - type: plot-its-photoresponse
    seq: "4-7"
    tag: "405nm_photoresponse"
    x_axis: power
```

#### ✅ New Way (1 unified entry)

```yaml
plots:
  # 405 nm photoresponse - all plots at once
  - type: plot-its-suite
    seq: "4-7"
    tag: "405nm_neg_gate"
```

**Result**: Same 3 plots, 66% less configuration!

---

## Basic Usage

### Minimal Configuration

```yaml
chip: 67

plots:
  - type: plot-its-suite
    seq: "4-7"
    tag: "405nm_photoresponse"
```

**Generates**:
- `figs/Alisson67/It/Light_It/405nm_photoresponse_It.png` (overlay)
- `figs/Alisson67/It/Light_It/405nm_photoresponse_seq_It.png` (sequential)
- `figs/Alisson67/It/Light_It/encap67_ITS_photoresponse_vs_power_405nm_photoresponse_photoresponse.png`

### Standard Configuration

```yaml
chip: 67
chip_group: "Alisson"

defaults:
  legend_by: irradiated_power

plots:
  - type: plot-its-suite
    seq: "4-7"
    tag: "405nm_neg_gate"
```

---

## Advanced Features

### Custom Photoresponse X-Axis

By default, photoresponse is plotted vs **power**. You can change this:

```yaml
plots:
  # Photoresponse vs wavelength
  - type: plot-its-suite
    seq: "4-44"
    tag: "wavelength_scan"
    photoresponse_x: wavelength

  # Photoresponse vs time (chronological)
  - type: plot-its-suite
    seq: "4-20"
    tag: "time_evolution"
    photoresponse_x: time

  # Photoresponse vs gate voltage
  - type: plot-its-suite
    seq: "4-7,21-24"
    tag: "gate_sweep"
    photoresponse_x: gate_voltage
```

**Options for `photoresponse_x`**:
- `power` (default) - Irradiated power
- `wavelength` - Laser wavelength
- `time` - Measurement timestamp
- `gate_voltage` - Gate voltage (Vg)

### Filters

Apply filters to the photoresponse plot:

```yaml
plots:
  # Filter to specific wavelength
  - type: plot-its-suite
    seq: "4-44"
    tag: "405nm_only"
    filter_wavelength: 405

  # Filter to specific gate voltage
  - type: plot-its-suite
    seq: "4-24"
    tag: "vg_neg04"
    filter_vg: -0.4

  # Combine filters
  - type: plot-its-suite
    seq: "4-44"
    tag: "405nm_vg_neg04"
    filter_wavelength: 405
    filter_vg: -0.4
```

### Custom Legend Grouping

Control how the overlay plot groups experiments:

```yaml
plots:
  # Group by power (default)
  - type: plot-its-suite
    seq: "4-7"
    tag: "by_power"
    legend_by: irradiated_power

  # Group by wavelength
  - type: plot-its-suite
    seq: "4-7,27-30,38-44"
    tag: "by_wavelength"
    legend_by: wavelength

  # Group by gate voltage
  - type: plot-its-suite
    seq: "4-7,21-24"
    tag: "by_vg"
    legend_by: vg
```

### Axis Scaling

Control photoresponse plot axis scaling:

```yaml
plots:
  # Linear scale (default)
  - type: plot-its-suite
    seq: "4-7"
    tag: "linear"

  # Log-log scale
  - type: plot-its-suite
    seq: "4-7"
    tag: "loglog"
    axtype: loglog

  # Semi-log X
  - type: plot-its-suite
    seq: "4-7"
    tag: "semilogx"
    axtype: semilogx

  # Semi-log Y
  - type: plot-its-suite
    seq: "4-7"
    tag: "semilogy"
    axtype: semilogy
```

---

## Complete Example

### Full-Featured Configuration

```yaml
chip: 67
chip_group: "Alisson"

defaults:
  legend_by: irradiated_power

plots:
  # 405 nm: All three plots with power dependence
  - type: plot-its-suite
    seq: "4-7"
    tag: "405nm_neg_gate"
    photoresponse_x: power
    filter_wavelength: 405

  # 385 nm: Wavelength comparison
  - type: plot-its-suite
    seq: "27-30"
    tag: "385nm_neg_gate"
    photoresponse_x: power
    filter_wavelength: 385

  # 365 nm: Time evolution
  - type: plot-its-suite
    seq: "38-44"
    tag: "365nm_evolution"
    photoresponse_x: time

  # Gate sweep: Vg dependence
  - type: plot-its-suite
    seq: "4-7,21-24"
    tag: "gate_dependence"
    photoresponse_x: gate_voltage
    legend_by: vg
    filter_wavelength: 405
```

**Run it**:
```bash
python3 process_and_analyze.py batch-plot config/batch_plots/its_suite_example.yaml --parallel 2
```

**Generates**: 12 plots total (3 plots × 4 entries)

---

## Parameter Reference

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `type` | string | Must be `"plot-its-suite"` | `type: plot-its-suite` |
| `seq` | string/list | Sequence numbers to plot | `seq: "4-7"` |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tag` | string | auto-generated | Custom tag for output filenames |
| `legend_by` | string | `irradiated_power` | Legend grouping (overlay plot) |
| `photoresponse_x` | string | `power` | Photoresponse X-axis variable |
| `filter_wavelength` | float | None | Filter photoresponse to wavelength (nm) |
| `filter_vg` | float | None | Filter photoresponse to gate voltage (V) |
| `axtype` | string | `linear` | Photoresponse axis scaling |

### Legend Options

- `irradiated_power` - Group by optical power
- `wavelength` - Group by laser wavelength
- `vg` - Group by gate voltage
- `led_voltage` - Group by LED control voltage
- `datetime` - Group by measurement time

### Photoresponse X-Axis Options

- `power` - Irradiated power (W)
- `wavelength` - Laser wavelength (nm)
- `time` - Measurement timestamp
- `gate_voltage` - Gate voltage (V)

### Axis Type Options

- `linear` - Linear X and Y axes
- `loglog` - Log X and log Y axes
- `semilogx` - Log X, linear Y
- `semilogy` - Linear X, log Y

---

## When to Use

### ✅ Use `plot-its-suite` When:

- You need all three standard ITS plots (overlay, sequential, photoresponse)
- You're analyzing photoresponse experiments
- You want to reduce configuration repetition
- You're doing systematic analysis (multiple wavelengths, gate voltages, etc.)

### ❌ Use Individual Commands When:

- You only need one or two of the plots
- You need different sequence numbers for each plot type
- You want fine-grained control over each plot
- You're generating custom photoresponse plots with special requirements

---

## Output Files

### Naming Convention

Given this configuration:
```yaml
- type: plot-its-suite
  seq: "4-7"
  tag: "405nm_neg_gate"
```

**Generated files**:
1. Overlay: `figs/Alisson67/It/Light_It/405nm_neg_gate_It.png`
2. Sequential: `figs/Alisson67/It/Light_It/405nm_neg_gate_seq_It.png`
3. Photoresponse: `figs/Alisson67/It/Light_It/encap67_ITS_photoresponse_vs_power_405nm_neg_gate_photoresponse.png`

### Directory Structure

```
figs/
└── Alisson67/
    └── It/
        └── Light_It/
            ├── 405nm_neg_gate_It.png              # Overlay
            ├── 405nm_neg_gate_seq_It.png           # Sequential
            └── encap67_ITS_photoresponse_vs_power_405nm_neg_gate_photoresponse.png  # Photoresponse
```

---

## Troubleshooting

### No Power Values in Legends ⚠️

**Symptom**: Legends show LED voltage (e.g., "2.5V") instead of power (e.g., "1.2 mW").

**Cause**: Using standard history without enriched power data.

**You'll see this warning**:
```
⚠  Using standard history (enriched not found)
   → Power legends may not show. Run: enrich-history 67
```

**Solution**:
```bash
# Step 1: Extract metrics with calibration matching
python3 process_and_analyze.py derive-all-metrics --calibrations

# Step 2: Enrich history with power data
python3 process_and_analyze.py enrich-history 67

# Step 3: Re-run batch plot
python3 process_and_analyze.py batch-plot config/batch_plots/your_config.yaml
```

**What this does**:
- Matches each light experiment with nearest laser calibration
- Interpolates irradiated power from LED voltage using calibration curves
- Adds `irradiated_power_w` column to history
- Legends now show "1.2 mW" instead of "2.5V"

---

### Photoresponse Plot Not Generated

**Symptom**: Only overlay and sequential plots generated, no photoresponse plot.

**Possible causes**:
1. **No light experiments**: Photoresponse requires `has_light == True`
2. **Metrics not extracted**: Run `derive-all-metrics` first
3. **No power data**: Enriched history needed for calibrated power

**Solutions**:
```bash
# Extract metrics
python3 process_and_analyze.py derive-all-metrics --calibrations

# Enrich history with calibrations
python3 process_and_analyze.py enrich-history 67

# Check if experiments have light
python3 process_and_analyze.py show-history 67 --proc It --light light
```

### Warning: "Photoresponse plot skipped"

**Example warning**:
```
Warning: Photoresponse plot skipped for 405nm_neg_gate: No delta_current column found
```

**This is normal** if:
- You haven't run `derive-all-metrics` yet
- Your experiments are all dark (no photoresponse to measure)
- History isn't enriched with metrics

**The overlay and sequential plots will still be generated.**

### All Dark Experiments

If all experiments have `has_light == False`, only the overlay and sequential plots are generated (photoresponse requires light).

---

## Comparison: Suite vs Individual

### Performance

| Approach | Commands | Plots | Time (sequential) | Time (parallel) |
|----------|----------|-------|-------------------|-----------------|
| Individual | 3 entries | 3 plots | ~6-9 seconds | ~3-5 seconds |
| Suite | 1 entry | 3 plots | ~6-9 seconds | ~3-5 seconds |

**Performance is identical** - the suite just reduces configuration.

### Configuration Size

**10 wavelength analysis**:
- Individual: 30 plot entries (10 wavelengths × 3 plots)
- Suite: 10 plot entries (10 wavelengths × 1 suite)
- **Reduction**: 67% fewer lines

---

## Migration Guide

### From Old to New

#### Old Configuration (30 entries)

```yaml
chip: 67
plots:
  # 405 nm
  - type: plot-its
    seq: "4-7"
    tag: "405nm"
  - type: plot-its-sequential
    seq: "4-7"
    tag: "405nm_seq"
  - type: plot-its-photoresponse
    seq: "4-7"
    tag: "405nm_photoresponse"
    x_axis: power

  # 385 nm
  - type: plot-its
    seq: "27-30"
    tag: "385nm"
  - type: plot-its-sequential
    seq: "27-30"
    tag: "385nm_seq"
  - type: plot-its-photoresponse
    seq: "27-30"
    tag: "385nm_photoresponse"
    x_axis: power

  # ... 8 more wavelengths (24 more entries)
```

#### New Configuration (10 entries)

```yaml
chip: 67
defaults:
  legend_by: irradiated_power

plots:
  # 405 nm
  - type: plot-its-suite
    seq: "4-7"
    tag: "405nm"

  # 385 nm
  - type: plot-its-suite
    seq: "27-30"
    tag: "385nm"

  # ... 8 more wavelengths (8 more entries)
```

**Same output, 67% less YAML!**

---

## Best Practices

### 1. Use Descriptive Tags

✅ **Good**:
```yaml
- type: plot-its-suite
  seq: "4-7"
  tag: "405nm_vg_neg04"  # Clear what it is
```

❌ **Bad**:
```yaml
- type: plot-its-suite
  seq: "4-7"
  tag: "test1"  # Not descriptive
```

### 2. Group Related Experiments

✅ **Good**:
```yaml
# All 405 nm at different Vg
- type: plot-its-suite
  seq: "4-7,9-12,15-18"
  tag: "405nm_vg_sweep"
  legend_by: vg
```

❌ **Bad**:
```yaml
# Mixed wavelengths and conditions
- type: plot-its-suite
  seq: "4,27,38,52"
  tag: "random_mix"
```

### 3. Specify Filters for Multi-Wavelength Data

✅ **Good**:
```yaml
- type: plot-its-suite
  seq: "4-44"  # Contains multiple wavelengths
  tag: "405nm_only"
  filter_wavelength: 405  # Filter photoresponse plot
```

### 4. Use Appropriate Legend Grouping

```yaml
# Power sweep → group by power
- type: plot-its-suite
  seq: "4-7"
  tag: "power_sweep"
  legend_by: irradiated_power

# Gate sweep → group by Vg
- type: plot-its-suite
  seq: "4-7,21-24"
  tag: "gate_sweep"
  legend_by: vg

# Wavelength scan → group by wavelength
- type: plot-its-suite
  seq: "4-44"
  tag: "wavelength_scan"
  legend_by: wavelength
```

---

## Real-World Example

### Complete Chip Analysis

**File**: `config/batch_plots/chip67_its_complete.yaml`

```yaml
chip: 67
chip_group: "Alisson"

defaults:
  legend_by: irradiated_power

plots:
  # ====================================
  # 405 nm PHOTORESPONSE
  # ====================================

  # Negative gate
  - type: plot-its-suite
    seq: "4-7"
    tag: "405nm_neg_gate_series1"

  - type: plot-its-suite
    seq: "9-12"
    tag: "405nm_neg_gate_series2"

  - type: plot-its-suite
    seq: "15-18"
    tag: "405nm_neg_gate_series3"

  # Positive gate
  - type: plot-its-suite
    seq: "21-24"
    tag: "405nm_pos_gate"

  # ====================================
  # 385 nm PHOTORESPONSE
  # ====================================

  - type: plot-its-suite
    seq: "27-30"
    tag: "385nm_neg_gate"

  - type: plot-its-suite
    seq: "32-35"
    tag: "385nm_pos_gate"

  # ====================================
  # 365 nm PHOTORESPONSE
  # ====================================

  - type: plot-its-suite
    seq: "38-44"
    tag: "365nm_full_range"

  - type: plot-its-suite
    seq: "57-60"
    tag: "365nm_cnp_region"

  # ====================================
  # SPECIAL ANALYSES
  # ====================================

  # Time evolution (chronological)
  - type: plot-its-suite
    seq: "4-60"
    tag: "full_time_evolution"
    photoresponse_x: time

  # Wavelength dependence
  - type: plot-its-suite
    seq: "4-44"
    tag: "wavelength_comparison"
    photoresponse_x: wavelength
    legend_by: wavelength
```

**Run it**:
```bash
python3 process_and_analyze.py batch-plot config/batch_plots/chip67_its_complete.yaml --parallel 4
```

**Generates**: 30 plots from 10 entries (instead of 30 entries!)

---

## See Also

- **Quick Reference**: [BATCH_PLOTTING_QUICK_REFERENCE.md](BATCH_PLOTTING_QUICK_REFERENCE.md)
- **User Guide**: [BATCH_PLOTTING_GUIDE.md](BATCH_PLOTTING_GUIDE.md)
- **Tutorial**: [BUILDING_BATCH_PLOT_PIPELINES.md](BUILDING_BATCH_PLOT_PIPELINES.md)
- **Integration**: [BATCH_PLOTTING_INTEGRATION.md](BATCH_PLOTTING_INTEGRATION.md)

---

**Last Updated**: January 2025
**Feature Version**: 3.3+
