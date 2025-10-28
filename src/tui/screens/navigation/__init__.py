"""
Navigation screens - Entry points and flow control.

Provides main menu and recent configurations access.
"""

from src.tui.screens.navigation.main_menu import MainMenuScreen
from src.tui.screens.navigation.recent_configs import RecentConfigsScreen

__all__ = [
    "MainMenuScreen",
    "RecentConfigsScreen",
]
