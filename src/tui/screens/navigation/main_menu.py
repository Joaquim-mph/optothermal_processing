"""
Main Menu Screen.

The entry point for the TUI wizard, providing options to:
- Start a new plot
- Load recent configurations
- Access batch mode
- Configure settings
- View help
- Quit
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class MainMenuScreen(WizardScreen):
    """Main menu screen with wizard entry points."""

    SCREEN_TITLE = "🔬 Experiment Plotting Assistant"
    STEP_NUMBER = None  # Main menu is not part of the wizard steps

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("q", "quit", "Quit", priority=True),
        Binding("n", "new_plot", "New Plot", show=False),
        Binding("ctrl+h", "history", "History", show=False),
        Binding("p", "process_data", "Process Data", show=False),
        Binding("r", "recent", "Recent", show=False),
        Binding("b", "batch", "Batch", show=False),
        Binding("s", "settings", "Settings", show=False),
        Binding("h", "help", "Help", show=False),
        Binding("up", "move_up", "Up", priority=True),
        Binding("down", "move_down", "Down", priority=True),
        Binding("enter", "select_current", "Select", show=False),
    ]

    # Menu-specific CSS (extends base WizardScreen CSS)
    CSS = WizardScreen.CSS + """
    #main-container {
        max-width: 80;
    }

    #subtitle {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 2;
    }

    .menu-button {
        width: 100%;
        margin: 1 0;
    }

    .menu-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }

    .menu-button:hover {
        background: $primary;
        color: $primary-background;
    }

    #help-text {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-top: 2;
        text-style: dim;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose custom header with title and subtitle."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static("NanoLab - Device Characterization", id="subtitle")

    def compose_content(self) -> ComposeResult:
        """Compose main menu buttons."""
        with Vertical():
            yield Button("New Plot", id="new-plot", variant="default", classes="menu-button")
            yield Button("View Chip Histories", id="history", variant="default", classes="menu-button")
            yield Button("Process New Data", id="process-data", variant="default", classes="menu-button")
            yield Button("Recent Configurations (0)", id="recent", variant="default", classes="menu-button")
            yield Button("Batch Mode", id="batch", variant="default", classes="menu-button")
            yield Button("Settings", id="settings", variant="default", classes="menu-button")
            yield Button("Help", id="help-button", variant="default", classes="menu-button")
            yield Button("Quit", id="quit", variant="error", classes="menu-button")

        yield Static("Use ↑↓ arrows to navigate, Enter to select, Ctrl+H for histories, P to process data, Q to quit", id="help-text")

    def on_mount(self) -> None:
        """Focus the first button when mounted and update config count."""
        self.query_one("#new-plot", Button).focus()
        self._update_recent_count()

    def _update_recent_count(self) -> None:
        """Update the recent configurations button with count."""
        try:
            count = self.app.config_manager.get_stats()["total_count"]
            button = self.query_one("#recent", Button)
            button.label = f"Recent Configurations ({count})"
        except Exception:
            pass  # Silently fail if config manager not available

    def on_button_focus(self, event: Button.Focus) -> None:
        """Update button labels to show arrow on focused button."""
        # Remove arrows from all buttons
        for button in self.query(".menu-button").results(Button):
            label = str(button.label)
            if label.startswith("→ "):
                button.label = label[2:]  # Remove arrow

        # Add arrow to focused button
        focused_button = event.button
        label = str(focused_button.label)
        if not label.startswith("→ "):
            focused_button.label = f"→ {label}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "new-plot":
            self.action_new_plot()
        elif button_id == "history":
            self.action_history()
        elif button_id == "process-data":
            self.action_process_data()
        elif button_id == "recent":
            self.action_recent()
        elif button_id == "batch":
            self.action_batch()
        elif button_id == "settings":
            self.action_settings()
        elif button_id == "help-button":
            self.action_help()
        elif button_id == "quit":
            self.action_quit()

    # ═══════════════════════════════════════════════════════════════════
    # Action Methods (using router for navigation)
    # ═══════════════════════════════════════════════════════════════════

    def action_new_plot(self) -> None:
        """Start new plot wizard (navigate to chip selector)."""
        # Reset wizard state for new plot
        self.app.session.reset_wizard_state()

        # Navigate to Chip Selector (Step 1) using router
        self.app.router.go_to_chip_selector(mode="plot")

    def action_history(self) -> None:
        """Start chip history browsing flow."""
        self.app.session.reset_wizard_state()
        try:
            self.app.router.go_to_chip_selector(mode="history")
        except Exception as exc:
            self.notify(str(exc), severity="error")

    def action_process_data(self) -> None:
        """Show process data confirmation dialog using router."""
        self.app.router.go_to_process_confirmation()

    def action_recent(self) -> None:
        """Show recent configurations using router."""
        self.app.router.go_to_recent_configs()

    def action_batch(self) -> None:
        """Show batch mode."""
        # TODO: Navigate to Batch Mode (Phase 6)
        self.app.notify("Batch Mode - Coming in Phase 6!")

    def action_settings(self) -> None:
        """Show theme settings."""
        from src.tui.screens.navigation.theme_settings import ThemeSettingsScreen
        self.app.push_screen(ThemeSettingsScreen())

    def action_help(self) -> None:
        """Show help."""
        # TODO: Show help screen (Phase 7)
        help_text = """
        Keyboard Shortcuts:
        - N: New Plot
        - Ctrl+H: View Chip Histories
        - R: Recent Configurations
        - B: Batch Mode
        - S: Settings
        - H: Help
        - Q: Quit
        - Ctrl+Q: Quit (global)
        """
        self.app.notify(help_text.strip())

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_select_current(self) -> None:
        """Select the currently focused button using Enter key."""
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    def action_move_up(self) -> None:
        """Move focus to previous button."""
        self.screen.focus_previous()

    def action_move_down(self) -> None:
        """Move focus to next button."""
        self.screen.focus_next()

    def action_back(self) -> None:
        """Override back action - main menu shouldn't go back."""
        # Do nothing - we're already at the entry point
        pass
