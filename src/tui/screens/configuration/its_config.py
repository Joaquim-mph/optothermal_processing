"""
ITS Configuration Screen (Custom Mode).

Step 4b of the wizard: Configure parameters for ITS (Current vs Time) plots.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static, Button, Input, Select, Label, Checkbox
from textual.binding import Binding

from src.tui.screens.base import FormScreen


class ITSConfigScreen(FormScreen):
    """ITS configuration screen (Step 4b - Custom mode or Step 5 - Preset mode)."""

    SCREEN_TITLE = "Custom Configuration - ITS"
    STEP_NUMBER = 4

    def __init__(self, chip_number: int, chip_group: str, plot_type: str = "ITS", preset_mode: bool = False):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.preset_mode = preset_mode  # True if using a preset (show read-only summary)

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
        """Compose header with title, chip info, and step indicator."""
        if self.preset_mode:
            # Get preset from session
            preset_name = self.app.session.preset or "custom"
            from src.plotting.its_presets import get_preset
            preset = get_preset(preset_name)

            yield Static(f"Preset Configuration - {preset.name if preset else 'ITS'}", id="title")
            yield Static(
                f"[bold]{self.chip_group}{self.chip_number}[/bold] - {self.plot_type}",
                id="chip-info"
            )
            yield Static("[Step 5/8]", id="step-indicator")

            # Show compact preset summary
            if preset:
                yield Static(
                    f"✓ [bold]{preset.name}[/bold] - {preset.description}",
                    classes="section-title"
                )
        else:
            yield Static(self.SCREEN_TITLE, id="title")
            yield Static(
                f"[bold]{self.chip_group}{self.chip_number}[/bold] - {self.plot_type}",
                id="chip-info"
            )
            yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose ITS configuration form content."""
        with VerticalScroll(id="content-scroll"):
            # Plot Options Section (show for both preset and custom mode)
            yield Static("─── Plot Options ──────────────────────", classes="section-title")

            # Get preset values if in preset mode to use as defaults
            if self.preset_mode:
                preset_name = self.app.session.preset or "custom"
                from src.plotting.its_presets import get_preset
                preset = get_preset(preset_name)
                # Use preset values as defaults
                default_legend = preset.legend_by if preset else "wavelength"
                # For baseline: if none mode, show 0; if auto, show empty (will be calculated); if fixed, show value
                if preset:
                    if preset.baseline_mode == "none":
                        default_baseline = "0"
                    elif preset.baseline_mode == "auto":
                        default_baseline = ""  # Empty means auto-calculate
                    else:  # fixed
                        default_baseline = str(preset.baseline_value) if preset.baseline_value else "60.0"
                else:
                    default_baseline = "60.0"
                default_padding = str(preset.padding) if preset else "0.05"
            else:
                # Use standard defaults for custom mode
                default_legend = "vg"
                default_baseline = "60.0"
                default_padding = "0.05"

            with Horizontal(classes="form-row"):
                yield Label("Legend by:", classes="form-label")
                yield Select(
                    [
                        ("Gate Voltage (Vg)", "vg"),
                        ("LED Voltage", "led_voltage"),
                        ("Wavelength", "wavelength"),
                    ],
                    value=default_legend,
                    id="legend-by-select",
                    classes="form-input"
                )
                yield Static("Legend grouping", classes="form-help")

            # Baseline correction checkbox and input
            with Horizontal(classes="form-row"):
                yield Checkbox("Apply baseline correction", id="baseline-enabled", value=True)

            with Horizontal(classes="form-row"):
                yield Label("Baseline (s):", classes="form-label")
                yield Input(
                    value=default_baseline,
                    placeholder="Empty = auto, 0 = none",
                    id="baseline-input",
                    classes="form-input"
                )
                yield Static("Empty=auto, 0=none, or value in seconds", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Label("Padding:", classes="form-label")
                yield Input(value=default_padding, id="padding-input", classes="form-input")
                yield Static("Y-axis padding", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Label("Output dir:", classes="form-label")
                yield Input(
                    value="figs",
                    placeholder="figs",
                    id="output-dir-input",
                    classes="form-input"
                )
                yield Static(f"→ figs/{self.chip_group}{self.chip_number}/", classes="form-help")

            # Buttons
            with Horizontal(id="button-container"):
                if not self.preset_mode:
                    yield Button("Save Config", id="save-button", variant="default", classes="nav-button")
                yield Button("← Back", id="back-button", variant="default", classes="nav-button")
                if self.preset_mode:
                    yield Button("Change Preset", id="change-preset-button", variant="default", classes="nav-button")
                yield Button("Next: Select Experiments →", id="next-button", variant="primary", classes="nav-button")

    def on_mount(self) -> None:
        """Initialize screen."""
        # Focus the first input field (legend select)
        self.query_one("#legend-by-select", Select).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox state changes."""
        if event.checkbox.id == "baseline-enabled":
            # Enable/disable baseline input based on checkbox state
            baseline_input = self.query_one("#baseline-input", Input)
            baseline_input.disabled = not event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()
        elif event.button.id == "save-button":
            self.action_save_config()
        elif event.button.id == "change-preset-button":
            # Go back to preset selector
            self.app.pop_screen()

    def action_next(self) -> None:
        """Collect configuration and proceed to next step."""
        # Collect all form values
        config = self._collect_config()

        # Validate configuration
        validation_error = self._validate_config(config)
        if validation_error:
            self.notify(validation_error, severity="error", timeout=5)
            return

        # Save to session (replaces app.update_config)
        for key, value in config.items():
            if hasattr(self.app.session, key):
                setattr(self.app.session, key, value)

        # Navigate to experiment selector using router
        self.app.router.go_to_experiment_selector()

    def action_save_config(self) -> None:
        """Save configuration to JSON file."""
        config = self._collect_config()

        # Validate configuration first
        validation_error = self._validate_config(config)
        if validation_error:
            self.notify(validation_error, severity="error", timeout=5)
            return

        # Add chip info to config
        config_to_save = {
            **config,
            "chip_number": self.chip_number,
            "chip_group": self.chip_group,
            "plot_type": self.plot_type,
        }

        # Save to ConfigManager
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
        """Validate configuration values.

        Returns error message if validation fails, None if OK.
        """
        # Validate baseline (must be positive or zero for "none" mode)
        baseline = config.get("baseline")
        if baseline is not None and baseline < 0:
            return "Baseline must be a positive number or zero"

        # Validate padding (must be between 0 and 1)
        padding = config.get("padding")
        if padding is not None and (padding < 0 or padding > 1):
            return "Padding must be between 0 and 1"

        return None

    def _collect_config(self) -> dict:
        """Collect all configuration values from the form."""
        # Get plot options from form (now shown for both preset and custom mode)
        legend_by = self.query_one("#legend-by-select", Select).value
        baseline_enabled = self.query_one("#baseline-enabled", Checkbox).value
        baseline_input = self.query_one("#baseline-input", Input).value.strip()
        padding = self.query_one("#padding-input", Input).value.strip()
        output_dir = self.query_one("#output-dir-input", Input).value.strip()

        # Check if baseline correction is disabled
        if not baseline_enabled:
            # Force baseline_mode to "none" when checkbox is unchecked
            baseline_mode = "none"
            baseline = None
            # Get preset defaults for other parameters
            if self.preset_mode:
                preset_name = self.app.session.preset or "custom"
                from src.plotting.its_presets import get_preset
                preset = get_preset(preset_name)
                if preset:
                    baseline_auto_divisor = preset.baseline_auto_divisor
                    plot_start_time = preset.plot_start_time
                    check_duration_mismatch = preset.check_duration_mismatch
                    duration_tolerance = preset.duration_tolerance
                else:
                    baseline_auto_divisor = 2.0
                    plot_start_time = 20.0
                    check_duration_mismatch = False
                    duration_tolerance = 0.10
            else:
                baseline_auto_divisor = 2.0
                plot_start_time = 20.0
                check_duration_mismatch = False
                duration_tolerance = 0.10
        # Get preset defaults if in preset mode
        elif self.preset_mode:
            preset_name = self.app.session.preset or "custom"
            from src.plotting.its_presets import get_preset
            preset = get_preset(preset_name)

            if preset:
                # Inherit preset parameters (can be overridden by user edits)
                baseline_auto_divisor = preset.baseline_auto_divisor
                plot_start_time = preset.plot_start_time
                check_duration_mismatch = preset.check_duration_mismatch
                duration_tolerance = preset.duration_tolerance

                # Determine baseline mode from user input
                if baseline_input == "" or baseline_input is None:
                    # Empty = auto mode
                    baseline_mode = "auto"
                    baseline = None
                else:
                    # Numeric value = fixed mode (including 0)
                    baseline_mode = "fixed"
                    baseline = baseline_input
            else:
                # Fallback defaults
                baseline = baseline_input
                baseline_mode = "fixed"
                baseline_auto_divisor = 2.0
                plot_start_time = 20.0
                check_duration_mismatch = False
                duration_tolerance = 0.10
        else:
            # Custom mode: always use fixed baseline
            baseline = baseline_input
            baseline_mode = "fixed"
            baseline_auto_divisor = 2.0
            plot_start_time = 20.0
            check_duration_mismatch = False
            duration_tolerance = 0.10

        # Build config dict with type conversion and error handling
        config = {
            "selection_mode": "interactive",  # Always interactive (experiment selector handles this)
            "legend_by": legend_by,
            "output_dir": output_dir,
        }

        # Convert numeric values with error handling
        try:
            # Check for empty string specifically (not just falsy, since 0.0 is valid)
            if baseline == "" or baseline is None:
                config["baseline"] = None  # Will be auto-calculated
            else:
                config["baseline"] = float(baseline)
        except ValueError:
            config["baseline"] = 60.0

        try:
            config["padding"] = float(padding) if padding else 0.05
        except ValueError:
            config["padding"] = 0.05

        # Add preset-specific parameters
        config["baseline_mode"] = baseline_mode
        config["baseline_auto_divisor"] = baseline_auto_divisor
        config["plot_start_time"] = plot_start_time
        config["check_duration_mismatch"] = check_duration_mismatch
        config["duration_tolerance"] = duration_tolerance

        return config
