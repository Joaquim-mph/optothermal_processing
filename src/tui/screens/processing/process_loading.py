"""
Data Processing Loading Screen.

Shows progress while processing metadata and chip histories.
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
    """Loading screen for data processing."""

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
        yield Static("Starting data processing", id="current-task")
        yield Static("", id="stats")

    def on_mount(self) -> None:
        """Start processing when screen loads."""
        self.start_time = time.time()

        # Start processing in background thread
        self.processing_thread = threading.Thread(target=self._run_processing, daemon=True)
        self.processing_thread.start()

    def _run_processing(self) -> None:
        """Run the data processing pipeline in background thread."""
        try:
            # Force non-interactive matplotlib backend for thread-safety (in case any imports trigger it)
            import matplotlib
            matplotlib.use('Agg')

            # Import legacy processing modules (only used in this method)
            import polars as pl
            from src.core.parser import parse_iv_metadata
            from src.core.timeline import build_chip_history

            raw_dir = Path("raw_data")
            meta_dir = Path("metadata")
            history_dir = Path("chip_histories")
            chip_group = "Alisson"

            # Step 1: Discover folders
            self.app.call_from_thread(self._update_progress, 5, "⣾ Discovering data folders...")

            folders = [item for item in raw_dir.iterdir() if item.is_dir() and list(item.glob("*.csv"))]
            total_folders = len(folders)

            if total_folders == 0:
                raise ValueError("No data folders found in raw_data/")

            self.app.call_from_thread(
                self._update_progress,
                10,
                f"⣾ Found {total_folders} folder(s) to process..."
            )

            # Step 2: Parse metadata from all folders
            meta_dir.mkdir(parents=True, exist_ok=True)
            total_files_processed = 0
            total_metadata_rows = 0

            for idx, folder in enumerate(folders):
                folder_name = folder.name
                progress = 10 + int((idx / total_folders) * 40)  # 10-50%

                self.app.call_from_thread(
                    self._update_progress,
                    progress,
                    f"⣾ Parsing metadata: {folder_name} ({idx + 1}/{total_folders})"
                )

                out_dir = meta_dir / folder_name
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / "metadata.csv"

                csv_files = sorted(folder.glob("*.csv"))
                metadata_rows = []

                for csv_file in csv_files:
                    try:
                        meta = parse_iv_metadata(csv_file)
                        if meta:
                            rel_path = f"{raw_dir.name}/{folder_name}/{csv_file.name}"
                            meta['source_file'] = rel_path
                            metadata_rows.append(meta)
                            total_files_processed += 1
                    except Exception:
                        pass

                if metadata_rows:
                    df = pl.DataFrame(metadata_rows)
                    df.write_csv(out_file)
                    total_metadata_rows += len(metadata_rows)

            self.app.call_from_thread(
                self._update_progress,
                50,
                f"✓ Parsed {total_files_processed} files → {total_metadata_rows} experiments"
            )
            time.sleep(0.5)

            # Step 3: Discover chips
            self.app.call_from_thread(self._update_progress, 55, "⣾ Discovering chips...")

            metadata_files = list(meta_dir.glob("**/metadata.csv")) + list(meta_dir.glob("**/*_metadata.csv"))

            all_chips = set()
            for meta_file in metadata_files:
                try:
                    meta = pl.read_csv(meta_file, ignore_errors=True)
                    if "Chip number" in meta.columns:
                        chips = meta.get_column("Chip number").drop_nulls().unique().to_list()
                        for c in chips:
                            try:
                                all_chips.add(int(float(c)))
                            except (ValueError, TypeError):
                                pass
                except Exception:
                    pass

            sorted_chips = sorted(all_chips)
            total_chips = len(sorted_chips)

            if total_chips == 0:
                raise ValueError("No chips found in metadata")

            self.app.call_from_thread(
                self._update_progress,
                60,
                f"⣾ Found {total_chips} chip(s)..."
            )

            # Step 4: Build chip histories
            history_dir.mkdir(parents=True, exist_ok=True)
            histories_created = 0

            for idx, chip_num in enumerate(sorted_chips):
                progress = 60 + int((idx / total_chips) * 35)  # 60-95%
                chip_name = f"{chip_group}{chip_num}"

                self.app.call_from_thread(
                    self._update_progress,
                    progress,
                    f"⣾ Building history: {chip_name} ({idx + 1}/{total_chips})"
                )

                try:
                    history = build_chip_history(meta_dir, Path("."), chip_num, chip_group)

                    if history.height >= 1:
                        out_file = history_dir / f"{chip_name}_history.csv"
                        history.write_csv(out_file)
                        histories_created += 1
                except Exception:
                    # Skip chips that fail
                    pass

            # Complete
            self.app.call_from_thread(self._update_progress, 100, "✓ Complete!")
            time.sleep(0.3)

            # Calculate statistics
            elapsed = time.time() - self.start_time

            # Show success screen
            self.app.call_from_thread(
                self._on_success,
                elapsed,
                total_files_processed,
                total_metadata_rows,
                histories_created,
                total_chips
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
