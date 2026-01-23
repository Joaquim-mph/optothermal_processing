"""
Experiment Data Preview Screen.

Shows terminal-based plots of selected experiments using plotext.
Procedure-specific rendering for different measurement types.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List
import io
import sys
import traceback

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import Static, Button, Label, RichLog
from textual.binding import Binding

from src.tui.screens.base import WizardScreen
from src.tui.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

try:
    import polars as pl
    import plotext as plt
    from src.core.utils import read_measurement_parquet
except ImportError:
    pl = None
    plt = None
    read_measurement_parquet = None


class ExperimentPreviewScreen(WizardScreen):
    """
    Preview screen showing terminal-based plots of selected experiments.

    Features:
    - Procedure-specific plot rendering (IVg, It, VVg, Vt, etc.)
    - Interactive experiment selection
    - Quick data quality check before generating final plots
    - Uses plotext for fast terminal rendering
    - Filters by both sequence numbers AND procedure type

    Example Usage
    -------------
    >>> preview_screen = ExperimentPreviewScreen(
    ...     chip_number=67,
    ...     chip_group="Alisson",
    ...     plot_type="ITS",
    ...     seq_numbers=[52, 57, 58],
    ...     procedure_filter="It",  # Only show It/ITt procedures
    ...     history_dir=Path("data/02_stage/chip_histories")
    ... )
    >>> app.push_screen(preview_screen)
    """

    SCREEN_TITLE = "Data Preview"
    STEP_NUMBER = 5

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        plot_type: str,
        seq_numbers: List[int],
        procedure_filter: Optional[str] = None,
        history_dir: Optional[Path] = None,
        stage_dir: Optional[Path] = None,
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.seq_numbers = seq_numbers
        self.procedure_filter = procedure_filter  # e.g., "It", "IVg", "all", or None
        self.history_dir = history_dir or Path("data/02_stage/chip_histories")
        self.stage_dir = stage_dir or Path("data/02_stage/raw_measurements")

        # Current experiment index for navigation
        self.current_index = 0

        # Cached data
        self._history_df: Optional[pl.DataFrame] = None
        self._experiments: List[dict] = []

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("left", "prev_experiment", "Previous", show=True),
        Binding("right", "next_experiment", "Next", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = WizardScreen.CSS + """
    .plot-display {
        height: auto;
        background: $surface;
        color: $text;
        padding: 1;
        margin: 1;
        border: solid green;
    }

    .experiment-info {
        background: $panel;
        color: $text-muted;
        padding: 1;
        margin: 1;
    }

    .nav-hint {
        text-align: center;
        color: $text-muted;
        text-style: italic;
        margin: 1;
    }

    ScrollableContainer {
        height: 1fr;
        border: solid $accent;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with title and info."""
        yield Static(f"{self.SCREEN_TITLE} - {self.plot_type}", id="title")
        yield Static(
            f"Chip: [bold]{self.chip_group}{self.chip_number}[/bold] | "
            f"Experiments: {len(self.seq_numbers)}",
            id="chip-info"
        )
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose preview content."""
        # ULTRA-MINIMAL TEST - Just one widget, no containers
        yield Static("🔴 TEST: If you can read this, compose_content() is working!", id="test-widget")
        yield Static("Experiment info will go here", id="experiment-info")
        yield Static("Plot will go here", id="plot-display")

        # Buttons
        with Horizontal(id="button-container"):
            yield Button("← Back", id="back-button", variant="default", classes="nav-button")
            yield Button("Continue →", id="next-button", variant="primary", classes="nav-button")

    def on_mount(self) -> None:
        """Load data and render first plot."""
        logger.info(f"ExperimentPreviewScreen mounted: chip={self.chip_group}{self.chip_number}, "
                   f"plot_type={self.plot_type}, seq_numbers={self.seq_numbers}")

        # Check dependencies
        if pl is None or plt is None:
            error_msg = "polars or plotext not installed"
            logger.error(error_msg)
            plot_widget = self.query_one("#plot-display", Static)
            plot_widget.update(
                "❌ Error: polars or plotext not installed\n"
                "Install with: pip install polars plotext"
            )
            return

        # Load history and experiments
        try:
            self._load_history()
            self._render_current_experiment()
        except Exception as e:
            logger.error(f"Error loading data: {e}", exc_info=True)
            plot_widget = self.query_one("#plot-display", Static)
            plot_widget.update(
                f"❌ Error loading data: {e}\n\nCheck logs/tui_*.log for details"
            )

    def _load_history(self) -> None:
        """Load chip history and filter by selected experiments."""
        chip_name = f"{self.chip_group}{self.chip_number}"
        history_file = self.history_dir / f"{chip_name}_history.parquet"

        logger.info(f"Loading history from: {history_file}")

        if not history_file.exists():
            logger.error(f"History file not found: {history_file}")
            raise FileNotFoundError(f"History file not found: {history_file}")

        # Load and filter history
        self._history_df = pl.read_parquet(history_file)
        logger.info(f"Loaded history with {len(self._history_df)} experiments")

        # Filter by sequence numbers
        filtered = self._history_df.filter(pl.col("seq").is_in(self.seq_numbers))
        logger.info(f"Filtered to {len(filtered)} experiments matching seq: {self.seq_numbers}")

        # Additionally filter by procedure if specified (and not "all")
        if self.procedure_filter and self.procedure_filter != "all":
            # Map procedure filter to actual procedure name(s) in history
            # Handle variants like It/ITt, IVg/IVgT
            procedure_variants = self._get_procedure_variants(self.procedure_filter)

            logger.info(f"Applying procedure filter: {self.procedure_filter} -> {procedure_variants}")
            filtered = filtered.filter(pl.col("proc").is_in(procedure_variants))
            logger.info(f"After procedure filter: {len(filtered)} experiments")

        # Convert to list of dicts for easy access
        self._experiments = filtered.to_dicts()

        if not self._experiments:
            logger.error(f"No experiments found with seq numbers: {self.seq_numbers} "
                        f"and procedure filter: {self.procedure_filter}")
            raise ValueError(f"No experiments found with seq numbers: {self.seq_numbers} "
                           f"and procedure filter: {self.procedure_filter}")

    def _get_procedure_variants(self, procedure: str) -> List[str]:
        """
        Get all procedure variants for a given procedure filter.

        For example, "It" should match both "It" and "ITt" in the history.

        Parameters
        ----------
        procedure : str
            Procedure filter from selector (e.g., "It", "IVg", "VVg", "Vt")

        Returns
        -------
        list[str]
            List of procedure names to match in history
        """
        # Map each procedure to its variants
        procedure_map = {
            "It": ["It", "ITt"],
            "IVg": ["IVg", "IVgT"],
            "VVg": ["VVg"],
            "Vt": ["Vt"],
            "LaserCalibration": ["LaserCalibration"],
            "Tt": ["Tt"],
            "IV": ["IV"],
        }

        # Return variants if found, otherwise return the procedure itself
        return procedure_map.get(procedure, [procedure])

    def _render_current_experiment(self) -> None:
        """Render plot for current experiment index."""
        if not self._experiments:
            return

        exp = self._experiments[self.current_index]
        # Handle both 'proc' and 'procedure' column names for backward compatibility
        procedure = exp.get('procedure') or exp.get('proc', 'UNKNOWN')
        logger.info(f"Rendering experiment {self.current_index + 1}/{len(self._experiments)}: "
                   f"seq={exp['seq']}, procedure={procedure}")

        # Update experiment info
        info_text = self._format_experiment_info(exp)
        self.query_one("#experiment-info", Static).update(info_text)

        # Render procedure-specific plot
        try:
            plot_output = self._render_plot_for_procedure(exp)
            logger.info(f"Plot output captured: {len(plot_output)} characters")
            logger.debug(f"Plot output preview: {plot_output[:200]}")

            # Strip ANSI codes for better display in Textual
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_output = ansi_escape.sub('', plot_output)

            # Get the Static widget
            try:
                plot_widget = self.query_one("#plot-display", Static)
                logger.info(f"✓ Found plot widget: {plot_widget}")
            except Exception as e:
                logger.error(f"❌ Failed to find plot widget: {e}")
                raise

            # Update with Rich Text object to preserve whitespace
            from rich.text import Text
            plot_text = Text(clean_output, no_wrap=True)

            logger.info(f"🧪 Updating with plot Text object ({len(clean_output)} chars)")
            plot_widget.update(plot_text)
            logger.info(f"✓ Updated widget with Text object")

            # Force refresh
            plot_widget.refresh()
            logger.info("✓ Refreshed plot widget")

            # No more scrolling needed - removed ScrollableContainer
            logger.info("✓ Widget should now be visible (no ScrollableContainer)")

            # Verify it's there
            logger.debug(f"First 100 chars of clean output: {clean_output[:100]}")
            logger.debug(f"Number of lines in plot: {clean_output.count(chr(10))}")
            logger.info(f"✓ Plot rendering complete for seq={exp['seq']}")
        except Exception as e:
            logger.error(f"Error rendering plot for seq={exp['seq']}, "
                        f"procedure={exp.get('procedure', 'UNKNOWN')}: {e}", exc_info=True)
            plot_widget = self.query_one("#plot-display", Static)
            plot_widget.update(
                f"❌ Error rendering plot: {e}\n\n"
                f"Procedure: {exp.get('procedure', 'UNKNOWN')}\n"
                f"Check logs/tui_*.log for full traceback"
            )

    def _format_experiment_info(self, exp: dict) -> str:
        """Format experiment metadata as readable text."""
        # Handle both 'proc' and 'procedure' column names for backward compatibility
        procedure = exp.get('procedure') or exp.get('proc', 'UNKNOWN')

        # Handle different time field names
        start_time = (exp.get('start_time_local') or
                     exp.get('time_hms') or
                     exp.get('datetime_local', 'N/A'))

        # Build filter description
        filter_desc = f"seq={self.seq_numbers}"
        if self.procedure_filter and self.procedure_filter != "all":
            filter_desc += f", proc={self.procedure_filter}"

        lines = [
            f"[bold]Experiment {self.current_index + 1}/{len(self._experiments)}[/bold] [dim](filtered: {filter_desc})[/dim]",
            f"Seq: {exp['seq']} | Procedure: {procedure}",
            f"Date: {exp.get('date_local') or exp.get('date', 'N/A')} | Start: {start_time}",
        ]

        # Add procedure-specific metadata
        if procedure in ['It', 'ITt']:
            # Handle both vg_v and vg_fixed_v (It uses vg_fixed_v)
            vg = exp.get('vg_v') or exp.get('vg_fixed_v', 'N/A')
            lines.append(f"VG: {vg} V | VDS: {exp.get('vds_v', 'N/A')} V")
            if 'wavelength_nm' in exp and exp['wavelength_nm'] is not None:
                lines.append(f"Wavelength: {exp['wavelength_nm']} nm")
        elif procedure in ['IVg', 'IVgT']:
            lines.append(f"VDS: {exp.get('vds_v', 'N/A')} V")
        elif procedure in ['VVg', 'Vt']:
            lines.append(f"IDS: {exp.get('ids_v', 'N/A')} A")

        # Light status - handle both 'light' (string) and 'has_light' (boolean)
        if 'light' in exp:
            light = exp['light']
            light_emoji = "💡" if light == "light" else "🌙" if light == "dark" else "❓"
        elif 'has_light' in exp:
            has_light = exp['has_light']
            light = "light" if has_light else "dark"
            light_emoji = "💡" if has_light else "🌙"
        else:
            light = "unknown"
            light_emoji = "❓"

        lines.append(f"Light: {light_emoji} {light}")

        return "\n".join(lines)

    def _render_plot_for_procedure(self, exp: dict) -> str:
        """
        Render procedure-specific plot using plotext.

        Returns ASCII art plot as string.
        """
        # Handle both 'proc' and 'procedure' column names for backward compatibility
        procedure = exp.get('procedure') or exp.get('proc', 'UNKNOWN')
        logger.info(f"Rendering procedure: {procedure}")

        # Load measurement data
        parquet_path = Path(exp['parquet_path'])
        logger.info(f"Loading measurement data from: {parquet_path}")

        if not parquet_path.exists():
            error_msg = f"Data file not found: {parquet_path}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

        try:
            measurement = read_measurement_parquet(parquet_path)
            logger.info(f"Loaded measurement data with {len(measurement)} rows, "
                       f"columns: {measurement.columns}")

            # Normalize column names (e.g., "Vg (V)" -> "VG", "I (A)" -> "I")
            from src.plotting.plot_utils import ensure_standard_columns
            measurement = ensure_standard_columns(measurement)
            logger.info(f"Normalized columns: {measurement.columns}")
        except Exception as e:
            logger.error(f"Error reading parquet file {parquet_path}: {e}", exc_info=True)
            raise

        # Clear previous plot
        plt.clear_figure()

        # Route to procedure-specific renderer
        if procedure in ['It', 'ITt']:
            logger.info(f"Rendering as ITS plot")
            return self._render_its_plot(measurement, exp)
        elif procedure in ['IVg', 'IVgT']:
            logger.info(f"Rendering as IVg plot")
            return self._render_ivg_plot(measurement, exp)
        elif procedure in ['VVg']:
            logger.info(f"Rendering as VVg plot")
            return self._render_vvg_plot(measurement, exp)
        elif procedure in ['Vt']:
            logger.info(f"Rendering as Vt plot")
            return self._render_vt_plot(measurement, exp)
        elif procedure == 'LaserCalibration':
            logger.info(f"Rendering as LaserCalibration plot")
            return self._render_laser_calibration_plot(measurement, exp)
        else:
            logger.warning(f"Preview not implemented for procedure: {procedure}")
            return f"⚠ Preview not implemented for procedure: {procedure}"

    def _render_its_plot(self, df: pl.DataFrame, exp: dict) -> str:
        """Render current vs time (ITS) plot."""
        # Extract data (using standard column names)
        time = df["t"].to_numpy()
        current = df["I"].to_numpy() * 1e6  # Convert to µA

        # Configure plot - use 70 width to fit most terminals
        plt.plotsize(70, 20)

        # Plot data
        plt.plot(time, current)

        # Labels
        plt.title(f"Current vs Time - Seq {exp['seq']}")
        plt.xlabel("Time (s)")
        plt.ylabel("IDS (µA)")

        # Theme
        plt.theme("dark")

        # Capture output
        return self._capture_plotext_output()

    def _render_ivg_plot(self, df: pl.DataFrame, exp: dict) -> str:
        """Render current vs gate voltage (IVg) plot."""
        # Extract data (using standard column names)
        vg = df["VG"].to_numpy()
        current = df["I"].to_numpy() * 1e6  # Convert to µA

        # Configure plot - use 70 width to fit most terminals
        plt.plotsize(70, 20)

        # Plot data
        plt.plot(vg, current)

        # Labels
        plt.title(f"IVg Curve - Seq {exp['seq']}")
        plt.xlabel("VG (V)")
        plt.ylabel("IDS (µA)")

        # Theme
        plt.theme("dark")

        return self._capture_plotext_output()

    def _render_vvg_plot(self, df: pl.DataFrame, exp: dict) -> str:
        """Render voltage vs gate voltage (VVg) plot."""
        # Extract data (using standard column names)
        vg = df["VG"].to_numpy()
        vds = df["VDS"].to_numpy() * 1e3  # Convert to mV

        # Configure plot - use 70 width to fit most terminals
        plt.plotsize(70, 20)

        # Plot data
        plt.plot(vg, vds)

        # Labels
        plt.title(f"VVg Curve - Seq {exp['seq']}")
        plt.xlabel("VG (V)")
        plt.ylabel("VDS (mV)")

        # Theme
        plt.theme("dark")

        return self._capture_plotext_output()

    def _render_vt_plot(self, df: pl.DataFrame, exp: dict) -> str:
        """Render voltage vs time (Vt) plot."""
        # Extract data (using standard column names)
        time = df["t"].to_numpy()
        vds = df["VDS"].to_numpy() * 1e3  # Convert to mV

        # Configure plot - use 70 width to fit most terminals
        plt.plotsize(70, 20)

        # Plot data
        plt.plot(time, vds)

        # Labels
        plt.title(f"Voltage vs Time - Seq {exp['seq']}")
        plt.xlabel("Time (s)")
        plt.ylabel("VDS (mV)")

        # Theme
        plt.theme("dark")

        return self._capture_plotext_output()

    def _render_laser_calibration_plot(self, df: pl.DataFrame, exp: dict) -> str:
        """Render laser calibration curve."""
        # Extract data (using standard column names where available)
        vl = df["VL"].to_numpy() if "VL" in df.columns else df["vl_v"].to_numpy()
        # Power column typically not renamed, check both variants
        if "photodiode_power_uw" in df.columns:
            power = df["photodiode_power_uw"].to_numpy()
        elif "Photodiode Power (uW)" in df.columns:
            power = df["Photodiode Power (uW)"].to_numpy()
        else:
            return "❌ Cannot find power column (photodiode_power_uw or 'Photodiode Power (uW)')"

        # Configure plot - use 70 width to fit most terminals
        plt.plotsize(70, 20)

        # Plot data
        plt.plot(vl, power)

        # Labels
        wl = exp.get('wavelength_nm', 'N/A')
        plt.title(f"Laser Calibration - {wl} nm - Seq {exp['seq']}")
        plt.xlabel("VL (V)")
        plt.ylabel("Power (µW)")

        # Theme
        plt.theme("dark")

        return self._capture_plotext_output()

    def _capture_plotext_output(self) -> str:
        """
        Capture plotext plot as string.

        Uses plotext's build() method to avoid stdout capture issues in Textual.
        """
        try:
            # Use build() instead of show() to get string directly
            # This avoids issues with stdout redirection in Textual
            output = plt.build()
            plt.clear_figure()
            return output
        except AttributeError:
            # Fallback to stdout capture if build() doesn't exist (older plotext)
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()

            try:
                plt.show()
                output = buffer.getvalue()
            finally:
                sys.stdout = old_stdout
                plt.clear_figure()

            return output

    def action_prev_experiment(self) -> None:
        """Navigate to previous experiment."""
        if self.current_index > 0:
            self.current_index -= 1
            self._render_current_experiment()
        else:
            self.app.notify(
                f"Already at first experiment (1 of {len(self._experiments)})",
                severity="information"
            )

    def action_next_experiment(self) -> None:
        """Navigate to next experiment."""
        if self.current_index < len(self._experiments) - 1:
            self.current_index += 1
            self._render_current_experiment()
        else:
            self.app.notify(
                f"Already at last experiment ({len(self._experiments)} of {len(self._experiments)})",
                severity="information"
            )

    def action_refresh(self) -> None:
        """Refresh current plot."""
        self._render_current_experiment()
        self.app.notify("Plot refreshed", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            # Continue to next step (preview confirmation or plot generation)
            self.app.router.go_to_preview()
