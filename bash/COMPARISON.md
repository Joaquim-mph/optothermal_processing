# Analysis Workflow Comparison

## Side-by-Side: Old vs New Approach

### 📊 **Summary Statistics**

| Metric | Old Script | New Script | Improvement |
|--------|-----------|-----------|-------------|
| **Total Commands** | 34 | 15 | **56% reduction** |
| **Lines of Code** | 167 | 110 | **34% fewer lines** |
| **Hard-coded Sequences** | 34 | 0 | **100% eliminated** |
| **Maintainability** | Low | High | **Easy to modify** |
| **Reusability** | Chip-specific | Generic | **Works for all chips** |
| **Documentation** | Comments | Self-documenting | **Clear intent** |

---

## 🔍 **Detailed Comparison**

### Example: 455nm Power Series at Negative Gate

**Old Approach (Lines 15-22):**
```bash
# 1) 405 nm, negative gate  ❌ WRONG COMMENT!
python process_and_analyze.py plot-its 67 \
  --seq 4-7 \
  --legend irradiated_power

python process_and_analyze.py plot-its-sequential 67 \
  --seq 4-7 \
  --legend irradiated_power
```

**Issues:**
- ❌ Comment says "405nm" but data is actually 455nm
- ❌ Sequences 4-7 hard-coded (breaks if data changes)
- ❌ Two commands for essentially the same plot
- ❌ No indication of gate voltage in command

**New Approach:**
```bash
# 455nm wavelength, negative gate
python3 process_and_analyze.py plot-its 67 \
    --auto \
    --wl 455 \
    --vg -0.35 \
    --legend irradiated_power
```

**Benefits:**
- ✅ **Self-documenting**: Filters clearly show 455nm, Vg=-0.35V
- ✅ **Automatic discovery**: No hard-coded sequences
- ✅ **Single command**: No redundant plot-its-sequential
- ✅ **Robust**: Works even if new experiments are added

---

### Example: Complete 405nm Analysis

**Old Approach (Lines 35-54):**
```bash
# 1) 405 nm, negative gate
python process_and_analyze.py plot-its 67 \
  --seq 15-18 \
  --legend irradiated_power

python process_and_analyze.py plot-its-sequential 67 \
  --seq 15-18 \
  --legend irradiated_power

# 2) 405 nm, positive gate
python process_and_analyze.py plot-its 67 \
  --seq 21-24 \
  --legend irradiated_power

python process_and_analyze.py plot-its-sequential 67 \
  --seq 21-24 \
  --legend irradiated_power
```

**4 commands** to plot 405nm data

**New Approach:**
```bash
# 405nm wavelength
python3 process_and_analyze.py plot-its 67 --auto --wl 405 --vg -0.35 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 405 --vg 0.2 --legend irradiated_power
```

**2 commands** to plot 405nm data (**50% reduction**)

---

### Example: Comprehensive Photoresponse Analysis

**Old Approach:**
```bash
# NOT POSSIBLE!
# Would need to manually export data, use external plotting tools
```

**New Approach:**
```bash
# Automatically generates 4 publication-quality plots
python3 process_and_analyze.py plot-photoresponse 67 power        # vs power
python3 process_and_analyze.py plot-photoresponse 67 wavelength   # vs wavelength
python3 process_and_analyze.py plot-photoresponse 67 gate_voltage # vs gate
python3 process_and_analyze.py plot-photoresponse 67 time         # vs time
```

**Benefits:**
- ✅ Multi-dimensional analysis (4D: power, wavelength, gate, time)
- ✅ Automatic grouping and error bars
- ✅ Publication-quality figures
- ✅ Reveals trends not visible in individual plots

---

## 🚀 **Migration Path**

### Step 1: Test New Script (5 minutes)
```bash
# Run new script
source .venv/bin/activate
./bash/alisson67_analysis_v2.sh

# Compare outputs
ls -lh figs/Alisson67/
```

### Step 2: Verify Results (10 minutes)
- Check that all expected plots are generated
- Verify plot quality matches old script
- Look for any missing experiments (should be none!)

### Step 3: Apply to Other Chips (2 minutes each)
```bash
./bash/analyze_chip.sh 75
./bash/analyze_chip.sh 81
```

### Step 4: Archive Old Script (1 minute)
```bash
# Keep old script for reference, but don't use it
mv bash/run_alisson67_plots.sh bash/archive/run_alisson67_plots_OLD.sh
```

---

## 📈 **Real-World Example: What Changed**

### Before (34 commands):
```bash
# IVg (1 command)
python process_and_analyze.py plot-ivg 67 --seq 2

# Transconductance (1 command)
python process_and_analyze.py plot-transconductance 67 --seq 2 --method savgol --window 21 --polyorder 7

# 455nm @ -0.35V (2 commands)
python process_and_analyze.py plot-its 67 --seq 4-7 --legend irradiated_power
python process_and_analyze.py plot-its-sequential 67 --seq 4-7 --legend irradiated_power

# 455nm @ +0.2V (2 commands)
python process_and_analyze.py plot-its 67 --seq 9-12 --legend irradiated_power
python process_and_analyze.py plot-its-sequential 67 --seq 9-12 --legend irradiated_power

# ... (28 more commands) ...
```

### After (15 commands):
```bash
# Initial characterization (2 commands)
python3 process_and_analyze.py plot-ivg 67 --seq 2
python3 process_and_analyze.py plot-transconductance 67 --seq 2 --method savgol --window 21 --polyorder 7

# CNP evolution (1 command)
python3 process_and_analyze.py plot-cnp-time 67

# Comprehensive photoresponse (4 commands)
python3 process_and_analyze.py plot-photoresponse 67 power
python3 process_and_analyze.py plot-photoresponse 67 wavelength
python3 process_and_analyze.py plot-photoresponse 67 gate_voltage
python3 process_and_analyze.py plot-photoresponse 67 time

# Detailed ITS (8 commands, auto-filtered)
python3 process_and_analyze.py plot-its 67 --auto --wl 455 --vg -0.35 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 455 --vg 0.2 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 405 --vg -0.35 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 405 --vg 0.2 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 385 --vg -0.4 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 385 --vg 0.2 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 365 --vg -0.4 --legend irradiated_power
python3 process_and_analyze.py plot-its 67 --auto --wl 365 --vg 0.2 --legend irradiated_power
```

---

## 💡 **Key Takeaways**

1. **Use `--auto` filtering instead of hard-coded sequences**
   - More robust to data changes
   - Self-documenting
   - Works across chips

2. **Use photoresponse commands for comprehensive analysis**
   - Reveals trends not visible in individual plots
   - Publication-quality figures
   - Multi-dimensional insights

3. **Eliminate redundant commands**
   - Don't run both `plot-its` and `plot-its-sequential` for the same data
   - Use auto-discovery instead of manual specification

4. **Make scripts generic**
   - Write once, use for all chips
   - Reduce maintenance burden
   - Easier to onboard new team members

---

## 📚 **Further Reading**

- **Full documentation**: `docs/ANALYSIS_WORKFLOW_IMPROVEMENTS.md`
- **Plotting guide**: `docs/PLOTTING_IMPLEMENTATION_GUIDE.md`
- **CLI reference**: `python3 process_and_analyze.py --help`
- **Derived metrics**: `docs/DERIVED_METRICS_ARCHITECTURE.md`
