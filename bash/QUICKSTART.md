# Quick Start: Improved Analysis Workflow

## 🎯 TL;DR

Your old script has **47% redundant commands**. I've created improved versions that are:
- **Shorter**: 30 → 16 commands
- **More robust**: No hard-coded sequences
- **Reusable**: Works for any chip
- **Self-documenting**: Clear intent from command structure

## 📁 What I Created

1. **`docs/ANALYSIS_WORKFLOW_IMPROVEMENTS.md`** - Comprehensive guide (recommended read!)
2. **`bash/alisson67_analysis_v2.sh`** - Improved version for chip 67
3. **`bash/analyze_chip.sh`** - Generic version for any chip
4. **`bash/COMPARISON.md`** - Side-by-side comparison

## 🚀 Try It Now (5 minutes)

### Option 1: Run Improved Alisson67 Script

```bash
source .venv/bin/activate
./bash/alisson67_analysis_v2.sh
```

**What it does:**
1. Initial IVg characterization
2. CNP evolution tracking
3. **Comprehensive photoresponse analysis** (power, wavelength, gate, time)
4. Detailed ITS power series (auto-discovered wavelength/gate combinations)

**Output:** `figs/Alisson67/` (same as old script, but better organized)

### Option 2: Run Generic Script for Any Chip

```bash
source .venv/bin/activate

# Full analysis
./bash/analyze_chip.sh 67

# Quick analysis (skip detailed ITS)
./bash/analyze_chip.sh 75 --quick

# Only photoresponse plots
./bash/analyze_chip.sh 81 --photoresponse-only
```

## 🔍 Key Improvements Explained

### 1. Auto-Filtering (No More Hard-coded Sequences!)

**Before:**
```bash
# ❌ Must know sequence numbers
# ❌ Breaks if data changes
python process_and_analyze.py plot-its 67 --seq 4-7 --legend irradiated_power
```

**After:**
```bash
# ✅ Automatic discovery
# ✅ Self-documenting (455nm, Vg=-0.35V)
# ✅ Robust to data changes
python3 process_and_analyze.py plot-its 67 --auto --wl 455 --vg -0.35 --legend irradiated_power
```

### 2. Photoresponse Analysis (New Scientific Insights!)

**Before:**
```bash
# NOT POSSIBLE without manual data export
```

**After:**
```bash
# ✅ Multi-dimensional photoresponse analysis
python3 process_and_analyze.py plot-photoresponse 67 power        # vs power (power-law)
python3 process_and_analyze.py plot-photoresponse 67 wavelength   # spectral response
python3 process_and_analyze.py plot-photoresponse 67 gate_voltage # doping dependence
python3 process_and_analyze.py plot-photoresponse 67 time         # degradation/recovery
```

**Why this matters:**
- Reveals trends not visible in individual ITS plots
- Publication-ready figures with error bars
- Automatic grouping and statistical analysis

### 3. Eliminated Redundancy

**Before (each wavelength/gate combination):**
```bash
python process_and_analyze.py plot-its 67 --seq 4-7 --legend irradiated_power
python process_and_analyze.py plot-its-sequential 67 --seq 4-7 --legend irradiated_power
# ↑ Same plot, different format (redundant!)
```

**After:**
```bash
python3 process_and_analyze.py plot-its 67 --auto --wl 455 --vg -0.35 --legend irradiated_power
# ↑ Single command, better organization
```

## 📊 Results Comparison

### Your Current Script (`bash/run_alisson67_plots.sh`)
```
Commands:  30
Lines:     166
Reusable:  ❌ No (chip 67 only)
Robust:    ❌ No (breaks if data changes)
Scientific:❌ No (just raw plots)
```

### New Script (`bash/alisson67_analysis_v2.sh`)
```
Commands:  16 (47% reduction)
Lines:     119 (28% reduction)
Reusable:  ✅ Yes (via analyze_chip.sh)
Robust:    ✅ Yes (auto-filtering)
Scientific:✅ Yes (photoresponse analysis)
```

## 🎓 Next Steps

### Step 1: Test New Approach (Now)
```bash
# Run new script
source .venv/bin/activate
./bash/alisson67_analysis_v2.sh

# Compare outputs (should match old script, but better organized)
ls -lh figs/Alisson67/
```

