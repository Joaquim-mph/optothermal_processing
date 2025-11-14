# ITS Suite Quick Start: Power Legends Workflow

**Problem**: No power values in plot legends? Here's the fix!

---

## The Issue

When you run batch plotting without enriched history, you'll see:

```
⚠  Using standard history (enriched not found)
   → Power legends may not show. Run: enrich-history 67
```

**Result**: Legends show LED voltage (e.g., "2.5V") instead of calibrated power (e.g., "1.2 mW").

---

## The Solution (One-Time Setup)

Run these commands **once per chip** to get power legends:

```bash
# Step 1: Extract metrics including laser calibration power matching
python3 process_and_analyze.py derive-all-metrics --calibrations

# Step 2: Enrich chip history with power data
python3 process_and_analyze.py enrich-history 67  # Replace 67 with your chip number

# Or enrich all chips at once
python3 process_and_analyze.py enrich-history -a
```

**What this does**:
1. Finds all laser calibration curves in your data
2. Matches each light experiment with the nearest calibration (same day, same wavelength)
3. Interpolates irradiated power from LED voltage using calibration data
4. Adds `irradiated_power_w` column to chip history
5. Saves enriched history to `data/03_derived/chip_histories_enriched/`

**Time**: ~30 seconds for typical chip with 100 experiments

---

## Complete Workflow

### First Time (Setup)

```bash
# 1. Stage your data
python3 process_and_analyze.py stage-all

# 2. Build chip histories
python3 process_and_analyze.py build-all-histories

# 3. Extract metrics with calibrations
python3 process_and_analyze.py derive-all-metrics --calibrations

# 4. Enrich history with power data
python3 process_and_analyze.py enrich-history -a
```

### After Setup (Regular Use)

```bash
# Just run batch plotting - it automatically uses enriched history!
python3 process_and_analyze.py batch-plot config/batch_plots/my_config.yaml --parallel 4
```

**You'll see**:
```
✓ Using enriched history (with calibrated power)
✓ Loaded 150 experiments in 0.12s
```

**Legends now show**: "1.2 mW", "2.5 mW", "5.0 mW" instead of "2.5V", "3.0V", "3.5V"

---

## Quick Test

Create this minimal config to test:

**File**: `config/batch_plots/test_power_legends.yaml`

```yaml
chip: 67
plots:
  - type: plot-its-suite
    seq: "4-7"  # Any ITS photoresponse sequence
    tag: "test_power"
```

**Run it**:
```bash
python3 process_and_analyze.py batch-plot config/batch_plots/test_power_legends.yaml
```

**Check the plots**:
```bash
# Overlay plot - check if legends show power values
open figs/Alisson67/It/Light_It/test_power_It.png

# Sequential plot - check if panel titles show power
open figs/Alisson67/It/Light_It/test_power_seq_It.png

# Photoresponse plot - X-axis should be power
open figs/Alisson67/It/Light_It/encap67_ITS_photoresponse_vs_power_test_power_photoresponse.png
```

---

## Automatic Behavior

The batch plotter **automatically**:

1. **Tries enriched history first**
   - Location: `data/03_derived/chip_histories_enriched/Alisson67_history.parquet`
   - Shows: `✓ Using enriched history (with calibrated power)`

2. **Falls back to standard history** if enriched not found
   - Location: `data/02_stage/chip_histories/Alisson67_history.parquet`
   - Shows: `⚠ Using standard history (enriched not found)`
   - Warning: `→ Power legends may not show. Run: enrich-history 67`

3. **Plots still work** without enrichment
   - ✅ All 3 plots generate
   - ⚠️ Legends just show voltage instead of power
   - 💡 Easy fix: Run enrichment commands above

---

## Verification

### Check if Enriched History Exists

```bash
# Check for enriched history file
ls -lh data/03_derived/chip_histories_enriched/Alisson67_history.parquet

# If it exists, check the power column
python3 -c "import polars as pl; h = pl.read_parquet('data/03_derived/chip_histories_enriched/Alisson67_history.parquet'); print('irradiated_power_w' in h.columns)"

# Should print: True
```

### Check Power Values

```bash
# View enriched history with power
python3 process_and_analyze.py show-history 67 --proc It --light light --format table | head -20

# Look for 'irradiated_power_w' column with values like 0.0012 (1.2 mW)
```

---

## Troubleshooting

### "No calibration found"

**Issue**: `derive-all-metrics --calibrations` reports "No laser calibrations found"

**Cause**: No `LaserCalibration` procedures in your data

**Solution**:
1. Check if you have calibration data:
   ```bash
   python3 process_and_analyze.py show-history 67 --proc LaserCalibration
   ```
2. If empty, you need to perform laser calibration experiments
3. Or skip calibrations and use LED voltage for legends (less precise)

### "Enrichment failed"

**Issue**: `enrich-history` command fails

**Cause**: Usually missing metrics or bad data

**Solution**:
```bash
# Re-run metrics extraction
python3 process_and_analyze.py derive-all-metrics --force --calibrations

# Try enrichment again
python3 process_and_analyze.py enrich-history 67 --verbose
```

### "Still showing voltage in legends"

**Issue**: After enrichment, legends still show voltage

**Possible causes**:
1. Old enriched history cached
2. Batch plot loaded wrong history

**Solution**:
```bash
# Clear cache and re-run
rm -rf data/03_derived/chip_histories_enriched/Alisson67_history.parquet
python3 process_and_analyze.py derive-all-metrics --calibrations
python3 process_and_analyze.py enrich-history 67
python3 process_and_analyze.py batch-plot config/batch_plots/test_power_legends.yaml
```

---

## What Gets Updated

### Before Enrichment

**Standard History** (`data/02_stage/chip_histories/Alisson67_history.parquet`):
- ✅ Has: `led_voltage`, `wavelength_nm`, `vg`, etc.
- ❌ Missing: `irradiated_power_w` (calibrated power)
- Result: Legends show "2.5V"

### After Enrichment

**Enriched History** (`data/03_derived/chip_histories_enriched/Alisson67_history.parquet`):
- ✅ Has: All standard columns PLUS
- ✅ Has: `irradiated_power_w` (calibrated power in watts)
- ✅ Has: `calibration_run_id` (which calibration was used)
- ✅ Has: `delta_current` (photoresponse metrics if extracted)
- Result: Legends show "1.2 mW" (converted from watts)

---

## Summary Commands

### One-Time Setup (Per Chip)

```bash
# Get power legends (run once)
python3 process_and_analyze.py derive-all-metrics --calibrations && \
python3 process_and_analyze.py enrich-history 67
```

### Regular Use (Daily Workflow)

```bash
# Just batch plot - uses enriched history automatically!
python3 process_and_analyze.py batch-plot config/batch_plots/my_analysis.yaml --parallel 4
```

---

## See Also

- **Complete Guide**: [ITS_SUITE_PLOTTING.md](ITS_SUITE_PLOTTING.md)
- **Tutorial**: [BUILDING_BATCH_PLOT_PIPELINES.md](BUILDING_BATCH_PLOT_PIPELINES.md)
- **Main Docs**: [../CLAUDE.md](../CLAUDE.md#derived-metrics-pipeline-new-in-v30)

---

**Last Updated**: January 2025
**Quick Fix**: `derive-all-metrics --calibrations && enrich-history 67`
