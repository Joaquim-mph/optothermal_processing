"""Pipeline Status Dashboard Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class PipelineStatusScreen(WizardScreen):
    """Pipeline status dashboard screen."""

    SCREEN_TITLE = "📊 Pipeline Status"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("home", "home", "Home", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = WizardScreen.CSS + """
    #status-dashboard {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-header {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .stat-row {
        margin: 0 0 0 2;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Process > Pipeline Status", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="status-dashboard"):
            yield Label("📊 PIPELINE OVERVIEW\n", classes="section-header")

            yield Label("Last Operations:")
            yield Label("├─ Staging:     2 hours ago ✅", classes="stat-row")
            yield Label("├─ Histories:   2 hours ago ✅", classes="stat-row")
            yield Label("├─ Metrics:     3 hours ago ✅", classes="stat-row")
            yield Label("└─ Validation:  3 hours ago ✅\n", classes="stat-row")

            yield Label("📈 DATA STATISTICS\n", classes="section-header")
            yield Label("├─ Manifest Entries:    1,234", classes="stat-row")
            yield Label("├─ Chips Tracked:       8", classes="stat-row")
            yield Label("├─ Total Experiments:   1,234", classes="stat-row")
            yield Label("├─ Enriched Histories:  8", classes="stat-row")
            yield Label("└─ Derived Metrics:     847\n", classes="stat-row")

            yield Label("💾 STORAGE\n", classes="section-header")
            yield Label("├─ Staged Data:         2.3 GB", classes="stat-row")
            yield Label("├─ Histories:           145 MB", classes="stat-row")
            yield Label("├─ Derived Metrics:     23 MB", classes="stat-row")
            yield Label("└─ Total:               2.47 GB", classes="stat-row")

        yield Button("🔄 Refresh", id="refresh-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#refresh-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-btn":
            self.action_refresh()

    def action_refresh(self) -> None:
        self.app.notify("Refreshing pipeline status...", severity="information")
        # TODO: Actually query file system and databases

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
