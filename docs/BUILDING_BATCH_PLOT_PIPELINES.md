# Building Batch Plot Pipelines: A Step-by-Step Guide

**Version**: 3.3 | **Tutorial Level**: Beginner to Advanced

This guide teaches you how to build your own batch plotting pipelines from scratch. Follow along with examples and build up from simple to complex configurations.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Your First Batch Plot](#your-first-batch-plot)
3. [Understanding YAML Structure](#understanding-yaml-structure)
4. [Building Common Pipelines](#building-common-pipelines)
5. [Advanced Techniques](#advanced-techniques)
6. [Optimization Strategies](#optimization-strategies)
7. [Troubleshooting](#troubleshooting)
8. [Real-World Examples](#real-world-examples)

---

## Prerequisites

### Before You Start

✅ **Required**:
1. Data has been staged: `python3 process_and_analyze.py stage-all`
2. Chip histories exist: `python3 process_and_analyze.py build-all-histories`
3. You know your chip number (e.g., 67, 81, 75)
4. Virtual environment is activated: `source .venv/bin/activate`

✅ **Recommended**:
- Familiarity with basic plotting commands
- Understanding of your experimental procedures (IVg, ITS, etc.)
- Text editor for YAML files (VS Code, nano, vim, etc.)

### Verify Your Setup

```bash
# 1. Check that chip history exists
python3 process_and_analyze.py show-history 67

# 2. Verify batch-plot command is available
python3 process_and_analyze.py batch-plot --help

# 3. Check example configuration
cat config/batch_plots/alisson67_plots.yaml
```

---

## Your First Batch Plot

### Step 1: Create a Simple Configuration

Let's start with the simplest possible batch plot - a single IVg plot.

**Create file**: `config/batch_plots/my_first_batch.yaml`

```yaml
chip: 67

plots:
  - type: plot-ivg
    seq: 2
```

**That's it!** Just 5 lines.

### Step 2: Test with Dry Run

Before executing, preview what will happen:

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/my_first_batch.yaml --dry-run
```

**Expected output**:
```
DRY RUN - Plots that would be generated:

  1. plot-ivg                chip=67 seq=2

Total: 1 plots
```

### Step 3: Execute Your First Batch

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/my_first_batch.yaml
```

**Expected output**:
```
✓ Loaded 1 plot specifications for Alisson67

Execution mode: Sequential
Caching: Enabled (automatic)

✓ plot-ivg (0.8s)

Total plots: 1
Successful: 1
Total time: 0.8s
```

🎉 **Congratulations!** You've run your first batch plot!

---

## Understanding YAML Structure

### Basic Anatomy

Every batch plot configuration has three sections:

```yaml
# ============================================================
# SECTION 1: CHIP IDENTIFICATION
# ============================================================
chip: 67                    # Required: Your chip number
chip_group: "Alisson"       # Optional: Defaults to "Alisson"

# ============================================================
# SECTION 2: DEFAULTS (Optional)
# ============================================================
defaults:
  legend_by: irradiated_power  # Applied to all plots

# ============================================================
# SECTION 3: PLOTS LIST
# ============================================================
plots:
  - type: plot-its          # First plot
    seq: "52-58"
    tag: "photoresponse"

  - type: plot-ivg          # Second plot
    seq: 2
```

### YAML Syntax Rules

⚠️ **Important YAML gotchas**:

1. **Indentation matters** (use 2 spaces, NOT tabs):
   ```yaml
   # ✅ CORRECT
   plots:
     - type: plot-its
       seq: 2

   # ❌ WRONG (missing indentation)
   plots:
   - type: plot-its
   seq: 2
   ```

2. **Strings with special characters need quotes**:
   ```yaml
   # ✅ CORRECT
   seq: "52-58"           # Range needs quotes
   tag: "405nm_test"      # Underscores are fine

   # ❌ WRONG (will be interpreted as math)
   seq: 52-58
   ```

3. **Lists use hyphens**:
   ```yaml
   # List of numbers
   seq: [52, 57, 58]

   # Or as a string
   seq: "52,57,58"

   # List of plots
   plots:
     - type: plot-its    # First item
       seq: 2
     - type: plot-ivg    # Second item
       seq: 3
   ```

### Testing Your YAML Syntax

```bash
# Dry run will catch syntax errors
python3 process_and_analyze.py batch-plot config/batch_plots/test.yaml --dry-run

# Or use a YAML validator
python3 -c "import yaml; yaml.safe_load(open('config/batch_plots/test.yaml'))"
```

---

## Building Common Pipelines

### Pipeline 1: Basic Chip Characterization

**Goal**: Generate standard characterization plots (IVg + transconductance).

**File**: `config/batch_plots/characterization.yaml`

```yaml
chip: 67
chip_group: "Alisson"

defaults:
  legend_by: irradiated_power

plots:
  # Step 1: Gate voltage sweep
  - type: plot-ivg
    seq: 2
    tag: "baseline_ivg"

  # Step 2: Transconductance analysis
  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7
    tag: "transconductance"
```

**Run it**:
```bash
python3 process_and_analyze.py batch-plot config/batch_plots/characterization.yaml
```

**What you get**:
- `figs/Alisson67/IVg/baseline_ivg_IVg.png`
- `figs/Alisson67/IVg/transconductance_transconductance.png`

---

### Pipeline 2: Photoresponse Analysis

**Goal**: Analyze photoresponse at different wavelengths.

**Step-by-Step Build**:

#### Step 1: Find Your Experiments

First, identify which experiments you want to plot:

```bash
# View all experiments for chip 67
python3 process_and_analyze.py show-history 67

# Filter for ITS (photoresponse) experiments
python3 process_and_analyze.py show-history 67 --proc It | grep "365"

# Example output:
# seq  procedure  wavelength  vg      start_time
# 52   It         365        -0.4     2024-10-15 14:20
# 57   It         365        -0.4     2024-10-15 15:10
# 58   It         365        -0.4     2024-10-15 15:45
```

#### Step 2: Build Configuration (Modern Way) 🆕

**File**: `config/batch_plots/photoresponse_365nm.yaml`

```yaml
chip: 67

defaults:
  legend_by: irradiated_power

plots:
  # NEW: Unified ITS suite (generates overlay, sequential, AND photoresponse!)
  - type: plot-its-suite
    seq: "52-58"
    tag: "365nm_analysis"
```

**Generates 3 plots**:
1. Overlay plot (all experiments on one plot)
2. Sequential plot (separate panels for each)
3. Photoresponse vs power plot

#### Step 2 (Alternative): Build Configuration (Individual Plots)

If you want more control, use individual plot types:

```yaml
chip: 67

defaults:
  legend_by: irradiated_power

plots:
  # Overlay plot (all experiments on one plot)
  - type: plot-its
    seq: "52-58"
    tag: "365nm_overlay"

  # Sequential plot (separate panels for each)
  - type: plot-its-sequential
    seq: "52-58"
    tag: "365nm_sequential"
```

#### Step 3: Run and Verify

```bash
# Preview first
python3 process_and_analyze.py batch-plot config/batch_plots/photoresponse_365nm.yaml --dry-run

# Execute
python3 process_and_analyze.py batch-plot config/batch_plots/photoresponse_365nm.yaml
```

#### Step 4: Expand to Multiple Wavelengths (Modern Way) 🆕

Use `plot-its-suite` for concise configuration:

```yaml
chip: 67

defaults:
  legend_by: irradiated_power

plots:
  # 405 nm - generates 3 plots
  - type: plot-its-suite
    seq: "4-7"
    tag: "405nm"

  # 385 nm - generates 3 plots
  - type: plot-its-suite
    seq: "27-30"
    tag: "385nm"

  # 365 nm - generates 3 plots
  - type: plot-its-suite
    seq: "52-58"
    tag: "365nm"
```

**Result**: 9 plots from 3 entries!

#### Step 4 (Alternative): Expand to Multiple Wavelengths (Individual)

Using individual plot types:

```yaml
chip: 67

defaults:
  legend_by: irradiated_power

plots:
  # 405 nm
  - type: plot-its
    seq: "4-7"
    tag: "405nm_photoresponse"

  # 385 nm
  - type: plot-its
    seq: "27-30"
    tag: "385nm_photoresponse"

  # 365 nm
  - type: plot-its
    seq: "52-58"
    tag: "365nm_photoresponse"
```

---

### Pipeline 3: Gate Voltage Sweep

**Goal**: Compare photoresponse at different gate voltages.

**File**: `config/batch_plots/gate_sweep.yaml`

```yaml
chip: 67

defaults:
  legend_by: vg  # Group by gate voltage instead of power

plots:
  # Negative gate voltages
  - type: plot-its
    seq: "4-7,9-12,15-18"  # Multiple ranges
    tag: "negative_gate"

  # Positive gate voltages
  - type: plot-its
    seq: "21-24"
    tag: "positive_gate"

  # CNP region (near 0V)
  - type: plot-its
    seq: "57-60"
    tag: "cnp_region"
```

**Alternative: Group by power**:

```yaml
chip: 67

plots:
  # Low power
  - type: plot-its
    seq: [4, 9, 15, 21]  # First of each series
    tag: "low_power"
    legend_by: vg

  # High power
  - type: plot-its
    seq: [7, 12, 18, 24]  # Last of each series
    tag: "high_power"
    legend_by: vg
```

---

### Pipeline 4: Complete Chip Analysis

**Goal**: Generate all plots for a chip (30+ plots).

**Strategy**: Organize by analysis type.

**File**: `config/batch_plots/complete_chip67.yaml`

```yaml
chip: 67
chip_group: "Alisson"

defaults:
  legend_by: irradiated_power

plots:
  # ====================================
  # SECTION 1: CHARACTERIZATION
  # ====================================

  - type: plot-ivg
    seq: 2
    tag: "baseline"

  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7

  # ====================================
  # SECTION 2: 405 nm PHOTORESPONSE
  # ====================================

  - type: plot-its
    seq: "4-7"
    tag: "405nm_neg_gate"

  - type: plot-its-sequential
    seq: "4-7"
    tag: "405nm_neg_gate_seq"

  - type: plot-its
    seq: "9-12"
    tag: "405nm_neg_gate_2"

  - type: plot-its
    seq: "21-24"
    tag: "405nm_pos_gate"

  # ====================================
  # SECTION 3: 385 nm PHOTORESPONSE
  # ====================================

  - type: plot-its
    seq: "27-30"
    tag: "385nm_neg_gate"

  - type: plot-its
    seq: "32-35"
    tag: "385nm_pos_gate"

  # ====================================
  # SECTION 4: 365 nm PHOTORESPONSE
  # ====================================

  - type: plot-its
    seq: "38-44"
    tag: "365nm_full_range"

  - type: plot-its
    seq: "57-60"
    tag: "365nm_cnp_region"

  # Special: Same power, different responses
  - type: plot-its
    seq: [38, 41, 52, 57, 65]
    tag: "365nm_power_comparison"
```

**Run with parallel execution**:

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/complete_chip67.yaml --parallel 4
```

---

## Advanced Techniques

### Technique 1: Custom Plot Parameters

Some plot types accept additional parameters:

#### Transconductance Methods

```yaml
plots:
  # Method 1: Simple gradient
  - type: plot-transconductance
    seq: 2
    method: gradient
    tag: "gm_gradient"

  # Method 2: Savitzky-Golay filter (smoother)
  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21      # Must be odd number
    polyorder: 7    # Polynomial order
    tag: "gm_savgol"

  # Method 3: Aggressive smoothing
  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 31      # Larger window = more smoothing
    polyorder: 5
    tag: "gm_smooth"
```

#### ITS Legend Grouping

```yaml
plots:
  # Group by irradiated power (default)
  - type: plot-its
    seq: "4-7"
    legend_by: irradiated_power

  # Group by wavelength
  - type: plot-its
    seq: "4-7,27-30,38-44"
    legend_by: wavelength

  # Group by gate voltage
  - type: plot-its
    seq: "4-7,21-24"
    legend_by: vg

  # Group by LED voltage (raw control)
  - type: plot-its
    seq: "4-7"
    legend_by: led_voltage

  # Group by timestamp
  - type: plot-its
    seq: "4-7"
    legend_by: datetime
```

---

### Technique 2: Organizing Large Configurations

For complex pipelines, use YAML comments for organization:

```yaml
chip: 67
chip_group: "Alisson"

# Global settings
defaults:
  legend_by: irradiated_power

plots:
  # ===========================================================================
  # BASELINE CHARACTERIZATION (Seq 1-3)
  # ===========================================================================
  # Purpose: Establish device baseline before photoresponse measurements
  # Date: 2024-10-15 morning

  - type: plot-ivg
    seq: 2
    tag: "baseline_ivg"

  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7

  # ===========================================================================
  # UV PHOTORESPONSE SWEEP (Seq 4-44)
  # ===========================================================================
  # Purpose: Map photoresponse across UV wavelengths (405, 385, 365 nm)
  # Date: 2024-10-15 afternoon

  # --- 405 nm Series ---

  - type: plot-its
    seq: "4-7"
    tag: "405nm_vg_neg04"  # Vg = -0.4V

  # --- 385 nm Series ---

  - type: plot-its
    seq: "27-30"
    tag: "385nm_vg_neg04"

  # --- 365 nm Series ---

  - type: plot-its
    seq: "38-44"
    tag: "365nm_full"
```

---

### Technique 3: Conditional Plots

Build different configurations for different analysis stages:

#### Development Configuration

**File**: `config/batch_plots/dev_chip67.yaml`

```yaml
# Quick check configuration (few plots for fast iteration)
chip: 67

plots:
  - type: plot-ivg
    seq: 2

  - type: plot-its
    seq: "4-7"
    tag: "test_405nm"
```

#### Production Configuration

**File**: `config/batch_plots/prod_chip67.yaml`

```yaml
# Full analysis configuration (all plots)
chip: 67

defaults:
  legend_by: irradiated_power

plots:
  # ... 30+ plots here ...
```

**Usage**:
```bash
# Development (fast, 2 plots)
python3 process_and_analyze.py batch-plot config/batch_plots/dev_chip67.yaml

# Production (comprehensive, 30+ plots)
python3 process_and_analyze.py batch-plot config/batch_plots/prod_chip67.yaml --parallel 4
```

---

### Technique 4: Reusable Templates

Create template files and copy them for new chips:

**Template**: `config/batch_plots/_template_characterization.yaml`

```yaml
# TEMPLATE: Chip Characterization Pipeline
# USAGE: Copy this file and replace CHIP_NUMBER and sequences
#
# cp config/batch_plots/_template_characterization.yaml \
#    config/batch_plots/chip75_characterization.yaml

chip: CHIP_NUMBER  # <-- REPLACE THIS
chip_group: "Alisson"

defaults:
  legend_by: irradiated_power

plots:
  # Baseline IVg (adjust seq as needed)
  - type: plot-ivg
    seq: 2  # <-- REPLACE WITH YOUR SEQ

  # Transconductance
  - type: plot-transconductance
    seq: 2  # <-- REPLACE WITH YOUR SEQ
    method: savgol
    window: 21
    polyorder: 7

  # Photoresponse (adjust seq ranges)
  - type: plot-its
    seq: "4-10"  # <-- REPLACE WITH YOUR RANGE
    tag: "photoresponse"
```

**Create new configuration**:
```bash
# Copy template
cp config/batch_plots/_template_characterization.yaml \
   config/batch_plots/chip75_characterization.yaml

# Edit with your sequences
nano config/batch_plots/chip75_characterization.yaml

# Update chip number and sequences, then run
python3 process_and_analyze.py batch-plot config/batch_plots/chip75_characterization.yaml
```

---

## Optimization Strategies

### Strategy 1: Sequential vs Parallel

#### Use Sequential When:

✅ Small batches (<10 plots)
✅ Simple plots (IVg, transconductance)
✅ Limited CPU cores (1-2 cores)
✅ Memory constrained (<8 GB RAM)

```bash
# Sequential (default)
python3 process_and_analyze.py batch-plot config/batch_plots/small_batch.yaml
```

#### Use Parallel When:

✅ Large batches (>10 plots)
✅ Complex plots (ITS with many points)
✅ Multi-core CPUs (4+ cores)
✅ Sufficient RAM (>8 GB)

```bash
# Parallel with 4 workers
python3 process_and_analyze.py batch-plot config/batch_plots/large_batch.yaml --parallel 4
```

#### Optimal Worker Count

```bash
# macOS: Detect cores
CORES=$(sysctl -n hw.ncpu)
WORKERS=$((CORES - 1))  # Leave 1 core free

# Linux: Detect cores
CORES=$(nproc)
WORKERS=$((CORES - 1))

# Run with optimal workers
python3 process_and_analyze.py batch-plot config/batch_plots/my_plots.yaml --parallel $WORKERS
```

---

### Strategy 2: Plot Organization

#### Group by Analysis Type

```yaml
# ✅ GOOD: Organized by analysis purpose
plots:
  # Characterization plots
  - type: plot-ivg
    seq: 2

  # Photoresponse plots
  - type: plot-its
    seq: "4-7"
    tag: "405nm"

  - type: plot-its
    seq: "27-30"
    tag: "385nm"
```

#### Group by Execution Speed

```yaml
# ✅ GOOD: Fast plots first (quick feedback)
plots:
  # Fast plots (~1s each)
  - type: plot-ivg
    seq: 2

  - type: plot-transconductance
    seq: 2

  # Slow plots (~3-5s each)
  - type: plot-its-sequential
    seq: "4-24"  # Many panels
```

---

### Strategy 3: Incremental Development

Build your pipeline incrementally:

#### Iteration 1: Single Plot

```yaml
chip: 67
plots:
  - type: plot-ivg
    seq: 2
```

Run: `python3 process_and_analyze.py batch-plot config/batch_plots/test.yaml --dry-run`

#### Iteration 2: Add Similar Plots

```yaml
chip: 67
plots:
  - type: plot-ivg
    seq: 2

  - type: plot-transconductance  # Similar to IVg
    seq: 2
```

Run: `python3 process_and_analyze.py batch-plot config/batch_plots/test.yaml`

#### Iteration 3: Expand to Full Pipeline

```yaml
chip: 67
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-ivg
    seq: 2

  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21

  - type: plot-its
    seq: "4-7"
    tag: "405nm"
```

Run: `python3 process_and_analyze.py batch-plot config/batch_plots/test.yaml --parallel 2`

---

## Troubleshooting

### Problem 1: "No experiments found for seq"

**Error**:
```
ValueError: No experiments found for seq=999
```

**Cause**: Sequence number doesn't exist in chip history.

**Solution**:
```bash
# Check what sequences are available
python3 process_and_analyze.py show-history 67

# Filter by procedure
python3 process_and_analyze.py show-history 67 --proc ITS

# Update your YAML with correct sequences
```

---

### Problem 2: YAML Syntax Error

**Error**:
```
yaml.scanner.ScannerError: mapping values are not allowed here
```

**Common causes**:

❌ **Missing quotes around ranges**:
```yaml
seq: 4-7  # Wrong
seq: "4-7"  # Correct
```

❌ **Inconsistent indentation**:
```yaml
plots:
- type: plot-its  # Wrong (missing indentation)
  seq: 2

plots:
  - type: plot-its  # Correct
    seq: 2
```

❌ **Tabs instead of spaces**:
```yaml
plots:
→   - type: plot-its  # Wrong (tab character)

plots:
  - type: plot-its    # Correct (2 spaces)
```

**Solution**: Validate YAML syntax
```bash
python3 -c "import yaml; yaml.safe_load(open('config/batch_plots/test.yaml'))"
```

---

### Problem 3: Chip History Not Found

**Error**:
```
FileNotFoundError: Chip history file not found: data/02_stage/chip_histories/Alisson67_history.parquet
```

**Solution**:
```bash
# Build chip histories
python3 process_and_analyze.py build-all-histories

# Verify history exists
ls -la data/02_stage/chip_histories/Alisson67_history.parquet

# Check history contents
python3 process_and_analyze.py show-history 67
```

---

### Problem 4: Slow Performance

**Symptom**: Batch mode slower than expected.

**Debugging**:

```bash
# 1. Check if history exists (should be fast)
ls -la data/02_stage/chip_histories/Alisson67_history.parquet

# 2. Try sequential mode first
python3 process_and_analyze.py batch-plot config/batch_plots/test.yaml

# 3. Use fewer parallel workers
python3 process_and_analyze.py batch-plot config/batch_plots/test.yaml --parallel 2

# 4. Check system resources
top  # or htop
```

**Common fixes**:
- Use sequential for <10 plots
- Reduce parallel workers if memory constrained
- Close other applications

---

### Problem 5: Mixed Illumination Warning

**Warning**:
```
Warning: Mixed illumination experiments found (dark and light). Plot saved to root folder.
```

**Cause**: Trying to plot both dark and light experiments in the same overlay.

**Not necessarily an error!** This is expected for sequential plots showing baseline + photoresponse.

**If intentional**: Ignore the warning
**If unintentional**: Split into separate plots:

```yaml
# ❌ Mixed (dark + light)
- type: plot-its
  seq: "1-10"  # Contains both dark (1-3) and light (4-10)

# ✅ Separate
- type: plot-its
  seq: "1-3"
  tag: "dark_baseline"

- type: plot-its
  seq: "4-10"
  tag: "light_photoresponse"
```

---

## Real-World Examples

### Example 1: Daily Lab Workflow

**Scenario**: You've just collected data for chip 81. You want to quickly visualize key results.

**File**: `config/batch_plots/daily_chip81.yaml`

```yaml
chip: 81
chip_group: "Encap"

defaults:
  legend_by: irradiated_power

plots:
  # Quick characterization
  - type: plot-ivg
    seq: 2

  # Today's photoresponse measurements
  - type: plot-its
    seq: "15-20"
    tag: "todays_measurements"

  # Compare with yesterday
  - type: plot-its
    seq: [10, 15]  # Yesterday's seq 10, today's seq 15
    tag: "day_comparison"
```

**Workflow**:
```bash
# 1. Stage new data
python3 process_and_analyze.py stage-all

# 2. Update chip history
python3 process_and_analyze.py build-all-histories

# 3. Generate plots
python3 process_and_analyze.py batch-plot config/batch_plots/daily_chip81.yaml

# 4. View results
open figs/Encap81/
```

---

### Example 2: Publication Figures

**Scenario**: Preparing figures for a paper. Need high-quality, consistent plots.

**File**: `config/batch_plots/publication_chip67.yaml`

```yaml
chip: 67
chip_group: "Alisson"

defaults:
  legend_by: irradiated_power

plots:
  # Figure 1: Device characterization
  - type: plot-ivg
    seq: 2
    tag: "fig1a_transfer_curve"

  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7
    tag: "fig1b_transconductance"

  # Figure 2: Wavelength dependence
  - type: plot-its
    seq: "4-7"
    tag: "fig2a_405nm"

  - type: plot-its
    seq: "27-30"
    tag: "fig2b_385nm"

  - type: plot-its
    seq: "38-44"
    tag: "fig2c_365nm"

  # Figure 3: Gate voltage dependence
  - type: plot-its
    seq: "4-7,21-24"  # Negative and positive Vg
    tag: "fig3_gate_dependence"
    legend_by: vg
```

**Workflow**:
```bash
# Generate all publication figures
python3 process_and_analyze.py batch-plot config/batch_plots/publication_chip67.yaml --parallel 4

# Figures saved with descriptive names
ls figs/Alisson67/*/fig*
```

---

### Example 3: Comparative Analysis

**Scenario**: Comparing photoresponse across multiple chips.

**Strategy**: Create separate configurations for each chip, then run them all.

**File 1**: `config/batch_plots/compare_chip67.yaml`
```yaml
chip: 67
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-its
    seq: "38-44"
    tag: "chip67_365nm"
```

**File 2**: `config/batch_plots/compare_chip75.yaml`
```yaml
chip: 75
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-its
    seq: "10-15"  # Equivalent experiments on chip 75
    tag: "chip75_365nm"
```

**File 3**: `config/batch_plots/compare_chip81.yaml`
```yaml
chip: 81
chip_group: "Encap"
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-its
    seq: "20-25"  # Equivalent experiments on chip 81
    tag: "chip81_365nm"
```

**Workflow**:
```bash
# Generate all comparison plots
python3 process_and_analyze.py batch-plot config/batch_plots/compare_chip67.yaml
python3 process_and_analyze.py batch-plot config/batch_plots/compare_chip75.yaml
python3 process_and_analyze.py batch-plot config/batch_plots/compare_chip81.yaml

# Or run them all in sequence with a loop
for chip in 67 75 81; do
  python3 process_and_analyze.py batch-plot config/batch_plots/compare_chip${chip}.yaml
done
```

---

### Example 4: Time-Series Analysis

**Scenario**: Monitor device stability over multiple measurement sessions.

**File**: `config/batch_plots/stability_chip67.yaml`

```yaml
chip: 67

defaults:
  legend_by: datetime  # Group by measurement time

plots:
  # Morning measurements (baseline)
  - type: plot-its
    seq: [4, 9, 15]  # First measurement of each series
    tag: "morning_baseline"

  # Afternoon measurements (after UV exposure)
  - type: plot-its
    seq: [7, 12, 18]  # Last measurement of each series
    tag: "afternoon_after_exposure"

  # End of day (recovery)
  - type: plot-its
    seq: [24, 30, 35]
    tag: "evening_recovery"
```

**Shows**: Device response evolution throughout the day.

---

## Best Practices Checklist

### Before Building

- [ ] Data is staged (`stage-all` completed)
- [ ] Chip histories exist (`build-all-histories` completed)
- [ ] You know your chip number and sequences
- [ ] You have a clear analysis goal

### While Building

- [ ] Start with a simple configuration (1-2 plots)
- [ ] Test with `--dry-run` before executing
- [ ] Use meaningful tags (e.g., `"405nm_photoresponse"` not `"plot1"`)
- [ ] Add comments to organize complex configurations
- [ ] Use consistent indentation (2 spaces)
- [ ] Quote string values with special characters

### After Building

- [ ] Run `--dry-run` to verify configuration
- [ ] Execute with sequential mode first
- [ ] Check that plots are generated correctly
- [ ] Use parallel mode for large batches
- [ ] Save configuration for reuse

---

## Quick Reference

### Minimal Configuration

```yaml
chip: 67
plots:
  - type: plot-its
    seq: "4-7"
```

### Standard Configuration

```yaml
chip: 67
chip_group: "Alisson"
defaults:
  legend_by: irradiated_power

plots:
  - type: plot-its
    seq: "4-7"
    tag: "photoresponse"
```

### Complete Configuration Template

```yaml
---
# Chip identification
chip: 67
chip_group: "Alisson"

# Global defaults
defaults:
  legend_by: irradiated_power

# Plots
plots:
  # Characterization
  - type: plot-ivg
    seq: 2

  - type: plot-transconductance
    seq: 2
    method: savgol
    window: 21
    polyorder: 7

  # Photoresponse
  - type: plot-its
    seq: "4-7"
    tag: "405nm"

  - type: plot-its-sequential
    seq: "4-7"
    tag: "405nm_seq"
```

---

## Next Steps

### Learn More

- **User Guide**: [BATCH_PLOTTING_GUIDE.md](BATCH_PLOTTING_GUIDE.md) - Complete reference
- **Quick Reference**: [BATCH_PLOTTING_QUICK_REFERENCE.md](BATCH_PLOTTING_QUICK_REFERENCE.md) - Command syntax
- **Integration**: [BATCH_PLOTTING_INTEGRATION.md](BATCH_PLOTTING_INTEGRATION.md) - Technical details

### Get Help

```bash
# Command help
python3 process_and_analyze.py batch-plot --help

# View examples
cat config/batch_plots/alisson67_plots.yaml

# Validate YAML
python3 -c "import yaml; yaml.safe_load(open('config/batch_plots/my_config.yaml'))"
```

### Example Configurations

Study the included examples:
```bash
# View example configuration
cat config/batch_plots/alisson67_plots.yaml

# Copy and modify
cp config/batch_plots/alisson67_plots.yaml config/batch_plots/my_analysis.yaml
nano config/batch_plots/my_analysis.yaml
```

---

**Happy plotting!** 📊

If you have questions or run into issues, refer to the troubleshooting section or check the complete documentation in `docs/BATCH_PLOTTING_GUIDE.md`.

---

**Last Updated**: January 2025
**Author**: Optothermal Processing Team
