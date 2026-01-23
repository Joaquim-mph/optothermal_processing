# Consecutive IVg/VVg Sweep Differencing - Implementation Plan

**Feature Request**: Extract differences between consecutive IVg or VVg measurements to track device evolution
**Use Case**: Understand how illumination (It experiments) affects device characteristics between sweeps
**Status**: Planning Phase

---

## Overview

### Objective

Implement a new type of derived metric extractor that computes differences between consecutive gate voltage sweeps (IVg or VVg). This enables tracking device characteristic evolution, particularly the effects of intervening experiments (e.g., light exposure).

### Example Scenario

```
Seq 1: IVg (dark) → CNP = -0.45V
Seq 2: It (365nm, 30min illumination)
Seq 3: IVg (dark) → CNP = -0.52V
```

**Goal**: Automatically compute `IVg_3 - IVg_1` to quantify the shift induced by the illumination.

**Output Metrics**:
- ΔR(Vg): Resistance difference curve
- ΔCNP: Change in charge neutrality point
- ΔI(Vg): Current difference (for IVg)
- ΔV(Vg): Voltage difference (for VVg)

---

## Current Architecture Analysis

### Key Findings

From my exploration of the codebase:

1. **Single-Measurement Extractors**: Current extractors process ONE measurement at a time
   - `extract(measurement, metadata)` receives single DataFrame
   - No mechanism to pass pairs/sequences

2. **Pipeline Flow**:
   ```
   manifest.parquet → For each row:
                      → Load measurement Parquet
                      → Run extractors
                      → Save to metrics.parquet
   ```

3. **No Pairwise Support**: Architecture doesn't support extractors that need multiple measurements

4. **CalibrationMatcher Exception**: Works outside standard pipeline
   - Processes entire chip histories
   - Custom workflow, not integrated into standard extraction

### Architectural Challenge

**Problem**: Pairwise extractors need:
- Access to chip history (to find consecutive experiments)
- Ability to load TWO measurement files
- Different data model (result belongs to BOTH measurements)

**Current system**: Extractors are stateless, process one measurement, return one metric.

---

## Implementation Options

### Option A: Pairwise Extractor Architecture (Recommended)

**Concept**: Extend the pipeline to support a new extractor type that works on measurement pairs.

**Pros**:
- ✅ Integrates cleanly with existing pipeline
- ✅ Reusable pattern for future pairwise extractors
- ✅ Maintains provenance and versioning
- ✅ Parallel processing support

**Cons**:
- ⚠️ Requires pipeline modifications
- ⚠️ More complex data model (which measurement does metric belong to?)

**Architecture**:
```python
# New base class
class PairwiseMetricExtractor(ABC):
    @abstractmethod
    def extract_pairwise(
        self,
        measurement_1: pl.DataFrame,
        metadata_1: Dict,
        measurement_2: pl.DataFrame,
        metadata_2: Dict
    ) -> Optional[DerivedMetric]:
        """Extract metric from pair of consecutive measurements."""
        pass

    @property
    def pairing_strategy(self) -> str:
        """How to pair measurements: 'consecutive_same_proc', 'time_window', etc."""
        return "consecutive_same_proc"
```

**Pipeline Changes**:
```python
class MetricPipeline:
    def _extract_pairwise_metrics(self, manifest: pl.DataFrame):
        """New method to handle pairwise extractors."""

        # Group by chip and procedure
        for (chip, proc), group in manifest.groupby(["chip_number", "proc"]):
            # Sort by seq_num
            sorted_group = group.sort("seq_num")

            # Process consecutive pairs
            for i in range(len(sorted_group) - 1):
                row_1 = sorted_group[i]
                row_2 = sorted_group[i + 1]

                # Load both measurements
                meas_1 = read_measurement_parquet(row_1["parquet_path"])
                meas_2 = read_measurement_parquet(row_2["parquet_path"])

                # Run pairwise extractors
                for extractor in self.pairwise_extractors:
                    if proc in extractor.applicable_procedures:
                        metric = extractor.extract_pairwise(meas_1, row_1, meas_2, row_2)
                        if metric:
                            metrics.append(metric)
```

