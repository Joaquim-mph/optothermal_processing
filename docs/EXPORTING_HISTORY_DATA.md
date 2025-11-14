# Exporting History Data

**Version**: 3.3.1+ | **Last Updated**: January 2025

---

## Quick Reference

### Essential Commands

```bash
# Organized export (recommended)
python3 process_and_analyze.py export-history 67

# Manual export to stdout
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null > history.csv

# Batch export all chips
python3 process_and_analyze.py export-all-histories
```

### Common Exports

| Use Case | Command |
|----------|---------|
| **Excel export** | `python3 process_and_analyze.py export-history 67 --format xlsx` |
| **JSON export** | `python3 process_and_analyze.py export-history 67 --format json` |
| **Light ITS only** | `python3 process_and_analyze.py export-history 67 --proc It --light light` |
| **Dark IVg only** | `python3 process_and_analyze.py export-history 67 --proc IVg --light dark` |
| **Last 50 experiments** | `python3 process_and_analyze.py export-history 67 --limit 50` |
| **Metrics only** | `python3 process_and_analyze.py export-history 67 --mode metrics` |
| **Compact view** | `python3 process_and_analyze.py export-history 67 --mode compact` |

### Flags Reference

| Flag | Short | Values | Default | Description |
|------|-------|--------|---------|-------------|
| `--format` | `-f` | csv, json, parquet, xlsx | csv | Output format |
| `--output-dir` | `-o` | path | data/04_exports/histories/ | Custom directory |
| `--proc` | `-p` | It, IVg, IV, etc. | All | Filter by procedure |
| `--light` | `-l` | light, dark, unknown | All | Filter by illumination |
| `--limit` | `-n` | integer | All | Last N experiments |
| `--mode` | `-m` | default, metrics, compact | default | Column set |
| `--no-timestamp` | | flag | False | Omit timestamp from filename |
| `--overwrite` | | flag | False | Overwrite existing files |

### Format Comparison

| Format | Size | Speed | Best For |
|--------|------|-------|----------|
| **CSV** | Medium | Fast | Excel, Google Sheets, universal compatibility |
| **JSON** | Large | Fast | APIs, scripting, jq filtering, automation |
| **Parquet** | Small | Fastest | Python (polars/pandas), efficient archiving |
| **Excel** | Large | Slow | Direct Excel compatibility (requires openpyxl) |

### Export Modes

| Mode | Columns | Use Case |
|------|---------|----------|
| **default** | 34+ columns | Complete data including all parameters and metrics |
| **metrics** | 13 columns | Focused on derived quantities (CNP, power, delta_current) |
| **compact** | 6 columns | Essential overview (seq, date, proc, summary, has_light) |

---

## Overview

You can export chip history data (standard or enriched) in multiple formats for analysis, archiving, or integration with other tools.

**Two methods available**:
1. **`export-history`** - Organized exports with automatic naming and folder structure (Recommended)
2. **`show-history --format`** - Manual exports with stdout redirection (Simple)

---

## Export Using `export-history` Command

### Basic Usage

```bash
# Export full history as CSV (default)
python3 process_and_analyze.py export-history 67

# Export as JSON
python3 process_and_analyze.py export-history 67 --format json

# Export as Parquet (efficient binary format)
python3 process_and_analyze.py export-history 67 --format parquet

# Export as Excel (requires openpyxl)
python3 process_and_analyze.py export-history 67 --format xlsx
```

**Features**:
- ✅ Automatic folder creation (`data/04_exports/histories/Alisson67/`)
- ✅ Timestamped filenames (no overwrites)
- ✅ Clean summary output
- ✅ Multiple format support (CSV, JSON, Parquet, Excel)

**Output**: `data/04_exports/histories/Alisson67/Alisson67_history_YYYYMMDD_HHMMSS.csv`

### Filtered Exports

