#!/usr/bin/env python3
"""
Test Phase 1 - New Main Menu & Hub Navigation.

Quick test script to launch TUI with new v4.0 main menu.
"""

from pathlib import Path
from src.tui.app import PlotterApp


def main():
    """Launch TUI with new v4 main menu."""
    # Configure app
    app = PlotterApp(
        stage_dir=Path("data/02_stage/raw_measurements"),
        history_dir=Path("data/02_stage/chip_histories"),
        output_dir=Path("figs"),
        chip_group="Alisson",
    )

    # Override on_mount to use new v4 menu
    original_on_mount = app.on_mount

    def new_on_mount():
        """Use new v4 main menu."""
        # Set theme
        app.theme = app.settings_manager.theme

        # Push new v4 main menu instead of old one
        from src.tui.screens.navigation.main_menu_v4 import MainMenuScreen
        app.push_screen(MainMenuScreen())

    app.on_mount = new_on_mount

    # Run app
    app.run()


if __name__ == "__main__":
    main()