---

### Option B: Post-Processing Analysis (Simple)

**Concept**: Separate command that loads metrics.parquet and computes differences.

**Pros**:
- ✅ No pipeline changes needed
- ✅ Simple to implement
- ✅ Can reuse existing CNP metrics

**Cons**:
- ❌ Not integrated into standard workflow
- ❌ Requires manual step
- ❌ Harder to version and track

**Example**:
```bash
python3 process_and_analyze.py analyze-consecutive-sweeps 67 --proc IVg
```

---

### Option C: Custom Enrichment Stage (Like CalibrationMatcher)

**Concept**: Add enrichment step that processes entire chip histories.

**Pros**:
- ✅ Similar to existing CalibrationMatcher pattern
- ✅ Can be added to enrich-history command

**Cons**:
- ❌ Not part of standard extractor pipeline
- ❌ Separate workflow to maintain
- ❌ Doesn't leverage parallel processing

---

## Recommended Approach: Option A (Pairwise Extractors)

### Why Option A?

1. **Extensible**: Creates reusable pattern for future pairwise analyses
2. **Integrated**: Works within standard pipeline workflow
3. **Automated**: Runs as part of `derive-all-metrics`
4. **Provenance**: Maintains versioning and tracking
5. **Performance**: Can leverage parallel processing

### Implementation Strategy

**Phase 1: Architecture Extension** (2-3 hours)
1. Create `PairwiseMetricExtractor` base class
2. Extend `MetricPipeline` with `_extract_pairwise_metrics()`
3. Add pairwise support to data model

**Phase 2: Consecutive Sweep Extractor** (3-4 hours)
1. Implement `ConsecutiveSweepDifferenceExtractor`
2. Compute ΔR(Vg), ΔCNP, ΔI/ΔV
3. Add quality metrics and validation

**Phase 3: Integration & Testing** (2-3 hours)
1. Add to default pipeline
2. Write unit tests
3. Add CLI command for analysis

**Phase 4: Documentation** (1 hour)
1. Update architecture docs
2. Add usage examples
3. Create plotting guide

**Total Estimated Time**: 8-11 hours

---

## Technical Design

### 1. Pairwise Extractor Base Class

**Location**: `src/derived/extractors/base_pairwise.py`

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
import polars as pl
from src.models.derived_metrics import DerivedMetric


class PairwiseMetricExtractor(ABC):
    """Base class for extractors that work on measurement pairs."""

    @property
    @abstractmethod
    def applicable_procedures(self) -> List[str]:
        """Procedures this extractor handles (e.g., ['IVg', 'VVg'])."""
        pass

    @property
    @abstractmethod
    def metric_name(self) -> str:
        """Unique identifier for the pairwise metric."""
        pass

    @property
    @abstractmethod
    def metric_category(self) -> str:
        """Category: 'electrical', 'photoresponse', etc."""
        pass

    @property
    def pairing_strategy(self) -> str:
        """
        How to pair measurements:
        - 'consecutive_same_proc': Only pair same procedure in sequence
        - 'consecutive_any': Pair any consecutive measurements
        - 'time_window': Pair within time window
        """
        return "consecutive_same_proc"

    @abstractmethod
    def extract_pairwise(
        self,
        measurement_1: pl.DataFrame,
        metadata_1: Dict[str, Any],
        measurement_2: pl.DataFrame,
        metadata_2: Dict[str, Any]
    ) -> Optional[List[DerivedMetric]]:
        """
        Extract metrics from a pair of measurements.

        Parameters
        ----------
        measurement_1 : pl.DataFrame
            Earlier measurement data
        metadata_1 : Dict
            Earlier measurement metadata (from manifest)
        measurement_2 : pl.DataFrame
            Later measurement data
        metadata_2 : Dict
            Later measurement metadata

        Returns
        -------
        List[DerivedMetric]
            List of metrics (may return multiple metrics per pair)
            Each metric should reference BOTH run_ids in metadata
        """
        pass

    @abstractmethod
    def validate(self, result: DerivedMetric) -> bool:
        """Validate extracted metric."""
        pass

    def should_pair(
        self,
        metadata_1: Dict[str, Any],
        metadata_2: Dict[str, Any]
    ) -> bool:
        """
        Determine if two measurements should be paired.

        Default implementation checks:
        - Same procedure
        - Consecutive seq_num
        - Same chip
        """
        if metadata_1["chip_number"] != metadata_2["chip_number"]:
            return False

        if metadata_1["proc"] != metadata_2["proc"]:
            return False

        seq_1 = metadata_1.get("seq_num")
        seq_2 = metadata_2.get("seq_num")

        if seq_1 is None or seq_2 is None:
            return False

        # Check if consecutive
        return seq_2 == seq_1 + 1
