# Upstream Measurement System Documentation

This document describes the `laser_setup` measurement system that generates raw CSV files in `data/01_raw/`. Understanding its architecture, limitations, and evolution strategy is critical for maintaining robust data processing in `optothermal_processing`.

**Last Updated**: 2025-10-29

---

## Architecture Overview

### System Components

The measurement system is built on PyMeasure and consists of:

**Instruments** (`laser_setup/instruments/`)
- **Keithley Sourcemeter**: Provides voltage sourcing and current measurement
  - Data format: `:READ?` relative timestamps (seconds since sweep start)
  - Timing precision: ~milliseconds
  - Reference: `laser_setup/instruments/keithley.py:39`

- **PT100 Temperature Sensors**: Stream temperature data via serial
  - Data format: Millisecond timestamps
  - Runs in independent thread
  - Reference: `laser_setup/instruments/serial.py:52`

- **TENMA Power Supply**: Voltage/current control with hardware validation
  - Safe ranges enforced at instrument level
  - Reference: `laser_setup/instruments/tenma.py:18-39`

- **Laser Controller**: Laser voltage/power control

**Instrument Management**
- `InstrumentManager` handles connection setup with fallback strategies
- Robust reconnection logic for dropped connections
- Reference: `laser_setup/instruments/manager.py:134-169`

### Procedure Framework

All measurements inherit from `BaseProcedure` (`laser_setup/procedures/BaseProcedure.py:44`):
- Defines parameter validation and sweep execution
- Includes `procedure_version` metadata (stored with each run)
- Provides `self.should_stop()` for graceful abort handling

**Implemented Procedures**:
- **IV**: Current-Voltage sweeps (includes laser burn-in period)
- **IVg**: Gate voltage sweeps
- **IVgT**: Gate sweeps with temperature variation
- **It**: Current vs time with temperature control (clicker stabilization delay)
- **It2**: Three-phase current logging (recently added)
- **ITt**: Current-Temperature-time sweeps
- **LaserCalibration**: Laser power calibration with fiber coupling metadata
- **Tt**: Temperature-time monitoring

### File Generation Pipeline

**Output Format**:
```
#Parameters:
<key>: <value>

#Metadata:
<key>: <value>

#Data:
<column_headers>
<data_rows>
```

**Filename Convention**:
- Controlled by `CONFIG.Filename` template (`laser_setup/assets/templates/config.yaml:155-160`)
- Default pattern: `<Procedure>YYYY-MM-DD_#.csv`
- Chip group/number stored in **headers**, not filenames
- Files organized in dated folders

**Writing Process**:
- Uses PyMeasure's `Results` class
- Headers written at sweep start
- Data rows appended incrementally during measurement
- File parsing utility: `read_pymeasure()` in `laser_setup/utils.py:175`

---

## Known Limitations

### Timing and Synchronization

**Timestamp Semantics**:
- Timestamps represent **"time since sweep start"**, NOT absolute wall-clock time
- NOT acquisition midpoints—use caution for integration windows
- Precision: Effectively milliseconds (limited by Python sleep intervals)

**Cross-Instrument Synchronization**:
- **NO shared clock source** between instruments
- PT100 threads and Keithley buffers run independently
- Jitter dominated by Python thread scheduling
- **Implication**: Cannot reliably correlate sub-second events across instruments
- **Workaround (if needed)**: Post-process resample everything to Keithley clock

**Recommendation for optothermal_processing**:
- Plot axis labels should say "Time since sweep start (s)"
- Document that cross-procedure temporal correlations are approximate
- Add warnings if sub-second synchronization is attempted

### Data Quality Issues

**Measurement Failures**:
1. **Instrument disconnections**:
   - Handled by `InstrumentManager` fallback logic
   - Usually recovers gracefully with log warnings

2. **User aborts (Ctrl+C, GUI stop button)**:
   - Produces **truncated CSVs** with only completed rows
   - NO explicit error flag in file (only log messages)
   - File appears valid but incomplete

3. **No automatic validation**:
   - Physical constraints (current limits, voltage compliance) not enforced per-chip
   - Range checks exist in code but not linked to chip-specific safe operating areas

**Recommendation for optothermal_processing**:
- Add truncation detection: compare actual rows vs expected from sweep parameters
- Add `is_complete` boolean field to `manifest.parquet`
- Flag incomplete runs in chip histories with warning indicators
- Validate measurements against chip-specific safe ranges from `config/chip_params.yaml`

### Known Transient Artifacts

Procedures include intentional stabilization periods that should be excluded from analysis:

1. **Laser burn-in** (IV procedure):
   - Location: `laser_setup/procedures/IV.py:104-110`
   - Purpose: Allow laser output to stabilize before measurement
   - Duration: Configurable parameter in sweep settings

2. **Thermal stabilization** (It procedure):
   - Location: `laser_setup/procedures/It.py:93-101`
   - Purpose: Wait for temperature controller to reach setpoint
   - Duration: "Clicker delay" parameter