```bash
# Export only light ITS experiments
python3 process_and_analyze.py export-history 67 --proc It --light light

# Export only IVg dark measurements
python3 process_and_analyze.py export-history 67 --proc IVg --light dark

# Export last 50 experiments
python3 process_and_analyze.py export-history 67 --limit 50
```

### File Naming

```bash
# With timestamp (default) - creates unique files
python3 process_and_analyze.py export-history 67
# Output: Alisson67_history_20251113_230353.csv

# Without timestamp - cleaner filenames
python3 process_and_analyze.py export-history 67 --no-timestamp
# Output: Alisson67_history.csv

# Overwrite existing file
python3 process_and_analyze.py export-history 67 --no-timestamp --overwrite
```

**Filename Patterns:**
- Default: `Alisson67_history_20251113_230353.csv`
- No timestamp: `Alisson67_history.csv`
- Metrics mode: `Alisson67_metrics_20251113_230353.csv`
- Filtered (It, light): `Alisson67_history_it_light_20251113_230353.csv`
- JSON format: `Alisson67_history_20251113_230353.json`

### Custom Output Directory

```bash
# Export to custom folder
python3 process_and_analyze.py export-history 67 --output-dir ~/my_exports

# Export to shared network drive
python3 process_and_analyze.py export-history 67 --output-dir /mnt/shared/exports
```

### Batch Export All Chips

```bash
# Export all available chips
python3 process_and_analyze.py export-all-histories

# Export all as JSON
python3 process_and_analyze.py export-all-histories --format json

# Export all metrics-only
python3 process_and_analyze.py export-all-histories --mode metrics
```

### Directory Structure

The `export-history` command creates organized folders:

```
data/04_exports/
└── histories/
    ├── Alisson67/
    │   ├── Alisson67_history_20251113_230353.csv
    │   ├── Alisson67_metrics.json
    │   ├── Alisson67_history_it_light.csv
    │   └── Alisson67_compact_20251113_235900.csv
    ├── Alisson75/
    │   └── Alisson75_history_20251113_230500.csv
    └── Alisson81/
        └── Alisson81_history_20251113_230600.csv
```

---

## Export Using `show-history --format`

### Basic Usage

```bash
# Export to file with stdout redirection
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null > history.csv
```

**Features**:
- ✅ Simple and direct
- ✅ Full control over filename and location
- ⚠️ Requires manual folder management
- ⚠️ Requires stderr redirection for clean output

### CSV Export (Spreadsheet-Compatible)

**Best for**: Excel, Google Sheets, pandas, R, data analysis

```bash
# Full export
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null > history.csv

# With filters
python3 process_and_analyze.py show-history 67 --proc It --light light --format csv 2>/dev/null > its_light.csv

# Limit to recent experiments
python3 process_and_analyze.py show-history 67 --limit 20 --format csv 2>/dev/null > recent_20.csv

# Metrics-only view
python3 process_and_analyze.py show-history 67 --mode metrics --format csv 2>/dev/null > metrics.csv
```

**Columns Included** (36 total):
- **Experiment Info**: seq, date, time_hms, datetime_local, proc, summary
- **Parameters**: has_light, laser_voltage_v, wavelength_nm, vds_v, vg_fixed_v, etc.
- **File Paths**: parquet_path, source_file, calibration_parquet_path
- **Enriched Metrics**:
  - `irradiated_power_w` - Calibrated laser power (watts)
  - `delta_current` - Photoresponse (amps)
  - `cnp_voltage` - Charge neutrality point voltage (V)
  - `calibration_time_delta_hours` - Time to nearest calibration

### JSON Export (Machine-Readable)

**Best for**: Scripting, APIs, jq filtering, automation

```bash
# Full export
python3 process_and_analyze.py show-history 67 --format json > history.json

# Pretty-printed JSON
python3 process_and_analyze.py show-history 67 --format json | jq '.' > history_pretty.json

# Filter with jq
python3 process_and_analyze.py show-history 67 --format json | \
  jq '.data[] | select(.has_light == true)' > light_experiments.json
```

