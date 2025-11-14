# Analysis Workflow Improvements for Alisson67

## Current Workflow Analysis

Your current bash script (`bash/run_alisson67_plots.sh`) runs **34 separate plotting commands** with significant repetition. The pattern shows systematic power-series measurements at different wavelengths and gate voltages:

### Identified Experiment Groups

| Wavelength | Gate Voltage | Sequences | Purpose |
|------------|-------------|-----------|---------|
| 455nm | -0.35V | 4-7 | Power series (4 points) |
| 455nm | +0.2V | 9-12 | Power series (4 points) |
| 405nm | -0.35V | 15-18 | Power series (4 points) |
| 405nm | +0.2V | 21-24 | Power series (4 points) |
| 385nm | -0.4V | 27-30 | Power series (4 points) |
| 385nm | +0.2V | 32-35 | Power series (4 points) |
| 365nm | -0.4V | 38-39 | Power series (2 points) |
| 365nm | -0.4V | 41-44 | Power series (4 points, includes IVg) |
| 365nm | +0.2V | 46-49 | Power series (4 points) |
| 365nm | -0.4V | 57-60 | Power series (4 points, repeat) |

### Issues with Current Approach

1. **High repetition**: Each group runs both `plot-its` AND `plot-its-sequential` with identical parameters
2. **Manual sequence management**: Hard-coded sequence numbers prone to errors
3. **No automation**: Difficult to apply same analysis to other chips
4. **Comment mismatches**: Script comments say "405nm" but sequences 4-7 are actually 455nm
5. **Mixed concerns**: Some plots are exploratory (comparing same power), others are systematic (power series)

---

## Recommended Approaches (Best to Good)

### ✅ **Approach 1: Auto-Filtering (RECOMMENDED)**

Use `--auto` flag with filters to automatically select experiments by metadata. No manual sequence numbers!

```bash
#!/bin/bash

# Single command per wavelength/gate combination
# The pipeline automatically finds all matching experiments and sorts by power

# 455nm wavelength
python3 process_and_analyze.py plot-its 67 --auto --wl 455 --vg -0.35 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 455 --vg 0.2 --legend irradiated_power

# 405nm wavelength
python3 process_and_analyze.py plot-its 67 --auto --wl 405 --vg -0.35 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 405 --vg 0.2 --legend irradiated_power

# 385nm wavelength
python3 process_and_analyze.py plot-its 67 --auto --wl 385 --vg -0.4 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 385 --vg 0.2 --legend irradiated_power

# 365nm wavelength
python3 process_and_analyze.py plot-its 67 --auto --wl 365 --vg -0.4 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 365 --vg 0.2 --legend irradiated_power

# IVg and transconductance (initial characterization)
python3 process_and_analyze.py plot-ivg 67 --auto
python3 process_and_analyze.py plot-transconductance 67 --auto --method savgol --window 21 --polyorder 7
```

**Benefits:**
- **34 commands → 10 commands** (70% reduction)
- No hard-coded sequence numbers
- Works across date ranges automatically
- Self-documenting (filters show intent)
- Easy to apply to other chips: just change `67` to `75`

---

### ✅ **Approach 2: Photoresponse Analysis Commands**

Use the new **derived metrics** commands specifically designed for power/wavelength analysis:

```bash
#!/bin/bash

# Generate comprehensive photoresponse plots
# These automatically group by wavelength and gate voltage

# Photoresponse vs power (for each wavelength, separate by gate voltage)
python3 process_and_analyze.py plot-photoresponse 67 power --vg -0.35
python3 process_and_analyze.py plot-photoresponse 67 power --vg -0.4
python3 process_and_analyze.py plot-photoresponse 67 power --vg 0.2

# Photoresponse vs wavelength (for each power level)
python3 process_and_analyze.py plot-photoresponse 67 wavelength --vg -0.35
python3 process_and_analyze.py plot-photoresponse 67 wavelength --vg -0.4
python3 process_and_analyze.py plot-photoresponse 67 wavelength --vg 0.2

# Photoresponse vs gate voltage (for each wavelength)
python3 process_and_analyze.py plot-photoresponse 67 gate_voltage --wl 455
python3 process_and_analyze.py plot-photoresponse 67 gate_voltage --wl 405
python3 process_and_analyze.py plot-photoresponse 67 gate_voltage --wl 385
python3 process_and_analyze.py plot-photoresponse 67 gate_voltage --wl 365

# Photoresponse evolution over time (degradation studies)
python3 process_and_analyze.py plot-photoresponse 67 time

# CNP evolution over time
python3 process_and_analyze.py plot-cnp-time 67
```