```

---

### 2. Consecutive Sweep Difference Extractor

**Location**: `src/derived/extractors/consecutive_sweep_difference.py`

```python
from __future__ import annotations
import numpy as np
import polars as pl
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from scipy.interpolate import interp1d

from src.models.derived_metrics import DerivedMetric
from .base_pairwise import PairwiseMetricExtractor
from .base import compute_confidence, build_flags


class ConsecutiveSweepDifferenceExtractor(PairwiseMetricExtractor):
    """
    Extract differences between consecutive IVg or VVg sweeps.

    Computes:
    - ΔR(Vg): Resistance difference curve
    - ΔCNP: Change in charge neutrality point
    - ΔI(Vg) or ΔV(Vg): Current/voltage difference

    Use Case:
    --------
    Track device evolution between measurements, especially
    after illumination or other treatments.

    Example:
        IVg_1 (dark) → It (illumination) → IVg_2 (dark)
        Compute: IVg_2 - IVg_1 to see illumination effect

    Parameters
    ----------
    vg_interpolation_points : int
        Number of points for Vg interpolation (default: 200)
    min_vg_overlap : float
        Minimum Vg range overlap required (volts, default: 1.0)
    """

    def __init__(
        self,
        vg_interpolation_points: int = 200,
        min_vg_overlap: float = 1.0
    ):
        self.vg_interpolation_points = vg_interpolation_points
        self.min_vg_overlap = min_vg_overlap

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg", "VVg"]

    @property
    def metric_name(self) -> str:
        return "consecutive_sweep_difference"

    @property
    def metric_category(self) -> str:
        return "electrical"

    def extract_pairwise(
        self,
        measurement_1: pl.DataFrame,
        metadata_1: Dict[str, Any],
        measurement_2: pl.DataFrame,
        metadata_2: Dict[str, Any]
    ) -> Optional[List[DerivedMetric]]:
        """Extract difference metrics from consecutive sweeps."""

        procedure = metadata_1["proc"]

        # Validate same procedure
        if metadata_2["proc"] != procedure:
            return None

        # Extract gate voltage (common to both IVg and VVg)
        vg_1 = measurement_1["Vg (V)"].to_numpy()
        vg_2 = measurement_2["Vg (V)"].to_numpy()

        # Extract dependent variable based on procedure
        if procedure == "IVg":
            y_1 = measurement_1["I (A)"].to_numpy()
            y_2 = measurement_2["I (A)"].to_numpy()
            y_label = "I"
            y_unit = "A"
            vds = metadata_1.get("vds_v", 0.1)  # For resistance calculation
        elif procedure == "VVg":
            y_1 = measurement_1["Vds (V)"].to_numpy()
            y_2 = measurement_2["Vds (V)"].to_numpy()
            y_label = "Vds"
            y_unit = "V"
            ids = metadata_1.get("ids_v", 1e-6)  # For resistance calculation
        else:
            return None

        # Check Vg range overlap
        vg_min = max(vg_1.min(), vg_2.min())
        vg_max = min(vg_1.max(), vg_2.max())
        vg_overlap = vg_max - vg_min

        if vg_overlap < self.min_vg_overlap:
            # Insufficient overlap
            return None

        # Create common Vg grid for interpolation
        vg_common = np.linspace(vg_min, vg_max, self.vg_interpolation_points)

        # Interpolate both sweeps onto common grid
        try:
            interp_1 = interp1d(vg_1, y_1, kind='cubic', fill_value='extrapolate')
            interp_2 = interp1d(vg_2, y_2, kind='cubic', fill_value='extrapolate')

            y_1_interp = interp_1(vg_common)
            y_2_interp = interp_2(vg_common)
        except Exception:
            # Interpolation failed
            return None

        # Compute differences
        delta_y = y_2_interp - y_1_interp

        # Compute resistance difference
        if procedure == "IVg":
            r_1 = np.abs(vds / y_1_interp)
            r_2 = np.abs(vds / y_2_interp)
        else:  # VVg
            r_1 = np.abs(y_1_interp / ids)
            r_2 = np.abs(y_2_interp / ids)

        delta_r = r_2 - r_1

        # Compute summary statistics
        max_delta_r = float(np.max(np.abs(delta_r)))
        mean_delta_r = float(np.mean(delta_r))
        max_delta_y = float(np.max(np.abs(delta_y)))

        # Find CNP shift (if available from prior extraction)
        cnp_1 = metadata_1.get("cnp_voltage")  # From enriched history
        cnp_2 = metadata_2.get("cnp_voltage")

        if cnp_1 is not None and cnp_2 is not None:
            delta_cnp = float(cnp_2 - cnp_1)
        else:
            delta_cnp = None

        # Quality checks
        checks = {
            "GOOD_OVERLAP": vg_overlap > self.min_vg_overlap,
            "REASONABLE_CHANGE": max_delta_r < 1e9,  # Not infinite resistance
            "NON_ZERO_CHANGE": max_delta_r > 1e-6,    # Detectable change
        }

        penalties = {
            "REASONABLE_CHANGE": 0.8,
            "NON_ZERO_CHANGE": 0.5,
        }

        confidence = compute_confidence(checks, penalties)
        flags = build_flags(checks)

        # Build detailed results JSON
        results = {
            "vg_min": float(vg_min),
            "vg_max": float(vg_max),
            "vg_overlap": float(vg_overlap),
            "max_delta_resistance": max_delta_r,
            "mean_delta_resistance": mean_delta_r,
            f"max_delta_{y_label.lower()}": max_delta_y,
            "delta_cnp": delta_cnp,
            "num_points": len(vg_common),
            "seq_1": metadata_1.get("seq_num"),
            "seq_2": metadata_2.get("seq_num"),
            "run_id_1": metadata_1["run_id"],
            "run_id_2": metadata_2["run_id"],
        }

        # Optionally save full difference curves (could be large!)
        # Uncomment if you want to save full arrays:
        # results["vg_array"] = vg_common.tolist()
        # results["delta_y_array"] = delta_y.tolist()
        # results["delta_r_array"] = delta_r.tolist()

        # Create metric
        # Note: We assign this metric to the SECOND measurement (later one)
        metric = DerivedMetric(
            run_id=metadata_2["run_id"],  # Belongs to later measurement
            chip_number=metadata_2["chip_number"],
            chip_group=metadata_2["chip_group"],
            procedure=procedure,
            seq_num=metadata_2.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=max_delta_r,  # Primary value: max resistance change
            value_json=json.dumps(results),
            unit="Ω",
            extraction_method="consecutive_sweep_interpolation",
            extraction_version=metadata_2.get("extraction_version"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=flags
        )

        return [metric] if self.validate(metric) else None

    def validate(self, result: DerivedMetric) -> bool:
        """Validate result is reasonable."""
        if result.value_float is None:
            return False

        # Check resistance change is finite and reasonable
        if not np.isfinite(result.value_float):
            return False

        # Typical graphene resistance: 1kΩ to 100kΩ
        # Allow changes up to 1GΩ (very large but possible)
        if abs(result.value_float) > 1e9:
            return False

        return True
```

---

### 3. Pipeline Integration

**Modifications to**: `src/derived/metric_pipeline.py`

```python
class MetricPipeline:
    def __init__(
        self,
        extractors: Optional[List[MetricExtractor]] = None,
        pairwise_extractors: Optional[List[PairwiseMetricExtractor]] = None,  # NEW
        base_dir: Optional[Path] = None
    ):
        # Existing code...

        # NEW: Pairwise extractors
        if pairwise_extractors is None:
            pairwise_extractors = self._default_pairwise_extractors()
        self.pairwise_extractors = pairwise_extractors

        # Build pairwise extractor map
        self.pairwise_extractor_map: Dict[str, List[PairwiseMetricExtractor]] = {}
        for extractor in self.pairwise_extractors:
            for proc in extractor.applicable_procedures:
                if proc not in self.pairwise_extractor_map:
                    self.pairwise_extractor_map[proc] = []
                self.pairwise_extractor_map[proc].append(extractor)

    def _default_pairwise_extractors(self) -> List[PairwiseMetricExtractor]:
        """Default pairwise extractors."""
        from src.derived.extractors.consecutive_sweep_difference import (
            ConsecutiveSweepDifferenceExtractor
        )
        return [
            ConsecutiveSweepDifferenceExtractor(
                vg_interpolation_points=200,
                min_vg_overlap=1.0
            )
        ]

    def derive_all_metrics(
        self,
        chip_numbers: Optional[List[int]] = None,
        procedures: Optional[List[str]] = None,
        workers: int = 1,
        force: bool = False
    ) -> Path:
        """Extract all metrics (single + pairwise)."""

        # Existing single-measurement extraction...
        metrics = self._extract_single_metrics(manifest, workers)

        # NEW: Pairwise extraction
        pairwise_metrics = self._extract_pairwise_metrics(manifest)

        # Combine and save
        all_metrics = metrics + pairwise_metrics
        self._save_metrics(all_metrics)

        return metrics_path

    def _extract_pairwise_metrics(
        self,
        manifest: pl.DataFrame
    ) -> List[DerivedMetric]:
        """Extract metrics from consecutive measurement pairs."""

        metrics = []

        # Group by chip and procedure
        grouped = manifest.groupby(["chip_number", "proc"])

        for (chip_num, proc), group_df in grouped:
            # Skip if no pairwise extractors for this procedure
            if proc not in self.pairwise_extractor_map:
                continue

            extractors = self.pairwise_extractor_map[proc]

            # Sort by seq_num
            sorted_group = group_df.sort("seq_num")
            rows = sorted_group.to_dicts()

            # Process consecutive pairs
            for i in range(len(rows) - 1):
                metadata_1 = rows[i]
                metadata_2 = rows[i + 1]

                # Check if measurements should be paired
                should_pair = all(
                    ext.should_pair(metadata_1, metadata_2)
                    for ext in extractors
                )

                if not should_pair:
                    continue

                # Load both measurements
                try:
                    meas_1 = read_measurement_parquet(Path(metadata_1["parquet_path"]))
                    meas_2 = read_measurement_parquet(Path(metadata_2["parquet_path"]))
                except Exception as e:
                    self.logger.warning(
                        f"Failed to load pair {metadata_1['run_id']}, {metadata_2['run_id']}: {e}"
                    )
                    continue

                # Run pairwise extractors
                for extractor in extractors:
                    try:
                        pair_metrics = extractor.extract_pairwise(
                            meas_1, metadata_1,
                            meas_2, metadata_2
                        )
                        if pair_metrics:
                            metrics.extend(pair_metrics)
                    except Exception as e:
                        self.logger.error(
                            f"Pairwise extraction failed for {extractor.metric_name}: {e}"
                        )

        return metrics
```

---

### 4. Data Model Considerations

**Question**: How do we link pairwise metrics to measurements?

**Options**:

**A. Link to Second Measurement** (Recommended)
```python
metric = DerivedMetric(
    run_id=metadata_2["run_id"],  # Later measurement
    seq_num=metadata_2["seq_num"],
    # ... store run_id_1 in value_json
)
```
- Simpler data model
- Metric "belongs to" the later measurement
- First measurement referenced in JSON

**B. Create Join Table** (Complex)
- New table: `pairwise_metric_links`
- Links metric to multiple run_ids
- More normalized but requires schema changes

**Recommendation**: Use Option A (link to second measurement, store first in JSON)

---

## Usage Examples

### CLI Command

```bash
# Extract all metrics (includes pairwise)
python3 process_and_analyze.py derive-all-metrics

# Extract only for specific chip
python3 process_and_analyze.py derive-all-metrics --chip 67

# Extract only IVg pairwise differences
python3 process_and_analyze.py derive-all-metrics --procedures IVg

# View results
python3 process_and_analyze.py show-history 67 --format table
# (enriched history will show consecutive_sweep_difference column)
```

### Programmatic Usage

```python
from pathlib import Path
from src.derived import MetricPipeline

# Extract pairwise metrics
pipeline = MetricPipeline(base_dir=Path("."))
metrics_path = pipeline.derive_all_metrics(chip_numbers=[67])

# Load results
import polars as pl
metrics = pl.read_parquet(metrics_path)

# Filter to pairwise metrics
pairwise = metrics.filter(pl.col("metric_name") == "consecutive_sweep_difference")

# Inspect results
for row in pairwise.iter_rows(named=True):
    details = json.loads(row["value_json"])
    print(f"Seq {details['seq_1']} → {details['seq_2']}: ΔCNP = {details['delta_cnp']:.3f}V")
```

### Plotting Example

```python
import polars as pl
import json
import matplotlib.pyplot as plt

# Load enriched history
history = pl.read_parquet("data/03_derived/chip_histories_enriched/Alisson67_history.parquet")

# Find consecutive IVg pairs with pairwise metrics
# (This requires enrichment to join metrics back to history)

# For now, load metrics directly
metrics = pl.read_parquet("data/03_derived/_metrics/metrics.parquet")
pairwise = metrics.filter(
    (pl.col("metric_name") == "consecutive_sweep_difference") &
    (pl.col("procedure") == "IVg")
)

# Plot CNP evolution from consecutive differences
for row in pairwise.iter_rows(named=True):
    details = json.loads(row["value_json"])
    if details["delta_cnp"] is not None:
        plt.scatter(
            details["seq_2"],
            details["delta_cnp"],
            label=f"Δ(Seq{details['seq_1']}→{details['seq_2']})"
        )

plt.xlabel("Sequence Number")
plt.ylabel("ΔCNP (V)")
plt.title("CNP Evolution - Consecutive Differences")
plt.legend()
plt.savefig("cnp_consecutive_differences.png", dpi=300)
```

---

## Testing Strategy

### Unit Tests

**Location**: `tests/derived/test_consecutive_sweep_difference.py`

```python
import pytest
import polars as pl
import numpy as np
from src.derived.extractors.consecutive_sweep_difference import (
    ConsecutiveSweepDifferenceExtractor
)


def test_consecutive_ivg_difference():
    """Test basic IVg consecutive difference extraction."""

    # Create synthetic IVg sweeps
    vg = np.linspace(-5, 5, 100)

    # Sweep 1: CNP at 0V
    i_1 = 1e-6 * (vg**2 + 1)
    meas_1 = pl.DataFrame({
        "Vg (V)": vg,
        "I (A)": i_1
    })
    metadata_1 = {
        "run_id": "test_1",
        "chip_number": 67,
        "chip_group": "Test",
        "proc": "IVg",
        "seq_num": 1,
        "vds_v": 0.1,
        "extraction_version": "test"
    }

    # Sweep 2: CNP shifted to -0.5V (illumination effect)
    i_2 = 1e-6 * ((vg + 0.5)**2 + 1)
    meas_2 = pl.DataFrame({
        "Vg (V)": vg,
        "I (A)": i_2
    })
    metadata_2 = {
        **metadata_1,
        "run_id": "test_2",
        "seq_num": 2
    }

    # Extract difference
    extractor = ConsecutiveSweepDifferenceExtractor()
    results = extractor.extract_pairwise(meas_1, metadata_1, meas_2, metadata_2)

    # Assertions
    assert results is not None
    assert len(results) == 1

    metric = results[0]
    assert metric.metric_name == "consecutive_sweep_difference"
    assert metric.run_id == "test_2"  # Linked to second measurement
    assert metric.confidence > 0.5

    # Check stored details
    import json
    details = json.loads(metric.value_json)
    assert details["seq_1"] == 1
    assert details["seq_2"] == 2
    assert details["vg_overlap"] > 9.0  # Good overlap


def test_non_consecutive_skipped():
    """Test that non-consecutive measurements are not paired."""

    extractor = ConsecutiveSweepDifferenceExtractor()

    metadata_1 = {"seq_num": 1, "proc": "IVg", "chip_number": 67}
    metadata_2 = {"seq_num": 5, "proc": "IVg", "chip_number": 67}  # Gap!

    # Should not pair
    assert not extractor.should_pair(metadata_1, metadata_2)


def test_mixed_procedures_rejected():
    """Test that IVg and VVg are not paired together."""

    extractor = ConsecutiveSweepDifferenceExtractor()

    metadata_1 = {"seq_num": 1, "proc": "IVg", "chip_number": 67}
    metadata_2 = {"seq_num": 2, "proc": "VVg", "chip_number": 67}

    # Should not pair different procedures
    assert not extractor.should_pair(metadata_1, metadata_2)
```

### Integration Tests

```bash
# Run on real data
python3 process_and_analyze.py derive-all-metrics --chip 67 --procedures IVg

# Check metrics were created
python3 << 'EOF'
import polars as pl
metrics = pl.read_parquet("data/03_derived/_metrics/metrics.parquet")
pairwise = metrics.filter(pl.col("metric_name") == "consecutive_sweep_difference")
print(f"Found {pairwise.height} pairwise metrics")
assert pairwise.height > 0, "No pairwise metrics extracted!"
print("✓ Integration test passed")
EOF
```

---

## Open Questions

1. **Full Curve Storage**: Should we store full ΔR(Vg) and ΔI(Vg) arrays?
   - **Pro**: Enables detailed analysis and plotting
   - **Con**: Large JSON blobs, slower queries
   - **Proposal**: Make optional with flag `--store-full-curves`

2. **CNP Dependency**: Should we require CNP to be extracted first?
   - **Pro**: Can compute ΔCNP automatically
   - **Con**: Creates dependency between extractors
   - **Proposal**: Optional - if CNP exists in metadata, include ΔCNP

3. **Parallel Processing**: Can pairwise extraction be parallelized?
   - **Challenge**: Pairs span multiple rows, need to partition carefully
   - **Proposal**: Start with sequential, optimize later if needed

4. **Enrichment Integration**: How to add pairwise metrics to chip histories?
   - **Current**: Enrichment joins metrics on run_id
   - **Issue**: Pairwise metric belongs to TWO measurements
   - **Proposal**: Join on run_id_2, add column `previous_run_id` from JSON

---

## Next Steps

### Immediate Actions

1. **Review this plan** - Confirm approach and technical design
2. **Prototype base class** - Implement `PairwiseMetricExtractor`
3. **Implement extractor** - Build `ConsecutiveSweepDifferenceExtractor`
4. **Test on real data** - Run on chip 67 IVg sequences
5. **Iterate based on results**

### Questions for Review

1. **Architecture**: Is Option A (pairwise extractors) the right approach?
2. **Data model**: Is linking to second measurement acceptable?
3. **Scope**: Should we include full curve storage or just summary stats?
4. **Enrichment**: How should pairwise metrics appear in chip histories?

---

**Status**: ✅ Ready for review
**Next**: Awaiting approval to begin implementation
