# Guide: Adding New Derived Metrics

**Last Updated:** October 31, 2025
**Version:** 3.0+

This guide walks you through adding a new derived metric to the pipeline. We'll use a real example: extracting **mobility (μ)** from IVg measurements.

## Prerequisites

- Derived metrics pipeline implemented (see `DERIVED_METRICS_ARCHITECTURE.md`)
- Understanding of the physical quantity you want to extract
- Access to sample data for testing

## Step-by-Step Process

### Step 1: Define the Metric

**What**: Mobility (μ) - how easily charge carriers move through the material
**Formula**: `μ = (L/W) * (1/C_ox) * gm / V_ds`
- L = channel length
- W = channel width
- C_ox = oxide capacitance
- gm = transconductance (dI/dVg at specific Vg)
- V_ds = drain-source voltage

**Applicable procedures**: IVg (need dI/dVg)
**Output**: Single float value (mobility) in cm²/V·s

### Step 2: Create Extractor Class

Create file: `src/derived/extractors/mobility_extractor.py`

```python
import polars as pl
import numpy as np
from typing import Optional, List
from scipy.signal import savgol_filter
from .base import MetricExtractor
from src.models.derived_metrics import DerivedMetric

class MobilityExtractor(MetricExtractor):
    """
    Extract field-effect mobility from IVg measurements.

    Computes μ = (L/W) * (1/C_ox) * gm_max / V_ds
    where gm_max is the peak transconductance.
    """

    def __init__(
        self,
        L: float = 50e-6,  # Channel length in meters (50 µm default)
        W: float = 200e-6,  # Channel width in meters (200 µm default)
        C_ox: float = 1.15e-8  # Oxide capacitance in F/cm² (SiO2 300nm default)
    ):
        """
        Args:
            L: Channel length in meters
            W: Channel width in meters
            C_ox: Oxide capacitance in F/cm²
        """
        self.L = L
        self.W = W
        self.C_ox = C_ox

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg"]

    @property
    def metric_name(self) -> str:
        return "mobility"

    @property
    def metric_category(self) -> str:
        return "electrical"

    def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
        """Extract mobility from IVg sweep."""

        # Extract gate voltage and drain current
        vg = measurement["Vg (V)"].to_numpy()
        ids = measurement["Ids (A)"].to_numpy()

        # Get V_ds from metadata (constant during IVg sweep)
        vds = metadata.get("vds")
        if vds is None or abs(vds) < 1e-6:
            return None  # Can't compute mobility without V_ds

        # Compute transconductance gm = dI/dVg using Savitzky-Golay filter
        # Window size: 11 points, polynomial order: 3
        window = min(11, len(vg) // 2 * 2 + 1)  # Must be odd
        if window < 5:
            return None  # Not enough points for derivative

        gm = savgol_filter(ids, window_length=window, polyorder=3, deriv=1, delta=np.mean(np.diff(vg)))

        # Find peak transconductance
        gm_max = np.max(np.abs(gm))
        gm_max_idx = np.argmax(np.abs(gm))
        vg_at_gm_max = vg[gm_max_idx]

        # Compute mobility: μ = (L/W) * (1/C_ox) * gm_max / V_ds
        mobility = (self.L / self.W) * (1 / self.C_ox) * gm_max / abs(vds)

        # Convert from m²/V·s to cm²/V·s
        mobility_cm2 = mobility * 1e4

        # Quality checks
        flags = []
        confidence = 1.0

        # Check if gm_max is at edge (might indicate incomplete sweep)
        if gm_max_idx < 5 or gm_max_idx > len(vg) - 5:
            flags.append("GM_MAX_AT_EDGE")
            confidence *= 0.6

        # Check for reasonable mobility range (0.1 to 10000 cm²/V·s for typical FETs)
        if not (0.1 <= mobility_cm2 <= 10000):
            flags.append("UNUSUAL_MOBILITY")
            confidence *= 0.5

        # Check for noisy gm (std > 30% of max)
        gm_std = np.std(gm)
        if gm_std / gm_max > 0.3:
            flags.append("NOISY_GM")
            confidence *= 0.7

        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure="IVg",
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=mobility_cm2,
            unit="cm²/V·s",
            extraction_method="peak_transconductance",
            extraction_version=metadata.get("extraction_version", "unknown"),
            confidence=confidence,
            flags=",".join(flags) if flags else None
        )

    def validate(self, result: DerivedMetric) -> bool:
        """Validate mobility is in physically reasonable range."""
        if result.value_float is None:
            return False

        # Mobility should be positive and less than 100,000 cm²/V·s
        if not (0 < result.value_float < 100000):
            return False

        return True
```

### Step 3: Register Extractor in Pipeline

Edit: `src/derived/metric_pipeline.py`

```python
# Add import at top
from .extractors.mobility_extractor import MobilityExtractor

# Update _default_extractors method
def _default_extractors(self) -> List[MetricExtractor]:
    """Return default set of metric extractors."""
    return [
        CNPExtractor(),
        PhotoresponseExtractor(),
        MobilityExtractor(L=50e-6, W=200e-6, C_ox=1.15e-8),  # ← ADD THIS
        # Add more extractors here as they're developed
    ]
```

