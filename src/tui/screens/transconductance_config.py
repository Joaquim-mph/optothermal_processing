"""Transconductance custom configuration screen (Step 4b - Custom mode)."""

from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static, Input, RadioSet, RadioButton, Select
from textual.containers import Vertical, Horizontal
from textual import events


class TransconductanceConfigScreen(Screen):
    """Transconductance custom configuration screen.

    Allows user to customize:
    - Selection mode (Interactive/Auto/Manual)
    - Calculation method (Gradient/Savitzky-Golay)
    - Savgol parameters (window_length, polyorder, min_segment_length)
    - Filters (VDS, date)
    - Output directory
    """

    CSS = """
    TransconductanceConfigScreen {
        background: $surface;
        padding: 1 2;
    }

    #title {
        width: 100%;
        text-align: center;
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    .section-title {
        width: 100%;
        text-align: center;
        color: $primary;
        margin: 1 0;
    }

    .field-label {
        width: 30;
        text-align: right;
        margin-right: 2;
    }

    .field-container {
        height: auto;
        margin-bottom: 1;
    }

    .nav-button {
        margin: 0 1;
    }

    .nav-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }

    #button-container {
        dock: bottom;
        height: auto;
        align: center middle;
        padding: 1 0;
    }

    .help-text {
        color: $text-muted;
        margin-left: 32;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        plot_type: str,
        metadata_dir: Path,
        raw_dir: Path,
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.metadata_dir = metadata_dir
        self.raw_dir = raw_dir

    def compose(self) -> ComposeResult:
        """Compose the configuration form."""
        yield Static("Custom Configuration - Transconductance", id="title")

        # Selection Mode Section
        yield Static("─── Selection Mode ───", classes="section-title")
        with Vertical(classes="field-container"):
            yield Static("How to select experiments:", classes="field-label")
            with RadioSet(id="selection-mode-radio"):
                yield RadioButton("Interactive (recommended)", id="interactive-radio", value=True)
                yield RadioButton("Auto (all experiments)", id="auto-radio")
                yield RadioButton("Manual (enter indices)", id="manual-radio")

        # Manual indices input (initially hidden)
        with Horizontal(classes="field-container", id="manual-indices-container"):
            yield Static("Experiment indices:", classes="field-label")
            yield Input(
                placeholder="e.g., 0,2,5-8",
                id="manual-indices-input",
            )

        # Calculation Method Section
        yield Static("─── Calculation Method ───", classes="section-title")
        with Vertical(classes="field-container"):
            yield Static("Method:", classes="field-label")
            with RadioSet(id="method-radio"):
                yield RadioButton("Gradient (default)", id="gradient-radio", value=True)
                yield RadioButton("Savitzky-Golay filtering", id="savgol-radio")
        yield Static("Gradient: Simple numerical derivative (dI/dVg)", classes="help-text")
        yield Static("Savgol: Smooth derivative using polynomial fitting", classes="help-text")

        # Savgol Parameters Section (initially hidden)
        yield Static("─── Savitzky-Golay Parameters ───", classes="section-title", id="savgol-title")

        with Horizontal(classes="field-container", id="window-length-container"):
            yield Static("Window length:", classes="field-label")
            yield Input(
                placeholder="Default: 9 (must be odd)",
                value="9",
                id="window-length-input",
            )
        yield Static("Number of data points in the smoothing window (must be odd)", classes="help-text", id="window-help")

        with Horizontal(classes="field-container", id="polyorder-container"):
            yield Static("Polynomial order:", classes="field-label")
            yield Input(
                placeholder="Default: 3",
                value="3",
                id="polyorder-input",
            )
        yield Static("Order of polynomial used for fitting (< window_length)", classes="help-text", id="poly-help")

        with Horizontal(classes="field-container", id="min-segment-container"):
            yield Static("Min segment length:", classes="field-label")
            yield Input(
                placeholder="Default: 10",
                value="10",
                id="min-segment-input",
            )
        yield Static("Minimum number of points in a sweep segment", classes="help-text", id="segment-help")

        # Filters Section
        yield Static("─── Filters (Optional) ───", classes="section-title")

        with Horizontal(classes="field-container"):
            yield Static("VDS filter (V):", classes="field-label")
            yield Input(
                placeholder="Leave empty for all, or e.g., 0.1",
                id="vds-filter-input",
            )

        with Horizontal(classes="field-container"):
            yield Static("Date filter:", classes="field-label")
            yield Input(
                placeholder="Leave empty for all, or YYYY-MM-DD",
                id="date-filter-input",
            )

        # Plot Options Section
        yield Static("─── Plot Options ───", classes="section-title")

        with Horizontal(classes="field-container"):
            yield Static("Output directory:", classes="field-label")
            yield Input(
                placeholder="figs",
                value="figs",
                id="output-dir-input",
            )
            yield Static(f"→ figs/{self.chip_group}{self.chip_number}/", classes="field-label")

        # Buttons
        with Horizontal(id="button-container"):
            yield Button("Save Config", id="save-button", variant="default", classes="nav-button")
            yield Button("← Back", variant="default", id="back-button", classes="nav-button")
            yield Button("Next →", variant="default", id="next-button", classes="nav-button")

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
        self.query_one("#window-help").display = False
        self.query_one("#polyorder-container").display = False
        self.query_one("#poly-help").display = False
        self.query_one("#min-segment-container").display = False
        self.query_one("#segment-help").display = False

    def _show_savgol_params(self) -> None:
        """Show Savgol parameter inputs."""
        self.query_one("#savgol-title").display = True
        self.query_one("#window-length-container").display = True
        self.query_one("#window-help").display = True
        self.query_one("#polyorder-container").display = True
        self.query_one("#poly-help").display = True
        self.query_one("#min-segment-container").display = True
        self.query_one("#segment-help").display = True

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

    def on_button_focus(self, event) -> None:
        """Add arrow indicator to focused button."""
        # Remove arrows from all buttons
        for button in self.query(".nav-button"):
            if button.label.startswith("→ ") or button.label.startswith("← "):
                # Remove first 2 characters (arrow + space)
                button.label = button.label[2:]

        # Add arrow to focused button
        if event.button.id == "back-button":
            if not event.button.label.startswith("← "):
                event.button.label = f"← {event.button.label}"
        elif event.button.id == "next-button":
            if not event.button.label.startswith("→ "):
                event.button.label = f"→ {event.button.label}"

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

    def action_back(self) -> None:
        """Go back to config mode selector."""
        self.app.pop_screen()

    def action_next(self) -> None:
        """Proceed to experiment selection or preview."""
        config = self._collect_config()

        # Validate Savgol parameters if using savgol method
        if config.get("method") == "savgol":
            validation_error = self._validate_savgol_params(config)
            if validation_error:
                self.notify(validation_error, severity="error", timeout=5)
                return

        # Determine selection mode
        selection_mode_radio = self.query_one("#selection-mode-radio", RadioSet)

        if selection_mode_radio.pressed_button.id == "interactive-radio":
            # Go to interactive experiment selector
            from src.tui.screens.experiment_selector import ExperimentSelectorScreen
            self.app.push_screen(
                ExperimentSelectorScreen(
                    chip_number=self.chip_number,
                    chip_group=self.chip_group,
                    plot_type=self.plot_type,
                    metadata_dir=self.metadata_dir,
                    raw_dir=self.raw_dir,
                    config=config,
                )
            )
        else:
            # Go directly to preview (Auto or Manual mode)
            from src.tui.screens.preview_screen import PreviewScreen
            self.app.push_screen(
                PreviewScreen(
                    chip_number=self.chip_number,
                    chip_group=self.chip_group,
                    plot_type=self.plot_type,
                    seq_numbers=[],  # TODO: Auto-select based on filters
                    config=config,
                    metadata_dir=self.metadata_dir,
                    raw_dir=self.raw_dir,
                )
            )

    def _validate_savgol_params(self, config: dict) -> str | None:
        """Validate Savitzky-Golay parameters.

        Returns error message if validation fails, None if OK.
        """
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
