# Output Formatters User Guide

**Version:** 3.1+
**Status:** Production-Ready
**Last Updated:** 2025-11-07

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Available Formats](#available-formats)
- [Commands with Format Support](#commands-with-format-support)
- [Usage Examples](#usage-examples)
- [JSON Format Details](#json-format-details)
- [CSV Format Details](#csv-format-details)
- [Scripting and Automation](#scripting-and-automation)
- [External Tool Integration](#external-tool-integration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

---

## Overview

Output formatters provide a clean way to export data from CLI commands in multiple formats, enabling:

- **Interactive exploration** - Beautiful Rich tables in the terminal (default)
- **Scripting and automation** - Machine-readable JSON for pipelines
- **Spreadsheet analysis** - CSV export for Excel, Google Sheets, etc.
- **Data integration** - Pipe to tools like `jq`, `column`, or custom scripts

### Key Benefits

✅ **Backward Compatible** - Default behavior unchanged
✅ **Machine-Readable** - JSON with proper type handling
✅ **Spreadsheet-Ready** - CSV with proper escaping
✅ **Pipeable** - Clean stdout for Unix tools
✅ **Extensible** - Easy to add new formats

---

## Quick Start

### View Data in Terminal (Default)

```bash
# Rich terminal table with colors and styling
python3 process_and_analyze.py show-history 67
```

### Export as JSON

```bash
# Machine-readable JSON
python3 process_and_analyze.py show-history 67 --format json

# Save to file
python3 process_and_analyze.py show-history 67 --format json > history.json
```

### Export as CSV

```bash
# CSV for spreadsheets
python3 process_and_analyze.py show-history 67 --format csv

# Save to file
python3 process_and_analyze.py show-history 67 --format csv > history.csv
```

---

## Available Formats

### Table Format (Default)

**Purpose:** Interactive terminal display with Rich styling

**Features:**
- Color-coded columns
- Light status emojis (💡 🌙 ❗)
- Box borders and styling
- Automatic column sizing
- Visual separators

**When to Use:**
- Interactive exploration
- Quick data inspection
- Terminal-based workflows

**Example:**
```bash
python3 process_and_analyze.py show-history 67 --limit 5
```

**Output:**
```
╭──────────────────────────────╮
│ Alisson67 Experiment History │
│ Total experiments: 5         │
╰──────────────────────────────╯

╭─────┬────────────┬──────────┬──────┬─────┬─────────╮
│ Seq │ Date       │ Time     │ Proc │ Vg  │ CNP (V) │
├─────┼────────────┼──────────┼──────┼─────┼─────────┤
│ 89  │ 2025-10-21 │ 16:19:19 │ IVg  │ ... │ 0.025   │
│ 90  │ 2025-10-21 │ 18:36:06 │ IVg  │ ... │ 0.025   │
╰─────┴────────────┴──────────┴──────┴─────┴─────────╯
```

### JSON Format

**Purpose:** Machine-readable structured data

**Features:**
- Self-documenting metadata
- Proper type preservation (null, float, int, etc.)
- Nested data support
- UTF-8 encoding
- Valid JSON (parseable by all JSON tools)

**When to Use:**
- Scripting and automation
- CI/CD pipelines
- Data analysis with Python/jq
- API integration
- Complex data structures

**Example:**
```bash
python3 process_and_analyze.py show-history 67 --format json --limit 2
```

**Output:**
```json
{
  "metadata": {
    "chip": "Alisson67",
    "chip_number": 67,
    "chip_group": "Alisson",
    "total_experiments": 90,
    "date_range": "2025-10-14 to 2025-10-21",
    "num_days": 8,
    "filters_applied": ["limit=2"],
    "title": "Alisson67 Experiment History",
    "row_count": 2
  },
  "data": [
    {
      "seq": 89,
      "date": "2025-10-21",
      "time_hms": "16:19:19",
      "datetime_local": "2025-10-21 13:19:19",
      "proc": "IVg",
      "has_light": false,
      "voltage": 0.1,
      "wavelength_nm": 455.0,
      "cnp_voltage": 0.025,
      "delta_current": null
    },
    {
      "seq": 90,
      "date": "2025-10-21",
      "time_hms": "18:36:06",
      "proc": "IVg",
      "voltage": 0.1,
      "cnp_voltage": 0.025
    }
  ]
}
```

### CSV Format

**Purpose:** Spreadsheet-compatible export

**Features:**
- Standard CSV format (RFC 4180 compliant)
- Header row with column names
- Proper comma/quote escaping
- UTF-8 encoding
- Null values as empty strings
- Nested columns automatically stringified

**When to Use:**
- Excel/Google Sheets analysis
- Simple data exports
- Flat data structures
- Sharing with non-technical users

**Example:**
```bash
python3 process_and_analyze.py show-history 67 --format csv --limit 2
```

**Output:**
```csv
seq,date,time_hms,datetime_local,proc,has_light,voltage,wavelength_nm,cnp_voltage,delta_current
89,2025-10-21,16:19:19,2025-10-21 13:19:19,IVg,false,0.1,455.0,0.025,
90,2025-10-21,18:36:06,2025-10-21 15:36:06,IVg,false,0.1,455.0,0.025,
```

---

## Commands with Format Support

### show-history

Display chip experiment history with filtering.

**Syntax:**
```bash
python3 process_and_analyze.py show-history <chip_number> [OPTIONS] --format <format>
```

**Options:**
- `--format, -f` - Output format: `table` (default), `json`, `csv`
- `--proc, -p` - Filter by procedure type
- `--light, -l` - Filter by light status
- `--limit, -n` - Limit number of rows
- `--mode, -m` - Display mode: `default`, `metrics`, `compact`

**Examples:**
```bash
# Default table view
python3 process_and_analyze.py show-history 67

# JSON export with filters
python3 process_and_analyze.py show-history 67 --proc IVg --format json

# CSV export with limit
python3 process_and_analyze.py show-history 67 --limit 50 --format csv > data.csv

# Metrics mode with JSON
python3 process_and_analyze.py show-history 67 --mode metrics --format json
```

### inspect-manifest

Inspect staged manifest data with filtering.

**Syntax:**
```bash
python3 process_and_analyze.py inspect-manifest [OPTIONS] --format <format>
```

**Options:**
- `--format, -f` - Output format: `table` (default), `json`, `csv`
- `--proc, -p` - Filter by procedure type
- `--chip, -c` - Filter by chip number
- `--limit, -n` - Number of rows to display (default: 20)

**Examples:**
```bash
# Default table view
python3 process_and_analyze.py inspect-manifest --chip 67

# JSON export for chip
python3 process_and_analyze.py inspect-manifest --chip 67 --format json

# CSV export for procedure
python3 process_and_analyze.py inspect-manifest --proc IVg --format csv > ivg_manifest.csv

# Large dataset export
python3 process_and_analyze.py inspect-manifest --limit 1000 --format json > full_manifest.json
```

---

## Usage Examples

### Example 1: Quick Data Exploration

```bash
# View recent experiments in terminal
python3 process_and_analyze.py show-history 67 --limit 10

# Check for specific procedure
python3 process_and_analyze.py show-history 67 --proc IVg

# Inspect manifest for chip
python3 process_and_analyze.py inspect-manifest --chip 67 --limit 20
```

### Example 2: Data Export for Analysis

```bash
# Export full history to CSV
python3 process_and_analyze.py show-history 67 --format csv > Alisson67_history.csv

# Export IVg experiments only
python3 process_and_analyze.py show-history 67 --proc IVg --format csv > ivg_data.csv

# Export manifest data
python3 process_and_analyze.py inspect-manifest --format csv > manifest.csv
```

### Example 3: JSON for Scripting

```bash
# Get metadata about chip
python3 process_and_analyze.py show-history 67 --format json | jq '.metadata'

# Extract experiment count
python3 process_and_analyze.py show-history 67 --format json | jq '.metadata.total_experiments'

# Get date range
python3 process_and_analyze.py show-history 67 --format json | jq '.metadata.date_range'
```

### Example 4: Filtering with jq

```bash
# Get all IVg experiments
python3 process_and_analyze.py show-history 67 --format json | \
  jq '.data[] | select(.proc == "IVg")'

# Extract CNP voltages
python3 process_and_analyze.py show-history 67 --format json | \
  jq '.data[] | select(.cnp_voltage != null) | {seq, date, cnp_voltage}'

# Count experiments by procedure
python3 process_and_analyze.py show-history 67 --format json | \
  jq '.data | group_by(.proc) | map({proc: .[0].proc, count: length})'

# Get experiments with high CNP
python3 process_and_analyze.py show-history 67 --format json | \
  jq '.data[] | select(.cnp_voltage > 0.5) | {seq, cnp_voltage}'
```

### Example 5: Data Quality Checks

```bash
# Check for failed experiments
python3 process_and_analyze.py inspect-manifest --format json | \
  jq '[.data[] | select(.status == "failed")] | length'

# Find experiments with missing wavelength
python3 process_and_analyze.py show-history 67 --format json | \
  jq '[.data[] | select(.wavelength_nm == null)] | length'

# List all unique procedures
python3 process_and_analyze.py show-history 67 --format json | \
  jq '[.data[].proc] | unique'
```

### Example 6: CSV Formatting

```bash
# Pretty-print CSV in terminal
python3 process_and_analyze.py show-history 67 --format csv | column -t -s,

# Convert CSV to TSV (tab-separated)
python3 process_and_analyze.py show-history 67 --format csv | tr ',' '\t'

# Count CSV rows (excluding header)
python3 process_and_analyze.py show-history 67 --format csv | tail -n +2 | wc -l
```

---

## JSON Format Details

### Structure

All JSON output follows this consistent structure:

```json
{
  "metadata": {
    // Command-specific metadata
    "chip": "string",
    "total_experiments": int,
    "filters_applied": ["string"],
    "title": "string",
    "row_count": int
  },
  "data": [
    // Array of data objects
    {
      "column1": value1,
      "column2": value2,
      ...
    }
  ]
}
```

### Metadata Fields

#### show-history Metadata

```json
{
  "metadata": {
    "chip": "Alisson67",
    "chip_number": 67,
    "chip_group": "Alisson",
    "total_experiments": 90,
    "date_range": "2025-10-14 to 2025-10-21",
    "num_days": 8,
    "filters_applied": ["proc=IVg", "limit=20"],
    "title": "Alisson67 Experiment History",
    "row_count": 20
  }
}
```

#### inspect-manifest Metadata

```json
{
  "metadata": {
    "manifest_path": "data/02_stage/raw_measurements/_manifest/manifest.parquet",
    "total_rows": 860,
    "filtered_rows": 90,
    "showing_rows": 20,
    "filters": ["chip=67"],
    "title": "Manifest Data",
    "row_count": 20
  }
}
```

### Data Type Handling

**Null Values:**
```json
{
  "voltage": null,          // Python None → JSON null
  "current": null,          // NaN → null
  "wavelength_nm": null     // Inf → null
}
```

**Numbers:**
```json
{
  "seq": 89,                // Integer
  "voltage": 0.1,           // Float (rounded to 10 decimals)
  "current": 1.5e-6,        // Scientific notation
  "wavelength_nm": 455.0    // Float
}
```

**Strings:**
```json
{
  "proc": "IVg",
  "date": "2025-10-21",
  "datetime_local": "2025-10-21 13:19:19"
}
```

**Booleans:**
```json
{
  "has_light": false
}
```

### Nested Data

JSON preserves nested structures:

```json
{
  "validation_messages": ["warning1", "warning2"],
  "metadata": {
    "sensor": "Keithley",
    "version": "1.0"
  }
}
```

---

## CSV Format Details

### Structure

CSV files include:
1. **Header row** - Column names
2. **Data rows** - Values separated by commas

```csv
column1,column2,column3
value1,value2,value3
value1,value2,value3
```

### Null Handling

Null values represented as **empty strings**:

```csv
seq,voltage,current
1,0.5,1.5e-6
2,,2.3e-6
3,0.3,
```

### Comma Escaping

Values containing commas are **automatically quoted**:

```csv
summary,value
"IVg, dark, 455nm",0.5
"It, light, 365nm",0.3
```

### Nested Column Handling

Nested columns (List, Struct) are **automatically stringified**:

```csv
validation_messages,proc
"[warning1, warning2]",IVg
"[error1]",ITS
,IV
```

### UTF-8 Encoding

CSV supports UTF-8 characters:

```csv
name,value
Naño,1.5
Müller,2.3
北京,3.1
```

---

## Scripting and Automation

### Python Scripts

```python
import json
import subprocess

# Get JSON data
result = subprocess.run(
    ["python3", "process_and_analyze.py", "show-history", "67", "--format", "json"],
    capture_output=True,
    text=True
)

data = json.loads(result.stdout)

# Process metadata
print(f"Chip: {data['metadata']['chip']}")
print(f"Total experiments: {data['metadata']['total_experiments']}")

# Process data
ivg_count = sum(1 for row in data['data'] if row['proc'] == 'IVg')
print(f"IVg experiments: {ivg_count}")

# Filter and analyze
cnp_voltages = [row['cnp_voltage'] for row in data['data']
                if row.get('cnp_voltage') is not None]
if cnp_voltages:
    avg_cnp = sum(cnp_voltages) / len(cnp_voltages)
    print(f"Average CNP: {avg_cnp:.3f} V")
```

### Bash Scripts

```bash
#!/bin/bash

# Extract experiment counts
CHIP=67
OUTPUT=$(python3 process_and_analyze.py show-history $CHIP --format json)

TOTAL=$(echo "$OUTPUT" | jq '.metadata.total_experiments')
IVG_COUNT=$(echo "$OUTPUT" | jq '[.data[] | select(.proc == "IVg")] | length')

echo "Chip $CHIP:"
echo "  Total experiments: $TOTAL"
echo "  IVg experiments: $IVG_COUNT"

# Check for errors
FAILED=$(python3 process_and_analyze.py inspect-manifest --chip $CHIP --format json | \
  jq '[.data[] | select(.status == "failed")] | length')

if [ "$FAILED" -gt 0 ]; then
    echo "Warning: $FAILED failed experiments"
    exit 1
fi
```

### CI/CD Integration

```yaml
# .github/workflows/data-quality.yml
name: Data Quality Checks

on: [push]

jobs:
  check-data:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Check for failed experiments
        run: |
          FAILED=$(python3 process_and_analyze.py inspect-manifest --format json | \
            jq '[.data[] | select(.status == "failed")] | length')

          if [ "$FAILED" -gt 10 ]; then
            echo "Error: Too many failed experiments ($FAILED)"
            exit 1
          fi

      - name: Export latest data
        run: |
          python3 process_and_analyze.py show-history 67 --format json > artifacts/history.json
          python3 process_and_analyze.py show-history 67 --format csv > artifacts/history.csv

      - uses: actions/upload-artifact@v3
        with:
          name: data-exports
          path: artifacts/
```

---

## External Tool Integration

### jq (JSON Query Tool)

**Install:**
```bash
# macOS
brew install jq

# Ubuntu/Debian
apt-get install jq
```

**Examples:**
```bash
# Pretty-print JSON
python3 process_and_analyze.py show-history 67 --format json | jq '.'

# Extract metadata
python3 process_and_analyze.py show-history 67 --format json | jq '.metadata'

# Filter data
python3 process_and_analyze.py show-history 67 --format json | jq '.data[] | select(.proc == "IVg")'

# Create custom output
python3 process_and_analyze.py show-history 67 --format json | \
  jq '.data[] | {seq, proc, voltage, cnp: .cnp_voltage}'

# Group and aggregate
python3 process_and_analyze.py show-history 67 --format json | \
  jq '.data | group_by(.proc) | map({proc: .[0].proc, count: length, avg_cnp: (map(.cnp_voltage | select(. != null)) | add / length)})'
```

### column (CSV Formatter)

**Examples:**
```bash
# Pretty-print CSV
python3 process_and_analyze.py show-history 67 --format csv | column -t -s,

# Align columns
python3 process_and_analyze.py show-history 67 --format csv | column -t -s, -o ' | '
```

### csvkit (CSV Tools)

**Install:**
```bash
pip install csvkit
```

**Examples:**
```bash
# CSV statistics
python3 process_and_analyze.py show-history 67 --format csv | csvstat

# CSV to JSON
python3 process_and_analyze.py show-history 67 --format csv | csvjson

# Filter CSV
python3 process_and_analyze.py show-history 67 --format csv | csvgrep -c proc -m IVg
```

### pandas (Python Data Analysis)

```python
import pandas as pd
import subprocess
import json

# Load JSON data
result = subprocess.run(
    ["python3", "process_and_analyze.py", "show-history", "67", "--format", "json"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)

# Convert to DataFrame
df = pd.DataFrame(data['data'])

# Analyze
print(df.describe())
print(df.groupby('proc').size())

# Plot
import matplotlib.pyplot as plt
df['cnp_voltage'].dropna().hist()
plt.xlabel('CNP Voltage (V)')
plt.show()
```

---

## Best Practices

### 1. Choose the Right Format

**Use `table` (default) when:**
- ✅ Interactive terminal use
- ✅ Quick data inspection
- ✅ Visual presentation needed

**Use `json` when:**
- ✅ Scripting and automation
- ✅ Complex data structures
- ✅ Piping to jq or other tools
- ✅ Preserving data types important

**Use `csv` when:**
- ✅ Spreadsheet analysis needed
- ✅ Simple flat data
- ✅ Sharing with non-technical users
- ✅ Excel/Google Sheets import

### 2. Combine Filters for Efficiency

```bash
# Good: Filter before export
python3 process_and_analyze.py show-history 67 --proc IVg --limit 100 --format json

# Less efficient: Export all then filter
python3 process_and_analyze.py show-history 67 --format json | jq '.data[] | select(.proc == "IVg")'
```

### 3. Use Limit for Large Datasets

```bash
# Avoid exporting huge datasets
python3 process_and_analyze.py show-history 67 --limit 1000 --format json

# Or use filters
python3 process_and_analyze.py show-history 67 --proc IVg --format json
```

### 4. Validate JSON Before Processing

```bash
# Validate JSON
python3 process_and_analyze.py show-history 67 --format json | python3 -m json.tool >/dev/null

# If valid, process
if python3 process_and_analyze.py show-history 67 --format json | python3 -m json.tool >/dev/null 2>&1; then
    echo "Valid JSON"
else
    echo "Invalid JSON"
fi
```

### 5. Save Exports with Timestamps

```bash
# Add timestamp to exports
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
python3 process_and_analyze.py show-history 67 --format json > "history_${TIMESTAMP}.json"
python3 process_and_analyze.py show-history 67 --format csv > "history_${TIMESTAMP}.csv"
```

---

## Troubleshooting

### Issue: Invalid Format Error

**Error:**
```
Error: Unknown format: 'jsn'. Valid formats: csv, json, table
```

**Solution:** Check format name spelling
```bash
# Wrong
python3 process_and_analyze.py show-history 67 --format jsn

# Correct
python3 process_and_analyze.py show-history 67 --format json
```

### Issue: JSON Parsing Failed

**Error:**
```
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Solution:** Check if command produced output
```bash
# Debug: Check raw output
python3 process_and_analyze.py show-history 67 --format json

# May need to redirect stderr
python3 process_and_analyze.py show-history 67 --format json 2>/dev/null | jq '.'
```

### Issue: CSV Parsing Error

**Error:**
```
csv.Error: line contains NUL
```

**Solution:** Ensure clean CSV output
```bash
# Check for binary data
python3 process_and_analyze.py show-history 67 --format csv | file -

# Save and inspect
python3 process_and_analyze.py show-history 67 --format csv > test.csv
head test.csv
```

### Issue: Empty Result Set

**Symptom:** No data in output

**Solution:** Check filters and chip existence
```bash
# Check if chip exists
python3 process_and_analyze.py show-history 67

# Check filter results
python3 process_and_analyze.py show-history 67 --proc IVg --format json | jq '.metadata.total_experiments'
```

### Issue: Large Export Hangs

**Symptom:** Command takes too long

**Solution:** Use limit or filters
```bash
# Add limit
python3 process_and_analyze.py show-history 67 --limit 100 --format json

# Filter by procedure
python3 process_and_analyze.py show-history 67 --proc IVg --format json
```

---

## API Reference

### Formatter Classes

Located in `src/cli/formatters.py`

#### OutputFormatter (Abstract Base)

```python
class OutputFormatter(ABC):
    @abstractmethod
    def format_dataframe(
        self,
        df: pl.DataFrame,
        title: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format DataFrame for output."""

    @abstractmethod
    def format_summary(self, data: Dict[str, Any]) -> str:
        """Format summary statistics."""
```

#### get_formatter()

```python
def get_formatter(format_name: str) -> OutputFormatter:
    """
    Get formatter instance by name.

    Args:
        format_name: "table", "json", "csv", or alias

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If format name unknown
    """
```

#### list_formatters()

```python
def list_formatters() -> List[str]:
    """
    List available formatter names.

    Returns:
        List of format names: ['csv', 'json', 'table']
    """
```

#### register_formatter()

```python
def register_formatter(
    name: str,
    formatter_class: Type[OutputFormatter]
) -> None:
    """
    Register a custom formatter.

    Args:
        name: Format name (used with --format)
        formatter_class: Formatter class (must inherit OutputFormatter)
    """
```

### Usage in Custom Code

```python
from src.cli.formatters import get_formatter
import polars as pl

# Create data
df = pl.DataFrame({
    "seq": [1, 2, 3],
    "proc": ["IVg", "ITS", "IV"],
    "voltage": [0.5, -0.3, 1.2],
})

# Get formatter
formatter = get_formatter("json")

# Format data
output = formatter.format_dataframe(
    df,
    title="My Data",
    metadata={"chip": 67, "total": 3}
)

# Print or save
print(output)
```

---

## See Also

- [CLAUDE.md](../CLAUDE.md) - Main documentation
- [OUTPUT_FORMATTERS_PLAN.md](OUTPUT_FORMATTERS_PLAN.md) - Implementation plan
- [OUTPUT_FORMATTERS_TEST_RESULTS.md](OUTPUT_FORMATTERS_TEST_RESULTS.md) - Test coverage
- [CLI_PLUGIN_SYSTEM.md](CLI_PLUGIN_SYSTEM.md) - Command plugin system

---

**Questions or Issues?** Check the troubleshooting section or open an issue!
