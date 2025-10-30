# Schema Validation Guide

## Overview

The staging pipeline now includes comprehensive schema validation that checks CSV files against the `config/procedures.yml` specification. This ensures data quality while supporting schema evolution (backward and forward compatibility).

## Features

### 1. Validation Severity Levels

- **ERROR**: Critical issues that fail in `--strict` mode
  - Missing REQUIRED data columns
  - Missing critical parameters (chip_number, chip_group)

- **WARN**: Important issues logged but non-blocking
  - Missing OPTIONAL columns (added as null automatically)
  - Unmapped CSV columns (potential typos)
  - Missing non-critical parameters

- **INFO**: Informational messages
  - Successful column mapping
  - Extra parameters not in schema

### 2. Schema Evolution Support

#### Problem Scenario
You add a new column (`t (s)`) to the IV procedure, but have 1000 existing IV measurements without this column.

#### Solution
Mark the new column as optional in `config/procedures.yml`:

```yaml
IV:
  Data:
    Vsd (V): float
    I (A): float
    t (s):                    # NEW COLUMN
      type: float
      required: false         # Optional for backward compat
```

**Result**:
- Old measurements → `t (s)` added as null, warning logged, processing continues ✓
- New measurements → `t (s)` validated and populated ✓
- All parquet files have consistent schema (can query on `t` column even for old data)

### 3. YAML Format Options

#### Simple Format (Default)
```yaml
Procedure:
  Parameters:
    Laser wavelength: float
    Chip number: int
  Data:
    I (A): float
    Vsd (V): float
```

#### Extended Format (For Optional Columns)
```yaml
Procedure:
  Parameters:
    Laser wavelength:
      type: float
      required: false        # Optional parameter
  Data:
    I (A): float             # Simple format (required by default)
    t (s):
      type: float
      required: false        # Extended format for optional column
```

**Both formats can be mixed in the same file.**

## Usage

### Command Line

#### Permissive Mode (Default)
```bash
# Logs warnings but continues processing
python3 process_and_analyze.py stage-all

# Example output:
# [warn] IV measurement: optional column 't (s)' not found (will add as null)
# [info] IV measurement: all required columns validated ✓
```

#### Strict Mode
```bash
# Fails on missing REQUIRED columns
python3 process_and_analyze.py stage-all --strict

# Fails with error if critical columns missing:
# [error] Data: required column 'I (A)' not found in CSV
# Schema validation failed in strict mode
```

#### Verbose Mode
```bash
# Show detailed file-by-file validation messages
python3 process_and_analyze.py stage-all --verbose
```

### Python API

```python
from pathlib import Path
from src.models.parameters import StagingParameters
from src.core import run_staging_pipeline

params = StagingParameters(
    raw_root=Path("data/01_raw"),
    stage_root=Path("data/02_stage/raw_measurements"),
    procedures_yaml=Path("config/procedures.yml"),
    strict=True,  # Enable strict validation
    workers=8
)

run_staging_pipeline(params)
```

## Validation Messages Reference

### Example Messages

```
[error] Parameters: critical parameter missing: 'Chip number' (required for all procedures)
  → Fix: Ensure CSV header includes "Chip number" parameter

[warn] Parameters: required parameter 'Laser wavelength' not found (will use null/default)
  → Info: Parameter expected by schema but missing - null will be used

[warn] Data: optional column 't (s)' not found (will add as null for schema consistency)
  → Info: Optional column missing - typed null column added automatically

[warn] Data: unmapped CSV column 'gate_voltage' (suggestion: similar to 'Vg (V)' - potential typo?)
  → Action: Check if column name has typo; if intentional, add synonym rule

[info] Data: unmapped CSV column 'custom_field' (not in YAML schema - will be kept if not using --only-yaml-data)
  → Info: Extra column not in schema - kept unless --only-yaml-data flag used

[info] Parameters: parameter 'Custom_Setting' not in schema (may be procedure-specific or deprecated)
  → Info: Extra parameter - logged for awareness
```

## Best Practices

### 1. Adding New Columns

**Step 1**: Update `config/procedures.yml`
```yaml
YourProcedure:
  Data:
    existing_column: float
    new_column:                    # Mark as optional
      type: float
      required: false
```

**Step 2**: Test staging
```bash
# Should show warnings for old data but succeed
python3 process_and_analyze.py stage-all --verbose
```

**Step 3**: Verify consistency
```python
import polars as pl
df = pl.read_parquet("data/02_stage/raw_measurements/proc=YourProcedure/...")
print(df.columns)  # Should include 'new_column' for all measurements
print(df["new_column"].null_count())  # Shows how many old measurements
```

**Step 4** (Optional): After data migration, mark as required
```yaml
new_column:
  type: float
  required: true  # Now enforced for new data
```

### 2. Production Validation

Use `--strict` mode in production to catch data quality issues early:

```bash
# In CI/CD pipeline or cron job
python3 process_and_analyze.py stage-all --strict --only-yaml-data

# Fails if:
# - Required columns missing
# - Critical parameters missing
# - Schema violations detected
```

