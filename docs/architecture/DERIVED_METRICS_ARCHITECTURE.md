# Derived Metrics Architecture

**Last Updated:** October 31, 2025
**Version:** 3.0 (Fully Implemented)

## Overview

This document describes the architecture for extracting and storing derived analytical metrics from staged measurement data.

## Data Flow

```
Raw CSV → Staging → Derived Metrics → Plotting/Export
          (Stage 2)  (Stage 3)
```

### Stage 2: Staged Data (Current)
- **Input**: Raw CSV files
- **Output**: `manifest.parquet` + staged Parquet measurements
- **Responsibility**: Validation, type coercion, metadata extraction

### Stage 3: Derived Metrics (New)
- **Input**: Staged Parquet files (via manifest.parquet)
- **Output**: `metrics.parquet` + enriched chip histories
- **Responsibility**: Analytical computations, feature extraction

## Directory Structure

```
data/
├── 01_raw/                           # Raw CSVs
├── 02_stage/                         # Staged data
│   ├── raw_measurements/             # Typed Parquet files
│   ├── chip_histories/               # Per-chip summaries
│   └── _manifest/
│       └── manifest.parquet          # Source of truth
└── 03_derived/                       # NEW: Derived metrics
    ├── _metrics/
    │   └── metrics.parquet           # All derived metrics
    └── chip_histories_enriched/      # Histories + metrics
        └── {chip_group}{chip_number}_history.parquet
```

## Data Schema

### metrics.parquet Schema

```python
# src/models/derived_metrics.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class DerivedMetric(BaseModel):
    """Single derived metric result."""

    # Linkage to source measurement
    run_id: str = Field(..., description="FK to manifest.parquet run_id")
    chip_number: int
    chip_group: str
    procedure: str
    seq_num: Optional[int] = Field(None, description="FK to chip history seq_num")

    # Metric identity
    metric_name: str = Field(..., description="e.g., 'cnp_voltage', 'delta_ids'")
    metric_category: str = Field(..., description="e.g., 'electrical', 'photoresponse'")

    # Metric value (polymorphic - store as appropriate type)
    value_float: Optional[float] = None
    value_str: Optional[str] = None
    value_json: Optional[str] = Field(None, description="JSON for complex metrics")

    # Metadata
    unit: Optional[str] = Field(None, description="e.g., 'V', 'A', 'Ω'")
    extraction_method: str = Field(..., description="Algorithm/function name")
    extraction_version: str = Field(..., description="Code version that computed this")
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Quality indicators
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="0-1 confidence score")
    flags: Optional[str] = Field(None, description="Comma-separated warnings/notes")

    class Config:
        validate_assignment = True
```

### Enriched Chip History Schema

Extends existing chip history with derived metric columns:

```python
# Existing columns from chip_histories/
chip_number, chip_group, seq_num, procedure, timestamp_local,
light, vg, vds, vl, parquet_path, ...

# NEW: Derived metric columns (nullable for backward compatibility)
cnp_voltage: Optional[float]      # Charge neutrality point (IVg, VVg)
cnp_resistance: Optional[float]   # Resistance at CNP (IVg, VVg)
delta_ids: Optional[float]        # Photo-induced current change (It)
delta_vds: Optional[float]        # Photo-induced voltage change (Vt)
photoresponse_ratio: Optional[float]  # ΔI/I_dark or ΔV/V_dark

# Metrics stored with provenance
derived_metrics_version: Optional[str]  # Version of extraction code
```

## Metric Extractors

### Extractor Interface

Each metric type implements a standard interface:

```python
# src/derived/extractors/base.py
from abc import ABC, abstractmethod
from pathlib import Path
import polars as pl
from typing import List
from src.models.derived_metrics import DerivedMetric

class MetricExtractor(ABC):
    """Base class for all metric extractors."""

    @property
    @abstractmethod
    def applicable_procedures(self) -> List[str]:
        """Which procedures this extractor applies to."""
        pass

    @property
    @abstractmethod
    def metric_name(self) -> str:
        """Unique identifier for this metric."""
        pass

    @property
    @abstractmethod
    def metric_category(self) -> str:
        """Category (e.g., 'electrical', 'photoresponse')."""
        pass

    @abstractmethod
    def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
        """
        Extract metric from a single measurement.

        Args:
            measurement: Polars DataFrame with measurement data
            metadata: Dict from manifest.parquet row (run_id, chip_number, etc.)

        Returns:
            DerivedMetric instance or None if extraction failed
        """
        pass

    @abstractmethod
    def validate(self, result: DerivedMetric) -> bool:
        """
        Validate extracted metric (optional QA step).

        Returns:
            True if metric passes quality checks
        """
        pass
```

