"""
TUI Navigation Router.

Centralizes screen navigation and construction logic for the wizard flow.
Eliminates repetitive imports and manual screen construction in individual screens.

Benefits:
- Single source of truth for navigation flow
- Consistent parameter passing
- Easy to refactor wizard flow
- Type-safe navigation with session state
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.tui.app import PlotterApp


class Router:
    """
    Centralized navigation router with screen construction helpers.

    All navigation between screens should go through router methods.
    This ensures consistent parameter passing and makes the wizard flow
    easy to understand and refactor.

    Example
    -------
    >>> # In a screen, instead of:
    >>> # from src.tui.screens.selection import PlotTypeSelectorScreen
    >>> # self.app.push_screen(PlotTypeSelectorScreen(chip_number=67, chip_group="Alisson"))
    >>>
    >>> # Use:
    >>> self.app.router.go_to_plot_type_selector()
    """

    def __init__(self, app: PlotterApp):
        """
        Initialize router with reference to app.

        Parameters
        ----------
        app : PlotterApp
            The main TUI application instance
        """
        self.app = app

    # ═══════════════════════════════════════════════════════════════════
    # Navigation Flow (Step-by-step wizard)
    # ═══════════════════════════════════════════════════════════════════

    def go_to_main_menu(self) -> None:
        """
        Navigate to main menu (entry point).

        Usually called after app initialization or when returning from wizard.
        """
        from src.tui.screens.navigation import MainMenuScreen
        self.app.push_screen(MainMenuScreen())

    def go_to_chip_selector(self, mode: str = "plot") -> None:
        """
        Navigate to chip selector (Step 1).

        Uses session state for history_dir and chip_group.
        """
        from src.tui.screens.selection import ChipSelectorScreen
        self.app.push_screen(ChipSelectorScreen(
            history_dir=self.app.session.history_dir,
            chip_group=self.app.session.chip_group,
            mode=mode,
        ))

    def go_to_plot_type_selector(self) -> None:
        """
        Navigate to plot type selector (Step 2).

        Requires session.chip_number and session.chip_group to be set.

        Raises
        ------
        ValueError
            If chip_number or chip_group not set in session
        """
        from src.tui.screens.selection import PlotTypeSelectorScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set before navigating to plot type selector")

        self.app.push_screen(PlotTypeSelectorScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    def go_to_config_mode_selector(self) -> None:
        """
        Navigate to config mode selector (Step 3).

        Requires session.chip_number, session.chip_group, and session.plot_type to be set.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.selection import ConfigModeSelectorScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")
        if self.app.session.plot_type is None:
            raise ValueError("plot_type must be set")

        self.app.push_screen(ConfigModeSelectorScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            plot_type=self.app.session.plot_type
        ))

    def go_to_its_config(self, preset_mode: bool = False) -> None:
        """
        Navigate to ITS configuration screen (Step 4).

        Parameters
        ----------
        preset_mode : bool
            If True, shows preset summary instead of full custom form

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration import ITSConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(ITSConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            plot_type=self.app.session.plot_type or "ITS",
            preset_mode=preset_mode
        ))

    def go_to_its_preset_selector(self) -> None:
        """
        Navigate to ITS preset selector.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.selection import ITSPresetSelectorScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(ITSPresetSelectorScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            plot_type="ITS"
        ))

    def go_to_vt_config(self, preset_mode: bool = False) -> None:
        """
        Navigate to Vt configuration screen (Step 3).

        Parameters
        ----------
        preset_mode : bool
            If True, show config for selected preset (read-only summary).
            If False, show full custom config form.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration import VtConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(VtConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            preset_mode=preset_mode
        ))

    def go_to_vt_preset_selector(self) -> None:
        """
        Navigate to Vt preset selector.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.selection import VtPresetSelectorScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(VtPresetSelectorScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            plot_type="Vt"
        ))

    def go_to_ivg_config(self) -> None:
        """
        Navigate to IVg configuration screen (Step 4).

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration import IVgConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(IVgConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    def go_to_transconductance_config(self) -> None:
        """
        Navigate to transconductance configuration screen (Step 4).

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration import TransconductanceConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(TransconductanceConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    # ═══════════════════════════════════════════════════════════════════
    # New Plot Type Configuration Screens (v3.0)
    # ═══════════════════════════════════════════════════════════════════

    def go_to_vvg_config(self) -> None:
        """
        Navigate to VVg configuration screen (Step 4).

        VVg plots show drain-source voltage vs gate voltage sweeps.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration.vvg_config import VVgConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(VVgConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    def go_to_vt_config(self, preset_mode: bool = False) -> None:
        """
        Navigate to Vt configuration screen (Step 4).

        Vt plots show voltage vs time measurements.

        Parameters
        ----------
        preset_mode : bool
            If True, shows preset summary instead of full custom form

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration.vt_config import VtConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(VtConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            preset_mode=preset_mode
        ))

    def go_to_cnp_config(self) -> None:
        """
        Navigate to CNP time plot configuration screen (Step 4).

        CNP plots show Charge Neutrality Point (Dirac point) evolution over time.
        Requires enriched chip histories with derived metrics.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration.cnp_config import CNPConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(CNPConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    def go_to_photoresponse_config(self) -> None:
        """
        Navigate to Photoresponse configuration screen (Step 4).

        Photoresponse plots analyze device response to illumination vs:
        - Power
        - Wavelength
        - Gate voltage
        - Time

        Requires enriched chip histories with derived metrics and laser calibration data.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration.photoresponse_config import PhotoresponseConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(PhotoresponseConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    def go_to_laser_calibration_config(self) -> None:
        """
        Navigate to Laser Calibration configuration screen (Step 4).

        Laser calibration plots show power output vs control voltage curves.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration.laser_calibration_config import LaserCalibrationConfigScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(LaserCalibrationConfigScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    def go_to_recent_configs(self) -> None:
        """
        Navigate to recent configurations screen.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.navigation import RecentConfigsScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")

        self.app.push_screen(RecentConfigsScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group
        ))

    def go_to_log_viewer(self) -> None:
        """
        Navigate to log viewer screen.

        Shows recent TUI log entries for debugging and troubleshooting.
        """
        from src.tui.screens.navigation import LogViewerScreen

        self.app.push_screen(LogViewerScreen())

    def go_to_experiment_selector(self) -> None:
        """
        Navigate to experiment selector (Step 5).

        Requires session.chip_number, session.chip_group, and session.plot_type to be set.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.selection import ExperimentSelectorScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")
        if self.app.session.plot_type is None:
            raise ValueError("plot_type must be set")

        self.app.push_screen(ExperimentSelectorScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            plot_type=self.app.session.plot_type,
            history_dir=self.app.session.history_dir
        ))

    def go_to_history_browser(self) -> None:
        """Navigate to the history browser screen."""
        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set before opening history browser")

        from src.tui.screens.analysis import HistoryBrowserScreen

        self.app.push_screen(HistoryBrowserScreen())

    def go_to_plot_browser(self) -> None:
        """
        Navigate to plot browser screen.

        Opens standalone plot viewer for browsing existing plots
        in the figs/ directory.

        No session state requirements - accessible from main menu.
        """
        from src.tui.screens.analysis import PlotBrowserScreen
        self.app.push_screen(PlotBrowserScreen())

    def go_to_preview(self) -> None:
        """
        Navigate to preview screen (Step 6).

        Requires session.chip_number, session.plot_type, and session.seq_numbers to be set.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.configuration import PreviewScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")
        if self.app.session.plot_type is None:
            raise ValueError("plot_type must be set")
        if not self.app.session.seq_numbers:
            raise ValueError("seq_numbers must be set")

        self.app.push_screen(PreviewScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            plot_type=self.app.session.plot_type,
            seq_numbers=self.app.session.seq_numbers,
            config=self.app.session.to_config_dict()
        ))

    def go_to_plot_generation(self) -> None:
        """
        Navigate to plot generation screen (Step 7).

        Starts the actual plot generation process.

        Raises
        ------
        ValueError
            If required session fields not set
        """
        from src.tui.screens.processing import PlotGenerationScreen

        if self.app.session.chip_number is None:
            raise ValueError("chip_number must be set")
        if self.app.session.plot_type is None:
            raise ValueError("plot_type must be set")
        if not self.app.session.seq_numbers:
            raise ValueError("seq_numbers must be set")

        self.app.push_screen(PlotGenerationScreen(
            chip_number=self.app.session.chip_number,
            chip_group=self.app.session.chip_group,
            plot_type=self.app.session.plot_type,
            seq_numbers=self.app.session.seq_numbers,
            config=self.app.session.to_config_dict()
        ))

    # ═══════════════════════════════════════════════════════════════════
    # Data Processing Flow
    # ═══════════════════════════════════════════════════════════════════

    def go_to_data_pipeline_menu(self) -> None:
        """
        Navigate to Data Pipeline menu (v3.0).

        Provides access to data processing commands:
        - Stage All Data (CSV → Parquet)
        - Generate Chip Histories
        - Extract Derived Metrics
        - Enrich Histories (join calibrations + metrics)
        - Run Full Pipeline
        """
        from src.tui.screens.navigation.data_pipeline_menu import DataPipelineMenuScreen
        self.app.push_screen(DataPipelineMenuScreen())

    def go_to_pipeline_loading(self, pipeline_type: str) -> None:
        """
        Navigate to pipeline loading screen (v3.0).

        Starts a specific data pipeline command in background.

        Parameters
        ----------
        pipeline_type : str
            Pipeline command to run:
            - 'stage-all': Stage raw CSVs to Parquet
            - 'build-histories': Generate chip histories from manifest
            - 'derive-metrics': Extract derived metrics (CNP, photoresponse)
            - 'enrich-histories': Enrich histories with calibrations + metrics
            - 'full-pipeline': Run all steps in sequence
        """
        from src.tui.screens.processing.pipeline_loading import PipelineLoadingScreen
        self.app.push_screen(PipelineLoadingScreen(pipeline_type=pipeline_type))

    def go_to_process_confirmation(self) -> None:
        """
        Navigate to process confirmation dialog.

        Asks user to confirm before running full data processing pipeline.
        """
        from src.tui.screens.configuration import ProcessConfirmationScreen
        self.app.push_screen(ProcessConfirmationScreen())

    def go_to_process_loading(self) -> None:
        """
        Navigate to process loading screen.

        Starts the data processing pipeline in background.
        """
        from src.tui.screens.processing import ProcessLoadingScreen
        self.app.push_screen(ProcessLoadingScreen())

    def go_to_process_success(
        self,
        elapsed: float,
        files_processed: int,
        experiments: int,
        histories: int,
        total_chips: int
    ) -> None:
        """
        Navigate to process success screen.

        Parameters
        ----------
        elapsed : float
            Processing time in seconds
        files_processed : int
            Number of files processed
        experiments : int
            Number of experiments found
        histories : int
            Number of chip histories created
        total_chips : int
            Total number of chips discovered
        """
        from src.tui.screens.results import ProcessSuccessScreen
        self.app.push_screen(ProcessSuccessScreen(
            elapsed=elapsed,
            files_processed=files_processed,
            experiments=experiments,
            histories=histories,
            total_chips=total_chips
        ))

    def go_to_process_error(
        self,
        error_type: str,
        error_msg: str,
        error_details: str = ""
    ) -> None:
        """
        Navigate to process error screen.

        Parameters
        ----------
        error_type : str
            Type of error (exception class name)
        error_msg : str
            Error message
        error_details : str, optional
            Full error traceback
        """
        from src.tui.screens.results import ProcessErrorScreen
        self.app.push_screen(ProcessErrorScreen(
            error_type=error_type,
            error_msg=error_msg,
            error_details=error_details
        ))

    # ═══════════════════════════════════════════════════════════════════
    # Plot Results Flow
    # ═══════════════════════════════════════════════════════════════════

    def go_to_plot_success(
        self,
        output_path,
        file_size: float,
        num_experiments: int,
        elapsed: float,
        chip_number: int = None,
        chip_group: str = None,
        plot_type: str = None
    ) -> None:
        """
        Navigate to plot success screen.

        Parameters
        ----------
        output_path : Path
            Path to generated plot file
        file_size : float
            File size in MB
        num_experiments : int
            Number of experiments plotted
        elapsed : float
            Generation time in seconds
        chip_number : int, optional
            Chip number
        chip_group : str, optional
            Chip group name
        plot_type : str, optional
            Type of plot generated
        """
        from src.tui.screens.results import PlotSuccessScreen
        self.app.push_screen(PlotSuccessScreen(
            output_path=output_path,
            file_size=file_size,
            num_experiments=num_experiments,
            elapsed=elapsed,
            chip_number=chip_number,
            chip_group=chip_group,
            plot_type=plot_type
        ))

    def go_to_plot_error(
        self,
        error_type: str,
        error_msg: str,
        config: dict,
        error_details: str = ""
    ) -> None:
        """
        Navigate to plot error screen.

        Parameters
        ----------
        error_type : str
            Type of error (exception class name)
        error_msg : str
            Error message
        config : dict
            Plot configuration that failed
        error_details : str, optional
            Full error traceback
        """
        from src.tui.screens.results import PlotErrorScreen
        self.app.push_screen(PlotErrorScreen(
            error_type=error_type,
            error_msg=error_msg,
            config=config,
            error_details=error_details
        ))

    # ═══════════════════════════════════════════════════════════════════
    # Utility Navigation
    # ═══════════════════════════════════════════════════════════════════

    def return_to_main_menu(self) -> None:
        """
        Pop all screens back to main menu.

        Keeps base app screen + MainMenuScreen only.
        Resets wizard state in session.
        """
        # Pop all screens except base + main menu
        while len(self.app.screen_stack) > 2:
            self.app.pop_screen()

        # Reset wizard state
        self.app.session.reset_wizard_state()

    def go_back(self) -> None:
        """
        Pop current screen (go back one step).

        Simple wrapper around app.pop_screen() for consistency.
        """
        self.app.pop_screen()

    # ═══════════════════════════════════════════════════════════════════
    # Smart Navigation (based on session state)
    # ═══════════════════════════════════════════════════════════════════

    def go_to_config_screen(self) -> None:
        """
        Navigate to appropriate config screen based on session.plot_type.

        Automatically routes to correct configuration screen for each plot type:

        v2.x Plot Types (original):
        - ITS → ConfigModeSelectorScreen (has presets)
        - IVg → IVgConfigScreen
        - Transconductance → TransconductanceConfigScreen

        v3.0 Plot Types (new):
        - VVg → VVgConfigScreen
        - Vt → ConfigModeSelectorScreen (has presets, like ITS)
        - CNP → CNPConfigScreen
        - Photoresponse → PhotoresponseConfigScreen
        - LaserCalibration → LaserCalibrationConfigScreen

        Raises
        ------
        ValueError
            If plot_type not set or invalid
        """
        if self.app.session.plot_type is None:
            raise ValueError("plot_type must be set")

        plot_type = self.app.session.plot_type

        # Map plot types to config screen navigation methods
        config_router = {
            # v2.x plot types
            "ITS": self.go_to_config_mode_selector,  # ITS has presets
            "IVg": self.go_to_ivg_config,
            "Transconductance": self.go_to_transconductance_config,

            # v3.0 measurement plots
            "VVg": self.go_to_vvg_config,
            "Vt": self.go_to_config_mode_selector,  # Vt has presets (like ITS)

            # v3.0 derived metric plots
            "CNP": self.go_to_cnp_config,
            "Photoresponse": self.go_to_photoresponse_config,

            # v3.0 specialized plots
            "LaserCalibration": self.go_to_laser_calibration_config,
        }

        nav_func = config_router.get(plot_type)
        if nav_func is None:
            raise ValueError(f"Unknown plot_type: {plot_type}")

        nav_func()

    def restart_wizard(self) -> None:
        """
        Restart wizard flow from chip selection.

        Resets wizard state and navigates to chip selector.
        """
        self.return_to_main_menu()
        self.go_to_chip_selector()
