"""
Navigation screens - Entry points and flow control.

Provides main menu, recent configurations access, and log viewer.
"""

from src.tui.screens.navigation.main_menu import MainMenuScreen
from src.tui.screens.navigation.recent_configs import RecentConfigsScreen
from src.tui.screens.navigation.log_viewer import LogViewerScreen

__all__ = [
    "MainMenuScreen",
    "RecentConfigsScreen",
    "LogViewerScreen",
]