**Structure**:
```json
{
  "metadata": {
    "chip": "Alisson67",
    "total_experiments": 90,
    "export_time": "2025-01-13T22:48:00",
    "history_type": "enriched"
  },
  "data": [
    {
      "seq": 1,
      "proc": "IVg",
      "has_light": false,
      "cnp_voltage": -0.45,
      "irradiated_power_w": null,
      ...
    }
  ]
}
```

### Table Display (Terminal)

**Best for**: Quick viewing, presentations, reports

```bash
# Default format (auto-detected terminal width)
python3 process_and_analyze.py show-history 67

# With filtering
python3 process_and_analyze.py show-history 67 --proc It --light light --limit 10
```

**Features**:
- Color-coded by procedure type
- Emoji indicators (🌙 dark, 💡 light)
- Auto-wrapped to terminal width
- Rich formatting with borders

---

## Common Use Cases

### 1. Export for Python Analysis

```bash
# Export to CSV
python3 process_and_analyze.py export-history 67 --format csv --no-timestamp

# Load in Python
python3 << 'EOF'
import pandas as pd

# Load enriched history
df = pd.read_csv('data/04_exports/histories/Alisson67/Alisson67_history.csv')

# Filter to light ITS experiments with power data
its_light = df[(df['proc'] == 'It') &
               (df['has_light'] == True) &
               (df['irradiated_power_w'].notna())]

# Convert power to mW
its_light['power_mw'] = its_light['irradiated_power_w'] * 1e3

# Plot photoresponse vs power
import matplotlib.pyplot as plt
plt.figure(figsize=(8, 6))
plt.scatter(its_light['power_mw'], its_light['delta_current'] * 1e6)
plt.xlabel('Irradiated Power (mW)')
plt.ylabel('Δ Current (µA)')
plt.title('Photoresponse vs Power')
plt.savefig('photoresponse_analysis.png', dpi=300)
print('✓ Saved photoresponse_analysis.png')
EOF
```

### 2. Export for R Analysis

```bash
# Export CSV
python3 process_and_analyze.py export-history 67 --no-timestamp

# Load in R
R << 'EOF'
library(tidyverse)

# Load data
data <- read_csv('data/04_exports/histories/Alisson67/Alisson67_history.csv')

# Filter and analyze
its_light <- data %>%
  filter(proc == 'It', has_light == TRUE, !is.na(irradiated_power_w)) %>%
  mutate(power_mw = irradiated_power_w * 1e3,
         delta_current_ua = delta_current * 1e6)

# Plot
ggplot(its_light, aes(x = power_mw, y = delta_current_ua, color = factor(wavelength_nm))) +
  geom_point() +
  labs(x = 'Irradiated Power (mW)',
       y = 'Δ Current (µA)',
       color = 'Wavelength (nm)') +
  theme_minimal()

ggsave('photoresponse_r.png', width = 8, height = 6, dpi = 300)
cat('✓ Saved photoresponse_r.png\n')
EOF
```

### 3. Bash Scripting: Extract CNP Voltages

```bash
# Export to JSON and extract CNP values with jq
python3 process_and_analyze.py show-history 67 --format json | \
  jq -r '.data[] | select(.cnp_voltage != null) |
    [.seq, .date, .cnp_voltage] | @csv' > cnp_voltages.csv

echo "seq,date,cnp_voltage" | cat - cnp_voltages.csv > temp && mv temp cnp_voltages.csv
```

### 4. Python: Batch Export Multiple Chips

