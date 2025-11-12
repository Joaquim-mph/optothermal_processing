"""
Process Confirmation Dialog.

Simple confirmation dialog before running the full data processing pipeline.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class ProcessConfirmationScreen(WizardScreen):
    """Confirmation dialog for processing new data."""

    SCREEN_TITLE = "Process New Data?"
    STEP_NUMBER = None  # Dialog, not part of wizard flow

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("enter", "confirm", "Start", priority=True),
    ]

    # Dialog-specific CSS (extends WizardScreen CSS)
    CSS = WizardScreen.CSS + """
    #main-container {
        max-width: 80;
    }

    #description {
        width: 100%;
        color: $text;
        margin-bottom: 2;
        padding: 1;
        background: $panel;
    }

    #command {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 2;
    }

    #warning {
        width: 100%;
        color: $warning;
        text-style: italic;
        margin-bottom: 2;
        content-align: center middle;
    }

    #status {
        width: 100%;
        content-align: center middle;
        color: $accent;
        text-style: bold;
        margin-bottom: 2;
    }

    .dialog-button {
        width: 1fr;
        margin: 0 1;
        min-height: 3;
    }

    .dialog-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }
    """

    def compose_content(self) -> ComposeResult:
        """Compose confirmation dialog content."""
        yield Static(
            "This will run the complete data processing pipeline:\n\n"
            "Step 1: Stage raw CSVs → Parquet (schema-validated)\n"
            "Step 2: Build chip histories from manifest\n"
            "Step 3: Extract derived metrics (CNP, photoresponse, power)\n"
            "Step 4: Enrich histories (join calibrations + metrics)\n\n"
            "Data paths:\n"
            "  → Raw: data/01_raw/\n"
            "  → Staged: data/02_stage/raw_measurements/\n"
            "  → Histories: data/02_stage/chip_histories/\n"
            "  → Derived: data/03_derived/_metrics/\n"
            "  → Enriched: data/03_derived/chip_histories_enriched/\n\n"
            "⚠ NOTE: On some systems, multiprocessing from the TUI\n"
            "may not work. If you encounter errors, please run:\n"
            "  python process_and_analyze.py full-pipeline",
            id="description"
        )

        yield Static("Complete pipeline: staging → histories → metrics → enrichment", id="command")

        yield Static("⚠ This may take several minutes for large datasets", id="warning")

        yield Static("", id="status")

        with Vertical(id="button-container"):
            yield Button("Cancel", id="cancel-button", variant="default", classes="dialog-button nav-button")
            yield Button("Start Processing", id="confirm-button", variant="primary", classes="dialog-button nav-button")

    def on_mount(self) -> None:
        """Focus the confirm button on mount."""
        self.query_one("#confirm-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-button":
            self.action_back()  # Use standard back action
        elif event.button.id == "confirm-button":
            self.action_confirm()

    def action_confirm(self) -> None:
        """Start processing with loading screen using router."""
        # Replace this screen with the loading screen
        self.app.pop_screen()
        self.app.router.go_to_process_loading()