### Example: CNP Extractor

```python
# src/derived/extractors/cnp_extractor.py
import polars as pl
import numpy as np
from typing import Optional, List
from .base import MetricExtractor
from src.models.derived_metrics import DerivedMetric

class CNPExtractor(MetricExtractor):
    """Extract charge neutrality point from IVg/VVg measurements."""

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg", "VVg"]

    @property
    def metric_name(self) -> str:
        return "cnp_voltage"

    @property
    def metric_category(self) -> str:
        return "electrical"

    def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
        """Find Vg where resistance is maximum (most resistive point)."""

        procedure = metadata["procedure"]

        # Column names depend on procedure
        if procedure == "IVg":
            vg_col = "Vg (V)"
            current_col = "Ids (A)"
            voltage_col = metadata.get("vds")  # From manifest
        elif procedure == "VVg":
            vg_col = "Vg (V)"
            current_col = metadata.get("ids")  # From manifest (constant)
            voltage_col = "Vds (V)"
        else:
            return None

        # Calculate resistance
        if procedure == "IVg":
            # R = Vds / Ids (Vds is constant from metadata)
            df = measurement.with_columns([
                (pl.lit(voltage_col) / pl.col(current_col).abs()).alias("resistance")
            ])
        else:  # VVg
            # R = Vds / Ids (Ids is constant from metadata)
            df = measurement.with_columns([
                (pl.col(voltage_col).abs() / pl.lit(abs(current_col))).alias("resistance")
            ])

        # Find Vg at maximum resistance
        max_r_row = df.sort("resistance", descending=True).row(0, named=True)

        cnp_vg = max_r_row[vg_col]
        cnp_resistance = max_r_row["resistance"]

        # Check if CNP is at edge of sweep (might be out of range)
        vg_min = df[vg_col].min()
        vg_max = df[vg_col].max()
        at_edge = (cnp_vg == vg_min) or (cnp_vg == vg_max)

        flags = []
        confidence = 1.0

        if at_edge:
            flags.append("CNP_AT_EDGE")
            confidence = 0.5  # Low confidence - true CNP might be out of range

        # Check for noisy data (std of resistance > 50% of max)
        r_std = df["resistance"].std()
        r_max = df["resistance"].max()
        if r_std / r_max > 0.5:
            flags.append("NOISY_DATA")
            confidence *= 0.7

        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=procedure,
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=cnp_vg,
            unit="V",
            extraction_method="max_resistance",
            extraction_version=metadata.get("extraction_version", "unknown"),
            confidence=confidence,
            flags=",".join(flags) if flags else None
        )

    def validate(self, result: DerivedMetric) -> bool:
        """Validate CNP is in reasonable range."""
        if result.value_float is None:
            return False

        # Typical CNP for these samples: -5V to +5V
        if not (-10.0 <= result.value_float <= 10.0):
            return False

        return True
```

### Example: Photoresponse Extractor

