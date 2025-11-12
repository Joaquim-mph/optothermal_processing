# Dark vs Illuminated It Measurements

This guide explains the difference between dark and illuminated It measurements, and how the plotting commands handle them.

## Overview

The pipeline supports two types of It (current vs time) measurements:

1. **Dark It** - No laser illumination during the entire measurement
2. **Illuminated ITS** - Laser cycles ON/OFF during measurement

## Key Differences

### Dark It Measurements
- **Laser voltage**: 0.0 V (LED completely off)
- **Purpose**: Measure dark current relaxation, drift, or baseline stability
- **Relaxation fit**: Applied to the entire measurement
- **Flag**: `has_light = false` in chip history

### Illuminated ITS Measurements
- **Laser voltage**: > 0.0 V (LED cycles ON and OFF)
- **Purpose**: Measure photoresponse buildup and decay
- **Relaxation fit**: Applied to the dark segment AFTER LED turns off
- **Flag**: `has_light = true` in chip history

## Example: Chip 81

```
Total It measurements: 158
├── Dark (has_light = false):     53 measurements
└── Illuminated (has_light = true): 105 measurements
```

## Plotting Behavior

### Default: `--dark-only` (Recommended)

**Both plotting commands default to dark-only measurements:**

```bash
# Only plots truly dark measurements (no laser)
python3 process_and_analyze.py plot-its-relaxation 81 --auto
python3 process_and_analyze.py plot-its-relaxation-batch 81
```

**Why?**
- Dark measurements have cleaner fits (no LED transitions)
- Consistent fitting conditions across all experiments
- Easier to compare relaxation dynamics

### Including Illuminated: `--all`

```bash
# Includes both dark and illuminated measurements
python3 process_and_analyze.py plot-its-relaxation 81 --auto --all
python3 process_and_analyze.py plot-its-relaxation-batch 81 --all
```

**When to use?**
- You want to see all It measurements
- Comparing dark relaxation across different conditions
- The fit segment is in the dark period after LED OFF

## Detection Logic

The commands detect dark vs illuminated measurements using:

1. **Primary**: `has_light` column (boolean)
   - `false` → Dark measurement
   - `true` → Illuminated measurement

2. **Fallback**: `laser_voltage_v` column (float)
   - `0.0` or `null` → Dark measurement
   - `> 0.0` → Illuminated measurement

## Visual Comparison

### Dark It Measurement
```
Current
  │
  │ ████████████████████████████  ← Entire measurement is dark
  │ (Fit applied to whole trace)
  │
  └────────────────────────────────► Time
```

### Illuminated ITS Measurement
```
Current
  │     LED ON        LED OFF
  │       ┌───────┐
  │       │       │
  │ ──────┘       └──────────────  ← Fit applied only here
  │                   (dark segment)
  │
  └────────────────────────────────► Time
```

## Statistics (Example: Chip 81)

After metric extraction:

| Type | Total | With Metrics | Success Rate |
|------|-------|--------------|--------------|
| **Dark** | 53 | 43 | 81% |
| **Illuminated** | 105 | 37 | 35% |

**Why lower success for illuminated?**
- Dark segment after LED OFF might be too short
- Photoresponse might not have fully decayed
- LED transitions can introduce artifacts

## Recommendations

### For Dark Relaxation Analysis
✅ **Use default (`--dark-only`)**
- Cleaner data
- Better fit quality
- Consistent conditions

### For Photoresponse Studies
⚠️ **Consider using ITSThreePhaseFitExtractor instead**
- Fits all three phases (PRE-DARK, LIGHT, POST-DARK)
- Extracts both buildup and decay times
- Better suited for illuminated measurements

### For Complete Overview
📊 **Use `--all` flag**
- See all available data
- Compare dark vs illuminated relaxation
- Check for systematic differences

## Command Examples

### Quick Start (Dark Only)
```bash
# Extract metrics for dark measurements
python3 process_and_analyze.py derive-all-metrics --chip 81 --procedures It

# Plot only dark measurements (default)
python3 process_and_analyze.py plot-its-relaxation-batch 81

# Output: 43 plots (dark only)
```

### Including Everything
```bash
# Plot all measurements (dark + illuminated)
python3 process_and_analyze.py plot-its-relaxation-batch 81 --all

# Output: 80 plots (all with metrics)
```

### Checking What You Have
```python
import polars as pl

history = pl.read_parquet("data/02_stage/chip_histories/Alisson81_history.parquet")
its = history.filter(pl.col("proc") == "It")

# Count dark vs illuminated
dark = its.filter(pl.col("has_light") == False)
light = its.filter(pl.col("has_light") == True)

print(f"Dark: {dark.height}")
print(f"Illuminated: {light.height}")
```

## See Also

- **ITS Relaxation Plotting Guide**: `docs/ITS_RELAXATION_PLOTTING_GUIDE.md`
- **Three-Phase Fitting**: `docs/ITS_THREE_PHASE_FITTING_GUIDE.md`
- **Extractor Documentation**: `src/derived/extractors/its_relaxation_extractor.py`