**Benefits:**
- **Scientifically meaningful plots**: Directly shows photoresponse trends
- **Automatic grouping**: No need to manually organize experiments
- **Multi-dimensional analysis**: Power, wavelength, gate voltage, and time
- **Publication-ready**: Includes error bars, fits, and proper formatting

---

### ✅ **Approach 3: Batch Plotting with Loop**

Automate repetitive commands using shell loops:

```bash
#!/bin/bash

# Define wavelengths and gate voltages
WAVELENGTHS=(455 405 385 365)
GATE_VOLTAGES=(-0.35 -0.4 0.2)

# Loop through all combinations
for wl in "${WAVELENGTHS[@]}"; do
    for vg in "${GATE_VOLTAGES[@]}"; do
        echo "Plotting: λ=${wl}nm, Vg=${vg}V"
        python3 process_and_analyze.py plot-its 67 \
            --auto \
            --wl "$wl" \
            --vg "$vg" \
            --legend irradiated_power
    done
done

# IVg characterization
python3 process_and_analyze.py plot-ivg 67 --auto
python3 process_and_analyze.py plot-transconductance 67 --auto \
    --method savgol --window 21 --polyorder 7
```

**Benefits:**
- **Easy to modify**: Change wavelengths/voltages in one place
- **Scalable**: Add new parameters without duplicating code
- **Clear structure**: Loop makes systematic approach explicit

---

### ✅ **Approach 4: Preset-Based Configuration**

Create reusable presets for common analysis patterns (requires adding custom preset):

```bash
#!/bin/bash

# Create preset configuration file: config/plot_presets/alisson67_power_series.yaml
# (See example below)

# Single command generates all plots
python3 process_and_analyze.py plot-its 67 --preset power_series_all
```

**Example Preset File** (`config/plot_presets/alisson67_power_series.yaml`):
```yaml
power_series_all:
  description: "Systematic power series at all wavelengths and gate voltages"
  groups:
    - filters:
        wavelength_nm: 455
        vg_fixed_v: -0.35
      legend: irradiated_power
      tag: "455nm_negVg"

    - filters:
        wavelength_nm: 455
        vg_fixed_v: 0.2
      legend: irradiated_power
      tag: "455nm_posVg"

    - filters:
        wavelength_nm: 405
        vg_fixed_v: -0.35
      legend: irradiated_power
      tag: "405nm_negVg"

    # ... etc for other combinations
```

**Benefits:**
- **Reusable**: Save analysis workflow for future experiments
- **Version controlled**: Track changes to analysis approach
- **Shareable**: Team members can use same presets
- **Self-documenting**: Preset file describes analysis intent

---

### ⚠️ **Approach 5: Keep Current Approach (NOT RECOMMENDED)**

If you must keep manual sequence numbers, at least improve the script:

```bash
#!/bin/bash

# Add variables for common parameters
CHIP=67
LEGEND="--legend irradiated_power"
TRANSCOND_PARAMS="--method savgol --window 21 --polyorder 7"

# Group related plots with clear comments
echo "=== Initial Characterization ==="
python3 process_and_analyze.py plot-ivg $CHIP --seq 2
python3 process_and_analyze.py plot-transconductance $CHIP --seq 2 $TRANSCOND_PARAMS

echo "=== 455nm Power Series ==="
# Negative gate (-0.35V)
python3 process_and_analyze.py plot-its $CHIP --seq 4-7 $LEGEND
# Positive gate (+0.2V)
python3 process_and_analyze.py plot-its $CHIP --seq 9-12 $LEGEND

echo "=== 405nm Power Series ==="
# Negative gate (-0.35V)
python3 process_and_analyze.py plot-its $CHIP --seq 15-18 $LEGEND
# Positive gate (+0.2V)
python3 process_and_analyze.py plot-its $CHIP --seq 21-24 $LEGEND

# ... etc
```

**Why avoid this:**
- Still brittle (sequence numbers change with new data)
- Doesn't scale to other chips
- High maintenance burden

---

## Implementation Recommendations

### For Your Current Analysis (Chip 67)

**Use Approach 1 + 2 combination:**