### 3. Monitoring Validation Results

Validation metrics are stored in the manifest:

```python
import polars as pl

manifest = pl.read_parquet("data/02_stage/raw_measurements/_manifest/manifest.parquet")

# Check for files with validation issues
issues = manifest.filter(
    (pl.col("validation_errors") > 0) | (pl.col("validation_warnings") > 0)
)

print(issues.select(["source_file", "proc", "validation_errors", "validation_warnings"]))
```

## Migration Example

### Scenario: Add Time Column to IV Procedure

**Before** (1000 existing IV measurements without time):
```
data/01_raw/2024-01-15/chip67_001.csv  → [Vsd (V), I (A)]
data/01_raw/2024-01-15/chip67_002.csv  → [Vsd (V), I (A)]
...
```

**Update Schema**:
```yaml
IV:
  Data:
    Vsd (V): float
    I (A): float
    t (s): {type: float, required: false}  # ADD THIS
```

**After Staging** (all measurements have consistent schema):
```python
# Old measurements
df_old = pl.read_parquet(".../chip67_001.parquet")
print(df_old["t (s)"])  # All null

# New measurements
df_new = pl.read_parquet(".../chip67_150.parquet")
print(df_new["t (s)"])  # Has actual values

# Query works across all data
all_data = pl.read_parquet("data/02_stage/raw_measurements/proc=IV/**/*.parquet")
recent = all_data.filter(pl.col("t (s)").is_not_null())  # Only new measurements
```

## Troubleshooting

### Issue: Too many warnings

**Problem**: Every file shows warnings for optional columns

**Solution**: This is expected during schema evolution. Warnings will stop once old data is processed.

```bash
# Filter warnings in production logs
python3 process_and_analyze.py stage-all 2>&1 | grep -v "optional column"
```

### Issue: Strict mode failing

**Problem**: `--strict` mode fails with missing required columns

**Solution**:
1. Check which columns are failing: look at validation error messages
2. Either:
   - Fix source CSV files to include required columns
   - Mark columns as optional if they're not critical: `required: false`
   - Add synonym rules if column names differ

### Issue: Column name mismatches

**Problem**: CSV has `current_A` but schema expects `I (A)`

**Solution**: Add synonym rule in `src/core/stage_raw_measurements.py`:

```python
YAML_DATA_SYNONYMS: Dict[str, List[str]] = {
    "I (A)": [r"^i$", r"^current(_a)?$", r"^ids?(_a)?$"],  # Add ^current_a$
    ...
}
```

## Schema Specification

### Parameter/Metadata/Data Types

Supported types in YAML:
- `float`: Floating-point number (extracts from strings like "450nm")
- `float_no_unit`: Strict float (no unit parsing)
- `int`: Integer
- `bool`: Boolean (recognizes "1", "true", "yes", "on", "y")
- `datetime`: Date/time (handles ISO format and Unix timestamps)
- `str`: String (default)

### Required vs Optional

**Default behavior**:
- Parameters: Optional by default (missing → null/default)
- Metadata: Optional by default
- Data columns: Optional by default (for backward compatibility)

**To make required**, use extended format:
```yaml
column_name:
  type: float
  required: true
```

**Critical fields** (always required regardless of schema):
- `Chip number` (parameter)
- `Chip group name` (parameter)
- `Start time` (metadata - uses fallback if missing but warns)

## Implementation Details

### Files Modified/Created

1. **New**: `src/core/schema_validator.py` - Validation engine
2. **Modified**: `src/core/stage_raw_measurements.py` - Integration
3. **Modified**: `src/models/parameters.py` - Added `strict` field
4. **Modified**: `src/cli/commands/stage.py` - Added `--strict` flag
5. **Updated**: `config/procedures.yml` - Example optional column

### Validation Flow

```
CSV File
  ↓
Parse Header (params, metadata)
  ↓
Read Data Table (DataFrame)
  ↓
Column Mapping (CSV → YAML names)
  ↓
Schema Validation ← config/procedures.yml
  ├─ Check Parameters
  ├─ Check Metadata
  └─ Check Data Columns
  ↓
Add Missing Optional Columns (as typed nulls)
  ↓
Log Validation Messages (errors, warnings, info)
  ↓
Write Parquet (with validation metrics in manifest)
```

### Performance Impact

- Minimal: Validation adds <5% overhead
- Parallel processing unaffected
- Validation cached per procedure per worker
- No impact on query performance (schema consistency improves it)

## Future Enhancements

Potential improvements (not yet implemented):

1. **YAML-based synonym configuration**: Move `YAML_DATA_SYNONYMS` to YAML file
2. **Validation reports**: Generate summary report of all validation issues
3. **Schema versioning**: Track schema changes over time in manifest
4. **Auto-fix suggestions**: Automatically suggest corrections for common issues
5. **Custom validation rules**: Procedure-specific validation logic in YAML