### Step 4: Update Enriched History Schema

Edit: `src/derived/metric_pipeline.py` in the `enrich_chip_histories` method

```python
# Add after photoresponse join
# Join mobility
mobility_metrics = chip_metrics.filter(pl.col("metric_name") == "mobility")
if mobility_metrics.height > 0:
    mobility_df = mobility_metrics.select([
        "run_id",
        pl.col("value_float").alias("mobility")
    ])
    history = history.join(mobility_df, on="run_id", how="left")
```

### Step 5: Test on Sample Data

Create test script: `tests/test_mobility_extractor.py`

```python
import polars as pl
from pathlib import Path
from src.derived.extractors.mobility_extractor import MobilityExtractor
from src.core.utils import read_measurement_parquet

def test_mobility_extraction():
    """Test mobility extractor on real IVg data."""

    # Load a sample IVg measurement
    sample_file = Path("data/02_stage/raw_measurements/IVg/Alisson67_002.parquet")
    measurement = read_measurement_parquet(sample_file)

    # Mock metadata (would come from manifest in real pipeline)
    metadata = {
        "run_id": "test_run_001",
        "chip_number": 67,
        "chip_group": "Alisson",
        "procedure": "IVg",
        "seq_num": 2,
        "vds": 0.1,  # 100 mV drain voltage
        "extraction_version": "v0.1.0"
    }

    # Extract mobility
    extractor = MobilityExtractor(L=50e-6, W=200e-6, C_ox=1.15e-8)
    result = extractor.extract(measurement, metadata)

    # Validate result
    assert result is not None, "Extraction failed"
    assert extractor.validate(result), "Validation failed"

    # Print results
    print(f"✓ Mobility extracted successfully")
    print(f"  Value: {result.value_float:.2f} {result.unit}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Flags: {result.flags or 'None'}")
    print(f"  Method: {result.extraction_method}")

if __name__ == "__main__":
    test_mobility_extraction()
```

Run test:
```bash
python3 tests/test_mobility_extractor.py
```

### Step 6: Extract Metrics for All Chips

```bash
# Extract all metrics (including new mobility)
python3 process_and_analyze.py derive-all-metrics

# Or just IVg procedures
python3 process_and_analyze.py derive-all-metrics --proc IVg

# Create enriched history
python3 process_and_analyze.py enrich-history 67

# View results
python3 -c "
import polars as pl
history = pl.read_parquet('data/03_derived/chip_histories_enriched/Alisson67_history.parquet')
ivg_data = history.filter(pl.col('procedure') == 'IVg')
print(ivg_data.select(['seq_num', 'timestamp_local', 'mobility']).head(10))
"
```

### Step 7: Use in Plotting (Optional)

Modify plotting functions to display mobility:

```python
# src/plotting/ivg.py (example modification)

def plot_ivg_with_mobility(df: pl.DataFrame, base_dir: Path, tag: str):
    """Plot IVg with mobility annotation."""

    # Check for enriched history
    chip_number = df["chip_number"][0]
    chip_group = df["chip_group"][0]
    enriched_path = base_dir / "data" / "03_derived" / "chip_histories_enriched" / f"{chip_group}{chip_number}_history.parquet"

    if enriched_path.exists():
        enriched_history = pl.read_parquet(enriched_path)
        # ... plotting logic with mobility annotations
```

## Common Patterns

### Pattern 1: Single-Value Extraction (like CNP, mobility)

```python
def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
    # Compute single value from measurement
    value = compute_something(measurement)

    return DerivedMetric(
        run_id=metadata["run_id"],
        chip_number=metadata["chip_number"],
        chip_group=metadata["chip_group"],
        procedure=metadata["procedure"],
        metric_name=self.metric_name,
        metric_category=self.metric_category,
        value_float=value,
        unit="...",
        extraction_method="...",
        extraction_version=metadata.get("extraction_version"),
        confidence=1.0
    )
```

### Pattern 2: Differential Extraction (like photoresponse)

```python
def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
    # Separate data by condition
    condition1 = measurement.filter(pl.col("condition_col") == value1)
    condition2 = measurement.filter(pl.col("condition_col") == value2)

    # Compute difference
    delta = condition2["signal_col"].mean() - condition1["signal_col"].mean()

    return DerivedMetric(
        # ... same as above with delta as value
    )
```

### Pattern 3: Multi-Value Extraction (store as JSON)

```python
def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
    # Compute multiple related values
    results = {
        "peak_voltage": peak_vg,
        "peak_current": peak_ids,
        "peak_time": peak_t
    }

    return DerivedMetric(
        # ... same fields but:
        value_json=json.dumps(results),
        unit="various"
    )
```

## Quality Checks Checklist

When implementing a new extractor, include these quality checks:

