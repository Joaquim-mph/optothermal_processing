"""
Data Processing Loading Screen.

Shows progress while staging data and generating chip histories using the modern pipeline.
"""

from __future__ import annotations
import time
import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, ProgressBar
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class ProcessLoadingScreen(WizardScreen):
    """Loading screen for modern staging pipeline + history generation."""

    SCREEN_TITLE = "Processing Data..."
    STEP_NUMBER = None  # Not part of main wizard flow

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CSS = WizardScreen.CSS + """
    #status {
        width: 100%;
        content-align: center middle;
        color: $text;
        margin-bottom: 2;
        min-height: 3;
    }

    #progress-container {
        width: 100%;
        height: auto;
        margin-bottom: 2;
        padding: 0 20;
    }

    #progress-bar {
        width: 100%;
    }

    #current-task {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 2;
    }

    #stats {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: dim;
        margin-top: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.processing_thread = None
        self.start_time = None

    def compose_content(self) -> ComposeResult:
        """Create loading screen widgets."""
        yield Static("⣾ Initializing...", id="status")
        with Horizontal(id="progress-container"):
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
        yield Static("Starting modern staging pipeline", id="current-task")
        yield Static("", id="stats")

    def on_mount(self) -> None:
        """Start processing when screen loads."""
        self.start_time = time.time()

        # Start processing in background thread
        self.processing_thread = threading.Thread(target=self._run_processing, daemon=True)
        self.processing_thread.start()

    def _run_processing(self) -> None:
        """Run the modern staging pipeline in background thread."""
        try:
            # Force non-interactive matplotlib backend for thread-safety
            import matplotlib
            matplotlib.use('Agg')

            # Import modern pipeline modules
            import polars as pl
            from src.models.parameters import StagingParameters
            from src.core import run_staging_pipeline, discover_csvs
            from src.core.history_builder import generate_all_chip_histories

            # Define paths (matching full-pipeline defaults)
            raw_root = Path("data/01_raw")
            stage_root = Path("data/02_stage/raw_measurements")
            history_dir = Path("data/02_stage/chip_histories")
            procedures_yaml = Path("config/procedures.yml")
            manifest_path = stage_root / "_manifest" / "manifest.parquet"

            # ═══════════════════════════════════════════════════════════
            # STEP 1: STAGING (0-60%)
            # ═══════════════════════════════════════════════════════════

            self.app.call_from_thread(
                self._update_progress,
                0,
                "⣾ Step 1/2: Staging raw CSVs → Parquet..."
            )

            # Validate paths
            if not raw_root.exists():
                raise FileNotFoundError(f"Raw data directory not found: {raw_root}")
            if not procedures_yaml.exists():
                raise FileNotFoundError(f"Procedures schema not found: {procedures_yaml}")

            # Discover CSV files
            self.app.call_from_thread(
                self._update_progress,
                5,
                "⣾ Discovering CSV files..."
            )
            csv_files = discover_csvs(raw_root)
            total_csvs = len(csv_files)

            if total_csvs == 0:
                raise ValueError(f"No CSV files found in {raw_root}")

            self.app.call_from_thread(
                self._update_progress,
                10,
                f"⣾ Found {total_csvs} CSV file(s), starting staging..."
            )

            # Create staging parameters
            # Use single worker for TUI to avoid multiprocessing issues on macOS
            params = StagingParameters(
                raw_root=raw_root,
                stage_root=stage_root,
                procedures_yaml=procedures_yaml,
                local_tz="America/Santiago",
                workers=1,  # Single worker to avoid multiprocessing issues in TUI
                polars_threads=1,
                force=False,  # Don't force overwrite existing data
                only_yaml_data=False,
            )

            # Run staging pipeline
            # Note: run_staging_pipeline doesn't provide progress callbacks,
            # so we'll simulate progress during this phase
            self.app.call_from_thread(
                self._update_progress,
                15,
                f"⣾ Staging {total_csvs} files (sequential processing)..."
            )

            # Run in increments with simulated progress
            staging_start = time.time()
            try:
                run_staging_pipeline(params)
            except (OSError, ValueError, TypeError) as e:
                # Handle multiprocessing errors gracefully on macOS
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["fds_to_keep", "bad value", "spawn", "pickle"]):
                    raise RuntimeError(
                        "Data processing from the TUI is not supported on your system due to multiprocessing limitations.\n\n"
                        "Please run the processing pipeline from the command line instead:\n"
                        "  python process_and_analyze.py full-pipeline\n\n"
                        "This command will:\n"
                        "  • Stage all raw CSVs → Parquet\n"
                        "  • Generate manifest.parquet\n"
                        "  • Build chip histories\n\n"
                        "After processing completes, you can use the TUI for plotting."
                    ) from e
                raise
            staging_elapsed = time.time() - staging_start

            self.app.call_from_thread(
                self._update_progress,
                60,
                f"✓ Staging complete ({staging_elapsed:.1f}s)"
            )
            time.sleep(0.3)

            # ═══════════════════════════════════════════════════════════
            # STEP 2: CHIP HISTORIES (60-95%)
            # ═══════════════════════════════════════════════════════════

            self.app.call_from_thread(
                self._update_progress,
                60,
                "⣾ Step 2/2: Generating chip histories from manifest..."
            )

            # Check manifest exists
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest_path}")

            # Load manifest to count chips
            self.app.call_from_thread(
                self._update_progress,
                65,
                "⣾ Reading manifest..."
            )

            manifest = pl.read_parquet(manifest_path).filter(
                pl.col("status") == "ok"
            )

            # Count unique chips
            chip_numbers = manifest.select("chip_number").unique().filter(
                pl.col("chip_number").is_not_null()
            ).height

            self.app.call_from_thread(
                self._update_progress,
                70,
                f"⣾ Found {chip_numbers} chip(s), generating histories..."
            )

            # Generate all chip histories
            history_dir.mkdir(parents=True, exist_ok=True)

            histories = generate_all_chip_histories(
                manifest_path=manifest_path,
                output_dir=history_dir,
                chip_group=None,  # Process all chip groups
                min_experiments=1,
                stage_root=stage_root,
            )

            # histories is a dict of chip_name -> history_file_path
            histories_created = len(histories)
            chips_skipped = chip_numbers - histories_created

            self.app.call_from_thread(
                self._update_progress,
                95,
                f"✓ Created {histories_created} histories ({chips_skipped} skipped)"
            )
            time.sleep(0.3)

            # ═══════════════════════════════════════════════════════════
            # COMPLETE
            # ═══════════════════════════════════════════════════════════

            self.app.call_from_thread(self._update_progress, 100, "✓ Complete!")
            time.sleep(0.3)

            # Calculate total statistics
            elapsed = time.time() - self.start_time

            # Count total experiments in manifest
            total_experiments = manifest.height

            # Show success screen
            self.app.call_from_thread(
                self._on_success,
                elapsed=elapsed,
                files_processed=total_csvs,
                experiments=total_experiments,
                histories=histories_created,
                total_chips=chip_numbers,
            )

        except Exception as e:
            # Show error screen
            import traceback
            error_details = traceback.format_exc()
            self.app.call_from_thread(self._on_error, str(e), type(e).__name__, error_details)

    def _update_progress(self, progress: float, status: str) -> None:
        """Update progress bar and status from background thread."""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=progress)

        status_widget = self.query_one("#status", Static)
        status_widget.update(status)

    def _on_success(
        self,
        elapsed: float,
        files_processed: int,
        experiments: int,
        histories: int,
        total_chips: int
    ) -> None:
        """Handle successful processing using router."""
        # Replace current screen with success screen
        self.app.pop_screen()
        self.app.router.go_to_process_success(
            elapsed=elapsed,
            files_processed=files_processed,
            experiments=experiments,
            histories=histories,
            total_chips=total_chips
        )

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        """Handle processing error using router."""
        # Replace current screen with error screen
        self.app.pop_screen()
        self.app.router.go_to_process_error(
            error_type=error_type,
            error_msg=error_msg,
            error_details=error_details
        )

    def action_cancel(self) -> None:
        """Cancel processing."""
        # TODO: Implement cancellation
        self.app.notify("Cancellation not yet implemented", severity="warning")
