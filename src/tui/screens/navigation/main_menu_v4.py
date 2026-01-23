"""
Main Menu Screen - Version 4.0 (TUI Reorganization).

Simplified hub-based navigation with 6 top-level options:
- Plots (all plotting activities)
- Chip Histories (data exploration)
- Process New Data (pipeline management)
- Settings (configuration)
- Help (documentation & support)
- Quit (exit application)
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class MainMenuScreen(WizardScreen):
    """Main menu screen with hub navigation (v4.0)."""

    SCREEN_TITLE = "🔬 Experiment Plotting Assistant"
    STEP_NUMBER = None  # Main menu is not part of the wizard steps

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+n", "new_plot", "New Plot", show=False),
        Binding("ctrl+h", "histories", "Histories", show=False),
        Binding("ctrl+p", "process", "Process", show=False),
        Binding("up", "move_up", "Up", priority=True),
        Binding("down", "move_down", "Down", priority=True),
        Binding("enter", "select_current", "Select", show=False),
    ]

    # Menu-specific CSS
    CSS = WizardScreen.CSS + """
    #subtitle {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 1;
    }

    .menu-button {
        width: 100%;
        height: 3;
        min-height: 3;
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
        """Compose header with title and subtitle."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static("NanoLab - Device Characterization", id="subtitle")

    def compose_content(self) -> ComposeResult:
        """Compose main menu with 6 hub buttons."""
        with Vertical():
            yield Button("📊 Plots", id="plots", variant="primary", classes="menu-button")
            yield Button("📂 Chip Histories", id="histories", variant="default", classes="menu-button")
            yield Button("⚙️  Process New Data", id="process", variant="default", classes="menu-button")
            yield Button("🛠️  Settings", id="settings", variant="default", classes="menu-button")
            yield Button("❓ Help", id="help-button", variant="default", classes="menu-button")
            yield Button("🚪 Quit", id="quit", variant="error", classes="menu-button")

        yield Static("Use ↑↓ to navigate, Enter to select, Ctrl+N for new plot, Ctrl+H for histories, Q to quit", id="help-text")

    def on_mount(self) -> None:
        """Focus the first button when mounted."""
        self.query_one("#plots", Button).focus()

    def on_button_focus(self, event: Button.Focus) -> None:
        """Update button labels to show arrow on focused button."""
        # Remove arrows from all buttons
        for button in self.query(".menu-button").results(Button):
            label = str(button.label)
            if label.startswith("→ "):
                button.label = label[2:]

        # Add arrow to focused button
        focused_button = event.button
        label = str(focused_button.label)
        if not label.startswith("→ "):
            focused_button.label = f"→ {label}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "plots":
            self.action_plots()
        elif button_id == "histories":
            self.action_histories()
        elif button_id == "process":
            self.action_process()
        elif button_id == "settings":
            self.action_settings()
        elif button_id == "help-button":
            self.action_help()
        elif button_id == "quit":
            self.action_quit()

    # ═══════════════════════════════════════════════════════════════════
    # Hub Navigation Actions
    # ═══════════════════════════════════════════════════════════════════

    def action_plots(self) -> None:
        """Navigate to Plots hub."""
        self.app.router.go_to_plots_hub()

    def action_histories(self) -> None:
        """Navigate to Chip Histories hub."""
        self.app.router.go_to_histories_hub()

    def action_process(self) -> None:
        """Navigate to Process New Data hub."""
        self.app.router.go_to_process_hub()

    def action_settings(self) -> None:
        """Navigate to Settings hub."""
        self.app.router.go_to_settings_hub()

    def action_help(self) -> None:
        """Navigate to Help hub."""
        self.app.router.go_to_help_hub()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    # ═══════════════════════════════════════════════════════════════════
    # Global Shortcuts
    # ═══════════════════════════════════════════════════════════════════

    def action_new_plot(self) -> None:
        """Global shortcut: Start new plot (Ctrl+N)."""
        # Go to plots hub, then new plot
        self.app.router.go_to_plots_hub()
        # TODO: In Phase 2, add router.go_to_new_plot()

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
        pass  # Do nothing - we're at the entry point