- [ ] **Edge detection**: Is result at boundary of sweep range?
- [ ] **Noise assessment**: Is signal-to-noise ratio sufficient?
- [ ] **Physical bounds**: Is value within expected range for the material?
- [ ] **Sufficient data**: Are there enough points for reliable extraction?
- [ ] **Singularities**: Check for division by zero, log of negative, etc.
- [ ] **Confidence scoring**: Assign 0-1 confidence based on data quality
- [ ] **Flags**: Add human-readable warnings for manual review

## Debugging Tips

### Issue: Extractor not running

Check:
```bash
# Is extractor registered?
python3 -c "from src.derived.metric_pipeline import MetricPipeline; p = MetricPipeline('.'); print([e.metric_name for e in p.extractors])"

# Is procedure in extractor map?
python3 -c "from src.derived.metric_pipeline import MetricPipeline; p = MetricPipeline('.'); print(p.extractor_map.keys())"
```

### Issue: Extraction fails silently

Add logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In extract method:
logging.debug(f"Processing {metadata['run_id']} with {len(measurement)} points")
```

### Issue: Unexpected values

Validate intermediate steps:
```python
# In extract method, add assertions:
assert vg.min() < 0 < vg.max(), "Vg sweep doesn't cross zero"
assert len(ids) == len(vg), "Mismatched array lengths"
```

### Issue: Performance problems

Profile extraction:
```python
import time

def extract(self, measurement, metadata):
    start = time.time()
    # ... extraction logic
    print(f"Extraction took {time.time() - start:.2f}s")
```

## Next Steps

After implementing your metric:

1. **Document in CLAUDE.md**: Add to list of available metrics
2. **Update procedures.yml**: If new columns needed, add to schema
3. **Create visualization**: Add plotting command if useful
4. **Share with team**: Write example analysis notebook

## Example: Full Workflow for Hysteresis Detection

Let's say you want to detect **hysteresis** (different I-V curves for forward/backward sweeps):

```python
# src/derived/extractors/hysteresis_extractor.py

class HysteresisExtractor(MetricExtractor):
    """Detect and quantify hysteresis in IVg sweeps."""

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg"]

    @property
    def metric_name(self) -> str:
        return "hysteresis_voltage"

    @property
    def metric_category(self) -> str:
        return "electrical"

    def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
        """Compute hysteresis as voltage shift between forward/backward sweeps."""

        # Detect sweep direction by checking if Vg is monotonic
        vg = measurement["Vg (V)"].to_numpy()

        # Find turning point (max Vg)
        max_idx = np.argmax(vg)

        if max_idx < 10 or max_idx > len(vg) - 10:
            return None  # No clear forward/backward sweep

        # Split into forward and backward
        forward = measurement[:max_idx]
        backward = measurement[max_idx:]

        # Find Vg where Ids crosses a reference current (e.g., 1 µA)
        ref_current = 1e-6

        # Forward crossing
        forward_cross = forward.filter(pl.col("Ids (A)").abs() > ref_current)
        if forward_cross.height == 0:
            return None
        vg_forward = forward_cross["Vg (V)"][0]

        # Backward crossing (search in reverse)
        backward_cross = backward.filter(pl.col("Ids (A)").abs() > ref_current)
        if backward_cross.height == 0:
            return None
        vg_backward = backward_cross["Vg (V)"][0]

        # Hysteresis = voltage shift
        hysteresis = abs(vg_forward - vg_backward)

        # Quality checks
        flags = []
        confidence = 1.0

        if hysteresis < 0.01:  # Less than 10 mV
            flags.append("NEGLIGIBLE_HYSTERESIS")

        if hysteresis > 2.0:  # More than 2V (unusual)
            flags.append("LARGE_HYSTERESIS")
            confidence *= 0.7

        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure="IVg",
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=hysteresis,
            unit="V",
            extraction_method="threshold_crossing",
            extraction_version=metadata.get("extraction_version"),
            confidence=confidence,
            flags=",".join(flags) if flags else None
        )

    def validate(self, result: DerivedMetric) -> bool:
        """Validate hysteresis is non-negative and reasonable."""
        if result.value_float is None:
            return False

        # Hysteresis should be 0-10V range
        if not (0 <= result.value_float <= 10.0):
            return False

        return True
```

Register it:
```python
# src/derived/metric_pipeline.py
def _default_extractors(self):
    return [
        CNPExtractor(),
        PhotoresponseExtractor(),
        MobilityExtractor(),
        HysteresisExtractor(),  # ← ADD THIS
    ]
```

Test and run:
```bash
python3 tests/test_hysteresis_extractor.py
python3 process_and_analyze.py derive-all-metrics --proc IVg
```

## Summary

**For each new metric**:
1. Create extractor class with `extract()` and `validate()` methods
2. Register in `metric_pipeline.py`
3. Update enriched history joins if needed
4. Test on sample data
5. Run pipeline to extract for all measurements
6. Use in plotting/analysis

**Key principles**:
- One extractor class per metric type
- Include quality checks and confidence scores
- Make extractors independent (no dependencies between them)
- Store provenance (method, version, timestamp)
- Validate outputs before saving

This architecture makes it **easy to add new metrics** without touching the core pipeline!
