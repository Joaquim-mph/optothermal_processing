"""
Stage Raw Data Screen.

Configuration screen for staging raw CSV files to Parquet.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Label, Select, Checkbox, Input
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class StageRawDataScreen(WizardScreen):
    """Stage raw data configuration screen."""

    SCREEN_TITLE = "📥 Stage Raw Data"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("home", "home", "Home", show=True),
    ]

    CSS = WizardScreen.CSS + """
    #breadcrumb {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #config-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .form-row {
        height: 3;
        margin: 0 0 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .action-button {
        width: 100%;
        height: 3;
        margin: 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header."""
        yield Static("Main Menu > Process > Stage Raw Data", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose staging configuration form."""
        with Vertical(id="config-form"):
            yield Label("Configuration:", classes="section-label")

            yield Label("\nRaw Data Path:")
            with Horizontal(classes="form-row"):
                yield Input(
                    value="data/01_raw",
                    placeholder="Path to raw CSV files...",
                    id="raw-path-input"
                )

            yield Label("\nOptions:", classes="section-label")
            yield Checkbox("Force Overwrite (re-stage existing files)", id="force-overwrite")
            yield Checkbox("Strict Mode (fail on validation errors)", id="strict-mode")

            yield Label("\nParallel Workers:", classes="section-label")
            with Horizontal(classes="form-row"):
                yield Select(
                    options=[("1", "1"), ("2", "2"), ("4", "4"), ("6", "6"), ("8", "8"), ("12", "12")],
                    value="6",
                    id="workers-select"
                )

            yield Label("\n💡 Estimated: ~120 CSV files", classes="muted")

        with Vertical():
            yield Button(
                "▶️  Start Staging",
                id="start-staging",
                variant="primary",
                classes="action-button"
            )

    def on_mount(self) -> None:
        """Focus start button."""
        self.query_one("#start-staging", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "start-staging":
            self._start_staging()

    def _start_staging(self) -> None:
        """Start staging process."""
        raw_path = self.query_one("#raw-path-input", Input).value
        force = self.query_one("#force-overwrite", Checkbox).value
        strict = self.query_one("#strict-mode", Checkbox).value
        workers = int(self.query_one("#workers-select", Select).value)

        self.app.notify(
            f"Starting staging: {raw_path} (workers={workers}, force={force}, strict={strict})",
            severity="information"
        )

        # Navigate to progress screen
        self.app.router.go_to_staging_progress(
            raw_path=raw_path,
            force_overwrite=force,
            strict_mode=strict,
            workers=workers
        )

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
