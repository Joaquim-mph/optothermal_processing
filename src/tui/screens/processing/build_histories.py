"""Build Chip Histories Screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Label, Select, Checkbox
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class BuildHistoriesScreen(WizardScreen):
    """Build chip histories screen."""

    SCREEN_TITLE = "🏗️  Build Chip Histories"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #config-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Process > Build Histories", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="config-form"):
            yield Label("Scope:", classes="section-label")
            yield Checkbox("All Chips (auto-discover)", id="all-chips", value=True)
            yield Checkbox("Specific Chip(s)", id="specific-chips")

            yield Label("\nDiscovered Chips (8):", classes="section-label")
            yield Label("  • Alisson67 (127 experiments)")
            yield Label("  • Encap81 (234 experiments)")
            yield Label("  • Encap75 (89 experiments)")
            yield Label("  • ... and 5 more\n")

            yield Label("Options:", classes="section-label")
            yield Checkbox("Force Rebuild (rebuild existing histories)", id="force-rebuild")

        yield Button("▶️  Start Build", id="start-build", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#start-build", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-build":
            self.app.notify("Building chip histories...", severity="information")
            # TODO: Implement actual build process
            self.app.notify("Build complete - 8 histories created!", severity="information")

    def action_home(self) -> None:
        self.app.router.return_to_main_menu()