3. **Instrument settling**:
   - General issue: First few points may show transients from voltage step changes

**Recommendation for optothermal_processing**:
- Parse burn-in/stabilization parameters from CSV headers
- Add `exclude_initial_rows` or `burn_in_seconds` to manifest
- Plotting functions should automatically skip transient regions
- Add `has_burn_in` boolean field for filtering

---

## Schema Evolution Strategy

### Current Versioning System

**Procedure Version Tracking**:
- Every procedure carries `procedure_version` parameter (e.g., `"1.2"`)
- Stored in `#Parameters:` section of each CSV
- Currently **not validated** by downstream pipeline—relies on analyst interpretation

**Header Structure Stability**:
- The three-section header format (`#Parameters:/#Metadata:/#Data:`) is **stable**
- All new procedures MUST maintain this format (required by `read_pymeasure()`)
- Backwards compatibility: Old CSVs keep old schemas; readers parse headers dynamically

### Planned Evolution

**When Schema Changes Are Needed**:
1. Bump `procedure_version` in procedure class
2. Add explicit `#SchemaVersion: x.y` tag to CSV header
   - Implementation location: Patch `laser_setup/patches.py` where `Results.__init__` is overridden
3. Document changes in upstream schema registry

**Proposed Schema Registry** (upstream, not yet implemented):
- YAML mapping: `version → expected columns/types`
- Enables validation at measurement time
- Helps analysts understand compatibility

### Integration with optothermal_processing

**Current State**:
- `config/procedures.yml` defines expected schemas
- Single schema per procedure type (no version awareness)
- Staging fails if unexpected columns appear

**Recommended Enhancements**:
1. **Read `procedure_version` from CSV headers** during staging
2. **Add `procedure_version` field to `manifest.parquet`** schema
3. **Create `config/schema_registry.yaml`**:
   ```yaml
   IV:
     "1.0":
       Parameters: [V1, V2, Vstep, ...]
       Data: [time, voltage, current]
     "1.1":
       Parameters: [V1, V2, Vstep, burn_in_seconds, ...]
       Data: [time, voltage, current, temperature]
   ```
4. **Version-aware validation**: Select schema based on CSV's declared version
5. **Graceful degradation**: Warn on unknown versions but attempt parsing

**Benefits**:
- Pipeline continues working when upstream adds fields
- Analyst can query "which experiments used old calibration procedure?"
- Automated detection of schema drift

---

## Roadmap and Future Changes

### Recently Added

**It2 Procedure** (three-phase current logging):
- Status: Implemented upstream, NOT YET SUPPORTED in optothermal_processing
- Required action: Add schema to `config/procedures.yml` and create plotting function
- Reference implementation: `src/plotting/its.py` (similar time-series structure)

### Planned Enhancements (Upstream)

**TUI Monitoring** (referenced in `TUI_PLAN.md`):
- Textual/plotext-based terminal UI for live experiment monitoring
- May produce new metadata about user interactions or mid-run annotations
- No schema impact expected (logs separate from CSV data)

**Potential Multi-Dimensional Sweeps**:
- Example: Vg × wavelength × temperature
- Current architecture supports via nested procedures
- Schema impact: Would require either:
  - Flattened data (one row per combination) ← Preferred, pipeline-compatible
  - Nested result files ← Would require pipeline redesign
- **Recommendation**: If this is planned, request flattened format now

### Calibration and Traceability (Future)

**Current Gaps**:
- Instrument serial numbers, firmware versions not recorded
- Calibration dates not linked to measurements
- No automated linkage between `LaserCalibration` runs and subsequent experiments

**Potential Additions**:
- Add instrument metadata to `#Metadata:` section (available via `InstrumentManager`)
- Include `calibration_run_id` reference in experiment headers
- Timestamp calibration files for automatic "active calibration" lookup

**optothermal_processing Impact**:
- Would enable power normalization based on calibration curves
- Requires `calibration_run_id` field in manifest
- Plotting functions could optionally apply calibration corrections

### Environmental Metadata (Future)

**Not Currently Captured**:
- Lab temperature, humidity during measurements
- Ambient light conditions
- Sample mounting details

**Potential Use Cases**:
- Diagnose unexpected variability
- Correlate device performance with environmental factors
- Reproducibility documentation for publications

**Implementation Notes**:
- Could add as optional parameters in procedure definitions
- Manual entry via GUI or automatic via additional sensors
- Pipeline would treat as standard metadata columns

### Hardware Constraint Enforcement (Under Discussion)

**Current State**:
- Safe ranges hardcoded in instrument drivers (e.g., TENMA voltage clamps)
- No per-chip or per-device derating

**Potential Enhancement**:
- Temperature ramp rate limits (currently no guard against aggressive cycling)
- Chip-specific safe operating areas (max current density, voltage breakdown)
- Automated shutdown on constraint violation

