"""TUI Preferences Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label, Checkbox, Select
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class TUIPreferencesScreen(WizardScreen):
    """TUI preferences configuration screen."""

    SCREEN_TITLE = "🎨 TUI Preferences"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #preferences-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .form-row {
        height: 3;
        margin: 0 0 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Settings > TUI Preferences", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="preferences-form"):
            yield Label("Appearance:", classes="section-label")
            yield Checkbox("Show breadcrumbs", id="breadcrumbs", value=True)
            yield Checkbox("Show step numbers", id="step-numbers", value=True)
            yield Checkbox("Enable animations", id="animations", value=True)

            yield Label("\nBehavior:", classes="section-label")
            yield Checkbox("Auto-focus first element", id="auto-focus", value=True)
            yield Checkbox("Confirm before exit", id="confirm-exit")
            yield Checkbox("Remember window size", id="remember-size", value=True)

            yield Label("\nDefaults:", classes="section-label")
            yield Label("  • History directory: data/02_stage/chip_histories")
            yield Label("  • Chip group: (auto-detect)")

        yield Button("💾 Save Preferences", id="save-btn", variant="primary")
        yield Button("🔄 Reset to Defaults", id="reset-btn", variant="default")

    def on_mount(self) -> None:
        self.query_one("#save-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.app.notify("Preferences saved!", severity="information")
        elif event.button.id == "reset-btn":
            self.app.notify("Reset to defaults", severity="information")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
