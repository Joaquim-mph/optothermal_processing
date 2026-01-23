"""Validate Manifest Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class ValidateManifestScreen(WizardScreen):
    """Validate manifest screen."""

    SCREEN_TITLE = "✅ Validate Manifest"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #validation-results {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .check-pass {
        color: $success;
    }

    .check-warn {
        color: $warning;
    }

    .check-fail {
        color: $error;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Process > Validate Manifest", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="validation-results"):
            yield Label("Running validation checks...\n")

            yield Label("✅ Schema Validation", classes="check-pass")
            yield Label("   All columns present and correct types\n")

            yield Label("✅ File Existence", classes="check-pass")
            yield Label("   All parquet_path files found (1,234/1,234)\n")

            yield Label("✅ Duplicate Detection", classes="check-pass")
            yield Label("   No duplicate run_ids found\n")

            yield Label("⚠️  Data Quality Checks", classes="check-warn")
            yield Label("   3 warnings found (view details)\n")

            yield Label("❌ Orphaned Files", classes="check-fail")
            yield Label("   2 parquet files not in manifest\n")

            yield Label("Overall: PASS (with warnings)")

        yield Button("📋 View Full Report", id="view-report", variant="primary")
        yield Button("🏠 Return to Main Menu", id="home-btn", variant="default")

    def on_mount(self) -> None:
        self.query_one("#view-report", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "view-report":
            self.app.notify("Full validation report - Coming soon!", severity="information")
        elif event.button.id == "home-btn":
            self.action_home()

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