```python
import subprocess
import polars as pl
from pathlib import Path

chips = [67, 75, 81]
output_dir = Path('exports')
output_dir.mkdir(exist_ok=True)

for chip in chips:
    # Export CSV
    csv_file = output_dir / f'chip{chip}_history.csv'
    cmd = [
        'python3', 'process_and_analyze.py',
        'show-history', str(chip),
        '--format', 'csv'
    ]

    with open(csv_file, 'w') as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL)

    print(f'✓ Exported chip {chip} to {csv_file}')

    # Load and summarize
    df = pl.read_csv(csv_file)
    print(f'  - {df.height} experiments')
    print(f'  - {df.filter(pl.col("has_light") == True).height} with light')
    print(f'  - {df.filter(pl.col("cnp_voltage").is_not_null()).height} with CNP')
    print()
```

---

## Direct Parquet Export

If you need the raw Parquet file instead of converted formats:

### Copy Enriched History Parquet

```bash
# Find enriched history location
ENRICHED="data/03_derived/chip_histories_enriched/Alisson67_history.parquet"

# Copy to your analysis directory
cp "$ENRICHED" ~/analysis/alisson67_enriched.parquet

# Load in Python
python3 << 'EOF'
import polars as pl

# Load enriched history (fast!)
df = pl.read_parquet('~/analysis/alisson67_enriched.parquet')

# Show schema
print(df.schema)

# Filter and export
its_light = df.filter(
    (pl.col('proc') == 'It') &
    (pl.col('has_light') == True)
)

# Export to CSV
its_light.write_csv('its_light.csv')

# Export to JSON
its_light.write_json('its_light.json')

# Export to Excel (requires openpyxl)
its_light.write_excel('its_light.xlsx')
EOF
```

### Copy Standard History

```bash
# Standard history (without enriched metrics)
STANDARD="data/02_stage/chip_histories/Alisson67_history.parquet"
cp "$STANDARD" ~/analysis/alisson67_standard.parquet
```

---

## Column Reference

### Standard Columns (Always Present)

| Column | Type | Description |
|--------|------|-------------|
| `seq` | int | Sequential experiment number |
| `date` | str | Date (YYYY-MM-DD) |
| `time_hms` | str | Time (HH:MM:SS) |
| `datetime_local` | str | Local datetime |
| `proc` | str | Procedure type (It, IVg, IV, etc.) |
| `summary` | str | Human-readable summary |
| `has_light` | bool | Light illumination flag |
| `laser_voltage_v` | float | LED/laser voltage (V) |
| `wavelength_nm` | float | Wavelength (nm) |
| `vds_v` | float | Drain-source voltage (V) |
| `vg_fixed_v` | float | Fixed gate voltage (V) |
| `parquet_path` | str | Path to measurement Parquet file |
| `chip_number` | int | Chip number (67, 75, 81, etc.) |
| `chip_group` | str | Chip group (Alisson, Encap, etc.) |

### Enriched Columns (From derive-all-metrics)

| Column | Type | Description | Procedure |
|--------|------|-------------|-----------|
| `irradiated_power_w` | float | Calibrated laser power (W) | It (light) |
| `delta_current` | float | Photoresponse ΔI (A) | It (light) |
| `cnp_voltage` | float | Charge neutrality point voltage (V) | IVg |
| `cnp_voltage_right` | float | Right-side CNP (if asymmetric) | IVg |
| `delta_current_right` | float | Right-side photoresponse | It (light) |
| `calibration_parquet_path` | str | Path to matched laser calibration | It (light) |
| `calibration_time_delta_hours` | float | Hours to nearest calibration | It (light) |
| `tau_pre_dark` | float | Pre-dark relaxation time (s) | It (3-phase) |
| `tau_light` | float | Light-on relaxation time (s) | It (3-phase) |
| `tau_post_dark` | float | Post-dark relaxation time (s) | It (3-phase) |
| `beta_pre_dark` | float | Pre-dark stretch exponent | It (3-phase) |
| `beta_light` | float | Light-on stretch exponent | It (3-phase) |
| `beta_post_dark` | float | Post-dark stretch exponent | It (3-phase) |

---

## Tips & Best Practices

### 1. Always Redirect stderr for Clean CSV

