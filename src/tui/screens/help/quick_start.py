"""Quick Start Guide Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, Label, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class QuickStartScreen(WizardScreen):
    """Quick start guide screen."""

    SCREEN_TITLE = "🚀 Quick Start Guide"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #guide-content {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
        height: 35;
    }

    .section-header {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .step-label {
        margin: 0 0 0 2;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Help > Quick Start", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with VerticalScroll(id="guide-content"):
            yield Label("📊 GENERATING YOUR FIRST PLOT\n", classes="section-header")
            yield Label("1. Select 📊 Plots from Main Menu", classes="step-label")
            yield Label("2. Click 🆕 New Plot", classes="step-label")
            yield Label("3. Choose your chip (e.g., Alisson67)", classes="step-label")
            yield Label("4. Select plot type (IVg, ITS, VVg, etc.)", classes="step-label")
            yield Label("5. Configure options (legend, baseline, etc.)", classes="step-label")
            yield Label("6. Select experiments by sequence number", classes="step-label")
            yield Label("7. Preview and generate!\n", classes="step-label")

            yield Label("📂 EXPLORING CHIP HISTORIES\n", classes="section-header")
            yield Label("1. Select 📂 Chip Histories from Main Menu", classes="step-label")
            yield Label("2. Click 📊 View Standard History", classes="step-label")
            yield Label("3. Select chip from dropdown", classes="step-label")
            yield Label("4. Filter by procedure, light, date", classes="step-label")
            yield Label("5. Click rows to view details\n", classes="step-label")

            yield Label("⚙️  PROCESSING NEW DATA\n", classes="section-header")
            yield Label("1. Select ⚙️  Process New Data from Main Menu", classes="step-label")
            yield Label("2. For a complete pipeline, click 🔄 Full Pipeline", classes="step-label")
            yield Label("3. Or run steps individually:", classes="step-label")
            yield Label("   • 📥 Stage Raw Data (CSV → Parquet)", classes="step-label")
            yield Label("   • 🏗️  Build Chip Histories", classes="step-label")
            yield Label("   • ✨ Extract Derived Metrics\n", classes="step-label")

            yield Label("⌨️  KEYBOARD SHORTCUTS\n", classes="section-header")
            yield Label("• ESC: Go back one screen", classes="step-label")
            yield Label("• Home: Return to main menu", classes="step-label")
            yield Label("• Tab: Navigate between fields", classes="step-label")
            yield Label("• Enter: Activate button/submit form", classes="step-label")

        yield Button("🏠 Return to Main Menu", id="home-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#home-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "home-btn":
            self.action_home()

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
