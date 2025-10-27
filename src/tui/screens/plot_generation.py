"""
Plot Generation and Results Screens.

Step 6/6 of the wizard: Generate the plot and show results/errors.
"""

from __future__ import annotations
import time
import threading
from pathlib import Path
from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, ProgressBar
from textual.binding import Binding
from textual import events


class PlotGenerationScreen(Screen):
    """Plot generation progress screen (Step 6/6)."""

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        plot_type: str,
        seq_numbers: List[int],
        config: dict,
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.seq_numbers = seq_numbers
        self.config = config
        self.generation_thread = None
        self.start_time = None

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CSS = """
    PlotGenerationScreen {
        align: center middle;
    }

    #main-container {
        width: 80;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 3 6;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }

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
    """

    def compose(self) -> ComposeResult:
        """Create generation progress widgets."""
        yield Header()

        with Container(id="main-container"):
            yield Static("Generating Plot...", id="title")
            yield Static("⣾ Initializing...", id="status")
            with Horizontal(id="progress-container"):
                yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            yield Static("Starting plot generation", id="current-task")

        yield Footer()

    def on_mount(self) -> None:
        """Start plot generation when screen loads."""
        self.start_time = time.time()

        # Start generation in background thread
        self.generation_thread = threading.Thread(target=self._generate_plot, daemon=True)
        self.generation_thread.start()

    def _generate_plot(self) -> None:
        """Generate the plot in background thread."""
        # Setup logging
        import logging
        from pathlib import Path as PathLib

        log_file = PathLib("tui_plot_generation.log")
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger(__name__)

        try:
            logger.info("="*80)
            logger.info("Starting plot generation")
            logger.info(f"Chip: {self.chip_group}{self.chip_number}")
            logger.info(f"Plot type: {self.plot_type}")
            logger.info(f"Seq numbers: {self.seq_numbers}")
            logger.info(f"Config keys: {list(self.config.keys())}")

            # Force non-interactive matplotlib backend for thread-safety
            import matplotlib
            matplotlib.use('Agg')  # Non-GUI backend for headless plotting
            logger.info("Set matplotlib backend to Agg")

            # Import plotting modules
            from src.plotting import its, ivg, transconductance
            import polars as pl
            logger.info("Imported plotting modules")

            # Step 1: Load history
            self.app.call_from_thread(self._update_progress, 10, "⣾ Loading experiment history...")

            history_dir = PathLib(self.config.get("history_dir", "data/03_history"))
            stage_dir = PathLib(self.config.get("stage_dir", "data/02_stage/raw_measurements"))

            logger.info(f"History directory: {history_dir} (exists: {history_dir.exists()})")
            logger.info(f"Stage directory: {stage_dir} (exists: {stage_dir.exists()})")

            # Load history file
            chip_name = f"{self.chip_group}{self.chip_number}"
            history_file = history_dir / f"{chip_name}_history.parquet"
            logger.info(f"Looking for history file: {history_file}")

            if not history_file.exists():
                logger.error(f"History file not found: {history_file}")
                raise FileNotFoundError(f"History file not found: {history_file}")

            logger.info(f"Loading history file: {history_file}")
            # Load and filter history for selected seq numbers
            history = pl.read_parquet(history_file)
            logger.info(f"Loaded history with {history.height} total experiments")
            logger.info(f"History columns: {history.columns}")

            meta = history.filter(pl.col("seq").is_in(self.seq_numbers))
            logger.info(f"Filtered to {meta.height} experiments matching seq numbers")

            if meta.height == 0:
                logger.error(f"No experiments found for seq numbers: {self.seq_numbers}")
                raise ValueError(f"No experiments found for seq numbers: {self.seq_numbers}")

            # Validate all seq numbers were found
            found_seqs = set(meta["seq"].to_list())
            missing_seqs = set(self.seq_numbers) - found_seqs
            if missing_seqs:
                logger.error(f"Missing seq numbers: {sorted(missing_seqs)}")
                raise ValueError(f"Seq numbers not found in history: {sorted(missing_seqs)}")

            # Rename parquet_path to source_file for compatibility with plotting functions
            if "parquet_path" in meta.columns:
                meta = meta.rename({"parquet_path": "source_file"})
                logger.info("Renamed 'parquet_path' to 'source_file'")
            elif "source_file" not in meta.columns:
                logger.error("History file missing both parquet_path and source_file columns")
                raise ValueError("History file missing both parquet_path and source_file columns")

            # FIX: source_file contains absolute paths but plotting functions expect relative paths
            # Strip the stage_dir prefix to make paths relative
            stage_dir_str = str(stage_dir)
            logger.info(f"Converting source_file paths from absolute to relative (removing prefix: {stage_dir_str})")

            def make_relative(path_str: str) -> str:
                """Remove stage_dir prefix if present."""
                if path_str.startswith(stage_dir_str + "/"):
                    return path_str[len(stage_dir_str) + 1:]
                elif path_str.startswith(stage_dir_str):
                    return path_str[len(stage_dir_str):]
                return path_str

            meta = meta.with_columns(
                pl.col("source_file").map_elements(make_relative, return_dtype=pl.Utf8).alias("source_file")
            )
            logger.info("Converted source_file paths to relative paths")

            logger.info(f"Metadata preview (after path conversion):\n{meta.head()}")

            # Check source_file paths
            logger.info("Checking source_file paths:")
            for row in meta.iter_rows(named=True):
                source = row.get("source_file", "MISSING")
                full_path = stage_dir / source if source != "MISSING" else "N/A"
                exists = full_path.exists() if full_path != "N/A" else False
                logger.info(f"  seq={row.get('seq')}, proc={row.get('proc')}, "
                           f"source_file={source}, full_path={full_path}, exists={exists}")

            self.app.call_from_thread(self._update_progress, 30, f"⣾ Loaded {meta.height} experiment(s)...")

            # Step 2: Setup output directory (always append chip subdirectory)
            base_output_dir = PathLib(self.config.get("output_dir", "figs"))
            logger.info(f"Base output directory: {base_output_dir}")

            # If user specified "figs/Alisson67/" or similar, extract just the base
            # Otherwise, always append chip subdirectory automatically
            base_str = str(base_output_dir)
            chip_subdir_name = f"{self.chip_group}{self.chip_number}"

            # Check if the path already ends with the chip subdirectory
            if base_str.endswith(f"/{chip_subdir_name}") or base_str.endswith(f"/{chip_subdir_name}/"):
                # Use as-is
                output_dir = base_output_dir
            elif base_str.endswith(chip_subdir_name):
                # Use as-is
                output_dir = base_output_dir
            else:
                # Append chip subdirectory
                output_dir = base_output_dir / chip_subdir_name

            logger.info(f"Final output directory: {output_dir}")
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created output directory (exists: {output_dir.exists()})")

            # Step 3: Generate plot tag from seq numbers
            seq_str = "_".join(map(str, self.seq_numbers[:10]))
            if len(self.seq_numbers) > 10:
                seq_str += f"_plus{len(self.seq_numbers) - 10}more"
            plot_tag = seq_str
            logger.info(f"Plot tag: {plot_tag}")

            self.app.call_from_thread(self._update_progress, 50, "⣾ Generating plot...")

            # Step 4: Call appropriate plotting function based on plot type
            logger.info(f"Calling plotting function for {self.plot_type}")

            if self.plot_type == "ITS":
                # ITS plot
                logger.info("Setting ITS FIG_DIR")
                its.FIG_DIR = output_dir

                # Get ITS-specific config
                legend_by = self.config.get("legend_by", "vg")  # Default to vg for ITS plots
                baseline_t = self.config.get("baseline", 60.0)
                padding = self.config.get("padding", 0.05)
                baseline_mode = self.config.get("baseline_mode", "fixed")
                baseline_auto_divisor = self.config.get("baseline_auto_divisor", 2.0)
                plot_start_time = self.config.get("plot_start_time", 20.0)
                check_duration_mismatch = self.config.get("check_duration_mismatch", False)
                duration_tolerance = self.config.get("duration_tolerance", 0.10)

                logger.info(f"ITS config - legend_by: {legend_by}, baseline_t: {baseline_t}, "
                           f"baseline_mode: {baseline_mode}, padding: {padding}")

                # Check if all ITS are dark (no laser)
                its_df = meta.filter(pl.col("proc") == "It")  # Changed from "ITS" to "It"
                all_dark = False

                if its_df.height > 0:
                    # Check laser toggle column if available
                    if "Laser toggle" in its_df.columns:
                        try:
                            laser_toggle_col = its_df["Laser toggle"]
                            toggles = []
                            for val in laser_toggle_col.to_list():
                                if isinstance(val, bool):
                                    toggles.append(val)
                                elif isinstance(val, str):
                                    toggles.append(val.lower() == "true")
                                else:
                                    toggles.append(True)

                            if all(not t for t in toggles):
                                all_dark = True
                        except Exception:
                            pass

                # Call appropriate ITS plotting function
                # For dark plots, always use vg legend (no LED/wavelength data)

                # Capture stdout from plotting function to log
                import sys
                import io

                stdout_capture = io.StringIO()
                old_stdout = sys.stdout

                try:
                    sys.stdout = stdout_capture

                    if all_dark:
                        logger.info("Calling plot_its_dark()")
                        logger.info(f"Arguments: stage_dir={stage_dir}, plot_tag={plot_tag}")
                        its.plot_its_dark(
                            meta,
                            stage_dir,
                            plot_tag,
                            baseline_t=baseline_t,
                            baseline_mode=baseline_mode,
                            baseline_auto_divisor=baseline_auto_divisor,
                            plot_start_time=plot_start_time,
                            legend_by="vg",  # Force vg for dark plots
                            padding=padding,
                            check_duration_mismatch=check_duration_mismatch,
                            duration_tolerance=duration_tolerance
                        )
                        logger.info("plot_its_dark() completed")
                    else:
                        logger.info("Calling plot_its_overlay()")
                        logger.info(f"Arguments: stage_dir={stage_dir}, plot_tag={plot_tag}")
                        its.plot_its_overlay(
                            meta,
                            stage_dir,
                            plot_tag,
                            baseline_t=baseline_t,
                            baseline_mode=baseline_mode,
                            baseline_auto_divisor=baseline_auto_divisor,
                            plot_start_time=plot_start_time,
                            legend_by=legend_by,
                            padding=padding,
                            check_duration_mismatch=check_duration_mismatch,
                            duration_tolerance=duration_tolerance
                        )
                        logger.info("plot_its_overlay() completed")
                finally:
                    sys.stdout = old_stdout
                    # Log any output from the plotting function
                    output = stdout_capture.getvalue()
                    if output:
                        logger.info(f"Output from plotting function:\n{output}")
                    else:
                        logger.info("No output from plotting function")

            elif self.plot_type == "IVg":
                # IVg plot
                logger.info("Setting IVg FIG_DIR")
                ivg.FIG_DIR = output_dir
                logger.info("Calling plot_ivg_sequence()")
                logger.info(f"Arguments: stage_dir={stage_dir}, plot_tag={plot_tag}")
                ivg.plot_ivg_sequence(meta, stage_dir, plot_tag)
                logger.info("plot_ivg_sequence() completed")

            elif self.plot_type == "Transconductance":
                # Transconductance plot
                logger.info("Setting Transconductance FIG_DIR")
                transconductance.FIG_DIR = output_dir

                # Get transconductance-specific config
                method = self.config.get("method", "gradient")
                logger.info(f"Transconductance method: {method}")

                if method == "savgol":
                    window_length = self.config.get("window_length", 9)
                    polyorder = self.config.get("polyorder", 3)
                    logger.info(f"Calling plot_ivg_transconductance_savgol() with window={window_length}, polyorder={polyorder}")
                    transconductance.plot_ivg_transconductance_savgol(
                        meta,
                        stage_dir,
                        plot_tag,
                        window_length=window_length,
                        polyorder=polyorder
                    )
                    logger.info("plot_ivg_transconductance_savgol() completed")
                else:
                    logger.info("Calling plot_ivg_transconductance()")
                    transconductance.plot_ivg_transconductance(
                        meta,
                        stage_dir,
                        plot_tag
                    )
                    logger.info("plot_ivg_transconductance() completed")
            else:
                logger.error(f"Unknown plot type: {self.plot_type}")
                raise ValueError(f"Unknown plot type: {self.plot_type}")

            logger.info("Plotting function completed successfully")
            self.app.call_from_thread(self._update_progress, 90, "⣾ Saving file...")

            # Step 5: Determine output file path (using standardized naming)
            if self.plot_type == "ITS":
                # Check if it's a dark measurement
                all_dark = False
                its_df = meta.filter(pl.col("proc") == "It")  # Changed from "ITS" to "It"
                if its_df.height > 0 and "Laser toggle" in its_df.columns:
                    try:
                        toggles = []
                        for val in its_df["Laser toggle"].to_list():
                            if isinstance(val, bool):
                                toggles.append(val)
                            elif isinstance(val, str):
                                toggles.append(val.lower() == "true")
                            else:
                                toggles.append(True)
                        all_dark = all(not t for t in toggles)
                    except Exception:
                        pass

                # Check if raw data mode (add _raw suffix)
                baseline_mode = self.config.get("baseline_mode", "fixed")
                raw_suffix = "_raw" if baseline_mode == "none" else ""

                if all_dark:
                    filename = f"encap{self.chip_number}_ITS_dark_{plot_tag}{raw_suffix}.png"
                else:
                    filename = f"encap{self.chip_number}_ITS_{plot_tag}{raw_suffix}.png"

            elif self.plot_type == "IVg":
                filename = f"encap{self.chip_number}_IVg_{plot_tag}.png"

            elif self.plot_type == "Transconductance":
                method = self.config.get("method", "gradient")
                if method == "savgol":
                    filename = f"encap{self.chip_number}_gm_savgol_{plot_tag}.png"
                else:
                    filename = f"encap{self.chip_number}_gm_{plot_tag}.png"

            output_path = output_dir / filename
            logger.info(f"Expected output file: {output_path}")

            # Get file size
            file_size = 0.0
            if output_path.exists():
                file_size = output_path.stat().st_size / (1024 * 1024)  # Convert to MB
                logger.info(f"Output file exists! Size: {file_size:.2f} MB")
            else:
                logger.warning(f"Output file does not exist at expected path: {output_path}")
                # List files in output directory to debug
                if output_dir.exists():
                    logger.info(f"Files in {output_dir}:")
                    for f in output_dir.iterdir():
                        logger.info(f"  - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
                else:
                    logger.error(f"Output directory does not exist: {output_dir}")

            # Complete
            self.app.call_from_thread(self._update_progress, 100, "✓ Complete!")
            time.sleep(0.3)

            # Show success screen
            elapsed = time.time() - self.start_time
            logger.info(f"Plot generation completed in {elapsed:.2f}s")
            logger.info("="*80)
            self.app.call_from_thread(self._on_success, elapsed, output_path, file_size)

        except Exception as e:
            # Show error screen
            import traceback
            error_details = traceback.format_exc()
            logger.error("="*80)
            logger.error(f"Plot generation failed with exception: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error("Full traceback:")
            logger.error(error_details)
            logger.error("="*80)
            self.app.call_from_thread(self._on_error, str(e), type(e).__name__, error_details)

    def _update_progress(self, progress: float, status: str) -> None:
        """Update progress bar and status from background thread."""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=progress)

        status_widget = self.query_one("#status", Static)
        status_widget.update(status)

    def _on_success(self, elapsed: float, output_path: Path, file_size: float) -> None:
        """Handle successful plot generation."""
        # Save configuration for reuse
        try:
            # Prepare config for saving (include seq_numbers and plot settings)
            save_config = {
                **self.config,
                "chip_number": self.chip_number,
                "chip_group": self.chip_group,
                "plot_type": self.plot_type,
                "seq_numbers": self.seq_numbers,
            }

            # Save to ConfigManager
            self.app.config_manager.save_config(save_config)
        except Exception as e:
            # Don't fail the success screen if config save fails
            print(f"Warning: Failed to save configuration: {e}")

        # Replace current screen with success screen
        self.app.pop_screen()

        self.app.push_screen(PlotSuccessScreen(
            output_path=output_path,
            file_size=file_size,
            num_experiments=len(self.seq_numbers),
            elapsed=elapsed,
            chip_number=self.chip_number,
            chip_group=self.chip_group,
            plot_type=self.plot_type,
        ))

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        """Handle plot generation error."""
        # Replace current screen with error screen
        self.app.pop_screen()

        self.app.push_screen(PlotErrorScreen(
            error_type=error_type,
            error_msg=error_msg,
            config=self.config,
            error_details=error_details,
        ))

    def action_cancel(self) -> None:
        """Cancel plot generation."""
        # TODO: Implement cancellation
        self.app.notify("Cancellation not yet implemented", severity="warning")


class PlotSuccessScreen(Screen):
    """Success screen after plot generation."""

    def __init__(
        self,
        output_path: Path,
        file_size: float,
        num_experiments: int,
        elapsed: float,
        chip_number: int = None,
        chip_group: str = None,
        plot_type: str = None,
    ):
        super().__init__()
        self.output_path = output_path
        self.file_size = file_size
        self.num_experiments = num_experiments
        self.elapsed = elapsed
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type

    BINDINGS = [
        Binding("escape", "main_menu", "Main Menu", priority=True),
    ]

    CSS = """
    PlotSuccessScreen {
        align: center middle;
    }

    #main-container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $success;
        padding: 2 4;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $success;
        margin-bottom: 2;
    }

    .info-row {
        color: $text;
        margin-left: 2;
        margin-bottom: 0;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        margin-top: 2;
    }

    .nav-button {
        width: 1fr;
        margin: 0 1;
    }

    .nav-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        """Create success screen widgets."""
        yield Header()

        with Container(id="main-container"):
            yield Static("Plot Generated Successfully! ✓", id="title")

            yield Static("Output file:", classes="section-title")
            yield Static(str(self.output_path), classes="info-row")

            yield Static(f"File size: {self.file_size:.1f} MB", classes="info-row")
            yield Static(f"Experiments plotted: {self.num_experiments}", classes="info-row")
            yield Static(f"Generation time: {self.elapsed:.1f}s", classes="info-row")

            yield Static("", classes="info-row")
            yield Static("Configuration saved to recent history.", classes="info-row")

            with Horizontal(id="button-container"):
                yield Button("Open File", id="open-button", variant="default", classes="nav-button")
                yield Button("Plot Another", id="another-button", variant="default", classes="nav-button")
                yield Button("Main Menu", id="menu-button", variant="default", classes="nav-button")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the main menu button."""
        self.query_one("#menu-button", Button).focus()

    def on_key(self, event: events.Key) -> None:
        """Handle arrow key navigation between buttons."""
        buttons = [
            self.query_one("#open-button", Button),
            self.query_one("#another-button", Button),
            self.query_one("#menu-button", Button),
        ]

        focused_idx = next((i for i, b in enumerate(buttons) if b.has_focus), None)

        if focused_idx is not None:
            if event.key in ("left", "up"):
                new_idx = (focused_idx - 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()
            elif event.key in ("right", "down"):
                new_idx = (focused_idx + 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()

    def on_button_focus(self, event) -> None:
        """Add arrow indicator to focused button."""
        # Remove arrows from all buttons
        for button in self.query(".nav-button"):
            label = str(button.label)
            if label.startswith("→ "):
                button.label = label[2:]

        # Add arrow to focused button
        focused_button = event.button
        label = str(focused_button.label)
        if not label.startswith("→ "):
            focused_button.label = f"→ {label}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "open-button":
            self.action_open_file()
        elif event.button.id == "another-button":
            self.action_plot_another()
        elif event.button.id == "menu-button":
            self.action_main_menu()

    def action_open_file(self) -> None:
        """Open the generated file."""
        # TODO: Implement file opening
        self.app.notify(f"Opening {self.output_path.name}...", severity="information")

    def action_plot_another(self) -> None:
        """Start a new plot of the same type."""
        # Pop all wizard screens to get back to main menu
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()

        # If we have the required info, jump directly to experiment selector
        if self.chip_number and self.chip_group and self.plot_type:
            from src.tui.screens.experiment_selector import ExperimentSelectorScreen
            from pathlib import Path as PathLib

            # Get config paths
            history_dir = PathLib(self.app.plot_config.get("history_dir", "data/03_history"))

            # Push experiment selector for the same plot type and chip
            self.app.push_screen(ExperimentSelectorScreen(
                chip_number=self.chip_number,
                chip_group=self.chip_group,
                plot_type=self.plot_type,
                history_dir=history_dir,
            ))

    def action_main_menu(self) -> None:
        """Return to main menu."""
        # Pop screens until we're back at the main menu (keep base + MainMenuScreen)
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()


class PlotErrorScreen(Screen):
    """Error screen if plot generation fails."""

    def __init__(self, error_type: str, error_msg: str, config: dict, error_details: str = ""):
        super().__init__()
        self.error_type = error_type
        self.error_msg = error_msg
        self.config = config
        self.error_details = error_details

    BINDINGS = [
        Binding("escape", "main_menu", "Main Menu", priority=True),
    ]

    CSS = """
    PlotErrorScreen {
        align: center middle;
    }

    #main-container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $error;
        padding: 2 4;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $error;
        margin-bottom: 2;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }

    .error-text {
        color: $text;
        margin-left: 2;
        margin-bottom: 1;
    }

    .suggestion-text {
        color: $warning;
        margin-left: 2;
        margin-bottom: 1;
        text-style: italic;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        margin-top: 2;
    }

    .nav-button {
        width: 1fr;
        margin: 0 1;
    }

    .nav-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        """Create error screen widgets."""
        yield Header()

        with Container(id="main-container"):
            yield Static("Plot Generation Failed ✗", id="title")

            yield Static("Error Type:", classes="section-title")
            yield Static(self.error_type, classes="error-text")

            yield Static("Message:", classes="section-title")
            yield Static(self.error_msg, classes="error-text")

            # Generate suggestion based on error
            suggestion = self._generate_suggestion()
            if suggestion:
                yield Static("Suggestion:", classes="section-title")
                yield Static(suggestion, classes="suggestion-text")

            with Horizontal(id="button-container"):
                yield Button("View Details", id="details-button", variant="default", classes="nav-button")
                yield Button("Edit Config", id="edit-button", variant="default", classes="nav-button")
                yield Button("Main Menu", id="menu-button", variant="default", classes="nav-button")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the edit config button."""
        self.query_one("#edit-button", Button).focus()

    def on_key(self, event: events.Key) -> None:
        """Handle arrow key navigation between buttons."""
        buttons = [
            self.query_one("#details-button", Button),
            self.query_one("#edit-button", Button),
            self.query_one("#menu-button", Button),
        ]

        focused_idx = next((i for i, b in enumerate(buttons) if b.has_focus), None)

        if focused_idx is not None:
            if event.key in ("left", "up"):
                new_idx = (focused_idx - 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()
            elif event.key in ("right", "down"):
                new_idx = (focused_idx + 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()

    def on_button_focus(self, event) -> None:
        """Add arrow indicator to focused button."""
        # Remove arrows from all buttons
        for button in self.query(".nav-button"):
            label = str(button.label)
            if label.startswith("→ "):
                button.label = label[2:]

        # Add arrow to focused button
        focused_button = event.button
        label = str(focused_button.label)
        if not label.startswith("→ "):
            focused_button.label = f"→ {label}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "details-button":
            self.action_view_details()
        elif event.button.id == "edit-button":
            self.action_edit_config()
        elif event.button.id == "menu-button":
            self.action_main_menu()

    def action_view_details(self) -> None:
        """View error details."""
        if self.error_details:
            # Show full traceback in a notification
            self.app.notify(
                f"Full traceback:\n{self.error_details}",
                severity="error",
                timeout=10
            )
        else:
            self.app.notify("No additional error details available", severity="information")

    def action_edit_config(self) -> None:
        """Go back to edit configuration."""
        # Pop this error screen to go back to preview
        self.app.pop_screen()

    def action_main_menu(self) -> None:
        """Return to main menu."""
        # Pop screens until we're back at the main menu (keep base + MainMenuScreen)
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()

    def _generate_suggestion(self) -> Optional[str]:
        """Generate helpful suggestion based on error."""
        error_lower = self.error_msg.lower()

        if "filter" in error_lower:
            return "Try adjusting or removing filters to include more experiments."
        elif "not found" in error_lower or "does not exist" in error_lower:
            return "Check that all required files exist in the specified directories."
        elif "empty" in error_lower or "no data" in error_lower:
            return "Verify that the selected experiments contain valid measurement data."
        else:
            return "Check your configuration and try again."
