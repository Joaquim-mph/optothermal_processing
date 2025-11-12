"""
Plot Generation Screen.

Step 6/6 of the wizard: Generate the plot and show progress.
"""

from __future__ import annotations
import time
import threading
from pathlib import Path
from typing import List

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, ProgressBar
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class PlotGenerationScreen(WizardScreen):
    """Plot generation progress screen (Step 6/6)."""

    SCREEN_TITLE = "Generating Plot..."
    STEP_NUMBER = None  # Progress screen, not a wizard step

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
        align-horizontal: center;
    }

    #progress-bar {
        width: 60%;
    }

    #current-task {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 2;
    }
    """

    def compose_content(self) -> ComposeResult:
        """Create generation progress widgets."""
        yield Static("⣾ Initializing...", id="status")
        with Horizontal(id="progress-container"):
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
        yield Static("Starting plot generation", id="current-task")

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

            history_dir = PathLib(self.config.get("history_dir", "data/02_stage/chip_histories"))
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
                if "source_file" in meta.columns:
                    meta = meta.rename({"source_file": "raw_source_file"})
                    logger.info("Renamed existing 'source_file' column to 'raw_source_file'")
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
                    # Check has_light column (more reliable than Laser toggle)
                    if "has_light" in its_df.columns:
                        try:
                            # If all experiments have has_light = False, it's all dark
                            has_light_values = its_df["has_light"].to_list()
                            all_dark = all(not val for val in has_light_values if val is not None)
                            logger.info(f"Dark detection: has_light values = {has_light_values}, all_dark = {all_dark}")
                        except Exception as e:
                            logger.warning(f"Failed to check has_light column: {e}")
                            pass
                    # Fallback: Check laser_voltage_v column
                    elif "laser_voltage_v" in its_df.columns:
                        try:
                            laser_voltages = its_df["laser_voltage_v"].to_list()
                            # All laser voltages < 0.1V = dark
                            all_dark = all(v < 0.1 for v in laser_voltages if v is not None)
                            logger.info(f"Dark detection (fallback): laser voltages = {laser_voltages}, all_dark = {all_dark}")
                        except Exception as e:
                            logger.warning(f"Failed to check laser_voltage_v column: {e}")
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

            elif self.plot_type == "VVg":
                # VVg plot (v3.0)
                from src.plotting import vvg
                logger.info("Setting VVg FIG_DIR")
                vvg.FIG_DIR = output_dir
                logger.info("Calling plot_vvg_sequence()")
                logger.info(f"Arguments: stage_dir={stage_dir}, plot_tag={plot_tag}")
                vvg.plot_vvg_sequence(meta, stage_dir, plot_tag)
                logger.info("plot_vvg_sequence() completed")

            elif self.plot_type == "Vt":
                # Vt plot (v3.0)
                from src.plotting import vt
                logger.info("Setting Vt FIG_DIR")
                vt.FIG_DIR = output_dir

                # Get Vt-specific config
                legend_by = self.config.get("legend_by", "wavelength")  # Default to wavelength for Vt plots
                baseline_t = self.config.get("baseline", 60.0)
                padding = self.config.get("padding", 0.05)
                baseline_mode = self.config.get("baseline_mode", "fixed")
                baseline_auto_divisor = self.config.get("baseline_auto_divisor", 2.0)
                plot_start_time = self.config.get("plot_start_time", 20.0)

                logger.info(f"Vt config - legend_by: {legend_by}, baseline_t: {baseline_t}, "
                           f"baseline_mode: {baseline_mode}, padding: {padding}")

                logger.info("Calling plot_vt_overlay()")
                logger.info(f"Arguments: stage_dir={stage_dir}, plot_tag={plot_tag}")
                vt.plot_vt_overlay(
                    meta,
                    stage_dir,
                    plot_tag,
                    baseline_t=baseline_t,
                    baseline_mode=baseline_mode,
                    baseline_auto_divisor=baseline_auto_divisor,
                    plot_start_time=plot_start_time,
                    legend_by=legend_by,
                    padding=padding
                )
                logger.info("plot_vt_overlay() completed")

            elif self.plot_type == "CNP":
                # CNP time evolution plot (v3.0 - requires enriched history)
                from src.plotting import cnp_time
                from src.tui.history_detection import load_chip_history

                logger.info("CNP plot requires enriched history")
                self.app.call_from_thread(self._update_progress, 20, "⣾ Loading enriched history...")

                # Load enriched history
                try:
                    enriched_dir = PathLib("data/03_derived/chip_histories_enriched")
                    history, is_enriched = load_chip_history(
                        self.chip_number,
                        self.chip_group,
                        history_dir,
                        enriched_dir,
                        prefer_enriched=True,
                        require_enriched=True,  # CNP requires enriched data
                    )

                    if not is_enriched:
                        raise ValueError(
                            f"CNP plots require enriched history for {self.chip_group}{self.chip_number}. "
                            f"Run: python3 process_and_analyze.py enrich-history {self.chip_number}"
                        )

                    logger.info(f"Loaded enriched history with {history.height} experiments")
                except Exception as e:
                    logger.error(f"Failed to load enriched history: {str(e)}")
                    raise

                self.app.call_from_thread(self._update_progress, 40, "⣾ Generating CNP plot...")

                logger.info("Setting CNP FIG_DIR")
                cnp_time.FIG_DIR = output_dir

                # Get CNP-specific config
                metric = self.config.get("cnp_metric", "cnp_voltage")
                show_illumination = self.config.get("cnp_show_illumination", True)

                logger.info(f"Calling plot_cnp_time() with metric={metric}, show_illumination={show_illumination}")
                cnp_time.plot_cnp_time(
                    history,
                    output_dir,
                    f"{self.chip_group}{self.chip_number}",
                    metric=metric,
                    show_illumination=show_illumination,
                )
                logger.info("plot_cnp_time() completed")

            elif self.plot_type == "Photoresponse":
                # Photoresponse analysis plot (v3.0 - requires enriched history)
                from src.plotting import photoresponse
                from src.tui.history_detection import load_chip_history

                logger.info("Photoresponse plot requires enriched history")
                self.app.call_from_thread(self._update_progress, 20, "⣾ Loading enriched history...")

                # Load enriched history
                try:
                    enriched_dir = PathLib("data/03_derived/chip_histories_enriched")
                    history, is_enriched = load_chip_history(
                        self.chip_number,
                        self.chip_group,
                        history_dir,
                        enriched_dir,
                        prefer_enriched=True,
                        require_enriched=True,  # Photoresponse requires enriched data
                    )

                    if not is_enriched:
                        raise ValueError(
                            f"Photoresponse plots require enriched history for {self.chip_group}{self.chip_number}. "
                            f"Run: python3 process_and_analyze.py enrich-history {self.chip_number}"
                        )

                    logger.info(f"Loaded enriched history with {history.height} experiments")
                except Exception as e:
                    logger.error(f"Failed to load enriched history: {str(e)}")
                    raise

                self.app.call_from_thread(self._update_progress, 40, "⣾ Generating photoresponse plot...")

                logger.info("Setting Photoresponse FIG_DIR")
                photoresponse.FIG_DIR = output_dir

                # Get photoresponse-specific config
                mode = self.config.get("photoresponse_mode", "power")
                filter_vg = self.config.get("photoresponse_filter_vg")
                filter_wl = self.config.get("photoresponse_filter_wl")

                logger.info(f"Calling plot_photoresponse() with mode={mode}, filter_vg={filter_vg}, filter_wl={filter_wl}")
                photoresponse.plot_photoresponse(
                    history,
                    output_dir,
                    f"{self.chip_group}{self.chip_number}",
                    mode=mode,
                    filter_vg=filter_vg,
                    filter_wl=filter_wl,
                )
                logger.info("plot_photoresponse() completed")

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

            elif self.plot_type == "VVg":
                filename = f"encap{self.chip_number}_VVg_{plot_tag}.png"

            elif self.plot_type == "Vt":
                filename = f"encap{self.chip_number}_Vt_{plot_tag}.png"

            elif self.plot_type == "CNP":
                metric = self.config.get("cnp_metric", "cnp_voltage")
                filename = f"encap{self.chip_number}_CNP_{metric}_time.png"

            elif self.plot_type == "Photoresponse":
                mode = self.config.get("photoresponse_mode", "power")
                filename = f"encap{self.chip_number}_photoresponse_{mode}.png"

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
        """Handle successful plot generation using router."""
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

        # Replace current screen with success screen using router
        self.app.pop_screen()
        self.app.router.go_to_plot_success(
            output_path=output_path,
            file_size=file_size,
            num_experiments=len(self.seq_numbers),
            elapsed=elapsed,
            chip_number=self.chip_number,
            chip_group=self.chip_group,
            plot_type=self.plot_type
        )

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        """Handle plot generation error using router."""
        # Replace current screen with error screen using router
        self.app.pop_screen()
        self.app.router.go_to_plot_error(
            error_type=error_type,
            error_msg=error_msg,
            config=self.config,
            error_details=error_details
        )

    def action_cancel(self) -> None:
        """Cancel plot generation."""
        # TODO: Implement cancellation
        self.app.notify("Cancellation not yet implemented", severity="warning")
