# Plotting Consecutive Sweep Differences - Quick Guide

**Command**: `plot-consecutive-sweep-diff`
**Purpose**: Visualize ΔI(Vg) or ΔV(Vg) curves between consecutive gate voltage sweeps

---

## Quick Start

```bash
# 1. Extract metrics (if not done already)
python3 process_and_analyze.py derive-all-metrics --chip 67

# 2. Generate all difference plots
python3 process_and_analyze.py plot-consecutive-sweep-diff 67
```

---

## What Gets Generated

### Individual Plots
One plot per consecutive pair showing:
- **Left panel**: ΔI(Vg) or ΔV(Vg) curve
- **Right panel**: ΔR(Vg) resistance difference (optional)
- **Annotation**: ΔCNP value if available

**Example output**: `figs/Alisson67/IVg/ConsecutiveSweepDiff/seq1_to_2.png`

### Summary Plot
All differences overlaid for comparison:
- Color-coded by pair
- Legend showing seq numbers
- Both ΔI/ΔV and ΔR panels

**Example output**: `figs/Alisson67/IVg/ConsecutiveSweepDiff/summary.png`

---

## Common Usage Patterns

### 1. Plot Only IVg Differences

```bash
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --proc IVg
```

**Output**:
- Individual plots for each consecutive IVg pair
- Summary overlay of all IVg differences

### 2. Plot Only VVg Differences

```bash
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --proc VVg
```

### 3. Plot Both IVg and VVg

```bash
python3 process_and_analyze.py plot-consecutive-sweep-diff 67
```

**Output**:
- Separate plots for IVg pairs
- Separate plots for VVg pairs
- Two summary plots (one for IVg, one for VVg)

### 4. Summary Only (No Individual Plots)

```bash
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --summary-only
```

**Use case**: Quick overview when you have many pairs

### 5. Individual Plots Only (No Summary)

```bash
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --individual-only
```

**Use case**: Detailed analysis of each pair

### 6. Without Resistance Plots

```bash
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --no-resistance
```

**Use case**: Faster generation, focus on current/voltage only

---

## Command Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--group` | `-g` | Chip group prefix | Alisson |
| `--proc` | `-p` | Filter to IVg or VVg | Both |
| `--no-resistance` | | Skip ΔR plots | Include ΔR |
| `--individual-only` | | Only individual plots | Both |
| `--summary-only` | | Only summary plot | Both |
| `--tag` | `-t` | Add tag to filenames | None |
| `--output-dir` | `-o` | Custom output directory | figs/ |

---

## Example Scenarios

### Scenario 1: Track CNP Evolution After Illumination

**Setup**:
```
Seq 1: IVg (dark)
Seq 2: It (365nm, 30min)
Seq 3: IVg (dark)
Seq 4: It (365nm, 60min)
Seq 5: IVg (dark)
```

**Command**:
```bash
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --proc IVg
```

**Result**:
- Plot 1: Seq 1→3 (shows effect of 30min illumination)
- Plot 2: Seq 3→5 (shows effect of additional 60min)
- Summary: Both curves overlaid

**Analysis**: Compare ΔCNP values to quantify cumulative shift

### Scenario 2: Compare IVg vs VVg Evolution

**Command**:
```bash
# Plot both procedures
python3 process_and_analyze.py plot-consecutive-sweep-diff 67

# Compare output files
ls figs/Alisson67/IVg/ConsecutiveSweepDiff/
ls figs/Alisson67/VVg/ConsecutiveSweepDiff/
```

**Use case**: Verify consistent evolution in both measurement types

### Scenario 3: Generate Publication Figures

**Command**:
```bash
# Generate only summary plots with custom tag
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 \
  --proc IVg \
  --summary-only \
  --tag "figure3"
```

**Output**: `figs/Alisson67/IVg/ConsecutiveSweepDiff/figure3_summary.png`

---

## Interpreting the Plots

