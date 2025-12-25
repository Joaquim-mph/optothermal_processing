"""
Experiment Selector Screen (Quick Plot Mode).

Step 4a of the wizard: Interactively select experiments for quick plotting.
Wraps the existing interactive_selector.py into the wizard flow.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List

import polars as pl
from textual.app import ComposeResult
from textual.binding import Binding

from src.tui.screens.base import WizardScreen
from src.interactive_selector import ExperimentSelectorScreen as BaseExperimentSelector


class ExperimentSelectorScreen(WizardScreen):
    """
    Experiment selector screen for the wizard (Step 4a - Quick mode).

    Wraps the existing ExperimentSelectorScreen and integrates it into the wizard.
    """

    SCREEN_TITLE = "Select Experiments"
    STEP_NUMBER = 5  # Step 5 in the wizard flow

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        plot_type: str,
        history_dir: Path,
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.history_dir = history_dir

    def compose_content(self) -> ComposeResult:
        """Compose is minimal - the nested screen handles the UI."""
        # This screen doesn't have its own widgets - it immediately pushes the selector
        return []

    def on_mount(self) -> None:
        """Load chip history and launch the interactive selector."""
        try:
            # Special case: LaserCalibration (global measurements from manifest)
            if self.plot_type == "LaserCalibration":
                self._load_laser_calibrations()
                return

            # Special case: ITSRelaxation (requires metrics filtering)
            if self.plot_type == "ITSRelaxation":
                self._load_its_relaxation_experiments()
                return

            # Standard case: Load chip history from Parquet file
            chip_name = f"{self.chip_group}{self.chip_number}"
            history_file = self.history_dir / f"{chip_name}_history.parquet"

            if not history_file.exists():
                self.app.notify(
                    f"History file not found: {history_file}",
                    severity="error",
                    timeout=5
                )
                self.app.pop_screen()
                return

            history_df = pl.read_parquet(history_file)

            if history_df.height == 0:
                self.app.notify(
                    f"No experiments found for {self.chip_group}{self.chip_number}",
                    severity="error",
                    timeout=5
                )
                self.app.pop_screen()
                return

            # Map plot type to procedure name in data
            # Some plot types have different names than their underlying procedure
            proc_mapping = {
                "ITS": "It",  # ITS plots use It (current vs time) procedure
                "Transconductance": "IVg",  # Transconductance calculated from IVg
                "Vt": "Vt",  # Vt plots use Vt procedure (explicit for clarity)
                "VVg": "VVg",  # VVg plots use VVg procedure (explicit for clarity)
                "IVg": "IVg",  # IVg plots use IVg procedure (explicit for clarity)
            }
            proc_filter = proc_mapping.get(self.plot_type, self.plot_type)

            # Update title to be clear about what experiments are being selected
            if self.plot_type == "Transconductance":
                title = f"Select IVg Experiments (for Transconductance) - {self.chip_group}{self.chip_number}"
            elif self.plot_type == "ITS":
                title = f"Select It Experiments (Current vs Time) - {self.chip_group}{self.chip_number}"
            else:
                title = f"Select {self.plot_type} Experiments - {self.chip_group}{self.chip_number}"

            selector = BaseExperimentSelector(
                chip_number=self.chip_number,
                chip_group=self.chip_group,
                history_df=history_df,
                proc_filter=proc_filter,
                title=title
            )

            # Push the selector and handle the result
            self.app.push_screen(selector, callback=self._on_selection)

        except Exception as e:
            self.app.notify(
                f"Error loading experiments: {str(e)}",
                severity="error",
                timeout=5
            )
            self.app.pop_screen()

    def _on_selection(self, result: Optional[List[int]]) -> None:
        """Handle the selection result from the interactive selector."""
        if result is None:
            # User cancelled - go back to config mode
            self.app.pop_screen()
        else:
            # User confirmed selection - save to session (replaces app.update_config)
            self.app.session.seq_numbers = result

            # Pop this screen (experiment selector wrapper)
            self.app.pop_screen()

            # Navigate to preview screen using router
            self.app.router.go_to_preview()

    def action_cancel(self) -> None:
        """Cancel and return to config mode."""
        self.app.pop_screen()

    def action_back(self) -> None:
        """Override back action to cancel."""
        self.action_cancel()

    def _load_laser_calibrations(self) -> None:
        """Load laser calibration experiments from manifest (special case)."""
        # Load manifest
        manifest_path = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
        if not manifest_path.exists():
            self.app.notify("Manifest not found - run 'stage-all' first", severity="error", timeout=5)
            self.app.pop_screen()
            return

        manifest = pl.read_parquet(manifest_path)

        # Filter to LaserCalibration procedure
        calibrations = manifest.filter(pl.col("proc") == "LaserCalibration")

        if calibrations.height == 0:
            self.app.notify("No laser calibrations found in manifest", severity="warning", timeout=5)
            self.app.pop_screen()
            return

        # Apply filters from config
        config = self.app.session
        if hasattr(config, 'wavelength_filter') and config.wavelength_filter:
            wl = float(config.wavelength_filter)
            calibrations = calibrations.filter(
                (pl.col("wavelength_nm") - wl).abs() < 1.0
            )

        if hasattr(config, 'fiber_filter') and config.fiber_filter:
            calibrations = calibrations.filter(
                pl.col("optical_fiber") == config.fiber_filter
            )

        if hasattr(config, 'date_filter') and config.date_filter:
            calibrations = calibrations.filter(
                pl.col("date_local") == config.date_filter
            )

        if calibrations.height == 0:
            self.app.notify("No calibrations match the filters", severity="warning", timeout=5)
            self.app.pop_screen()
            return

        # Sort by timestamp and assign seq numbers
        time_col = "start_time_utc" if "start_time_utc" in calibrations.columns else "start_dt"
        calibrations = calibrations.sort(time_col)
        calibrations = calibrations.with_row_index(name="seq", offset=1)

        # Ensure parquet_path column exists
        if "path" in calibrations.columns and "parquet_path" not in calibrations.columns:
            calibrations = calibrations.rename({"path": "parquet_path"})

        # Add summary column for interactive selector filtering
        # Format: "{wavelength}nm {fiber} {date}"
        calibrations = calibrations.with_columns([
            pl.concat_str([
                pl.col("wavelength_nm").cast(pl.Utf8).fill_null("unknown"),
                pl.lit("nm "),
                pl.col("optical_fiber").cast(pl.Utf8).fill_null("unknown"),
                pl.lit(" "),
                pl.col("date_local").cast(pl.Utf8).fill_null("unknown")
            ]).alias("summary")
        ])

        # Create selector with global calibrations
        title = "Select Laser Calibrations (Global Measurements)"
        selector = BaseExperimentSelector(
            chip_number=0,  # Not chip-specific
            chip_group="",
            history_df=calibrations,
            proc_filter="LaserCalibration",
            title=title
        )

        # Push the selector and handle the result
        self.app.push_screen(selector, callback=self._on_selection)

    def _load_its_relaxation_experiments(self) -> None:
        """Load It experiments that have relaxation metrics (special case)."""
        # Load chip history
        chip_name = f"{self.chip_group}{self.chip_number}"
        history_file = self.history_dir / f"{chip_name}_history.parquet"

        if not history_file.exists():
            self.app.notify("Chip history not found - run 'build-all-histories'", severity="error", timeout=5)
            self.app.pop_screen()
            return

        history = pl.read_parquet(history_file)

        # Filter to It procedures
        its_experiments = history.filter(pl.col("proc") == "It")

        if its_experiments.height == 0:
            self.app.notify("No It experiments found", severity="warning", timeout=5)
            self.app.pop_screen()
            return

        # Apply dark-only filter if requested
        config = self.app.session
        if hasattr(config, 'dark_only') and config.dark_only:
            if "has_light" in its_experiments.columns:
                its_experiments = its_experiments.filter(pl.col("has_light") == False)
            elif "laser_voltage_v" in its_experiments.columns:
                its_experiments = its_experiments.filter(
                    (pl.col("laser_voltage_v") == 0.0) | pl.col("laser_voltage_v").is_null()
                )

        # Load metrics
        metrics_path = Path("data/03_derived/_metrics/metrics.parquet")
        if not metrics_path.exists():
            self.app.notify("Metrics not found - run 'derive-all-metrics' first", severity="error", timeout=5)
            self.app.pop_screen()
            return

        metrics = pl.read_parquet(metrics_path)

        # Filter to relaxation_time metrics for this chip
        relaxation_metrics = metrics.filter(
            (pl.col("metric_name") == "relaxation_time") &
            (pl.col("chip_number") == self.chip_number) &
            (pl.col("chip_group") == self.chip_group)
        )

        if relaxation_metrics.height == 0:
            self.app.notify("No relaxation metrics found - run 'derive-all-metrics'", severity="error", timeout=5)
            self.app.pop_screen()
            return

        # Filter experiments to those with metrics (join by run_id)
        if "run_id" not in its_experiments.columns:
            self.app.notify("History missing run_id - rebuild with 'build-all-histories'", severity="error", timeout=5)
            self.app.pop_screen()
            return

        experiments_with_metrics = its_experiments.filter(
            pl.col("run_id").is_in(relaxation_metrics["run_id"])
        )

        if experiments_with_metrics.height == 0:
            self.app.notify("No It experiments have relaxation metrics", severity="warning", timeout=5)
            self.app.pop_screen()
            return

        # Apply segment filter if specified
        if hasattr(config, 'fit_segment') and config.fit_segment and config.fit_segment != "both":
            import json
            filtered_run_ids = []
            for metric_row in relaxation_metrics.iter_rows(named=True):
                try:
                    details = json.loads(metric_row["value_json"])
                    segment_type = details.get("segment_type")
                    if segment_type == config.fit_segment:
                        filtered_run_ids.append(metric_row["run_id"])
                except (json.JSONDecodeError, KeyError):
                    continue

            if filtered_run_ids:
                experiments_with_metrics = experiments_with_metrics.filter(
                    pl.col("run_id").is_in(filtered_run_ids)
                )

        # Create selector
        title = f"Select It Experiments (with Relaxation Fits) - {chip_name}"
        selector = BaseExperimentSelector(
            chip_number=self.chip_number,
            chip_group=self.chip_group,
            history_df=experiments_with_metrics,
            proc_filter="It",
            title=title
        )

        # Push the selector and handle the result
        self.app.push_screen(selector, callback=self._on_selection)
