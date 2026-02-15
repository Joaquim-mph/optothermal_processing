"""
Main PyQt6 Application for Biotite Lab Plotter.

Provides MainWindow with sidebar navigation, QStackedWidget for pages,
and session/config management reused from the TUI.
"""

from __future__ import annotations
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence

from src.gui.theme import STYLESHEET
from src.gui.router import Router
from src.tui.session import PlotSession
from src.tui.config_manager import ConfigManager
from src.tui.settings_manager import SettingsManager
from src.tui.logging_config import setup_tui_logging, get_logger


class MainWindow(QMainWindow):
    """
    Main application window with sidebar + QStackedWidget layout.

    Reuses PlotSession, ConfigManager, and SettingsManager from the TUI
    for state management and persistence.
    """

    SIDEBAR_ITEMS = [
        ("New Plot", "chip_selector"),
        ("History", "history_browser"),
        ("Plots", "plot_browser"),
        ("Process Data", "data_pipeline_menu"),
        ("Recent", "recent_configs"),
        ("Logs", "log_viewer"),
        ("Settings", "settings"),
    ]

    def __init__(
        self,
        stage_dir: Path = Path("data/02_stage/raw_measurements"),
        history_dir: Path = Path("data/02_stage/chip_histories"),
        output_dir: Path = Path("figs"),
        chip_group: str = "Alisson",
    ):
        super().__init__()
        self.setWindowTitle("Biotite Lab Plotter")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)

        # Session & managers (reused from TUI - zero Textual dependency)
        self.session = PlotSession(
            stage_dir=stage_dir,
            history_dir=history_dir,
            output_dir=output_dir,
            chip_group=chip_group,
        )
        self.config_manager = ConfigManager()
        self.settings_manager = SettingsManager()

        # Logging
        self.log_file = setup_tui_logging(log_dir="logs")
        self.logger = get_logger("src.gui")

        # Router (initialized before UI so pages can reference it)
        self.router = Router(self)

        # Build UI
        self._init_ui()

        # Register and create pages
        self._register_pages()

        # Keyboard shortcuts
        self._init_shortcuts()

        # Navigate to main menu
        self.router.return_to_main_menu()

        self.logger.info("GUI application initialized")

    def _init_ui(self) -> None:
        """Build the main window layout: sidebar + breadcrumb + stacked widget."""
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 12, 0, 12)
        sidebar_layout.setSpacing(0)

        # Logo / App name at top of sidebar
        logo_label = QLabel("Biotite")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 12px 0 16px 0;")
        sidebar_layout.addWidget(logo_label)

        # Sidebar navigation buttons
        self._sidebar_buttons: dict[str, QPushButton] = {}
        for label, page_name in self.SIDEBAR_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("sidebar-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(self._make_nav_handler(page_name))
            sidebar_layout.addWidget(btn)
            self._sidebar_buttons[page_name] = btn

        sidebar_layout.addStretch()

        # Quit button
        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName("sidebar-btn-quit")
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self.close)
        sidebar_layout.addWidget(quit_btn)

        root_layout.addWidget(sidebar)

        # ── Right panel (breadcrumb + content) ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Breadcrumb bar
        self._breadcrumb = QLabel("Home")
        self._breadcrumb.setObjectName("breadcrumb")
        right_layout.addWidget(self._breadcrumb)

        # Stacked widget for pages
        self.stack = QStackedWidget()
        self.stack.setObjectName("page-content")
        right_layout.addWidget(self.stack)

        root_layout.addWidget(right_panel, stretch=1)

    def _register_pages(self) -> None:
        """Create and register all page widgets."""
        from src.gui.pages.main_menu import MainMenuPage
        from src.gui.pages.chip_selector import ChipSelectorPage
        from src.gui.pages.plot_type_selector import PlotTypeSelectorPage
        from src.gui.pages.config_mode_selector import ConfigModeSelectorPage
        from src.gui.pages.its_preset_selector import ITSPresetSelectorPage
        from src.gui.pages.vt_preset_selector import VtPresetSelectorPage
        from src.gui.pages.experiment_selector import ExperimentSelectorPage
        from src.gui.pages.preview import PreviewPage
        from src.gui.pages.plot_generation import PlotGenerationPage
        from src.gui.pages.plot_success import PlotSuccessPage
        from src.gui.pages.plot_error import PlotErrorPage
        from src.gui.pages.history_browser import HistoryBrowserPage
        from src.gui.pages.plot_browser import PlotBrowserPage
        from src.gui.pages.recent_configs import RecentConfigsPage
        from src.gui.pages.data_pipeline_menu import DataPipelineMenuPage
        from src.gui.pages.process_confirmation import ProcessConfirmationPage
        from src.gui.pages.pipeline_loading import PipelineLoadingPage
        from src.gui.pages.process_success import ProcessSuccessPage
        from src.gui.pages.process_error import ProcessErrorPage
        from src.gui.pages.log_viewer import LogViewerPage
        from src.gui.pages.settings import SettingsPage
        from src.gui.config_pages.its_config import ITSConfigPage
        from src.gui.config_pages.ivg_config import IVgConfigPage
        from src.gui.config_pages.vvg_config import VVgConfigPage
        from src.gui.config_pages.vt_config import VtConfigPage
        from src.gui.config_pages.transconductance_config import TransconductanceConfigPage
        from src.gui.config_pages.cnp_config import CNPConfigPage
        from src.gui.config_pages.photoresponse_config import PhotoresponseConfigPage
        from src.gui.config_pages.laser_calibration_config import LaserCalibrationConfigPage
        from src.gui.config_pages.its_relaxation_config import ITSRelaxationConfigPage

        pages = [
            ("main_menu", MainMenuPage(self)),
            ("chip_selector", ChipSelectorPage(self)),
            ("plot_type_selector", PlotTypeSelectorPage(self)),
            ("config_mode_selector", ConfigModeSelectorPage(self)),
            ("its_preset_selector", ITSPresetSelectorPage(self)),
            ("vt_preset_selector", VtPresetSelectorPage(self)),
            ("its_config", ITSConfigPage(self)),
            ("ivg_config", IVgConfigPage(self)),
            ("vvg_config", VVgConfigPage(self)),
            ("vt_config", VtConfigPage(self)),
            ("transconductance_config", TransconductanceConfigPage(self)),
            ("cnp_config", CNPConfigPage(self)),
            ("photoresponse_config", PhotoresponseConfigPage(self)),
            ("laser_calibration_config", LaserCalibrationConfigPage(self)),
            ("its_relaxation_config", ITSRelaxationConfigPage(self)),
            ("experiment_selector", ExperimentSelectorPage(self)),
            ("preview", PreviewPage(self)),
            ("plot_generation", PlotGenerationPage(self)),
            ("plot_success", PlotSuccessPage(self)),
            ("plot_error", PlotErrorPage(self)),
            ("history_browser", HistoryBrowserPage(self)),
            ("plot_browser", PlotBrowserPage(self)),
            ("recent_configs", RecentConfigsPage(self)),
            ("data_pipeline_menu", DataPipelineMenuPage(self)),
            ("process_confirmation", ProcessConfirmationPage(self)),
            ("pipeline_loading", PipelineLoadingPage(self)),
            ("process_success", ProcessSuccessPage(self)),
            ("process_error", ProcessErrorPage(self)),
            ("log_viewer", LogViewerPage(self)),
            ("settings", SettingsPage(self)),
        ]

        for name, widget in pages:
            idx = self.stack.addWidget(widget)
            self.router.register_page(name, idx)

    def _init_shortcuts(self) -> None:
        """Set up global keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            lambda: self.router.navigate_to("chip_selector")
        )
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            self.router.go_back
        )
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self.router.go_back
        )
        QShortcut(QKeySequence("F5"), self).activated.connect(
            self._refresh_current_page
        )

    def _refresh_current_page(self) -> None:
        """Re-trigger on_enter for the current page."""
        current = self.stack.currentWidget()
        if hasattr(current, "on_enter"):
            current.on_enter()

    def _make_nav_handler(self, page_name: str):
        """Create a click handler that navigates to a page."""
        def handler():
            self.router.navigate_to(page_name)
        return handler

    def update_breadcrumb(self, page_name: str) -> None:
        """Update the breadcrumb label based on current navigation context."""
        # Build breadcrumb from session state
        parts = ["Home"]

        if page_name == "main_menu":
            self._breadcrumb.setText("Home")
            return

        friendly_names = {
            "chip_selector": "Select Chip",
            "plot_type_selector": "Plot Type",
            "config_mode_selector": "Config Mode",
            "its_preset_selector": "ITS Presets",
            "vt_preset_selector": "Vt Presets",
            "its_config": "ITS Configuration",
            "ivg_config": "IVg Configuration",
            "vvg_config": "VVg Configuration",
            "vt_config": "Vt Configuration",
            "transconductance_config": "Transconductance Configuration",
            "cnp_config": "CNP Configuration",
            "photoresponse_config": "Photoresponse Configuration",
            "laser_calibration_config": "Laser Calibration Configuration",
            "its_relaxation_config": "ITS Relaxation Configuration",
            "experiment_selector": "Select Experiments",
            "preview": "Preview",
            "plot_generation": "Generating...",
            "plot_success": "Success",
            "plot_error": "Error",
            "history_browser": "History Browser",
            "plot_browser": "Plot Browser",
            "data_pipeline_menu": "Process Data",
            "process_confirmation": "Confirm Processing",
            "pipeline_loading": "Processing...",
            "process_success": "Processing Complete",
            "process_error": "Processing Error",
            "recent_configs": "Recent Configs",
            "log_viewer": "Logs",
            "settings": "Settings",
        }

        # Add chip info if selected
        if self.session.chip_number is not None:
            parts.append(f"Chip {self.session.chip_number}")

        # Add plot type if selected
        if self.session.plot_type is not None:
            parts.append(self.session.plot_type)

        # Add current page
        parts.append(friendly_names.get(page_name, page_name))

        self._breadcrumb.setText("  >  ".join(parts))

    def update_sidebar_selection(self, page_name: str) -> None:
        """Highlight the active sidebar button."""
        # Map wizard pages to their parent sidebar item
        page_to_sidebar = {
            "main_menu": None,
            "chip_selector": "chip_selector",
            "plot_type_selector": "chip_selector",
            "config_mode_selector": "chip_selector",
            "its_preset_selector": "chip_selector",
            "vt_preset_selector": "chip_selector",
            "its_config": "chip_selector",
            "ivg_config": "chip_selector",
            "vvg_config": "chip_selector",
            "vt_config": "chip_selector",
            "transconductance_config": "chip_selector",
            "cnp_config": "chip_selector",
            "photoresponse_config": "chip_selector",
            "laser_calibration_config": "chip_selector",
            "its_relaxation_config": "chip_selector",
            "experiment_selector": "chip_selector",
            "preview": "chip_selector",
            "plot_generation": "chip_selector",
            "plot_success": "chip_selector",
            "plot_error": "chip_selector",
            "history_browser": "history_browser",
            "plot_browser": "plot_browser",
            "data_pipeline_menu": "data_pipeline_menu",
            "process_confirmation": "data_pipeline_menu",
            "pipeline_loading": "data_pipeline_menu",
            "process_success": "data_pipeline_menu",
            "process_error": "data_pipeline_menu",
            "recent_configs": "recent_configs",
            "log_viewer": "log_viewer",
            "settings": "settings",
        }
        active = page_to_sidebar.get(page_name, page_name)

        for name, btn in self._sidebar_buttons.items():
            btn.setChecked(name == active)


def main():
    """Launch the GUI application."""
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    stage_dir = Path("data/02_stage/raw_measurements")
    history_dir = Path("data/02_stage/chip_histories")
    output_dir = Path("figs")
    chip_group = "Alisson"

    window = MainWindow(
        stage_dir=stage_dir,
        history_dir=history_dir,
        output_dir=output_dir,
        chip_group=chip_group,
    )
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
