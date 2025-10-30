# YAML-Driven Manifest Columns & Procedure Configuration

## Overview

The staging pipeline now supports **YAML-driven manifest column extraction** and **configurable procedure logic**. This means you can add new procedures or modify existing ones **without touching Python code** - just update `config/procedures.yml`.

## Features

### 1. ManifestColumns Section
Define which parameters should be extracted to the manifest table and what names they should use.

**Benefits:**
- No hardcoded parameter extraction in Python
- Easy to add new procedures
- Consistent naming across procedures
- Automatic type inference from column name suffixes

### 2. Config Section
Configure procedure-specific behavior like light detection logic.

**Benefits:**
- Eliminates hardcoded `if proc == "LaserCalibration"` checks
- Easy to customize procedure behavior
- Self-documenting configuration

## Quick Example

```yaml
procedures:
  IVg:
    Parameters:
      VDS: float
      VG start: float
      VG end: float
      Laser wavelength: float
      Laser voltage: float

    ManifestColumns:
      vds_v: [VDS, Vds, VSD]              # Tries VDS first, then Vds, then VSD
      vg_start_v: [VG start, Vg start]    # Manifest column name: parameter aliases
      vg_end_v: [VG end, Vg end]
      wavelength_nm: [Laser wavelength]   # Type inferred from _nm suffix (float)
      laser_voltage_V: [Laser voltage]    # Type inferred from _V suffix (float)

    Config:
      light_detection: standard            # Use standard light detection logic
```

## ManifestColumns Specification

### Format

```yaml
ManifestColumns:
  manifest_column_name: [Primary Name, Alias 1, Alias 2, ...]
```

### Column Name Conventions

The manifest column name determines the extraction type:

| Suffix Pattern | Type | Examples |
|---|---|---|
| `_v` or `_V` | float | `vds_v`, `laser_voltage_V` |
| `_nm` | float | `wavelength_nm` |
| `_s` | float | `laser_period_s` |
| `_a` or `_A` | float | `current_a` |
| `_step` | float | `vg_step_v`, `vsd_step_v` |
| `_period` | float | `laser_period_s` |
| (no suffix) | string | `optical_fiber`, `sensor_model` |

**Type inference is automatic** - the system extracts floats for voltage/wavelength/current columns, keeps strings for text fields.

### Alias Matching

Aliases are tried **in order** until a match is found:

```yaml
vds_v: [VDS, Vds, VSD, Drain voltage]
```

1. Tries `params["VDS"]`
2. If not found, tries `params["Vds"]`
3. If not found, tries `params["VSD"]`
4. If not found, tries `params["Drain voltage"]`
5. If none match, value is `None`

### Metadata Source

You can extract from both Parameters and Metadata sections:

```yaml
ManifestColumns:
  wavelength_nm: [Laser wavelength]  # From Parameters
  sensor_model: [Sensor model]       # From Metadata
```

The extraction function checks both sources automatically.

### Complete Example: IVg

```yaml
IVg:
  Parameters:
    Irange: float
    VDS: float
    VG start: float
    VG end: float
    VG step: float
    Laser wavelength: float
    Laser voltage: float
    # ... other parameters

  Metadata:
    Start time: datetime

  Data:
    Vg (V): float
    I (A): float

  # Manifest column extraction (optional - has sensible fallback)
  ManifestColumns:
    vds_v: [VDS, Vds, VSD, Drain voltage]
    vg_start_v: [VG start, Vg start]
    vg_end_v: [VG end, Vg end]
    vg_step_v: [VG step, Vg step]
    wavelength_nm: [Laser wavelength]
    laser_voltage_V: [Laser voltage]

  # Procedure-specific configuration (optional)
  Config:
    light_detection: standard  # Options: standard, laser_calibration, none
```

## Config Specification

### Light Detection Modes

```yaml
Config:
  light_detection: <mode>
```

Available modes:

#### `standard` (default for most procedures)
Light is detected if:
- Wavelength parameter exists
- Laser voltage parameter exists and > 0

**Use for**: IVg, IV, ITt, It, etc.

```yaml
IVg:
  Config:
    light_detection: standard
```

#### `laser_calibration`
Light is detected if:
- Wavelength parameter exists
- Laser voltage sweep is defined (start OR end voltage exists)

**Use for**: LaserCalibration procedure

```yaml
LaserCalibration:
  Config:
    light_detection: laser_calibration
```

#### `none`
Always returns `False` for light detection.

**Use for**: Temperature-only procedures (Tt)

