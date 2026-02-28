"""
GUI Smoke Tests.

Headless tests using QT_QPA_PLATFORM=offscreen to verify:
- App startup
- Page registration
- Navigation
- Widget creation
"""

import os
import sys
import pytest

# Force offscreen rendering for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="module")
def qapp():
    """Create a QApplication instance for the test session."""
    from PyQt6.QtWidgets import QApplication
    from src.gui.theme import STYLESHEET

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setStyleSheet(STYLESHEET)
    yield app


@pytest.fixture
def main_window(qapp):
    """Create a MainWindow instance."""
    from src.gui.app import MainWindow
    window = MainWindow()
    yield window
    window.close()


EXPECTED_PAGES = [
    "main_menu", "chip_selector", "plot_type_selector",
    "config_mode_selector", "its_preset_selector", "vt_preset_selector",
    "its_config", "ivg_config", "vvg_config", "vt_config",
    "transconductance_config", "cnp_config", "photoresponse_config",
    "laser_calibration_config", "its_relaxation_config",
    "experiment_selector", "preview", "plot_generation",
    "plot_success", "plot_error",
    "history_browser", "plot_browser", "recent_configs",
    "data_pipeline_menu", "process_confirmation", "pipeline_loading",
    "process_success", "process_error",
    "log_viewer", "settings",
    "batch_plot", "batch_progress", "batch_results",
]


def test_app_startup(main_window):
    """MainWindow creates without error."""
    assert main_window is not None
    assert main_window.session is not None
    assert main_window.config_manager is not None
    assert main_window.settings_manager is not None
    assert main_window.router is not None


def test_all_pages_registered(main_window):
    """All expected pages are registered in the router."""
    for page_name in EXPECTED_PAGES:
        assert page_name in main_window.router._pages, f"Missing page: {page_name}"


def test_page_count(main_window):
    """Stack widget has the expected number of pages."""
    assert main_window.stack.count() == len(EXPECTED_PAGES)


def test_navigation_forward_back(main_window):
    """Basic forward/back navigation works."""
    main_window.router.navigate_to("chip_selector")
    assert main_window.router.current_page == "chip_selector"

    main_window.router.navigate_to("plot_type_selector")
    assert main_window.router.current_page == "plot_type_selector"

    main_window.router.go_back()
    assert main_window.router.current_page == "chip_selector"


def test_return_to_main_menu(main_window):
    """return_to_main_menu clears history and goes home."""
    main_window.router.navigate_to("chip_selector")
    main_window.router.navigate_to("plot_browser")
    main_window.router.return_to_main_menu()
    assert main_window.router.current_page == "main_menu"
    assert not main_window.router.can_go_back


def test_sidebar_buttons(main_window):
    """Sidebar has expected buttons."""
    expected_sidebar = [
        "chip_selector", "history_browser", "plot_browser",
        "data_pipeline_menu", "batch_plot", "recent_configs", "log_viewer", "settings",
    ]
    assert list(main_window._sidebar_buttons.keys()) == expected_sidebar


def test_breadcrumb_updates(main_window):
    """Breadcrumb updates on navigation."""
    main_window.router.return_to_main_menu()
    assert main_window._breadcrumb.text() == "Home"

    main_window.router.navigate_to("settings")
    assert "Settings" in main_window._breadcrumb.text()


def test_navigate_all_pages(main_window):
    """Navigate to every page without crashing."""
    for page_name in EXPECTED_PAGES:
        main_window.router.navigate_to(page_name)
        assert main_window.router.current_page == page_name