**optothermal_processing Impact**:
- Validation could check measured values against declared safe ranges
- Add `constraint_violations` field to manifest
- Flag anomalous measurements for review

---

## File Organization and Naming

### Current Convention

**Directory Structure** (in `data/01_raw/`):
- Dated folders: `YYYY-MM-DD/`
- Or experiment-specific folders (analyst-controlled)
- No hierarchical wafer/die/device structure

**Filename Pattern**:
- Template-driven: `<Procedure>YYYY-MM-DD_#.csv`
- Sequential numbering within day (`#` auto-increments)
- Chip identification in **headers only** (not in filename)

**In-Header Identification**:
```
#Parameters:
chip_group: Alisson
chip_number: 67

#Metadata:
wavelength: 640
...
```

### Potential Changes

**Hierarchical Organization** (if requested):
- Could implement: `01_raw/{wafer_id}/{die_id}/{device_id}/`
- Requires: Config template changes in `laser_setup/assets/templates/config.yaml`
- Pipeline impact: Path parsing logic would need update

**Chip-in-Filename** (alternative):
- Pattern: `{ChipGroup}{ChipNumber}_{FileIndex}.csv`
- Benefit: Easier manual file identification
- Risk: Redundancy if also in header (prefer header as source of truth)

**Recommendation**:
- Keep current system (header-based identification) for robustness
- If hierarchy needed, coordinate with upstream before implementation
- optothermal_processing can adapt—staging already parses paths dynamically

---

## Integration Points for optothermal_processing

### Critical Dependencies

**Must Remain Stable**:
1. Three-section header format (`#Parameters:/#Metadata:/#Data:`)
2. `read_pymeasure()` compatibility (shared parsing logic)
3. Unix epoch timestamps in data columns
4. CSV text encoding (UTF-8)

**Can Change** (with coordination):
1. Parameter names and types (handle via schema versioning)
2. Metadata additions (pipeline ignores unknown fields)
3. Directory organization (pipeline scans recursively)
4. Filename patterns (parsing extracts from headers, not filenames)

### Communication Channels

**Error Reporting** (currently one-way):
- Upstream logs to `LogWidget` and log files
- No feedback from pipeline to measurement system
- No automated quarantine workflow

**Potential Bidirectional Integration**:
- optothermal_processing could write validation status JSON files
- Measurement GUI could display pipeline results
- Enable "re-run flagged measurements" workflow

### Real-Time Integration (Future)

**Streaming Validation**:
- optothermal_processing could tail incomplete CSVs
- Provide live feedback during multi-hour experiments
- Alert on: Flatlines, instrument errors, constraint violations

**Implementation Approach**:
1. Create `validate_streaming_csv()` function
2. Watch `01_raw/` for new/modified files
3. Write status to JSON sidecar files
4. Measurement system polls for validation results

**Benefits**:
- Catch issues during experiment, not hours later
- Allow operator intervention before measurement completes
- Reduce wasted time on failed long runs

---

## Recommendations Summary

### High Priority (Implement Soon)
1. ✅ Parse and store `procedure_version` from headers
2. ✅ Detect truncated CSVs (compare row count vs sweep parameters)
3. ✅ Filter transient artifacts (burn-in, stabilization periods)
4. ✅ Document timestamp semantics in plots

### Medium Priority (Plan Architecture)
5. ⚙️ Design calibration linkage system
6. ⚙️ Implement per-chip constraint validation
7. ⚙️ Add It2 procedure support

### Low Priority (Future Enhancement)
8. 🔮 Real-time validation hooks
9. 🔮 Multi-experiment relationship tracking
10. 🔮 Environmental metadata capture

### Communication Needed
- Confirm multi-dimensional sweep format preference (flattened vs nested)
- Request `#SchemaVersion` tag in future CSV outputs
- Discuss bidirectional error reporting requirements
- Clarify instrument metadata capture priority

---

## References

**Upstream Code Locations** (laser_setup repository):
- BaseProcedure: `laser_setup/procedures/BaseProcedure.py:44`
- Keithley interface: `laser_setup/instruments/keithley.py:39`
- PT100 sensors: `laser_setup/instruments/serial.py:52`
- Instrument manager: `laser_setup/instruments/manager.py:134-169`
- Config template: `laser_setup/assets/templates/config.yaml:155-160`
- CSV parser: `laser_setup/utils.py:175`

**Related Documentation**:
- optothermal_processing architecture: `CLAUDE.md`
- Plotting implementation: `docs/PLOTTING_IMPLEMENTATION_GUIDE.md`
- CLI plugin system: `docs/CLI_PLUGIN_SYSTEM.md`
- Procedure schemas: `config/procedures.yml`
- Chip parameters: `config/chip_params.yaml`

---

**Maintenance Note**: Update this document when:
- New procedures are added upstream
- Schema changes are deployed
- Timing/synchronization improvements are made
- File organization conventions change
- Integration interfaces are established
