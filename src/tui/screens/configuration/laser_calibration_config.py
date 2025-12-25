"""
Laser Calibration Configuration Screen.

Configure laser calibration plot parameters. Unlike other plot types, laser
calibrations are global measurements (not chip-specific).

Data source: manifest.parquet filtered by proc == "LaserCalibration"
"""

from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button, Input, Select, Checkbox
from textual.binding import Binding

from src.tui.screens.base import FormScreen


class LaserCalibrationConfigScreen(FormScreen):
    """Laser calibration configuration screen."""

    SCREEN_TITLE = "Configure Laser Calibration Plot"
    STEP_NUMBER = 3  # Step 3 since we skip chip selection

    def __init__(self, chip_number: int = 0, chip_group: str = ""):
        """Initialize (chip params ignored for laser calibrations)."""
        super().__init__()
        self.chip_number = chip_number  # Dummy for compatibility
        self.chip_group = chip_group    # Dummy for compatibility

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
        """Compose header with title and step indicator."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static(
            "[bold]Global Measurement[/bold] (not chip-specific)",
            id="chip-info"
        )
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose laser calibration configuration form."""
        with VerticalScroll(id="content-scroll"):
            # Info section
            yield Static(
                "[bold]Laser Calibration Plots[/bold]\n\n"
                "Plot optical power vs laser PSU voltage curves for characterizing\n"
                "laser output. Calibrations are global measurements used to calculate\n"
                "irradiated power for all chips.\n\n"
                "[dim]Data loaded from manifest.parquet (LaserCalibration procedure)[/dim]",
                classes="info-text"
            )

            # Filter Options Section
            yield Static("─── Filter Options ────────────────────────", classes="section-title")

            with Horizontal(classes="form-row"):
                yield Static("Wavelength (nm):", classes="form-label")
                yield Input(
                    placeholder="Leave empty for all, or e.g., 365",
                    id="wavelength-filter-input",
                    classes="form-input"
                )
                yield Static("Filter by wavelength", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Static("Optical fiber:", classes="form-label")
                yield Input(
                    placeholder="Leave empty for all",
                    id="fiber-filter-input",
                    classes="form-input"
                )
                yield Static("Filter by fiber name", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Static("Date:", classes="form-label")
                yield Input(
                    placeholder="YYYY-MM-DD",
                    id="date-filter-input",
                    classes="form-input"
                )
                yield Static("Filter by calibration date", classes="form-help")

            # Plot Options Section
            yield Static("─── Plot Options ──────────────────────────", classes="section-title")

            with Horizontal(classes="form-row"):
                yield Static("Power unit:", classes="form-label")
                yield Select(
                    [
                        ("Microwatts (µW)", "uW"),
                        ("Milliwatts (mW)", "mW"),
                        ("Watts (W)", "W"),
                    ],
                    value="uW",
                    id="power-unit-select",
                    classes="form-input"
                )
                yield Static("Y-axis unit", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Checkbox("Group by wavelength", id="group-wavelength-checkbox", value=True)
                yield Static("Color-code curves by wavelength", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Checkbox("Show markers", id="show-markers-checkbox", value=False)
                yield Static("Display data point markers", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Checkbox("Comparison mode (subplots)", id="comparison-checkbox", value=False)
                yield Static("One subplot per wavelength", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Static("Output dir:", classes="form-label")
                yield Input(
                    value="figs/laser_calibrations",
                    placeholder="figs/laser_calibrations",
                    id="output-dir-input",
                    classes="form-input"
                )
                yield Static("→ figs/laser_calibrations/", classes="form-help")

            # Buttons
            with Horizontal(id="button-container"):
                yield Button("Save Config", id="save-button", variant="default", classes="nav-button")
                yield Button("← Back", id="back-button", variant="default", classes="nav-button")
                yield Button("Next: Select Calibrations →", id="next-button", variant="primary", classes="nav-button")

    def on_mount(self) -> None:
        """Initialize screen."""
        self.query_one("#wavelength-filter-input", Input).focus()

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

        # Validate configuration
        validation_error = self._validate_config(config)
        if validation_error:
            self.notify(validation_error, severity="error", timeout=5)
            return

        # Save to session
        for key, value in config.items():
            if hasattr(self.app.session, key):
                setattr(self.app.session, key, value)

        # Navigate to experiment selector
        # NOTE: Experiment selector needs to handle LaserCalibration specially
        self.app.router.go_to_experiment_selector()

    def action_save_config(self) -> None:
        """Save configuration to JSON file."""
        config = self._collect_config()

        # Validate
        validation_error = self._validate_config(config)
        if validation_error:
            self.notify(validation_error, severity="error", timeout=5)
            return

        # Save to ConfigManager
        config_to_save = {
            **config,
            "plot_type": "LaserCalibration",
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

    def _validate_config(self, config: dict) -> str | None:
        """Validate configuration values."""
        # Validate date format
        date_filter = config.get("date_filter")
        if date_filter:
            import re
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_filter):
                return "Date must be in YYYY-MM-DD format"

        # Validate wavelength (must be numeric)
        wavelength = config.get("wavelength_filter")
        if wavelength:
            try:
                float(wavelength)
            except ValueError:
                return "Wavelength must be a number"

        return None

    def _collect_config(self) -> dict:
        """Collect all configuration values from the form."""
        config = {
            "selection_mode": "interactive",  # Always interactive for now
            "plot_type": "LaserCalibration",
        }

        # Filters
        wavelength_str = self.query_one("#wavelength-filter-input", Input).value.strip()
        config["wavelength_filter"] = wavelength_str if wavelength_str else None

        fiber_str = self.query_one("#fiber-filter-input", Input).value.strip()
        config["fiber_filter"] = fiber_str if fiber_str else None

        date_str = self.query_one("#date-filter-input", Input).value.strip()
        config["date_filter"] = date_str if date_str else None

        # Plot options
        config["power_unit"] = self.query_one("#power-unit-select", Select).value
        config["group_by_wavelength"] = self.query_one("#group-wavelength-checkbox", Checkbox).value
        config["show_markers"] = self.query_one("#show-markers-checkbox", Checkbox).value
        config["comparison"] = self.query_one("#comparison-checkbox", Checkbox).value

        output_dir = self.query_one("#output-dir-input", Input).value.strip()
        config["output_dir"] = output_dir if output_dir else "figs/laser_calibrations"

        return config
