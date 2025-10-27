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
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.binding import Binding


class MainMenuScreen(Screen):
    """Main menu screen with wizard entry points."""

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("n", "new_plot", "New Plot", show=False),
        Binding("p", "process_data", "Process Data", show=False),
        Binding("r", "recent", "Recent", show=False),
        Binding("b", "batch", "Batch", show=False),
        Binding("s", "settings", "Settings", show=False),
        Binding("h", "help", "Help", show=False),
        Binding("up", "move_up", "Up", priority=True),
        Binding("down", "move_down", "Down", priority=True),
        Binding("enter", "select_current", "Select", show=False),
    ]

    CSS = """
    MainMenuScreen {
        align: center middle;
    }

    #main-container {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
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

    def compose(self) -> ComposeResult:
        """Create main menu widgets."""
        yield Header()

        with Container(id="main-container"):
            yield Static("🔬 Experiment Plotting Assistant", id="title")
            yield Static("NanoLab - Device Characterization", id="subtitle")

            with Vertical():
                yield Button("New Plot", id="new-plot", variant="default", classes="menu-button")
                yield Button("Process New Data", id="process-data", variant="default", classes="menu-button")
                yield Button("Recent Configurations (0)", id="recent", variant="default", classes="menu-button")
                yield Button("Batch Mode", id="batch", variant="default", classes="menu-button")
                yield Button("Settings", id="settings", variant="default", classes="menu-button")
                yield Button("Help", id="help-button", variant="default", classes="menu-button")
                yield Button("Quit", id="quit", variant="error", classes="menu-button")

            yield Static("Use ↑↓ arrows to navigate, Enter to select, P to process data, Q to quit", id="help-text")

        yield Footer()

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

    def action_new_plot(self) -> None:
        """Start new plot wizard."""
        from src.tui.screens.chip_selector import ChipSelectorScreen

        # Reset configuration for new plot
        self.app.reset_config()

        # Navigate to Chip Selector (Step 1)
        self.app.push_screen(ChipSelectorScreen(
            metadata_dir=self.app.metadata_dir,
            raw_dir=self.app.raw_dir,
            history_dir=self.app.history_dir,
            chip_group=self.app.chip_group,
        ))

    def action_process_data(self) -> None:
        """Show process data confirmation dialog."""
        from src.tui.screens.process_confirmation import ProcessConfirmationScreen

        self.app.push_screen(ProcessConfirmationScreen())

    def action_recent(self) -> None:
        """Show recent configurations."""
        from src.tui.screens.recent_configs import RecentConfigsScreen

        self.app.push_screen(RecentConfigsScreen())

    def action_batch(self) -> None:
        """Show batch mode."""
        # TODO: Navigate to Batch Mode (Phase 6)
        self.app.notify("Batch Mode - Coming in Phase 6!")

    def action_settings(self) -> None:
        """Show settings."""
        # TODO: Navigate to Settings (Phase 6)
        self.app.notify("Settings - Coming in Phase 6!")

    def action_help(self) -> None:
        """Show help."""
        # TODO: Show help screen (Phase 7)
        help_text = """
        Keyboard Shortcuts:
        - N: New Plot
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
