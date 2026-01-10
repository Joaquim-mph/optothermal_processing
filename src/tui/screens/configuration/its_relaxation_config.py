"""
ITS Relaxation Configuration Screen.

Configure ITS relaxation time visualization. Shows raw current vs time data
with overlaid stretched exponential fits and extracted parameters (τ, β, R²).

Requires:
- data/03_derived/_metrics/metrics.parquet (relaxation_time metrics)
- Chip history with run_id column
"""

from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button, Input, Select, Checkbox
from textual.binding import Binding

from src.tui.screens.base import FormScreen


class ITSRelaxationConfigScreen(FormScreen):
    """ITS relaxation fit configuration screen."""

    SCREEN_TITLE = "Configure It Relaxation Fits"
    STEP_NUMBER = 3

    def __init__(self, chip_number: int, chip_group: str):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group

    BINDINGS = FormScreen.BINDINGS + [
        Binding("ctrl+s", "save_config", "Save Config", show=False),
    ]

    CSS = FormScreen.CSS + """
    #content-scroll {
        width: 100%;
        height: 1fr;
        min-height: 20;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with title and chip info."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static(
            f"Chip: [bold]{self.chip_group}{self.chip_number}[/bold]",
            id="chip-info"
        )
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose ITS relaxation configuration form."""
        with VerticalScroll(id="content-scroll"):
            # Info section
            yield Static(
                "[bold]It Relaxation Time Fits[/bold]\n\n"
                "Visualize stretched exponential relaxation time extraction.\n"
                "Shows raw current data with overlaid fits and extracted\n"
                "parameters: τ (relaxation time), β (stretch exponent), R².\n\n"
                "[dim]Requires: derive-all-metrics to have been run[/dim]",
                classes="info-text"
            )

            # Filter Options Section
            yield Static("─── Filter Options ────────────────────────", classes="section-title")

            with Horizontal(classes="form-row"):
                yield Static("Fit segment:", classes="form-label")
                yield Select(
                    [
                        ("All segments", "both"),
                        ("Light segment only", "light"),
                        ("Dark segment only", "dark"),
                    ],
                    value="both",
                    id="segment-filter-select",
                    classes="form-input"
                )
                yield Static("Which fit segment to include", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Checkbox("Dark-only measurements", id="dark-only-checkbox", value=True)
                yield Static("Only show truly dark It (no laser)", classes="form-help")

            # Plot Options Section
            yield Static("─── Plot Options ──────────────────────────", classes="section-title")

            with Horizontal(classes="form-row"):
                yield Static("Output dir:", classes="form-label")
                yield Input(
                    value="figs",
                    placeholder="figs",
                    id="output-dir-input",
                    classes="form-input"
                )
                yield Static(f"→ figs/{self.chip_group}{self.chip_number}/", classes="form-help")

            # Buttons
            with Horizontal(id="button-container"):
                yield Button("Save Config", id="save-button", variant="default", classes="nav-button")
                yield Button("← Back", id="back-button", variant="default", classes="nav-button")
                yield Button("Next: Select Experiments →", id="next-button", variant="primary", classes="nav-button")

    def on_mount(self) -> None:
        """Initialize screen."""
        self.query_one("#segment-filter-select", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()
        elif event.button.id == "save-button":
            self.action_save_config()

    def action_next(self) -> None:
        """Collect configuration and proceed to experiment selector."""
        config = self._collect_config()

        # Save to session
        for key, value in config.items():
            if hasattr(self.app.session, key):
                setattr(self.app.session, key, value)

        # Navigate to experiment selector
        # NOTE: Experiment selector needs to filter to It experiments with relaxation metrics
        self.app.router.go_to_experiment_selector()

    def action_save_config(self) -> None:
        """Save configuration to JSON file."""
        config = self._collect_config()

        config_to_save = {
            **config,
            "chip_number": self.chip_number,
            "chip_group": self.chip_group,
            "plot_type": "ITSRelaxation",
        }

        try:
            config_id = self.app.config_manager.save_config(config_to_save)
            self.notify(
                f"✓ Configuration saved (ID: {config_id})",
                severity="information",
                timeout=3
            )
        except Exception as e:
            self.notify(
                f"Failed to save configuration: {e}",
                severity="error",
                timeout=5
            )

    def _collect_config(self) -> dict:
        """Collect all configuration values from the form."""
        config = {
            "selection_mode": "interactive",
            "plot_type": "ITSRelaxation",
        }

        # Filters
        config["fit_segment"] = self.query_one("#segment-filter-select", Select).value
        config["dark_only"] = self.query_one("#dark-only-checkbox", Checkbox).value

        # Output
        output_dir = self.query_one("#output-dir-input", Input).value.strip()
        config["output_dir"] = output_dir if output_dir else "figs"

        return config
