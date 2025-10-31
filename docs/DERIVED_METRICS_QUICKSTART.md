# Derived Metrics Quickstart

## ✅ Core Infrastructure - COMPLETED

The foundational infrastructure for the derived metrics pipeline is now in place!

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

## Usage Examples (Once Extractors Implemented)

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

## CLI Integration (To Be Implemented)

Future CLI commands will look like:

```bash
# Extract all metrics
python3 process_and_analyze.py derive-all-metrics

# Extract for specific procedures
python3 process_and_analyze.py derive-all-metrics --proc IVg,It

# Enrich chip history
python3 process_and_analyze.py enrich-history 67

# View enriched history
python3 process_and_analyze.py show-history 67 --enriched
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

## Questions?

The core infrastructure is complete and tested. You can now:

1. **Implement CNP extractor** - I can guide you through this
2. **Implement photoresponse extractor** - Complete example already documented
3. **Add CLI commands** - Connect to existing Typer CLI
4. **Test on real data** - Run on your Chip 67 measurements

What would you like to implement first?