1. **Create `bash/alisson67_analysis_v2.sh`:**
```bash
#!/bin/bash
set -e  # Exit on error

CHIP=67

echo "=== Alisson67 Photoresponse Analysis ==="

# Initial characterization
echo "Generating IVg and transconductance plots..."
python3 process_and_analyze.py plot-ivg $CHIP --auto
python3 process_and_analyze.py plot-transconductance $CHIP --auto --method savgol --window 21 --polyorder 7

# CNP evolution
echo "Analyzing CNP evolution..."
python3 process_and_analyze.py plot-cnp-time $CHIP

# Photoresponse analysis (comprehensive)
echo "Generating photoresponse plots..."
python3 process_and_analyze.py plot-photoresponse $CHIP power
python3 process_and_analyze.py plot-photoresponse $CHIP wavelength
python3 process_and_analyze.py plot-photoresponse $CHIP gate_voltage
python3 process_and_analyze.py plot-photoresponse $CHIP time

# Individual power series (for detailed inspection)
echo "Generating detailed ITS plots by wavelength..."
for wl in 455 405 385 365; do
    for vg in -0.35 -0.4 0.2; do
        python3 process_and_analyze.py plot-its $CHIP --auto --wl $wl --vg $vg --legend irradiated_power || true
    done
done

echo "✓ Analysis complete! Check figs/Alisson$CHIP/"
```

2. **Run it:**
```bash
chmod +x bash/alisson67_analysis_v2.sh
./bash/alisson67_analysis_v2.sh
```

### For Future Chips

**Create a generic analysis script:**

```bash
#!/bin/bash
# Usage: ./bash/analyze_chip.sh 75

CHIP=$1

if [ -z "$CHIP" ]; then
    echo "Usage: $0 <chip_number>"
    exit 1
fi

echo "=== Analyzing Chip $CHIP ==="

# Run standard analysis pipeline
python3 process_and_analyze.py plot-ivg $CHIP --auto
python3 process_and_analyze.py plot-cnp-time $CHIP
python3 process_and_analyze.py plot-photoresponse $CHIP power
python3 process_and_analyze.py plot-photoresponse $CHIP wavelength
python3 process_and_analyze.py plot-photoresponse $CHIP gate_voltage

# Auto-generate ITS plots for all wavelength/gate combinations
python3 -c "
import polars as pl
from pathlib import Path

# Load history
history = pl.read_parquet('data/02_stage/chip_histories/Alisson${CHIP}_history.parquet')

# Filter for It measurements with light
its = history.filter((pl.col('procedure') == 'It') & (pl.col('has_light') == True))

# Get unique wavelength/gate combinations
groups = its.select(['wavelength_nm', 'vg_fixed_v']).unique()

# Generate plot commands
for row in groups.iter_rows(named=True):
    wl = row['wavelength_nm']
    vg = row['vg_fixed_v']
    print(f'python3 process_and_analyze.py plot-its $CHIP --auto --wl {wl} --vg {vg} --legend irradiated_power')
" | bash

echo "✓ Analysis complete!"
```

---

## Migration Path

### Step 1: Validate New Approach
Run both old and new scripts, compare outputs:
```bash
# Run old script
./bash/run_alisson67_plots.sh

# Run new script
./bash/alisson67_analysis_v2.sh

# Compare outputs (should be nearly identical, but new version has better organization)
ls -lh figs/Alisson67/
```

### Step 2: Adopt for New Chips
Use the generic script for chips 75, 81, etc.:
```bash
./bash/analyze_chip.sh 75
./bash/analyze_chip.sh 81
```

### Step 3: Build Pipeline Integration (Future)
Add a CLI command for standardized analysis:
```bash
# Future enhancement
python3 process_and_analyze.py analyze-chip 67 --suite photoresponse
```

---

## Expected Results

**Current approach:**
- 34 commands
- ~2-3 minutes runtime
- Hard to modify/reuse
- Prone to errors (wrong comments, missed experiments)

**Recommended approach:**
- 10-15 commands
- ~1-2 minutes runtime (fewer redundant operations)
- Easy to modify (change filters, not sequences)
- Works across chips automatically
- Self-documenting code

---

## Summary

**Your current workflow is doing systematic power-series analysis at multiple wavelengths and gate voltages.**

**Best solution:** Use `--auto` filtering with photoresponse analysis commands (Approach 1 + 2).

**Why it's better:**
- **70% fewer commands** (34 → 10)
- **No manual sequence numbers** (robust to data changes)
- **Scientifically meaningful outputs** (photoresponse vs power/wavelength/gate)
- **Reusable across chips** (just change chip number)
- **Publication-ready figures** automatically

**Next steps:**
1. Review the proposed `alisson67_analysis_v2.sh` script above
2. Test it on chip 67 to validate outputs
3. Apply to other chips (75, 81)
4. Consider adding custom presets for your specific analysis patterns
