"""
QThread workers for long-running operations.

PlotWorker runs plot_executor.execute_plot() in a background thread,
emitting progress/finished/error signals for the GUI.
"""

from __future__ import annotations
import traceback

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.plot_executor import PlotRequest, PlotResult, execute_plot


class PlotWorker(QThread):
    """Background thread for plot generation."""

    progress = pyqtSignal(float, str)  # percent, status_msg
    completed = pyqtSignal(object)     # PlotResult
    error = pyqtSignal(str, str, str)  # error_msg, error_type, traceback

    def __init__(self, request: PlotRequest, parent=None):
        super().__init__(parent)
        self._request = request

    def run(self) -> None:
        try:
            result = execute_plot(
                self._request,
                progress=self._on_progress,
            )
            self.completed.emit(result)
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(str(e), type(e).__name__, tb)

    def _on_progress(self, percent: float, status: str) -> None:
        self.progress.emit(percent, status)


class BatchPlotWorker(QThread):
    """Background thread for batch plot generation from YAML config."""

    plot_started = pyqtSignal(int, int, str)   # current_index, total, description
    plot_finished = pyqtSignal(int, object)     # current_index, PlotResult
    all_finished = pyqtSignal(list)             # list[PlotResult]
    error = pyqtSignal(str, str, str)           # error_msg, error_type, traceback

    def __init__(self, config_path: str, parallel: bool = False, workers: int = 4, parent=None):
        super().__init__(parent)
        self._config_path = config_path
        self._parallel = parallel
        self._workers = workers
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation (checked between plots / shuts down executor)."""
        self._cancelled = True

    def run(self) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")

            from pathlib import Path
            from src.plotting.batch import load_batch_config, execute_plot as batch_execute_plot

            chip, chip_group, plot_specs = load_batch_config(Path(self._config_path))
            total = len(plot_specs)

            if self._parallel and total > 1:
                results = self._run_parallel(plot_specs, chip_group, total)
            else:
                results = self._run_sequential(plot_specs, chip_group, total)

            self.all_finished.emit(results)

        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(str(e), type(e).__name__, tb)

    def _run_sequential(self, plot_specs, chip_group: str, total: int) -> list:
        from src.plotting.batch import execute_plot as batch_execute_plot

        results = []
        for i, spec in enumerate(plot_specs):
            if self._cancelled:
                break

            tag_str = f" ({spec.tag})" if spec.tag else ""
            desc = f"{spec.type}{tag_str}"
            self.plot_started.emit(i, total, desc)

            result = batch_execute_plot(spec, chip_group, quiet=True)
            results.append(result)
            self.plot_finished.emit(i, result)

        return results

    def _run_parallel(self, plot_specs, chip_group: str, total: int) -> list:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from src.plotting.batch import execute_plot as batch_execute_plot, _worker_init

        results = []
        completed = 0

        self.plot_started.emit(0, total, f"Parallel ({self._workers} workers)")

        with ProcessPoolExecutor(max_workers=self._workers, initializer=_worker_init) as executor:
            futures = {
                executor.submit(batch_execute_plot, spec, chip_group, True): spec
                for spec in plot_specs
            }

            for future in as_completed(futures):
                if self._cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                result = future.result()
                results.append(result)
                completed += 1
                self.plot_finished.emit(completed - 1, result)
                self.plot_started.emit(completed, total, f"Parallel ({self._workers} workers)")

        return results


class PipelineWorker(QThread):
    """Background thread for the full data processing pipeline."""

    progress = pyqtSignal(float, str)    # percent, status_msg
    completed = pyqtSignal(dict)         # result stats dict
    error = pyqtSignal(str, str, str)    # error_msg, error_type, traceback

    def run(self) -> None:
        import time
        start = time.time()

        try:
            import matplotlib
            matplotlib.use("Agg")

            import polars as pl
            from pathlib import Path
            from src.models.parameters import StagingParameters
            from src.core import run_staging_pipeline_tui, discover_csvs
            from src.core.history_builder import generate_all_chip_histories

            raw_root = Path("data/01_raw")
            stage_root = Path("data/02_stage/raw_measurements")
            history_dir = Path("data/02_stage/chip_histories")
            procedures_yaml = Path("config/procedures.yml")
            manifest_path = stage_root / "_manifest" / "manifest.parquet"

            # Step 1: Staging (0-60%)
            self.progress.emit(5, "Discovering CSV files...")
            csv_files = discover_csvs(raw_root)
            total_csvs = len(csv_files)

            if total_csvs == 0:
                raise ValueError(f"No CSV files found in {raw_root}")

            self.progress.emit(10, f"Staging {total_csvs} files...")

            params = StagingParameters(
                raw_root=raw_root,
                stage_root=stage_root,
                procedures_yaml=procedures_yaml,
                local_tz="America/Santiago",
                workers=6,
                polars_threads=1,
                force=False,
                only_yaml_data=False,
            )
            run_staging_pipeline_tui(params)
            self.progress.emit(60, "Staging complete")

            # Step 2: Chip histories (60-75%)
            self.progress.emit(60, "Building chip histories...")

            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest_path}")

            manifest = pl.read_parquet(manifest_path)

            history_dir.mkdir(parents=True, exist_ok=True)
            histories = generate_all_chip_histories(
                manifest_path=manifest_path,
                output_dir=history_dir,
                chip_group=None,
                min_experiments=1,
                stage_root=stage_root,
            )
            histories_created = len(histories)
            self.progress.emit(75, f"Created {histories_created} histories")

            # Step 3: Derive metrics (75-87%)
            self.progress.emit(75, "Extracting derived metrics...")
            metrics_count = 0
            try:
                from src.derived.metric_pipeline import MetricPipeline
                pipeline = MetricPipeline(
                    base_dir=Path("."),
                    extraction_version=None,
                    stage_root=stage_root,
                    manifest_path=manifest_path,
                )
                metrics_path = pipeline.derive_all_metrics(
                    procedures=None, chip_numbers=None,
                    parallel=True, workers=6, skip_existing=True,
                )
                if metrics_path.exists():
                    metrics_count = pl.read_parquet(metrics_path).height
            except Exception:
                pass  # Non-fatal
            self.progress.emit(87, f"Extracted {metrics_count} metrics")

            # Step 4: Enrich histories (87-95%)
            self.progress.emit(87, "Enriching histories...")
            try:
                enriched_paths = pipeline.enrich_all_chip_histories()
                self.progress.emit(95, f"Enriched {len(enriched_paths)} histories")
            except Exception:
                self.progress.emit(95, "Enrichment had errors (non-fatal)")

            self.progress.emit(100, "Complete!")
            elapsed = time.time() - start

            self.completed.emit({
                "elapsed": elapsed,
                "files_processed": total_csvs,
                "experiments": manifest.height,
                "histories": histories_created,
                "total_chips": histories_created,
            })

        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(str(e), type(e).__name__, tb)


class PipelineStepWorker(QThread):
    """Background thread for individual pipeline steps."""

    progress = pyqtSignal(float, str)    # percent, status_msg
    completed = pyqtSignal(dict)         # result dict
    error = pyqtSignal(str, str, str)    # error_msg, error_type, traceback
    log_output = pyqtSignal(str)         # text output for info-only commands

    # Step descriptions shown as progress messages
    STEP_LABELS = {
        "full_pipeline": "Running full pipeline",
        "stage_all": "Staging raw CSVs",
        "build_histories": "Building chip histories",
        "derive_all_metrics": "Extracting all metrics",
        "derive_fitting_metrics": "Extracting fitting metrics",
        "derive_consecutive_sweeps": "Extracting consecutive sweep differences",
        "enrich_history": "Enriching chip histories",
        "validate_manifest": "Validating manifest",
        "staging_stats": "Gathering staging statistics",
    }

    def __init__(self, step_name: str, options: dict | None = None, parent=None):
        super().__init__(parent)
        self._step_name = step_name
        self._options = options or {}

    def run(self) -> None:
        import time
        start = time.time()

        try:
            import matplotlib
            matplotlib.use("Agg")

            handler = getattr(self, f"_run_{self._step_name}", None)
            if handler is None:
                raise ValueError(f"Unknown pipeline step: {self._step_name}")

            result = handler()
            result["elapsed"] = time.time() - start
            result["step_name"] = self._step_name
            self.progress.emit(100, "Complete!")
            self.completed.emit(result)

        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(str(e), type(e).__name__, tb)

    # ── Step implementations ──────────────────────────────────────

    def _run_stage_all(self) -> dict:
        from pathlib import Path
        from src.models.parameters import StagingParameters
        from src.core import run_staging_pipeline_tui, discover_csvs

        raw_root = Path("data/01_raw")
        stage_root = Path("data/02_stage/raw_measurements")
        procedures_yaml = Path("config/procedures.yml")

        self.progress.emit(5, "Discovering CSV files...")
        csv_files = discover_csvs(raw_root)
        total_csvs = len(csv_files)

        if total_csvs == 0:
            raise ValueError(f"No CSV files found in {raw_root}")

        self.progress.emit(10, f"Staging {total_csvs} files...")

        workers = self._options.get("workers", 6)
        force = self._options.get("force", False)
        strict = self._options.get("strict", False)

        params = StagingParameters(
            raw_root=raw_root,
            stage_root=stage_root,
            procedures_yaml=procedures_yaml,
            local_tz="America/Santiago",
            workers=workers,
            polars_threads=1,
            force=force,
            only_yaml_data=False,
            strict=strict,
        )
        run_staging_pipeline_tui(params)

        self.progress.emit(90, "Staging complete")

        # Count results
        import polars as pl
        manifest_path = stage_root / "_manifest" / "manifest.parquet"
        experiments = 0
        if manifest_path.exists():
            experiments = pl.read_parquet(manifest_path).filter(
                pl.col("status") == "ok"
            ).height

        return {
            "files_processed": total_csvs,
            "experiments": experiments,
            "summary": f"Staged {total_csvs} CSV files -> {experiments} experiments",
        }

    def _run_build_histories(self) -> dict:
        from pathlib import Path
        import polars as pl
        from src.core.history_builder import generate_all_chip_histories

        stage_root = Path("data/02_stage/raw_measurements")
        history_dir = Path("data/02_stage/chip_histories")
        manifest_path = stage_root / "_manifest" / "manifest.parquet"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        self.progress.emit(10, "Reading manifest...")

        chip_group = self._options.get("chip_group") or None
        min_experiments = self._options.get("min_experiments", 1)

        self.progress.emit(20, "Building chip histories...")
        history_dir.mkdir(parents=True, exist_ok=True)
        histories = generate_all_chip_histories(
            manifest_path=manifest_path,
            output_dir=history_dir,
            chip_group=chip_group,
            min_experiments=min_experiments,
            stage_root=stage_root,
        )
        histories_created = len(histories)

        self.progress.emit(90, f"Created {histories_created} histories")

        # Count unique chips from the histories actually generated
        total_chips = len(histories)

        return {
            "histories": histories_created,
            "total_chips": total_chips,
            "summary": f"Generated {histories_created} chip histories",
        }

    def _run_derive_all_metrics(self) -> dict:
        from pathlib import Path
        import polars as pl
        from src.derived.metric_pipeline import MetricPipeline

        stage_root = Path("data/02_stage/raw_measurements")
        manifest_path = stage_root / "_manifest" / "manifest.parquet"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        self.progress.emit(10, "Initializing metric pipeline...")

        workers = self._options.get("workers", 6)
        force = self._options.get("force", False)
        skip_existing = not force

        pipeline = MetricPipeline(
            base_dir=Path("."),
            extraction_version=None,
            stage_root=stage_root,
            manifest_path=manifest_path,
        )

        self.progress.emit(20, "Extracting metrics...")
        metrics_path = pipeline.derive_all_metrics(
            procedures=None,
            chip_numbers=None,
            parallel=True,
            workers=workers,
            skip_existing=skip_existing,
        )

        metrics_count = 0
        if metrics_path.exists():
            metrics_count = pl.read_parquet(metrics_path).height

        self.progress.emit(90, f"Extracted {metrics_count} metrics")
        return {
            "metrics_count": metrics_count,
            "metrics_path": str(metrics_path),
            "summary": f"Extracted {metrics_count} metrics",
        }

    def _run_derive_fitting_metrics(self) -> dict:
        from pathlib import Path
        import polars as pl
        from src.derived.metric_pipeline import MetricPipeline
        from src.derived.extractors import (
            ITSRelaxationExtractor,
            ITSThreePhaseFitExtractor,
            DriftExtractor,
        )

        stage_root = Path("data/02_stage/raw_measurements")
        manifest_path = stage_root / "_manifest" / "manifest.parquet"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        self.progress.emit(10, "Initializing fitting extractors...")

        workers = self._options.get("workers", 6)
        force = self._options.get("force", False)
        skip_existing = not force

        pipeline = MetricPipeline(
            base_dir=Path("."),
            extractors=[
                ITSRelaxationExtractor(),
                ITSThreePhaseFitExtractor(),
                DriftExtractor(),
            ],
            extraction_version=None,
            stage_root=stage_root,
            manifest_path=manifest_path,
        )

        self.progress.emit(20, "Extracting fitting metrics (Numba-accelerated)...")
        metrics_path = pipeline.derive_all_metrics(
            procedures=None,
            chip_numbers=None,
            parallel=True,
            workers=workers,
            skip_existing=skip_existing,
        )

        metrics_count = 0
        if metrics_path.exists():
            metrics_count = pl.read_parquet(metrics_path).height

        self.progress.emit(90, f"Extracted {metrics_count} fitting metrics")
        return {
            "metrics_count": metrics_count,
            "metrics_path": str(metrics_path),
            "summary": f"Extracted {metrics_count} fitting metrics (relaxation, 3-phase, drift)",
        }

    def _run_derive_consecutive_sweeps(self) -> dict:
        from pathlib import Path
        import polars as pl
        from src.derived.metric_pipeline import MetricPipeline
        from src.derived.extractors import ConsecutiveSweepDifferenceExtractor

        stage_root = Path("data/02_stage/raw_measurements")
        manifest_path = stage_root / "_manifest" / "manifest.parquet"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        self.progress.emit(10, "Initializing consecutive sweep extractor...")

        workers = self._options.get("workers", 6)
        force = self._options.get("force", False)
        skip_existing = not force

        pipeline = MetricPipeline(
            base_dir=Path("."),
            extractors=[],
            pairwise_extractors=[ConsecutiveSweepDifferenceExtractor()],
            extraction_version=None,
            stage_root=stage_root,
            manifest_path=manifest_path,
        )

        self.progress.emit(20, "Extracting consecutive sweep differences...")
        metrics_path = pipeline.derive_all_metrics(
            procedures=None,
            chip_numbers=None,
            parallel=True,
            workers=workers,
            skip_existing=skip_existing,
        )

        metrics_count = 0
        if metrics_path.exists():
            metrics_count = pl.read_parquet(metrics_path).height

        self.progress.emit(90, f"Extracted {metrics_count} sweep difference metrics")
        return {
            "metrics_count": metrics_count,
            "metrics_path": str(metrics_path),
            "summary": f"Extracted {metrics_count} consecutive sweep difference metrics",
        }

    def _run_enrich_history(self) -> dict:
        from pathlib import Path
        from src.derived.metric_pipeline import MetricPipeline

        stage_root = Path("data/02_stage/raw_measurements")
        manifest_path = stage_root / "_manifest" / "manifest.parquet"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        self.progress.emit(10, "Initializing enrichment pipeline...")

        pipeline = MetricPipeline(
            base_dir=Path("."),
            extraction_version=None,
            stage_root=stage_root,
            manifest_path=manifest_path,
        )

        chip_number = self._options.get("chip_number")
        all_chips = self._options.get("all_chips", True)

        if chip_number and not all_chips:
            self.progress.emit(30, f"Enriching chip {chip_number}...")
            chip_group = self._options.get("chip_group", "Alisson")
            path = pipeline.enrich_chip_history(
                chip_number=chip_number,
                chip_group=chip_group,
            )
            self.progress.emit(90, "Enrichment complete")
            return {
                "enriched_count": 1,
                "summary": f"Enriched history for chip {chip_group}{chip_number}",
            }
        else:
            self.progress.emit(30, "Enriching all chip histories...")
            enriched_paths = pipeline.enrich_all_chip_histories()
            count = len(enriched_paths)
            self.progress.emit(90, f"Enriched {count} histories")
            return {
                "enriched_count": count,
                "summary": f"Enriched {count} chip histories with metrics and calibrations",
            }

    def _run_validate_manifest(self) -> dict:
        """Quick info command - validates manifest schema."""
        from pathlib import Path
        import polars as pl

        stage_root = Path("data/02_stage/raw_measurements")
        manifest_path = stage_root / "_manifest" / "manifest.parquet"

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        self.progress.emit(20, "Loading manifest...")
        df = pl.read_parquet(manifest_path)
        total_rows = df.height

        self.progress.emit(40, "Validating schema...")

        lines = []
        lines.append(f"Manifest: {manifest_path}")
        lines.append(f"Total rows: {total_rows}")

        # Status counts
        status_counts = df.group_by("status").len().sort("len", descending=True)
        status_parts = []
        for row in status_counts.iter_rows(named=True):
            status_parts.append(f"{row['status']}: {row['len']}")
        lines.append("Status: " + ", ".join(status_parts))

        ok_count = df.filter(pl.col("status") == "ok").height

        # Procedure counts (use full manifest, not just "ok" rows)
        lines.append("")
        lines.append("Procedures:")
        proc_counts = df.group_by("proc").len().sort("len", descending=True)
        for row in proc_counts.iter_rows(named=True):
            lines.append(f"  {row['proc']}: {row['len']}")

        # Unique chips (use full manifest)
        lines.append("")
        unique_chips = df.select("chip_number").unique().filter(
            pl.col("chip_number").is_not_null()
        ).height
        lines.append(f"Unique chips: {unique_chips}")

        # Duplicate run_id check
        lines.append("")
        dup_count = total_rows - df.select("run_id").unique().height
        if dup_count > 0:
            lines.append(f"WARNING: {dup_count} duplicate run_id values!")
        else:
            lines.append("No duplicate run_ids found.")

        # Date range
        if "start_time_utc" in df.columns:
            dated_df = df.filter(pl.col("start_time_utc").is_not_null())
            if dated_df.height > 0:
                min_dt = dated_df.select(pl.col("start_time_utc").min()).item()
                max_dt = dated_df.select(pl.col("start_time_utc").max()).item()
                lines.append(f"Date range: {min_dt} to {max_dt}")

        # Schema validation via Pydantic
        lines.append("")
        self.progress.emit(60, "Validating Pydantic schema...")
        try:
            from src.models.manifest import ManifestRow
            from pydantic import TypeAdapter
            ta = TypeAdapter(list[ManifestRow])
            ta.validate_python(df.to_dicts())
            lines.append("Schema validation: PASSED")
        except Exception as e:
            lines.append(f"Schema validation: FAILED - {e}")

        output = "\n".join(lines)
        self.log_output.emit(output)
        self.progress.emit(90, "Validation complete")

        return {
            "total_rows": total_rows,
            "ok_count": ok_count,
            "unique_chips": unique_chips,
            "output": output,
            "summary": f"Manifest validated: {total_rows} rows, {unique_chips} chips",
        }

    def _run_staging_stats(self) -> dict:
        """Quick info command - gathering staging directory statistics."""
        from pathlib import Path
        import polars as pl

        raw_root = Path("data/01_raw")
        stage_root = Path("data/02_stage/raw_measurements")
        history_dir = Path("data/02_stage/chip_histories")
        derived_dir = Path("data/03_derived")
        manifest_path = stage_root / "_manifest" / "manifest.parquet"

        self.progress.emit(10, "Scanning directories...")

        lines = []

        # Raw CSV count
        csv_count = len(list(raw_root.glob("*.csv"))) if raw_root.exists() else 0
        lines.append(f"Raw CSVs:    {csv_count} files in {raw_root}")

        # Staged parquet count
        if stage_root.exists():
            parquet_files = list(stage_root.rglob("*.parquet"))
            # Exclude manifest directory
            parquet_files = [p for p in parquet_files if "_manifest" not in str(p)]
            staged_count = len(parquet_files)
            staged_size_mb = sum(p.stat().st_size for p in parquet_files) / (1024 * 1024)
            lines.append(f"Staged:      {staged_count} parquet files ({staged_size_mb:.1f} MB) in {stage_root}")
        else:
            lines.append(f"Staged:      directory not found ({stage_root})")

        # Manifest info
        if manifest_path.exists():
            df = pl.read_parquet(manifest_path)
            status_counts = df.group_by("status").len().sort("len", descending=True)
            status_str = ", ".join(
                f"{r['status']}: {r['len']}" for r in status_counts.iter_rows(named=True)
            )
            lines.append(f"Manifest:    {df.height} rows ({status_str})")
        else:
            lines.append(f"Manifest:    not found ({manifest_path})")

        # History files
        if history_dir.exists():
            history_files = list(history_dir.glob("*_history.parquet"))
            lines.append(f"Histories:   {len(history_files)} chip history files")
        else:
            lines.append(f"Histories:   directory not found ({history_dir})")

        # Derived metrics
        metrics_path = derived_dir / "_metrics" / "metrics.parquet"
        if metrics_path.exists():
            metrics_df = pl.read_parquet(metrics_path)
            lines.append(f"Metrics:     {metrics_df.height} derived metric rows")
        else:
            lines.append(f"Metrics:     not found ({metrics_path})")

        # Enriched histories
        enriched_dir = derived_dir / "chip_histories_enriched"
        if enriched_dir.exists():
            enriched_files = list(enriched_dir.glob("*.parquet"))
            lines.append(f"Enriched:    {len(enriched_files)} enriched history files")
        else:
            lines.append(f"Enriched:    directory not found ({enriched_dir})")

        output = "\n".join(lines)
        self.log_output.emit(output)
        self.progress.emit(90, "Stats gathered")

        return {
            "output": output,
            "summary": f"Staging stats: {csv_count} raw CSVs",
        }
