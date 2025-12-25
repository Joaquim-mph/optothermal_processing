"""Transconductance custom configuration screen (Step 4b - Custom mode)."""

from pathlib import Path
from textual.app import ComposeResult
from textual.widgets import Button, Static, Input, RadioSet, RadioButton
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.binding import Binding
from textual import events

from src.tui.screens.base import FormScreen


class TransconductanceConfigScreen(FormScreen):
    """Transconductance custom configuration screen.

    Allows user to customize:
    - Selection mode (Interactive/Auto/Manual)
    - Calculation method (Gradient/Savitzky-Golay)
    - Savgol parameters (window_length, polyorder, min_segment_length)
    - Filters (VDS, date)
    - Output directory
    """

    SCREEN_TITLE = "Custom Configuration - Transconductance"
    STEP_NUMBER = 4

    BINDINGS = FormScreen.BINDINGS + [
        Binding("ctrl+s", "save_config", "Save Config", show=False),
    ]

    # Transconductance-specific CSS (extends FormScreen CSS)
    CSS = FormScreen.CSS + """
    #content-scroll {
        width: 100%;
        height: 1fr;
        min-height: 20;
    }

    #manual-indices-container,
    #window-length-container,
    #polyorder-container,
    #min-segment-container {
        height: auto;
        margin-bottom: 1;
    }

    .field-container {
        height: auto;
        margin-bottom: 1;
    }

    .help-text {
        color: $text-muted;
        margin-left: 2;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        plot_type: str = "Transconductance",
        history_dir: Path = Path("data/02_stage/chip_histories"),
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.history_dir = history_dir

    def compose_header(self) -> ComposeResult:
        """Compose header with title, chip info, and step indicator."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static(
            f"[bold]{self.chip_group}{self.chip_number}[/bold] - {self.plot_type}",
            id="chip-info"
        )
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose the configuration form."""
        with VerticalScroll(id="content-scroll"):
            # Selection Mode Section
            yield Static("─── Selection Mode ───", classes="section-title")
            with Vertical(classes="field-container"):
                yield Static("How to select experiments:")
                with RadioSet(id="selection-mode-radio"):
                    yield RadioButton("Interactive (recommended)", id="interactive-radio", value=True)
                    yield RadioButton("Auto (all experiments)", id="auto-radio")
                    yield RadioButton("Manual (enter indices)", id="manual-radio")

            # Manual indices input (initially hidden)
            with Horizontal(classes="form-row", id="manual-indices-container"):
                yield Static("Experiment indices:")
                yield Input(
                    placeholder="e.g., 0,2,5-8",
                    id="manual-indices-input",
                    classes="form-input"
                )

            # Calculation Method Section
            yield Static("─── Calculation Method ───", classes="section-title")
            with Vertical(classes="field-container"):
                yield Static("Method:")
                with RadioSet(id="method-radio"):
                    yield RadioButton("Gradient (default)", id="gradient-radio", value=True)
                    yield RadioButton("Savitzky-Golay filtering", id="savgol-radio")
            yield Static("Gradient: Simple numerical derivative (dI/dVg)", classes="help-text")
            yield Static("Savgol: Smooth derivative using polynomial fitting", classes="help-text")

            # Savgol Parameters Section (initially hidden)
            yield Static("─── Savitzky-Golay Parameters ───", classes="section-title", id="savgol-title")

            with Horizontal(classes="form-row", id="window-length-container"):
                yield Static("Window length:", classes="form-label")
                yield Input(
                    placeholder="Default: 9 (must be odd)",
                    value="9",
                    id="window-length-input",
                    classes="form-input"
                )
                yield Static("# of data points in smoothing window (odd)", classes="form-help")

            with Horizontal(classes="form-row", id="polyorder-container"):
                yield Static("Polynomial order:", classes="form-label")
                yield Input(
                    placeholder="Default: 3",
                    value="3",
                    id="polyorder-input",
                    classes="form-input"
                )
                yield Static("Order of polynomial (< window_length)", classes="form-help")

            with Horizontal(classes="form-row", id="min-segment-container"):
                yield Static("Min segment length:", classes="form-label")
                yield Input(
                    placeholder="Default: 10",
                    value="10",
                    id="min-segment-input",
                    classes="form-input"
                )
                yield Static("Minimum points in a sweep segment", classes="form-help")

            # Filters Section
            yield Static("─── Filters (Optional) ───", classes="section-title")

            with Horizontal(classes="form-row"):
                yield Static("VDS filter (V):", classes="form-label")
                yield Input(
                    placeholder="Leave empty for all, or e.g., 0.1",
                    id="vds-filter-input",
                    classes="form-input"
                )
                yield Static("Filter by drain-source voltage", classes="form-help")

            with Horizontal(classes="form-row"):
                yield Static("Date filter:", classes="form-label")
                yield Input(
                    placeholder="Leave empty for all, or YYYY-MM-DD",
                    id="date-filter-input",
                    classes="form-input"
                )
                yield Static("Filter by experiment date", classes="form-help")

            # Plot Options Section
            yield Static("─── Plot Options ───", classes="section-title")

            with Horizontal(classes="form-row"):
                yield Static("Output directory:", classes="form-label")
                yield Input(
                    placeholder="figs",
                    value="figs",
                    id="output-dir-input",
                    classes="form-input"
                )
                yield Static(f"→ figs/{self.chip_group}{self.chip_number}/", classes="form-help")

            # Buttons
            with Horizontal(id="button-container"):
                yield Button("Save Config", id="save-button", variant="default", classes="nav-button")
                yield Button("← Back", variant="default", id="back-button", classes="nav-button")
                yield Button("Next →", variant="primary", id="next-button", classes="nav-button")

    def on_mount(self) -> None:
        """Initialize the screen after mounting."""
        # Hide manual indices input initially
        manual_container = self.query_one("#manual-indices-container")
        manual_container.display = False

        # Hide Savgol parameters initially (gradient is default)
        self._hide_savgol_params()

        # Focus the first radio button
        self.query_one("#interactive-radio").focus()

    def _hide_savgol_params(self) -> None:
        """Hide Savgol parameter inputs."""
        self.query_one("#savgol-title").display = False
        self.query_one("#window-length-container").display = False
        self.query_one("#polyorder-container").display = False
        self.query_one("#min-segment-container").display = False

    def _show_savgol_params(self) -> None:
        """Show Savgol parameter inputs."""
        self.query_one("#savgol-title").display = True
        self.query_one("#window-length-container").display = True
        self.query_one("#polyorder-container").display = True
        self.query_one("#min-segment-container").display = True

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Show/hide conditional inputs based on radio selections."""
        # Handle selection mode radio
        if event.radio_set.id == "selection-mode-radio":
            manual_container = self.query_one("#manual-indices-container")
            if event.pressed.id == "manual-radio":
                manual_container.display = True
            else:
                manual_container.display = False

        # Handle method radio
        elif event.radio_set.id == "method-radio":
            if event.pressed.id == "savgol-radio":
                self._show_savgol_params()
            else:
                self._hide_savgol_params()

    def on_key(self, event: events.Key) -> None:
        """Handle arrow key navigation between buttons."""
        buttons = [
            self.query_one("#save-button", Button),
            self.query_one("#back-button", Button),
            self.query_one("#next-button", Button),
        ]

        focused_idx = next((i for i, b in enumerate(buttons) if b.has_focus), None)

        if focused_idx is not None:
            if event.key in ("left", "up"):
                new_idx = (focused_idx - 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()
            elif event.key in ("right", "down"):
                new_idx = (focused_idx + 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()
        elif event.button.id == "save-button":
            self.action_save_config()

    def action_save_config(self) -> None:
        """Save configuration for later reuse."""
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

    def action_next(self) -> None:
        """Proceed to experiment selection or preview."""
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

        # Determine selection mode
        selection_mode_radio = self.query_one("#selection-mode-radio", RadioSet)

        if selection_mode_radio.pressed_button.id == "interactive-radio":
            # Go to interactive experiment selector using router
            self.app.router.go_to_experiment_selector()
        else:
            # Go directly to preview (Auto or Manual mode)
            # TODO: Implement auto-select based on filters
            self.app.notify("Auto/Manual mode not yet implemented", severity="warning")
            # For now, still go to interactive selector
            self.app.router.go_to_experiment_selector()

    def _validate_config(self, config: dict) -> str | None:
        """Validate configuration values.

        Returns error message if validation fails, None if OK.
        """
        # Validate Savgol parameters if using savgol method
        if config.get("method") == "savgol":
            window_length = config.get("window_length")
            polyorder = config.get("polyorder")
            min_segment_length = config.get("min_segment_length")

            # Window length must be odd and positive
            if window_length is not None:
                if window_length % 2 == 0:
                    return "Window length must be an odd number"
                if window_length < 3:
                    return "Window length must be at least 3"

            # Polyorder must be positive and less than window_length
            if polyorder is not None:
                if polyorder < 1:
                    return "Polynomial order must be at least 1"
                if window_length is not None and polyorder >= window_length:
                    return f"Polynomial order ({polyorder}) must be less than window length ({window_length})"

            # Min segment length must be positive
            if min_segment_length is not None and min_segment_length < 1:
                return "Minimum segment length must be at least 1"

        # Date format validation
        date_filter = config.get("date_filter")
        if date_filter:
            import re
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_filter):
                return "Date must be in YYYY-MM-DD format"

        # Manual indices validation
        if config.get("selection_mode") == "manual":
            manual_indices = config.get("manual_indices")
            if not manual_indices:
                return "Manual mode requires experiment indices (e.g., 0,2,5-8)"

        return None

    def _collect_config(self) -> dict:
        """Collect all configuration values into a dict."""
        config = {
            "plot_type": self.plot_type,
            "chip_number": self.chip_number,
            "chip_group": self.chip_group,
        }

        # Selection mode
        selection_mode_radio = self.query_one("#selection-mode-radio", RadioSet)
        if selection_mode_radio.pressed_button.id == "interactive-radio":
            config["selection_mode"] = "interactive"
        elif selection_mode_radio.pressed_button.id == "auto-radio":
            config["selection_mode"] = "auto"
        else:
            config["selection_mode"] = "manual"
            # Get manual indices
            manual_indices = self.query_one("#manual-indices-input", Input).value.strip()
            config["manual_indices"] = manual_indices if manual_indices else None

        # Calculation method with error handling
        method_radio = self.query_one("#method-radio", RadioSet)
        if method_radio.pressed_button.id == "gradient-radio":
            config["method"] = "gradient"
        else:
            config["method"] = "savgol"
            # Get Savgol parameters with error handling
            window_str = self.query_one("#window-length-input", Input).value.strip()
            try:
                config["window_length"] = int(window_str) if window_str else 9
            except ValueError:
                config["window_length"] = 9

            poly_str = self.query_one("#polyorder-input", Input).value.strip()
            try:
                config["polyorder"] = int(poly_str) if poly_str else 3
            except ValueError:
                config["polyorder"] = 3

            min_seg_str = self.query_one("#min-segment-input", Input).value.strip()
            try:
                config["min_segment_length"] = int(min_seg_str) if min_seg_str else 10
            except ValueError:
                config["min_segment_length"] = 10

        # VDS filter with error handling
        vds_str = self.query_one("#vds-filter-input", Input).value.strip()
        try:
            config["vds_filter"] = float(vds_str) if vds_str else None
        except ValueError:
            config["vds_filter"] = None

        # Date filter
        date_str = self.query_one("#date-filter-input", Input).value.strip()
        config["date_filter"] = date_str if date_str else None

        # Output directory
        output_dir = self.query_one("#output-dir-input", Input).value.strip()
        config["output_dir"] = output_dir if output_dir else "figs/"

        return config