```bash
# BAD - cache messages pollute CSV
python3 process_and_analyze.py show-history 67 --format csv > data.csv

# GOOD - clean CSV output
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null > data.csv
```

### 2. Use Filters to Reduce File Size

```bash
# Full export: 90 rows
python3 process_and_analyze.py export-history 67

# Filtered: only 30 light experiments
python3 process_and_analyze.py export-history 67 --light light
```

### 3. Preview Before Export

Use `show-history` to preview what will be exported:

```bash
# Preview
python3 process_and_analyze.py show-history 67 --proc It --light light --limit 5

# Export (same filters)
python3 process_and_analyze.py export-history 67 --proc It --light light
```

### 4. Use No-Timestamp for Reproducibility

```bash
# Always overwrites same file (good for automated workflows)
python3 process_and_analyze.py export-history 67 \
  --no-timestamp \
  --overwrite
```

### 5. Check Enriched History Exists

```bash
# Check if enriched history is available
if [ -f "data/03_derived/chip_histories_enriched/Alisson67_history.parquet" ]; then
    echo "✓ Enriched history available"
else
    echo "⚠ Enriched history missing. Run: enrich-history 67"
fi
```

### 6. Combine with Standard Unix Tools

```bash
# Count experiments by procedure
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null | \
  tail -n +2 | cut -d',' -f5 | sort | uniq -c

# Extract specific columns
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null | \
  cut -d',' -f1,5,7,32,34 > seq_proc_light_power_delta.csv
```

---

## Troubleshooting

### Issue: Cache messages in CSV

**Problem**: First line contains `[cache] Enabled caching...`

**Solution**: Redirect stderr
```bash
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null > clean.csv
```

### Issue: Empty CSV or JSON

**Problem**: No output or empty file

**Cause**: History file doesn't exist

**Solution**:
```bash
# Build history first
python3 process_and_analyze.py build-all-histories

# Then export
python3 process_and_analyze.py export-history 67
```

### Issue: "Chip history file not found"

**Solution**:
```bash
# Build history first
python3 process_and_analyze.py build-all-histories

# Then export
python3 process_and_analyze.py export-history 67
```

### Issue: "File already exists"

**Solution**:
```bash
# Option 1: Use timestamp (creates new file, default behavior)
python3 process_and_analyze.py export-history 67

# Option 2: Overwrite
python3 process_and_analyze.py export-history 67 --no-timestamp --overwrite
```

### Issue: Missing enriched columns

**Problem**: CSV doesn't have `delta_current`, `cnp_voltage`, `irradiated_power_w`

**Cause**: Using standard history instead of enriched

**Solution**:
```bash
# Extract metrics
python3 process_and_analyze.py derive-all-metrics --calibrations

# Enrich history
python3 process_and_analyze.py enrich-history 67

# Export again
python3 process_and_analyze.py export-history 67
```

### Issue: "Excel export failed"

**Solution**:
```bash
# Install openpyxl
pip install openpyxl

# Then retry
python3 process_and_analyze.py export-history 67 --format xlsx
```

### Issue: Encoding errors in Excel

**Problem**: Special characters (⚙️, 🌙, 💡) corrupted in Excel

**Solution**:
1. Open Excel
2. Go to Data → From Text/CSV
3. Select file
4. Set encoding to UTF-8
5. Import

Or remove emojis:
```bash
python3 process_and_analyze.py show-history 67 --format csv 2>/dev/null | \
  sed 's/[🌙💡⚙️❗]//g' > no_emoji.csv
```

---

## See Also

- **Output Formatters Guide**: `OUTPUT_FORMATTERS.md`
- **Derived Metrics**: `DERIVED_METRICS_ARCHITECTURE.md`
- **History Building**: Main `CLAUDE.md` documentation
- **CLI Reference**: `python3 process_and_analyze.py --help`

---

**Last Updated**: January 2025
**Quick Export**: `python3 process_and_analyze.py export-history 67`
