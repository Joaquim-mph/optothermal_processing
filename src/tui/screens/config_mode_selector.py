"""
Configuration Mode Selector Screen.

Step 3 of the wizard: Choose between Quick Plot (smart defaults) or Custom Plot (full configuration).

Quick mode uses sensible defaults and goes straight to experiment selection.
Custom mode allows detailed configuration of all plotting parameters.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, RadioButton, RadioSet
from textual.binding import Binding

from src.tui.screens.experiment_selector import ExperimentSelectorScreen
from src.tui.screens.its_preset_selector import ITSPresetSelectorScreen
from src.tui.screens.ivg_config import IVgConfigScreen
from src.tui.screens.transconductance_config import TransconductanceConfigScreen


class ConfigModeSelectorScreen(Screen):
    """Configuration mode selection screen (Step 3 of wizard)."""

    def __init__(self, chip_number: int = 0, chip_group: str = "", plot_type: str = ""):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type

    BINDINGS = [
        Binding("escape", "back", "Back", priority=True),
        Binding("ctrl+b", "back", "Back", show=False),
        Binding("enter", "next", "Next", priority=True),
        Binding("space", "toggle_selection", "Select", show=False),
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
    ]

    CSS = """
    ConfigModeSelectorScreen {
        align: center middle;
    }

    #main-container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }

    #header-container {
        width: 100%;
        height: auto;
        margin-bottom: 2;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
    }

    #chip-plot-info {
        width: 100%;
        content-align: center middle;
        color: $accent;
        margin-bottom: 1;
    }

    #step-indicator {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    RadioSet {
        width: 100%;
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: $panel;
    }

    RadioButton {
        margin: 1 0;
    }

    .mode-description {
        width: 100%;
        color: $text-muted;
        margin: 0 2 1 2;
        padding: 1;
        background: $panel-lighten-1;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
    }

    .nav-button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Create configuration mode selector widgets."""
        yield Header()

        with Container(id="main-container"):
            with Vertical(id="header-container"):
                yield Static("Configuration Mode", id="title")
                if self.chip_number and self.chip_group and self.plot_type:
                    yield Static(
                        f"[bold]{self.chip_group}{self.chip_number}[/bold] - {self.plot_type}",
                        id="chip-plot-info"
                    )
                yield Static("[Step 3/6]", id="step-indicator")

            with RadioSet(id="mode-radio"):
                yield RadioButton("Quick Plot", id="quick-radio")
                yield RadioButton("Custom Plot", id="custom-radio")

            # Descriptions below radio buttons
            yield Static(
                "[bold]Quick Plot[/bold]\n"
                "Use smart defaults, just select experiments interactively. "
                "Best for routine plotting.",
                classes="mode-description"
            )
            yield Static(
                "[bold]Custom Plot[/bold]\n"
                "Configure all parameters: filters, baseline, legend style, etc. "
                "For specialized analysis.",
                classes="mode-description"
            )

            with Vertical(id="button-container"):
                yield Button("← Back", id="back-button", variant="default", classes="nav-button")
                yield Button("Next →", id="next-button", variant="primary", classes="nav-button")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen - focus the radio set."""
        self.query_one(RadioSet).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()

    def action_back(self) -> None:
        """Go back to plot type selector."""
        self.app.pop_screen()

    def action_toggle_selection(self) -> None:
        """Toggle the currently focused radio button with Space key."""
        focused = self.focused
        radio_set = self.query_one(RadioSet)

        # If focused on RadioSet or a RadioButton, toggle it
        if focused == radio_set or (hasattr(focused, 'parent') and focused.parent == radio_set):
            radio_set.action_toggle_button()

    def action_next(self) -> None:
        """Select highlighted option and proceed to next screen."""
        radio_set = self.query_one(RadioSet)
        focused = self.focused

        # Find which RadioButton is currently focused/highlighted
        highlighted_button = None

        # Check if a RadioButton is directly focused
        if isinstance(focused, RadioButton):
            highlighted_button = focused
        # If RadioSet is focused, find the one with -selected class
        elif focused == radio_set:
            radio_buttons = list(self.query(RadioButton).results(RadioButton))
            for button in radio_buttons:
                if button.has_class("-selected"):
                    highlighted_button = button
                    break

        # If we found a highlighted button, make sure it's selected
        if highlighted_button:
            # Toggle it if it's not already the pressed button
            if radio_set.pressed_button != highlighted_button:
                highlighted_button.toggle()
            selected = highlighted_button
        else:
            # Fall back to whatever is already selected
            selected = radio_set.pressed_button

        # Validate selection
        if selected is None:
            self.app.notify("Please select a configuration mode", severity="warning")
            return

        # Map radio button to mode
        mode_map = {
            "quick-radio": "quick",
            "custom-radio": "custom",
        }

        mode = mode_map.get(selected.id)

        if mode is None:
            self.app.notify("Invalid mode selected", severity="error")
            return

        # Save mode to app state
        self.app.update_config(mode=mode)

        # Navigate to next screen
        if mode == "quick":
            # Go to experiment selector (interactive selection)
            self.app.push_screen(ExperimentSelectorScreen(
                chip_number=self.chip_number,
                chip_group=self.chip_group,
                plot_type=self.plot_type,
                history_dir=self.app.history_dir,
            ))
        else:
            # Go to custom config screen for the plot type
            if self.plot_type == "ITS":
                # For ITS, go to preset selector first
                self.app.push_screen(ITSPresetSelectorScreen(
                    chip_number=self.chip_number,
                    chip_group=self.chip_group,
                ))
            elif self.plot_type == "IVg":
                self.app.push_screen(IVgConfigScreen(
                    chip_number=self.chip_number,
                    chip_group=self.chip_group,
                    plot_type=self.plot_type,
                    history_dir=self.app.history_dir,
                ))
            elif self.plot_type == "Transconductance":
                self.app.push_screen(TransconductanceConfigScreen(
                    chip_number=self.chip_number,
                    chip_group=self.chip_group,
                    plot_type=self.plot_type,
                    history_dir=self.app.history_dir,
                ))
            else:
                self.app.notify(f"Unknown plot type: {self.plot_type}", severity="error")