```yaml
Tt:
  Config:
    light_detection: none  # Temperature measurement, no light
```

### Fallback Behavior

If `Config` section is omitted, the system uses intelligent fallbacks:

- `LaserCalibration` → `laser_calibration` mode
- `Tt` → `none` mode
- All others → `standard` mode

**This means existing procedures work without modification.**

## Adding a New Procedure

### Step 1: Define Basic Schema

Add the procedure to `config/procedures.yml`:

```yaml
MyNewProcedure:
  Parameters:
    Chip group name: str
    Chip number: int
    VDS: float
    VG: float
    Custom parameter: float
    # ... other parameters

  Metadata:
    Start time: datetime

  Data:
    I (A): float
    t (s): float
```

### Step 2: Add ManifestColumns (Optional)

Define which parameters to extract to the manifest:

```yaml
MyNewProcedure:
  # ... Parameters, Metadata, Data as above

  ManifestColumns:
    vds_v: [VDS, Vds]
    vg_fixed_v: [VG, Vg]
    custom_value: [Custom parameter]
```

**If omitted**: Legacy hardcoded extraction is used as fallback (for backward compatibility).

### Step 3: Add Config (Optional)

Configure procedure behavior:

```yaml
MyNewProcedure:
  # ... as above

  Config:
    light_detection: standard  # or laser_calibration, or none
```

**If omitted**: Sensible defaults are applied based on procedure name.

### Step 4: Test

Run staging with your new procedure:

```bash
python3 process_and_analyze.py stage-all
```

The manifest will automatically include your configured columns!

## Backward Compatibility

### For Procedures Without ManifestColumns

If a procedure doesn't have a `ManifestColumns` section, the system falls back to **legacy hardcoded extraction**:

```python
# Legacy fallback (automatic if ManifestColumns not defined)
manifest_cols = {
    "wavelength_nm": extract_from(["Laser wavelength"]),
    "laser_voltage_V": extract_from(["Laser voltage"]),
    "vds_v": extract_from(["VDS", "Vds", "VSD"]),
    # ... standard columns
}
```

This ensures **existing data processing continues to work** while you migrate procedures to YAML-driven configuration.

### Migration Path

1. **Current state**: Procedures without ManifestColumns use hardcoded fallback ✓
2. **Add ManifestColumns gradually**: Update one procedure at a time
3. **Test each procedure**: Verify manifest contains expected columns
4. **Eventually**: All procedures use YAML configuration (no more hardcoded extraction)

## Examples by Procedure Type

### Voltage Sweep (IVg, IV)

```yaml
IVg:
  ManifestColumns:
    vds_v: [VDS, Vds]
    vg_start_v: [VG start]
    vg_end_v: [VG end]
    vg_step_v: [VG step]
    wavelength_nm: [Laser wavelength]
    laser_voltage_V: [Laser voltage]
  Config:
    light_detection: standard
```

### Time Series (ITt, It)

```yaml
ITt:
  ManifestColumns:
    vds_v: [VDS]
    vg_fixed_v: [VG]
    wavelength_nm: [Laser wavelength]
    laser_voltage_V: [Laser voltage]
    laser_period_s: [Laser ON+OFF period]
  Config:
    light_detection: standard
```

### Calibration (LaserCalibration)

```yaml
LaserCalibration:
  ManifestColumns:
    wavelength_nm: [Laser wavelength]
    laser_voltage_start_v: [Laser voltage start]
    laser_voltage_end_v: [Laser voltage end]
    laser_voltage_step_v: [Laser voltage step]
    optical_fiber: [Optical fiber]
    sensor_model: [Sensor model]  # From Metadata
  Config:
    light_detection: laser_calibration  # Special logic for calibration
```

### Temperature Only (Tt)

```yaml
Tt:
  # No ManifestColumns needed (no measurement parameters to extract)
  Config:
    light_detection: none  # Temperature measurement, no light
```

## Manifest Schema Evolution

### Adding New Columns

To add a new manifest column to an existing procedure:

**Step 1**: Add parameter to YAML:

```yaml
IVg:
  Parameters:
    # ... existing parameters
    New parameter: float  # ADD THIS

  ManifestColumns:
    # ... existing columns
    new_param_v: [New parameter]  # ADD THIS
```

**Step 2**: Run staging - new column automatically appears in manifest!

```bash
python3 process_and_analyze.py stage-all
```

**Old data**: Missing column will be `null`
**New data**: Column will have actual values

### Renaming Parameters

If lab equipment changes parameter names:

