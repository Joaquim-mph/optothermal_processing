# Derived Metrics Quickstart

**Last Updated:** October 31, 2025
**Status:** ✅ FULLY IMPLEMENTED (v3.0)

## ✅ Complete System - Production Ready

The derived metrics pipeline is fully implemented and production-ready!

## What Was Created

### 1. Data Models (`src/models/derived_metrics.py`)

**DerivedMetric** - Pydantic schema for storing derived analytical results:
- Links to source measurement via `run_id` (foreign key to manifest.parquet)
- Polymorphic value storage (float, string, or JSON)
- Provenance tracking (extraction method, version, timestamp)
- Quality indicators (confidence score, flags)
- Automatic field normalization (run_id lowercase, chip_group titlecase, metric_name lowercase)

**Helper functions:**
- `metric_display_name()` - Human-readable names
- `format_metric_value()` - Smart formatting with units

### 2. Base Extractor (`src/derived/extractors/base.py`)

**MetricExtractor** - Abstract base class for all extractors:
- `applicable_procedures` - Which procedures this extractor handles
- `metric_name` - Unique identifier
- `metric_category` - Organization category
- `extract()` - Core extraction logic
- `validate()` - Quality checks

**Helper functions:**
- `safe_get_column()` - Safe DataFrame column access
- `compute_confidence()` - Calculate confidence from checks
- `build_flags()` - Build flag string from failed checks

### 3. Pipeline Orchestration (`src/derived/metric_pipeline.py`)

**MetricPipeline** - Orchestrates metric extraction:
- Loads manifest.parquet to find measurements
- Filters by procedure, chip, etc.
- Runs applicable extractors (sequential or parallel)
- Saves results to `data/03_derived/_metrics/metrics.parquet`
- Creates enriched chip histories with metrics as columns

**Key methods:**
- `derive_all_metrics()` - Extract all metrics (with parallel support)
- `enrich_chip_history()` - Add metrics to chip history
- `enrich_all_chip_histories()` - Process all chips

## Directory Structure

```
src/
├── models/
│   └── derived_metrics.py          ✓ Pydantic schema
└── derived/
    ├── __init__.py                  ✓ Package exports
    ├── metric_pipeline.py           ✓ Orchestration logic
    └── extractors/
        ├── __init__.py              ✓ Extractor exports
        └── base.py                  ✓ Base class & helpers

data/
└── 03_derived/                      (Created automatically)
    ├── _metrics/
    │   └── metrics.parquet          (All derived metrics)
    └── chip_histories_enriched/
        └── {chip}_history.parquet   (Histories + metrics)
```

## Testing Results

✅ All imports successful
✅ DerivedMetric model validation working
✅ Field normalization working
✅ Helper functions working
✅ MetricPipeline initialization working

## Next Steps

Now you're ready to implement actual extractors! Choose one:

### Option 1: CNP Extractor (Charge Neutrality Point)
- **Input**: IVg or VVg measurements
- **Output**: Voltage where resistance is maximum
- **Difficulty**: Medium
- **See**: `docs/ADDING_NEW_METRICS_GUIDE.md` (Mobility example)

### Option 2: Photoresponse Extractor (ΔI_ds, ΔV_ds)
- **Input**: It or Vt measurements with VL column
- **Output**: Current/voltage change when light is on
- **Difficulty**: Easy
- **See**: `docs/DERIVED_METRICS_ARCHITECTURE.md` (Complete example)

### Option 3: Custom Extractor
- **See**: `docs/ADDING_NEW_METRICS_GUIDE.md` for step-by-step guide

## Implementation Pattern

```python
# 1. Create extractor in src/derived/extractors/my_metric.py
from src.derived.extractors.base import MetricExtractor
from src.models.derived_metrics import DerivedMetric
import polars as pl

class MyMetricExtractor(MetricExtractor):
    @property
    def applicable_procedures(self):
        return ["IVg"]  # Which procedures

    @property
    def metric_name(self):
        return "my_metric"

    @property
    def metric_category(self):
        return "electrical"

    def extract(self, measurement: pl.DataFrame, metadata: dict):
        # Your extraction logic here
        value = compute_something(measurement)

        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=metadata["procedure"],
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=value,
            unit="V",
            extraction_method="my_algorithm",
            extraction_version=metadata["extraction_version"],
            confidence=1.0
        )

    def validate(self, result: DerivedMetric):
        # Quality checks
        return result.value_float is not None

# 2. Register in src/derived/metric_pipeline.py
def _default_extractors(self):
    return [
        MyMetricExtractor(),  # Add here
    ]

# 3. Run pipeline
from src.derived import MetricPipeline
pipeline = MetricPipeline(Path("."))
metrics_path = pipeline.derive_all_metrics()
```