### Step 2: Read Documentation (10 minutes)
- **Start here**: `docs/ANALYSIS_WORKFLOW_IMPROVEMENTS.md` (comprehensive guide)
- **Quick comparison**: `bash/COMPARISON.md` (side-by-side examples)

### Step 3: Apply to Other Chips (2 minutes each)
```bash
./bash/analyze_chip.sh 75
./bash/analyze_chip.sh 81
```

### Step 4: Explore New Features
```bash
# Relaxation time analysis (Numba-accelerated fitting)
python3 process_and_analyze.py plot-its-relaxation 67 --auto

# Export data for external analysis
python3 process_and_analyze.py show-history 67 --format csv > chip67_data.csv
python3 process_and_analyze.py show-history 67 --format json | jq '.data[] | select(.wavelength_nm == 365)'

# Laser calibration plots
python3 process_and_analyze.py plot-laser-calibration 67
```

## 💡 Pro Tips

### Tip 1: Use Loops for Systematic Analysis
```bash
# Analyze multiple chips
for chip in 67 75 81; do
    ./bash/analyze_chip.sh $chip
done
```

### Tip 2: Filter History for Specific Conditions
```bash
# Show only 365nm experiments
python3 process_and_analyze.py show-history 67 --proc It | grep "365.0"

# Export JSON and filter with jq
python3 process_and_analyze.py show-history 67 --format json | \
    jq '.data[] | select(.wavelength_nm == 365 and .vg_fixed_v < 0)'
```

### Tip 3: Check What Auto-Discovery Will Select
```bash
# Preview without plotting
python3 process_and_analyze.py show-history 67 --proc It --format table | grep "455.0.*-0.35"
```

### Tip 4: Build Custom Workflows
```bash
# Create chip-specific analysis script
cat > bash/my_custom_analysis.sh << 'EOF'
#!/bin/bash
CHIP=$1

# Your custom workflow
python3 process_and_analyze.py plot-cnp-time $CHIP
python3 process_and_analyze.py plot-photoresponse $CHIP power
python3 process_and_analyze.py plot-its $CHIP --auto --wl 365 --vg -0.4
EOF

chmod +x bash/my_custom_analysis.sh
./bash/my_custom_analysis.sh 67
```

## 🆘 Common Issues

### Issue 1: "No experiments found"
**Cause:** No experiments match the filters
**Solution:** Check available wavelengths and gate voltages
```bash
python3 process_and_analyze.py show-history 67 --proc It --format table
```

### Issue 2: "Enriched history not found"
**Cause:** Derived metrics haven't been extracted
**Solution:** Run enrichment pipeline
```bash
python3 process_and_analyze.py derive-all-metrics
python3 process_and_analyze.py enrich-history 67
```

### Issue 3: Script fails on specific chip
**Cause:** Chip may have different experimental structure
**Solution:** Use `--quick` or `--photoresponse-only` mode
```bash
./bash/analyze_chip.sh 75 --quick
```

## 📚 Further Reading

### Essential Docs (Read These!)
1. **`docs/ANALYSIS_WORKFLOW_IMPROVEMENTS.md`** - Complete workflow guide
2. **`bash/COMPARISON.md`** - Side-by-side comparison with examples
3. **`CLAUDE.md`** - Complete project documentation

### Feature-Specific Guides
- **Derived metrics**: `docs/DERIVED_METRICS_ARCHITECTURE.md`
- **Relaxation times**: `docs/ITS_RELAXATION_TIME_EXTRACTOR.md`
- **Plotting guide**: `docs/PLOTTING_IMPLEMENTATION_GUIDE.md`
- **Output formats**: `docs/OUTPUT_FORMATTERS.md`

### CLI Reference
```bash
# List all commands
python3 process_and_analyze.py --help

# Command-specific help
python3 process_and_analyze.py plot-its --help
python3 process_and_analyze.py plot-photoresponse --help
```

## 🎉 Summary

Your workflow analysis revealed a systematic power-series study at multiple wavelengths and gate voltages. The new approach:

1. **Reduces commands by 47%** (30 → 16)
2. **Eliminates hard-coded sequences** (robust to data changes)
3. **Adds scientific analysis** (photoresponse trends)
4. **Works for all chips** (generic, reusable)
5. **Self-documenting** (clear intent from filters)

**Start here:** `./bash/alisson67_analysis_v2.sh`

**Questions?** Check `docs/ANALYSIS_WORKFLOW_IMPROVEMENTS.md` or ask!
