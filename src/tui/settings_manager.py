"""
Settings Manager for TUI Preferences.

Handles persistent UI settings like theme, font size, and other preferences.
Stores settings as JSON in user's home directory.
"""

from __future__ import annotations
import json
import copy
from pathlib import Path
from typing import Dict, Any, Optional, Literal


# Available themes (shared between TUI and GUI)
Theme = Literal[
    "tokyo-night",
    "nord",
    "dracula",
    "gruvbox",
    "catppuccin-mocha",
    "catppuccin-latte",
]

DEFAULT_THEME: Theme = "tokyo-night"
DEFAULT_SETTINGS = {
    "version": "1.0.0",
    "ui": {
        "theme": DEFAULT_THEME,
        "animations": True,
        "notifications_timeout": 5,  # seconds
    }
}


class SettingsManager:
    """
    Manage persistent TUI settings.

    Features:
    - Theme preference (tokyo-night, nord, dracula, etc.)
    - UI preferences (animations, notifications)
    - Automatic config file creation
    - Safe defaults on load failure

    Storage location: ~/.lab_plotter_tui.json
    """

    def __init__(self, settings_file: Optional[Path] = None):
        """
        Initialize SettingsManager.

        Parameters
        ----------
        settings_file : Path, optional
            Path to settings file. Defaults to ~/.lab_plotter_tui.json
        """
        if settings_file is None:
            self.settings_file = Path.home() / ".lab_plotter_tui.json"
        else:
            self.settings_file = Path(settings_file)

        self._settings: Dict[str, Any] = {}
        self._ensure_settings_file()
        self.load()

    def _ensure_settings_file(self) -> None:
        """Create settings file with defaults if it doesn't exist."""
        if not self.settings_file.exists():
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_data(DEFAULT_SETTINGS)

    def _save_data(self, data: Dict[str, Any]) -> None:
        """Save settings data to JSON file."""
        with open(self.settings_file, "w") as f:
            json.dump(data, f, indent=2)

    def _load_data(self) -> Dict[str, Any]:
        """Load settings data from JSON file."""
        try:
            with open(self.settings_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # Return defaults if corrupted or missing
            return DEFAULT_SETTINGS.copy()

    def load(self) -> None:
        """Load settings from file."""
        data = self._load_data()

        # Merge with defaults to handle missing keys (deep copy to avoid mutations)
        self._settings = copy.deepcopy(DEFAULT_SETTINGS)
        if "ui" in data:
            self._settings["ui"].update(data.get("ui", {}))

    def save(self) -> None:
        """Save current settings to file."""
        self._save_data(self._settings)

    # ═══════════════════════════════════════════════════════════════════
    # Theme Settings
    # ═══════════════════════════════════════════════════════════════════

    @property
    def theme(self) -> str:
        """
        Get current theme.

        Returns
        -------
        str
            Theme name (e.g., "tokyo-night", "nord", "dracula")
        """
        return self._settings["ui"].get("theme", DEFAULT_THEME)

    @theme.setter
    def theme(self, value: str) -> None:
        """
        Set theme and save to disk.

        Parameters
        ----------
        value : str
            Theme name (must be a valid Textual theme)
        """
        self._settings["ui"]["theme"] = value
        self.save()

    # ═══════════════════════════════════════════════════════════════════
    # UI Preferences
    # ═══════════════════════════════════════════════════════════════════

    @property
    def animations(self) -> bool:
        """Get animations enabled state."""
        return self._settings["ui"].get("animations", True)

    @animations.setter
    def animations(self, value: bool) -> None:
        """Set animations enabled state and save."""
        self._settings["ui"]["animations"] = value
        self.save()

    @property
    def notifications_timeout(self) -> int:
        """Get notifications timeout in seconds."""
        return self._settings["ui"].get("notifications_timeout", 5)

    @notifications_timeout.setter
    def notifications_timeout(self, value: int) -> None:
        """Set notifications timeout and save."""
        self._settings["ui"]["notifications_timeout"] = max(1, min(value, 60))
        self.save()

    # ═══════════════════════════════════════════════════════════════════
    # Utility Methods
    # ═══════════════════════════════════════════════════════════════════

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.save()
        self.load()  # Reload to ensure consistency

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all settings as dictionary.

        Returns
        -------
        dict
            Complete settings dictionary
        """
        return self._settings.copy()

    def update_settings(self, settings: Dict[str, Any]) -> None:
        """
        Update multiple settings at once.

        Parameters
        ----------
        settings : dict
            Settings to update (will be merged with existing settings)
        """
        if "ui" in settings:
            self._settings["ui"].update(settings["ui"])
        self.save()

    @staticmethod
    def get_available_themes() -> list[str]:
        """
        Get list of available Textual themes.

        Returns
        -------
        list[str]
            List of theme names
        """
        return [
            "tokyo-night",
            "nord",
            "dracula",
            "gruvbox",
            "catppuccin-mocha",
            "catppuccin-latte",
        ]

    def get_theme_display_name(self, theme: str) -> str:
        """
        Get human-readable display name for theme.

        Parameters
        ----------
        theme : str
            Theme identifier

        Returns
        -------
        str
            Display name
        """
        display_names = {
            "tokyo-night": "Tokyo Night",
            "nord": "Nord",
            "dracula": "Dracula",
            "gruvbox": "Gruvbox",
            "catppuccin-mocha": "Catppuccin Mocha (Dark)",
            "catppuccin-latte": "Catppuccin Latte (Light)",
        }
        return display_names.get(theme, theme.title())
