"""
Process New Data Hub Screen.

Central hub for data pipeline management:
- Stage Raw Data (CSV → Parquet)
- Build Chip Histories
- Extract Derived Metrics
- Full Pipeline (All Steps)
- Validate Manifest
- Pipeline Status
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class ProcessHubScreen(WizardScreen):
    """Process New Data hub menu screen."""

    SCREEN_TITLE = "⚙️  Process New Data"
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

    .hub-button {
        width: 100%;
        height: 3;
        margin: 1 0;
    }

    .hub-button:focus {
        background: $primary;
        border: tall $accent;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with breadcrumb and title."""
        yield Static("Main Menu > Process New Data", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose process hub menu."""
        with Vertical():
            yield Button("📥 Stage Raw Data", id="stage", variant="default", classes="hub-button")
            yield Button("🏗️  Build Chip Histories", id="histories", variant="default", classes="hub-button")
            yield Button("✨ Extract Derived Metrics", id="metrics", variant="default", classes="hub-button")
            yield Button("🔄 Full Pipeline", id="full", variant="primary", classes="hub-button")
            yield Button("✅ Validate Manifest", id="validate", variant="default", classes="hub-button")
            yield Button("📊 Pipeline Status", id="status", variant="default", classes="hub-button")

    def on_mount(self) -> None:
        """Focus first button."""
        self.query_one("#stage", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "stage":
            self.app.router.go_to_stage_raw_data()
        elif button_id == "histories":
            self.app.router.go_to_build_histories()
        elif button_id == "metrics":
            self.app.router.go_to_extract_metrics()
        elif button_id == "full":
            self.app.router.go_to_full_pipeline()
        elif button_id == "validate":
            self.app.router.go_to_validate_manifest()
        elif button_id == "status":
            self.app.router.go_to_pipeline_status()

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