**Before**:
```yaml
Parameters:
  Laser wavelength: float
```

**After** (equipment now calls it "Wavelength"):
```yaml
Parameters:
  Wavelength: float  # New name from equipment

ManifestColumns:
  wavelength_nm: [Wavelength, Laser wavelength]  # Try new name first, fallback to old
```

This handles **mixed old/new data** gracefully during transition periods.

## Troubleshooting

### Issue: Manifest column is always null

**Problem**: Parameter name doesn't match any alias

**Solution**: Check parameter name in CSV header, add alias:

```yaml
ManifestColumns:
  vds_v: [VDS, Vds, VSD, Drain voltage, V_DS]  # Add more aliases
```

### Issue: Light detection wrong for my procedure

**Problem**: Default light detection logic doesn't match procedure semantics

**Solution**: Add explicit Config:

```yaml
MyProcedure:
  Config:
    light_detection: none  # Force no light detection
```

### Issue: Need custom column that doesn't exist in parameters

**Problem**: Want to add computed/derived column to manifest

**Current solution**: Add to legacy fallback for now
**Future**: Could extend ManifestColumns to support expressions

```yaml
# Not yet supported (future enhancement):
ManifestColumns:
  vg_range_v:
    expression: "VG end - VG start"  # Computed column
```

### Issue: Procedure not extracting expected columns

**Debug steps**:

1. Check YAML syntax (indentation, colons, brackets)
2. Verify parameter names match exactly (case-sensitive)
3. Test YAML loading:

```python
from src.core.stage_raw_measurements import load_procedures_yaml
from pathlib import Path

specs = load_procedures_yaml(Path("config/procedures.yml"))
print(specs["YourProcedure"].manifest_columns)
```

4. Check manifest after staging:

```python
import polars as pl
manifest = pl.read_parquet("data/02_stage/raw_measurements/_manifest/manifest.parquet")
print(manifest.columns)  # Should include your manifest columns
```

## Best Practices

### 1. Use Consistent Naming

Stick to conventions for manifest column names:

- Voltages: `_v` or `_V` suffix
- Wavelengths: `_nm` suffix
- Times/periods: `_s` suffix
- Currents: `_a` or `_A` suffix

### 2. Order Aliases by Frequency

Put most common parameter names first:

```yaml
vds_v: [VDS, Vds, VSD]  # VDS is most common, try first
```

### 3. Document Unusual Configurations

Add comments for non-obvious configs:

```yaml
MyProcedure:
  Config:
    light_detection: none  # Special case: indirect light measurement via fluorescence
```

### 4. Test New Procedures Incrementally

Don't add 10 procedures at once. Add one, test staging, verify manifest, then add next.

### 5. Keep Fallback for Old Procedures

Don't rush to add ManifestColumns to every procedure. The fallback works fine for procedures that rarely change.

**Prioritize**:
- New procedures being added
- Procedures that frequently need new manifest columns
- Procedures with custom logic (use Config for these)

## Future Enhancements

Potential additions (not yet implemented):

1. **Computed Columns**: Support expressions in ManifestColumns
2. **Conditional Extraction**: Extract column only if condition met
3. **Type Validation**: Validate extracted types match expectations
4. **Custom Extractors**: User-defined extraction functions
5. **Manifest Column Documentation**: Auto-generate docs from YAML

## Migration Checklist

Migrating an existing procedure to YAML-driven config:

- [ ] Copy parameter list from Python to YAML Parameters section
- [ ] Identify which parameters should be in manifest (look at old `event_common` dict)
- [ ] Create ManifestColumns section with appropriate aliases
- [ ] Determine light detection logic, add to Config if non-standard
- [ ] Test staging with sample data
- [ ] Verify manifest contains expected columns
- [ ] Check backward compatibility (old data still processes)
- [ ] Update procedure documentation if needed
- [ ] Remove hardcoded extraction from Python (if applicable)

## Summary

**Before** (hardcoded):
```python
# Python code
vds_v = _get_float(["VDS", "Vds", "VSD"])
vg_start_v = _get_float(["VG start", "Vg start"])
if proc == "LaserCalibration":
    with_light = special_logic()
else:
    with_light = standard_logic()
```

**After** (YAML-driven):
```yaml
# config/procedures.yml
IVg:
  ManifestColumns:
    vds_v: [VDS, Vds, VSD]
    vg_start_v: [VG start, Vg start]
  Config:
    light_detection: standard
```

**Result**: No Python code changes needed when adding procedures or modifying extraction logic!