### ΔI(Vg) Curves (IVg)

**Positive ΔI**:
- Current increased in second measurement
- Possible causes: doping change, defect healing, improved contact

**Negative ΔI**:
- Current decreased
- Possible causes: degradation, increased defects, contact damage

**Zero ΔI**:
- Device stable between measurements
- No significant change

### ΔCNP Values

**Positive ΔCNP** (CNP shifts right):
- More negative (electron) doping in second measurement
- Common after some types of illumination

**Negative ΔCNP** (CNP shifts left):
- More positive (hole) doping
- Can indicate charge transfer or doping changes

### ΔR(Vg) Curves

**Shows resistance evolution**:
- Positive ΔR: Resistance increased (degradation?)
- Negative ΔR: Resistance decreased (improved conductivity?)
- Look for Vg regions with largest changes

---

## Troubleshooting

### Error: "No consecutive sweep differences found"

**Cause**: No pairwise metrics extracted

**Solution**:
```bash
# Extract metrics first
python3 process_and_analyze.py derive-all-metrics --chip 67

# Verify extraction worked
python3 -c "
import polars as pl
metrics = pl.read_parquet('data/03_derived/_metrics/metrics.parquet')
pairwise = metrics.filter(
    (pl.col('metric_name') == 'consecutive_sweep_difference') &
    (pl.col('chip_number') == 67)
)
print(f'Found {pairwise.height} pairwise metrics')
"
```

### Error: "Metrics file not found"

**Cause**: Metrics pipeline not run

**Solution**:
```bash
# Run full pipeline
python3 process_and_analyze.py full-pipeline

# Or just metrics extraction
python3 process_and_analyze.py derive-all-metrics
```

### No Pairs Found (But Metrics Exist)

**Possible causes**:
1. Seq_num has gaps (not consecutive)
2. All measurements are different procedures
3. Insufficient Vg overlap (< 1.0V)

**Check**:
```bash
# View chip history to see seq numbers
python3 process_and_analyze.py show-history 67 --proc IVg

# Look for gaps in seq_num column
```

---

## Advanced Usage

### Custom Output Directory

```bash
# Save to specific folder
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 \
  --output-dir ~/Desktop/figures
```

### Batch Processing Multiple Chips

```bash
# Create bash script
for chip in 67 75 81; do
    echo "Processing chip $chip..."
    python3 process_and_analyze.py plot-consecutive-sweep-diff $chip \
      --proc IVg \
      --summary-only
done
```

### Integration with Other Plots

```bash
# Generate complete figure set
python3 process_and_analyze.py plot-ivg 67 --auto
python3 process_and_analyze.py plot-cnp-time 67
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --proc IVg
```

---

## Tips & Best Practices

1. **Run metrics extraction first**: Always ensure `derive-all-metrics` has been run

2. **Check for consecutive measurements**: Use `show-history` to verify no gaps

3. **Start with summary plot**: Use `--summary-only` for quick overview

4. **Filter by procedure**: Usually better to plot IVg and VVg separately

5. **Use tags for organization**: Add `--tag` for different analyses

6. **Combine with CNP plots**: Compare with `plot-cnp-time` for context

---

## See Also

- **Implementation**: `docs/CONSECUTIVE_SWEEP_IMPLEMENTATION_SUMMARY.md`
- **Technical Plan**: `docs/CONSECUTIVE_SWEEP_DIFFERENCING_PLAN.md`
- **Metric Extraction**: `python3 process_and_analyze.py derive-all-metrics --help`
- **CNP Evolution**: `python3 process_and_analyze.py plot-cnp-time --help`

---

**Quick Reference**:
```bash
# Extract metrics
python3 process_and_analyze.py derive-all-metrics --chip 67

# Plot all differences
python3 process_and_analyze.py plot-consecutive-sweep-diff 67

# Plot IVg only (summary)
python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --proc IVg --summary-only
```
