"""About Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Label, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class AboutScreen(WizardScreen):
    """About / version info screen."""

    SCREEN_TITLE = "ℹ️  About"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #about-content {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-header {
        color: $accent;
        text-style: bold;
        margin-top: 1;
        text-align: center;
    }

    .info-row {
        margin: 0 0 0 2;
        text-align: center;
    }

    .logo {
        color: $primary;
        text-style: bold;
        font-size: 2;
        text-align: center;
        margin: 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Help > About", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="about-content"):
            yield Label("📊 OPTOTHERMAL PROCESSING PIPELINE", classes="logo")

            yield Label("\n🔬 APPLICATION INFO\n", classes="section-header")
            yield Label("Version: 4.0.0 (TUI v4.0 - Hub Reorganization)", classes="info-row")
            yield Label("Python: 3.11+", classes="info-row")
            yield Label("Framework: Textual 0.x", classes="info-row")

            yield Label("\n📚 STACK\n", classes="section-header")
            yield Label("• Data: Polars (DataFrame library)", classes="info-row")
            yield Label("• Validation: Pydantic v2+", classes="info-row")
            yield Label("• CLI: Typer + Rich", classes="info-row")
            yield Label("• Plotting: Matplotlib + scienceplots", classes="info-row")
            yield Label("• Terminal UI: Textual", classes="info-row")
            yield Label("• Acceleration: Numba (JIT compilation)", classes="info-row")

            yield Label("\n🎯 FEATURES\n", classes="section-header")
            yield Label("• CSV → Parquet staging with validation", classes="info-row")
            yield Label("• Chip history tracking (1,200+ experiments)", classes="info-row")
            yield Label("• Derived metrics: CNP, photoresponse, relaxation times", classes="info-row")
            yield Label("• Publication-quality plots", classes="info-row")
            yield Label("• Batch processing with YAML configs", classes="info-row")
            yield Label("• Interactive TUI for lab users", classes="info-row")

            yield Label("\n📝 PHASE COMPLETION\n", classes="section-header")
            yield Label("✅ Phase 1: Main Menu + Hub Navigation", classes="info-row")
            yield Label("✅ Phase 2: Plots Hub (9 screens)", classes="info-row")
            yield Label("✅ Phase 3: Chip Histories Hub (9 screens)", classes="info-row")
            yield Label("✅ Phase 4: Process New Data Hub (8 screens)", classes="info-row")
            yield Label("✅ Phase 5: Settings & Help Hubs (8 screens)", classes="info-row")
            yield Label("⏳ Phase 6: Polish & Testing (In Progress)", classes="info-row")

            yield Label("\n🙏 ACKNOWLEDGMENTS\n", classes="section-header")
            yield Label("Developed for NanoLab experimental data processing", classes="info-row")
            yield Label("Kedro-based pipeline architecture", classes="info-row")

        yield Button("🏠 Return to Main Menu", id="home-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#home-btn", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "home-btn":
            self.action_home()

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
