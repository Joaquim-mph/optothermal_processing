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
    finished = pyqtSignal(object)      # PlotResult
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
            self.finished.emit(result)
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(str(e), type(e).__name__, tb)

    def _on_progress(self, percent: float, status: str) -> None:
        self.progress.emit(percent, status)


class PipelineWorker(QThread):
    """Background thread for the full data processing pipeline."""

    progress = pyqtSignal(float, str)   # percent, status_msg
    finished = pyqtSignal(dict)          # result stats dict
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

            manifest = pl.read_parquet(manifest_path).filter(pl.col("status") == "ok")
            chip_numbers = manifest.select("chip_number").unique().filter(
                pl.col("chip_number").is_not_null()
            ).height

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

            self.finished.emit({
                "elapsed": elapsed,
                "files_processed": total_csvs,
                "experiments": manifest.height,
                "histories": histories_created,
                "total_chips": chip_numbers,
            })

        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(str(e), type(e).__name__, tb)