## Usage Examples

```python
from pathlib import Path
from src.derived import MetricPipeline

# Initialize pipeline
pipeline = MetricPipeline(base_dir=Path("."))

# Extract all metrics
metrics_path = pipeline.derive_all_metrics(
    procedures=["IVg", "It"],  # Optional filter
    chip_numbers=[67],          # Optional filter
    parallel=True,              # Use multiprocessing
    workers=6                   # Number of workers
)

# Create enriched history
enriched_path = pipeline.enrich_chip_history(
    chip_number=67,
    chip_group="Alisson"
)

# Enrich all chips
all_paths = pipeline.enrich_all_chip_histories()
```

## CLI Commands (Available Now!)

The complete CLI is implemented and ready to use:

```bash
# Extract all metrics (CNP, photoresponse, laser power)
python3 process_and_analyze.py derive-all-metrics

# Extract for specific procedures
python3 process_and_analyze.py derive-all-metrics --procedures IVg,It

# Extract for specific chip
python3 process_and_analyze.py derive-all-metrics --chip 67

# Preview what would be extracted (dry run)
python3 process_and_analyze.py derive-all-metrics --dry-run

# Force re-extraction (overwrite existing)
python3 process_and_analyze.py derive-all-metrics --force

# Include laser calibration power extraction (enabled by default)
python3 process_and_analyze.py derive-all-metrics --calibrations

# Enrich chip history with metrics
python3 process_and_analyze.py enrich-history 67

# Plot CNP evolution over time
python3 process_and_analyze.py plot-cnp-time 81

# Plot photoresponse vs power
python3 process_and_analyze.py plot-photoresponse 81 power

# Plot photoresponse vs wavelength (with filters)
python3 process_and_analyze.py plot-photoresponse 81 wavelength --vg -0.4

# Plot photoresponse vs gate voltage
python3 process_and_analyze.py plot-photoresponse 81 gate_voltage --wl 660
```

## Architecture Benefits

✅ **Modular**: Each metric is a separate extractor class
✅ **Extensible**: Add new metrics without touching core code
✅ **Traceable**: Full provenance (method, version, timestamp)
✅ **Robust**: Quality checks and confidence scores
✅ **Fast**: Parallel processing support
✅ **Type-safe**: Pydantic validation throughout

## Documentation

- **`DERIVED_METRICS_ARCHITECTURE.md`** - Complete system design
- **`ADDING_NEW_METRICS_GUIDE.md`** - Step-by-step implementation guide
- **`DERIVED_METRICS_QUICKSTART.md`** - This file

## Complete Workflow

Now you can run the entire pipeline:

```bash
# 1. Stage raw data
python3 process_and_analyze.py full-pipeline

# 2. Extract derived metrics
python3 process_and_analyze.py derive-all-metrics

# 3. Generate plots
python3 process_and_analyze.py plot-cnp-time 81
python3 process_and_analyze.py plot-photoresponse 81 power
python3 process_and_analyze.py plot-its 67 --auto
```

## What's Implemented

✅ **Core Infrastructure**
- DerivedMetric Pydantic model
- MetricExtractor base class
- MetricPipeline orchestration
- Registry-based extractor discovery

✅ **Extractors**
- CNPExtractor (Charge Neutrality Point)
- PhotoresponseExtractor (ΔI, ΔV)
- CalibrationMatcher (laser power interpolation)

✅ **CLI Commands**
- `derive-all-metrics` - Extract all metrics
- `enrich-history` - Add metrics to histories
- `plot-cnp-time` - CNP evolution plots
- `plot-photoresponse` - Photoresponse analysis plots

✅ **Plotting Functions**
- CNP vs time plots (`src/plotting/cnp_time.py`)
- Photoresponse vs power/wavelength/gate/time (`src/plotting/photoresponse.py`)
- Integration with chip histories

✅ **Documentation**
- Architecture guide (DERIVED_METRICS_ARCHITECTURE.md)
- Implementation guide (ADDING_NEW_METRICS_GUIDE.md)
- CNP extractor guide (CNP_EXTRACTOR_GUIDE.md)
- This quickstart guide

## Adding New Metrics

Want to add your own metric extractor? See [ADDING_NEW_METRICS_GUIDE.md](ADDING_NEW_METRICS_GUIDE.md) for step-by-step instructions.
