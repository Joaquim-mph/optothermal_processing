"""
Metric pipeline for extracting derived analytical results from staged measurements.

This module orchestrates the extraction of metrics like CNP, photoresponse,
mobility, etc. from staged Parquet files using registered MetricExtractor instances.
"""

from __future__ import annotations

import polars as pl
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import logging

from src.core.utils import read_measurement_parquet
from src.models.derived_metrics import DerivedMetric
from .extractors.base import MetricExtractor

# Configure logging
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Pipeline Orchestration
# ══════════════════════════════════════════════════════════════════════

class MetricPipeline:
    """
    Orchestrates extraction of derived metrics from staged measurements.

    The pipeline:
    1. Loads manifest.parquet to identify measurements
    2. Filters by procedure type (only extract from applicable procedures)
    3. For each measurement:
       - Loads staged Parquet data
       - Runs applicable extractors
       - Validates results
       - Collects metrics
    4. Saves all metrics to metrics.parquet
    5. Optionally creates enriched chip histories

    Parameters
    ----------
    base_dir : Path
        Project base directory (contains data/ folder)
    extractors : Optional[List[MetricExtractor]]
        List of metric extractors to use. If None, uses default extractors.
    extraction_version : Optional[str]
        Code version string for provenance (e.g., 'v0.1.0+g1a2b3c')

    Examples
    --------
    >>> from src.derived import MetricPipeline
    >>> from src.derived.extractors.cnp_extractor import CNPExtractor
    >>>
    >>> pipeline = MetricPipeline(
    ...     base_dir=Path("."),
    ...     extractors=[CNPExtractor()]
    ... )
    >>>
    >>> # Extract all metrics
    >>> metrics_path = pipeline.derive_all_metrics(parallel=True, workers=6)
    >>>
    >>> # Create enriched history
    >>> history_path = pipeline.enrich_chip_history(chip_number=67)
    """

    def __init__(
        self,
        base_dir: Path,
        extractors: Optional[List[MetricExtractor]] = None,
        extraction_version: Optional[str] = None
    ):
        """Initialize pipeline with extractors."""
        self.base_dir = Path(base_dir)
        self.stage_dir = self.base_dir / "data" / "02_stage"
        self.derived_dir = self.base_dir / "data" / "03_derived"

        # Register extractors
        if extractors is None:
            self.extractors = self._default_extractors()
        else:
            self.extractors = extractors

        # Build extractor lookup by procedure
        self.extractor_map: Dict[str, List[MetricExtractor]] = {}
        for extractor in self.extractors:
            for proc in extractor.applicable_procedures:
                if proc not in self.extractor_map:
                    self.extractor_map[proc] = []
                self.extractor_map[proc].append(extractor)

        # Extraction version for provenance
        if extraction_version is None:
            extraction_version = self._get_git_version()
        self.extraction_version = extraction_version

        logger.info(
            f"Initialized MetricPipeline with {len(self.extractors)} extractors "
            f"covering {len(self.extractor_map)} procedures"
        )

    def _default_extractors(self) -> List[MetricExtractor]:
        """
        Return default set of metric extractors.

        Returns
        -------
        List[MetricExtractor]
            Default extractors
        """
        from .extractors.cnp_extractor import CNPExtractor
        from .extractors.photoresponse_extractor import PhotoresponseExtractor

        return [
            CNPExtractor(cluster_threshold_v=0.5, prominence_factor=0.1),
            PhotoresponseExtractor(vl_threshold=0.1, min_samples_per_state=5),
            # TODO: Add more extractors as they're implemented:
            # MobilityExtractor(),
        ]

    def _get_git_version(self) -> str:
        """Get git version for provenance tracking."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "describe", "--always", "--dirty"],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    # ═══════════════════════════════════════════════════════════════════
    # Main Pipeline Methods
    # ═══════════════════════════════════════════════════════════════════

    def derive_all_metrics(
        self,
        procedures: Optional[List[str]] = None,
        chip_numbers: Optional[List[int]] = None,
        parallel: bool = True,
        workers: int = 6,
        skip_existing: bool = False
    ) -> Path:
        """
        Extract all metrics from staged measurements.

        Parameters
        ----------
        procedures : Optional[List[str]]
            Filter to specific procedures (e.g., ['IVg', 'It']). If None, process all.
        chip_numbers : Optional[List[int]]
            Filter to specific chip numbers. If None, process all.
        parallel : bool
            Use multiprocessing for parallel extraction (default: True)
        workers : int
            Number of parallel workers (default: 6)
        skip_existing : bool
            Skip measurements that already have metrics (default: False)

        Returns
        -------
        Path
            Path to saved metrics.parquet file

        Examples
        --------
        >>> # Extract all metrics in parallel
        >>> pipeline.derive_all_metrics()
        PosixPath('data/03_derived/_metrics/metrics.parquet')

        >>> # Extract only from IVg measurements
        >>> pipeline.derive_all_metrics(procedures=['IVg'])

        >>> # Extract for specific chip
        >>> pipeline.derive_all_metrics(chip_numbers=[67])
        """
        logger.info("Starting metric extraction pipeline")

        # Load manifest
        manifest_path = self.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        manifest = pl.read_parquet(manifest_path)
        logger.info(f"Loaded manifest with {manifest.height} measurements")

        # Filter by procedure if specified
        if procedures:
            manifest = manifest.filter(pl.col("proc").is_in(procedures))
            logger.info(f"Filtered to {manifest.height} measurements in procedures: {procedures}")

        # Filter by chip numbers if specified
        if chip_numbers:
            manifest = manifest.filter(pl.col("chip_number").is_in(chip_numbers))
            logger.info(f"Filtered to {manifest.height} measurements for chips: {chip_numbers}")

        # Filter to only procedures with extractors
        applicable_procs = list(self.extractor_map.keys())
        manifest = manifest.filter(pl.col("proc").is_in(applicable_procs))
        logger.info(f"Found {manifest.height} measurements with applicable extractors")

        if manifest.height == 0:
            logger.warning("No measurements to process")
            return self._save_empty_metrics()

        # Load existing metrics if skip_existing
        existing_run_ids = set()
        if skip_existing:
            existing_metrics_path = self.derived_dir / "_metrics" / "metrics.parquet"
            if existing_metrics_path.exists():
                existing_metrics = pl.read_parquet(existing_metrics_path)
                existing_run_ids = set(existing_metrics["run_id"].unique().to_list())
                logger.info(f"Found {len(existing_run_ids)} measurements with existing metrics")

        # Extract metrics
        if parallel:
            metrics = self._extract_parallel(manifest, workers, existing_run_ids)
        else:
            metrics = self._extract_sequential(manifest, existing_run_ids)

        logger.info(f"Extracted {len(metrics)} metrics from {manifest.height} measurements")

        # Save metrics
        metrics_path = self._save_metrics(metrics)

        return metrics_path

    def _extract_sequential(
        self,
        manifest: pl.DataFrame,
        skip_run_ids: set
    ) -> List[DerivedMetric]:
        """Extract metrics sequentially (for debugging)."""
        metrics = []
        total = manifest.height

        for i, row in enumerate(manifest.iter_rows(named=True), 1):
            if row["run_id"] in skip_run_ids:
                logger.debug(f"[{i}/{total}] Skipping {row['run_id']} (already processed)")
                continue

            chip_name = f"{row.get('chip_group', '?')}{row.get('chip_number', '?')}"
            logger.info(
                f"[{i}/{total}] Processing {chip_name} "
                f"({row.get('proc', '?')})"
            )

            row_metrics = self._extract_from_measurement(row)
            metrics.extend(row_metrics)

        return metrics

    def _extract_parallel(
        self,
        manifest: pl.DataFrame,
        workers: int,
        skip_run_ids: set
    ) -> List[DerivedMetric]:
        """Extract metrics in parallel using ProcessPoolExecutor."""
        rows = [
            row for row in manifest.iter_rows(named=True)
            if row["run_id"] not in skip_run_ids
        ]

        if not rows:
            logger.info("All measurements already processed")
            return []

        logger.info(f"Processing {len(rows)} measurements with {workers} workers")

        metrics = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            future_to_row = {
                executor.submit(self._extract_from_measurement, row): row
                for row in rows
            }

            # Collect results as they complete
            completed = 0
            total = len(future_to_row)

            for future in as_completed(future_to_row):
                completed += 1
                row = future_to_row[future]

                try:
                    row_metrics = future.result()
                    metrics.extend(row_metrics)
                    chip_name = f"{row.get('chip_group', '?')}{row.get('chip_number', '?')}"
                    logger.info(
                        f"[{completed}/{total}] Completed {chip_name} "
                        f"({row.get('proc', '?')}) - extracted {len(row_metrics)} metrics"
                    )
                except Exception as e:
                    chip_name = f"{row.get('chip_group', '?')}{row.get('chip_number', '?')}"
                    logger.error(
                        f"[{completed}/{total}] Failed {chip_name} "
                        f"({row.get('proc', '?')}): {e}"
                    )

        return metrics

    def _extract_from_measurement(self, metadata: Dict[str, Any]) -> List[DerivedMetric]:
        """
        Extract all applicable metrics from a single measurement.

        Parameters
        ----------
        metadata : Dict[str, Any]
            Metadata from manifest.parquet row

        Returns
        -------
        List[DerivedMetric]
            Extracted metrics (may be empty if all extractors fail)
        """
        metrics = []

        procedure = metadata.get("proc", metadata.get("procedure"))  # Support both column names
        parquet_path = Path(metadata.get("parquet_path", metadata.get("path")))

        # Get extractors for this procedure
        extractors = self.extractor_map.get(procedure, [])

        if not extractors:
            return metrics

        # Load measurement data
        try:
            measurement = read_measurement_parquet(parquet_path)
        except Exception as e:
            logger.error(f"Failed to load {parquet_path}: {e}")
            return metrics

        # Add extraction version to metadata for provenance
        metadata["extraction_version"] = self.extraction_version

        # Run each applicable extractor
        for extractor in extractors:
            try:
                metric = extractor.extract(measurement, metadata)

                if metric is None:
                    logger.debug(f"Extractor {extractor.metric_name} returned None for {parquet_path}")
                    continue

                # Validate result
                if not extractor.validate(metric):
                    logger.warning(
                        f"Validation failed for {extractor.metric_name} from {parquet_path}: "
                        f"value={metric.value_float}"
                    )
                    # Still save the metric but log the warning

                metrics.append(metric)

            except Exception as e:
                logger.error(
                    f"Extractor {extractor.metric_name} failed on {parquet_path}: {e}",
                    exc_info=True
                )

        return metrics

    # ═══════════════════════════════════════════════════════════════════
    # Saving & Loading
    # ═══════════════════════════════════════════════════════════════════

    def _save_metrics(self, metrics: List[DerivedMetric]) -> Path:
        """
        Save metrics to Parquet file.

        Parameters
        ----------
        metrics : List[DerivedMetric]
            Metrics to save

        Returns
        -------
        Path
            Path to saved metrics.parquet
        """
        metrics_dir = self.derived_dir / "_metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = metrics_dir / "metrics.parquet"

        if not metrics:
            logger.warning("No metrics to save - creating empty metrics.parquet")
            return self._save_empty_metrics()

        # Convert to Polars DataFrame
        metrics_dicts = [m.model_dump() for m in metrics]
        metrics_df = pl.DataFrame(metrics_dicts)

        # Sort by chip, procedure, sequence number for better compression
        metrics_df = metrics_df.sort(["chip_group", "chip_number", "procedure", "seq_num"])

        # Write to Parquet
        metrics_df.write_parquet(metrics_path)

        logger.info(f"Saved {len(metrics)} metrics to {metrics_path}")

        return metrics_path

    def _save_empty_metrics(self) -> Path:
        """Create empty metrics.parquet with correct schema."""
        metrics_dir = self.derived_dir / "_metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = metrics_dir / "metrics.parquet"

        # Create empty DataFrame with correct schema
        empty_df = pl.DataFrame({
            "run_id": pl.Series([], dtype=pl.Utf8),
            "chip_number": pl.Series([], dtype=pl.Int64),
            "chip_group": pl.Series([], dtype=pl.Utf8),
            "procedure": pl.Series([], dtype=pl.Utf8),
            "seq_num": pl.Series([], dtype=pl.Int64),
            "metric_name": pl.Series([], dtype=pl.Utf8),
            "metric_category": pl.Series([], dtype=pl.Utf8),
            "value_float": pl.Series([], dtype=pl.Float64),
            "value_str": pl.Series([], dtype=pl.Utf8),
            "value_json": pl.Series([], dtype=pl.Utf8),
            "unit": pl.Series([], dtype=pl.Utf8),
            "extraction_method": pl.Series([], dtype=pl.Utf8),
            "extraction_version": pl.Series([], dtype=pl.Utf8),
            "extraction_timestamp": pl.Series([], dtype=pl.Datetime),
            "confidence": pl.Series([], dtype=pl.Float64),
            "flags": pl.Series([], dtype=pl.Utf8),
        })

        empty_df.write_parquet(metrics_path)

        return metrics_path

    # ═══════════════════════════════════════════════════════════════════
    # Enriched Chip Histories
    # ═══════════════════════════════════════════════════════════════════

    def enrich_chip_history(
        self,
        chip_number: int,
        chip_group: str = "Alisson",
        metric_names: Optional[List[str]] = None
    ) -> Path:
        """
        Create enriched chip history with derived metrics as columns.

        Parameters
        ----------
        chip_number : int
            Chip number
        chip_group : str
            Chip group name (default: 'Alisson')
        metric_names : Optional[List[str]]
            Specific metrics to include. If None, includes all available metrics.

        Returns
        -------
        Path
            Path to enriched history Parquet file

        Examples
        --------
        >>> # Enrich history with all available metrics
        >>> pipeline.enrich_chip_history(67)

        >>> # Enrich with specific metrics only
        >>> pipeline.enrich_chip_history(67, metric_names=['cnp_voltage', 'mobility'])
        """
        # Load base history
        history_path = self.stage_dir / "chip_histories" / f"{chip_group}{chip_number}_history.parquet"
        if not history_path.exists():
            raise FileNotFoundError(f"Chip history not found: {history_path}")

        history = pl.read_parquet(history_path)
        logger.info(f"Loaded chip history with {history.height} measurements")

        # Load metrics
        metrics_path = self.derived_dir / "_metrics" / "metrics.parquet"
        if not metrics_path.exists():
            logger.warning(f"No metrics found at {metrics_path} - creating history without metrics")
            enriched_path = self._save_enriched_history(history, chip_number, chip_group)
            return enriched_path

        metrics = pl.read_parquet(metrics_path)

        # Filter metrics for this chip
        chip_metrics = metrics.filter(
            (pl.col("chip_number") == chip_number) &
            (pl.col("chip_group") == chip_group)
        )

        if metric_names:
            chip_metrics = chip_metrics.filter(pl.col("metric_name").is_in(metric_names))

        logger.info(f"Found {chip_metrics.height} metrics for this chip")

        # Pivot metrics to wide format (one column per metric)
        # Get unique metric names
        unique_metrics = chip_metrics["metric_name"].unique().to_list()

        # Drop existing metric columns to avoid duplicates with _right suffix
        for metric_name in unique_metrics:
            if metric_name in history.columns:
                history = history.drop(metric_name)
                logger.info(f"Dropped existing column '{metric_name}' before re-enrichment")

        for metric_name in unique_metrics:
            metric_df = chip_metrics.filter(pl.col("metric_name") == metric_name)

            # Select run_id and value (prefer float, then str, then json)
            metric_df = metric_df.select([
                "run_id",
                pl.coalesce(["value_float", "value_str", "value_json"]).alias(metric_name)
            ])

            # Join to history
            history = history.join(metric_df, on="run_id", how="left")

        # Save enriched history
        enriched_path = self._save_enriched_history(history, chip_number, chip_group)

        return enriched_path

    def _save_enriched_history(
        self,
        history: pl.DataFrame,
        chip_number: int,
        chip_group: str
    ) -> Path:
        """Save enriched chip history."""
        enriched_dir = self.derived_dir / "chip_histories_enriched"
        enriched_dir.mkdir(parents=True, exist_ok=True)

        enriched_path = enriched_dir / f"{chip_group}{chip_number}_history.parquet"
        history.write_parquet(enriched_path)

        logger.info(f"Saved enriched history to {enriched_path}")

        return enriched_path

    def enrich_all_chip_histories(self) -> List[Path]:
        """
        Create enriched histories for all chips in manifest.

        Returns
        -------
        List[Path]
            Paths to all enriched history files

        Examples
        --------
        >>> paths = pipeline.enrich_all_chip_histories()
        >>> print(f"Created {len(paths)} enriched histories")
        """
        # Load manifest to find all chips
        manifest_path = self.stage_dir / "_manifest" / "manifest.parquet"
        manifest = pl.read_parquet(manifest_path)

        # Get unique chip combinations
        chips = (
            manifest
            .select(["chip_group", "chip_number"])
            .unique()
            .filter(pl.col("chip_number").is_not_null())
        )

        logger.info(f"Creating enriched histories for {chips.height} chips")

        enriched_paths = []
        for row in chips.iter_rows(named=True):
            try:
                path = self.enrich_chip_history(
                    chip_number=row["chip_number"],
                    chip_group=row["chip_group"]
                )
                enriched_paths.append(path)
            except Exception as e:
                logger.error(
                    f"Failed to enrich history for {row['chip_group']}{row['chip_number']}: {e}"
                )

        logger.info(f"Created {len(enriched_paths)} enriched histories")

        return enriched_paths