```python
# src/derived/extractors/photoresponse_extractor.py
import polars as pl
from typing import Optional, List
from .base import MetricExtractor
from src.models.derived_metrics import DerivedMetric

class PhotoresponseExtractor(MetricExtractor):
    """Extract ΔI_ds or ΔV_ds from illuminated It/Vt measurements."""

    @property
    def applicable_procedures(self) -> List[str]:
        return ["It", "Vt"]

    @property
    def metric_name(self) -> str:
        return "delta_ids"  # Or "delta_vds" for Vt

    @property
    def metric_category(self) -> str:
        return "photoresponse"

    def extract(self, measurement: pl.DataFrame, metadata: dict) -> Optional[DerivedMetric]:
        """Calculate ΔI or ΔV using VL column as mask."""

        procedure = metadata["procedure"]

        # Check if measurement has light modulation
        if "VL (V)" not in measurement.columns:
            return None

        # Separate dark and light regions
        dark_data = measurement.filter(pl.col("VL (V)") == 0)
        light_data = measurement.filter(pl.col("VL (V)") > 0)

        if dark_data.height == 0 or light_data.height == 0:
            return None  # Need both dark and light regions

        # Calculate mean values
        if procedure == "It":
            signal_col = "Ids (A)"
            unit = "A"
            metric_name = "delta_ids"
        elif procedure == "Vt":
            signal_col = "Vds (V)"
            unit = "V"
            metric_name = "delta_vds"
        else:
            return None

        dark_mean = dark_data[signal_col].mean()
        light_mean = light_data[signal_col].mean()

        delta = light_mean - dark_mean

        # Calculate photoresponse ratio (normalized change)
        if abs(dark_mean) > 1e-12:  # Avoid division by zero
            ratio = delta / dark_mean
        else:
            ratio = None

        # Quality checks
        flags = []
        confidence = 1.0

        # Check for sufficient data points
        if dark_data.height < 10 or light_data.height < 10:
            flags.append("INSUFFICIENT_POINTS")
            confidence *= 0.7

        # Check for noise (std > 10% of delta)
        dark_std = dark_data[signal_col].std()
        light_std = light_data[signal_col].std()
        if max(dark_std, light_std) > abs(delta) * 0.1:
            flags.append("NOISY_SIGNAL")
            confidence *= 0.8

        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=procedure,
            seq_num=metadata.get("seq_num"),
            metric_name=metric_name,
            metric_category=self.metric_category,
            value_float=delta,
            unit=unit,
            extraction_method="mean_difference",
            extraction_version=metadata.get("extraction_version", "unknown"),
            confidence=confidence,
            flags=",".join(flags) if flags else None
        )

    def validate(self, result: DerivedMetric) -> bool:
        """Validate photoresponse is non-zero and reasonable."""
        if result.value_float is None:
            return False

        # Sanity check: photoresponse should be measurable
        if abs(result.value_float) < 1e-15:  # Below noise floor
            return False

        return True
```

## Pipeline Implementation

### Core Module

```python
# src/derived/metric_pipeline.py
import polars as pl
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ProcessPoolExecutor
from rich.progress import Progress
from src.core.utils import read_measurement_parquet
from src.models.derived_metrics import DerivedMetric
from .extractors.base import MetricExtractor
from .extractors.cnp_extractor import CNPExtractor
from .extractors.photoresponse_extractor import PhotoresponseExtractor

class MetricPipeline:
    """Orchestrates extraction of derived metrics from staged data."""

    def __init__(self, base_dir: Path, extractors: Optional[List[MetricExtractor]] = None):
        self.base_dir = Path(base_dir)
        self.stage_dir = self.base_dir / "data" / "02_stage"
        self.derived_dir = self.base_dir / "data" / "03_derived"

        # Register extractors
        if extractors is None:
            self.extractors = self._default_extractors()
        else:
            self.extractors = extractors

        # Build extractor lookup by procedure
        self.extractor_map = {}
        for extractor in self.extractors:
            for proc in extractor.applicable_procedures:
                if proc not in self.extractor_map:
                    self.extractor_map[proc] = []
                self.extractor_map[proc].append(extractor)

    def _default_extractors(self) -> List[MetricExtractor]:
        """Return default set of metric extractors."""
        return [
            CNPExtractor(),
            PhotoresponseExtractor(),
            # Add more extractors here as they're developed
        ]

    def derive_all_metrics(
        self,
        procedures: Optional[List[str]] = None,
        parallel: bool = True,
        workers: int = 6
    ) -> Path:
        """
        Extract all metrics from staged measurements.

        Args:
            procedures: Filter to specific procedures (None = all)
            parallel: Use multiprocessing
            workers: Number of parallel workers

        Returns:
            Path to metrics.parquet
        """
        # Load manifest
        manifest_path = self.stage_dir / "_manifest" / "manifest.parquet"
        manifest = pl.read_parquet(manifest_path)

        # Filter by procedure if specified
        if procedures:
            manifest = manifest.filter(pl.col("procedure").is_in(procedures))

        # Filter to only procedures with extractors
        manifest = manifest.filter(
            pl.col("procedure").is_in(list(self.extractor_map.keys()))
        )

        # Extract metrics
        if parallel:
            metrics = self._extract_parallel(manifest, workers)
        else:
            metrics = self._extract_sequential(manifest)

        # Save metrics.parquet
        metrics_dir = self.derived_dir / "_metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = metrics_dir / "metrics.parquet"

        metrics_df = pl.DataFrame([m.model_dump() for m in metrics])
        metrics_df.write_parquet(metrics_path)

        return metrics_path

    def _extract_sequential(self, manifest: pl.DataFrame) -> List[DerivedMetric]:
        """Extract metrics sequentially (for debugging)."""
        metrics = []

        with Progress() as progress:
            task = progress.add_task("Extracting metrics", total=manifest.height)

            for row in manifest.iter_rows(named=True):
                row_metrics = self._extract_from_measurement(row)
                metrics.extend(row_metrics)
                progress.advance(task)

        return metrics

    def _extract_parallel(self, manifest: pl.DataFrame, workers: int) -> List[DerivedMetric]:
        """Extract metrics in parallel."""
        rows = [row for row in manifest.iter_rows(named=True)]

        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(self._extract_from_measurement, rows))

        # Flatten results
        metrics = []
        for row_metrics in results:
            metrics.extend(row_metrics)

        return metrics

    def _extract_from_measurement(self, metadata: dict) -> List[DerivedMetric]:
        """Extract all applicable metrics from a single measurement."""
        metrics = []

        procedure = metadata["procedure"]
        parquet_path = Path(metadata["parquet_path"])

        # Get extractors for this procedure
        extractors = self.extractor_map.get(procedure, [])

        if not extractors:
            return metrics

        # Load measurement data
        try:
            measurement = read_measurement_parquet(parquet_path)
        except Exception as e:
            print(f"Failed to load {parquet_path}: {e}")
            return metrics

        # Run each applicable extractor
        for extractor in extractors:
            try:
                metric = extractor.extract(measurement, metadata)
                if metric and extractor.validate(metric):
                    metrics.append(metric)
            except Exception as e:
                print(f"Extractor {extractor.metric_name} failed on {parquet_path}: {e}")

        return metrics

    def enrich_chip_histories(self, chip_number: int, chip_group: str = "Alisson") -> Path:
        """
        Create enriched chip history with derived metrics.

        Args:
            chip_number: Chip number
            chip_group: Chip group name

        Returns:
            Path to enriched history file
        """
        # Load base history
        history_path = self.stage_dir / "chip_histories" / f"{chip_group}{chip_number}_history.parquet"
        history = pl.read_parquet(history_path)

        # Load metrics
        metrics_path = self.derived_dir / "_metrics" / "metrics.parquet"
        metrics = pl.read_parquet(metrics_path)

        # Filter metrics for this chip
        chip_metrics = metrics.filter(
            (pl.col("chip_number") == chip_number) &
            (pl.col("chip_group") == chip_group)
        )

        # Pivot metrics to wide format (one column per metric)
        # This is complex in Polars - might need custom logic
        # For now, use join approach for specific metrics

        # Join CNP voltage
        cnp_metrics = chip_metrics.filter(pl.col("metric_name") == "cnp_voltage")
        if cnp_metrics.height > 0:
            cnp_df = cnp_metrics.select([
                "run_id",
                pl.col("value_float").alias("cnp_voltage")
            ])
            history = history.join(cnp_df, on="run_id", how="left")

        # Join photoresponse
        photo_metrics = chip_metrics.filter(pl.col("metric_name") == "delta_ids")
        if photo_metrics.height > 0:
            photo_df = photo_metrics.select([
                "run_id",
                pl.col("value_float").alias("delta_ids")
            ])
            history = history.join(photo_df, on="run_id", how="left")

        # Save enriched history
        enriched_dir = self.derived_dir / "chip_histories_enriched"
        enriched_dir.mkdir(parents=True, exist_ok=True)
        enriched_path = enriched_dir / f"{chip_group}{chip_number}_history.parquet"

        history.write_parquet(enriched_path)

        return enriched_path
```

## CLI Commands

### derive-all-metrics

```python
# src/cli/commands/derive_metrics.py
from src.cli.plugin_system import cli_command
import typer
from pathlib import Path
from rich.console import Console
from src.derived.metric_pipeline import MetricPipeline

console = Console()

@cli_command(
    name="derive-all-metrics",
    group="pipeline",
    description="Extract derived metrics from staged measurements"
)
def derive_all_metrics_command(
    procedures: str = typer.Option(None, "--proc", help="Comma-separated procedures (e.g., 'IVg,It')"),
    workers: int = typer.Option(6, "--workers", help="Number of parallel workers"),
    base_dir: Path = typer.Option(Path.cwd(), "--base-dir", help="Base directory")
):
    """
    Extract derived metrics from staged measurements.

    This computes analytical results like:
    - Charge neutrality point (CNP) from IVg/VVg
    - Photoresponse (ΔI, ΔV) from It/Vt

    Results stored in data/03_derived/metrics.parquet
    """

    proc_list = procedures.split(",") if procedures else None

    console.print(f"[bold blue]Extracting derived metrics...[/bold blue]")
    if proc_list:
        console.print(f"Procedures: {', '.join(proc_list)}")

    pipeline = MetricPipeline(base_dir)
    metrics_path = pipeline.derive_all_metrics(
        procedures=proc_list,
        parallel=True,
        workers=workers
    )

    console.print(f"[bold green]✓[/bold green] Metrics saved to {metrics_path}")


@cli_command(
    name="enrich-history",
    group="history",
    description="Create enriched chip history with derived metrics"
)
def enrich_history_command(
    chip_number: int = typer.Argument(..., help="Chip number"),
    chip_group: str = typer.Option("Alisson", "--group", help="Chip group"),
    base_dir: Path = typer.Option(Path.cwd(), "--base-dir", help="Base directory")
):
    """
    Create chip history enriched with derived metrics.

    Output includes all base history columns plus:
    - cnp_voltage (from IVg/VVg)
    - delta_ids (from It)
    - delta_vds (from Vt)
    """

    pipeline = MetricPipeline(base_dir)
    enriched_path = pipeline.enrich_chip_histories(chip_number, chip_group)

    console.print(f"[bold green]✓[/bold green] Enriched history saved to {enriched_path}")
```

## Usage Examples

### Extract All Metrics

```bash
# Extract metrics from all procedures
python3 process_and_analyze.py derive-all-metrics

# Extract only from specific procedures
python3 process_and_analyze.py derive-all-metrics --proc IVg,VVg
```

### Create Enriched History

```bash
# Create enriched history for chip 67
python3 process_and_analyze.py enrich-history 67

# View enriched history
python3 process_and_analyze.py show-history 67 --enriched
```

### Use in Plotting

Plotting commands can optionally use enriched histories:

```python
# src/plotting/its.py (modified)
def plot_its_with_cnp(df: pl.DataFrame, base_dir: Path, tag: str):
    """Plot ITS with CNP annotations."""

    # Check if enriched history is available
    enriched_path = base_dir / "data" / "03_derived" / "chip_histories_enriched" / f"Alisson67_history.parquet"

    if enriched_path.exists():
        history = pl.read_parquet(enriched_path)

        # Annotate plots with CNP if available
        for row in history.iter_rows(named=True):
            if row["cnp_voltage"] is not None:
                plt.axvline(row["cnp_voltage"], color="red", linestyle="--", alpha=0.5, label="CNP")

    # ... rest of plotting logic
```

## Testing

```bash
# Test CNP extraction on specific chip
python3 -c "
from src.derived.extractors.cnp_extractor import CNPExtractor
from src.core.utils import read_measurement_parquet
import polars as pl

extractor = CNPExtractor()
measurement = read_measurement_parquet('data/02_stage/raw_measurements/IVg/Alisson67_002.parquet')
metadata = {
    'run_id': 'test',
    'chip_number': 67,
    'chip_group': 'Alisson',
    'procedure': 'IVg',
    'vds': 0.1
}

result = extractor.extract(measurement, metadata)
print(f'CNP Voltage: {result.value_float} V')
print(f'Confidence: {result.confidence}')
print(f'Flags: {result.flags}')
"
```

## Adding New Metrics

To add a new metric extractor:

1. **Create extractor class** in `src/derived/extractors/my_metric.py`
2. **Inherit from `MetricExtractor`** and implement abstract methods
3. **Register in pipeline** by adding to `_default_extractors()` in `metric_pipeline.py`
4. **Test extraction** on sample data
5. **Update enriched history** logic in `enrich_chip_histories()` if needed

See existing extractors (`cnp_extractor.py`, `photoresponse_extractor.py`) as templates.

## Migration Path

1. **Phase 1**: Implement core pipeline (this document)
2. **Phase 2**: Add CNP and photoresponse extractors
3. **Phase 3**: Integrate enriched histories into plotting
4. **Phase 4**: Add more extractors as needed (mobility, hysteresis, etc.)
5. **Phase 5**: Deprecate inline calculations in plotting code

## Notes

- Derived metrics are **immutable** - if extraction algorithm changes, bump `extraction_version`
- Metrics can be **recomputed** without re-staging raw data
- **Confidence scores** help identify unreliable extractions
- **Flags** provide human-readable warnings for manual review
