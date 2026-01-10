"""
Plot Generation Success Screen.

Shows results after successful plot generation.
"""

from __future__ import annotations
from pathlib import Path
import subprocess
import platform

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Button
from textual.binding import Binding
from textual import events

from src.tui.screens.base import SuccessScreen


class PlotSuccessScreen(SuccessScreen):
    """Success screen after plot generation."""

    SCREEN_TITLE = "Plot Generated Successfully! ✓"
    CSS = SuccessScreen.CSS + """
    #button-container {
        layout: grid;
        grid-size: 3;
        grid-gutter: 1 2;
        align: center middle;
    }

    .nav-button {
        height: 3;
        min-height: 3;
    }

    #menu-button {
        column-span: 3;
    }
    """

    def __init__(
        self,
        output_path: Path,
        file_size: float,
        num_experiments: int,
        elapsed: float,
        chip_number: int = None,
        chip_group: str = None,
        plot_type: str = None,
    ):
        super().__init__()
        self.output_path = output_path
        self.file_size = file_size
        self.num_experiments = num_experiments
        self.elapsed = elapsed
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type

    BINDINGS = SuccessScreen.BINDINGS + [
        Binding("enter", "main_menu", "Main Menu", priority=True),
    ]

    def compose_content(self) -> ComposeResult:
        """Compose success screen content."""
        yield Static("Output file:", classes="section-title")
        yield Static(str(self.output_path), classes="info-row")

        yield Static(f"File size: {self.file_size:.1f} MB", classes="info-row")
        yield Static(f"Experiments plotted: {self.num_experiments}", classes="info-row")
        yield Static(f"Generation time: {self.elapsed:.1f}s", classes="info-row")

        yield Static("", classes="info-row")
        yield Static("Configuration saved to recent history.", classes="info-row")

        with Horizontal(id="button-container"):
            yield Button("Open File", id="open-button", variant="default", classes="nav-button")
            yield Button("Browse Plots", id="browse-button", variant="default", classes="nav-button")
            yield Button("Plot Another", id="another-button", variant="default", classes="nav-button")
            yield Button("Main Menu", id="menu-button", variant="default", classes="nav-button")

    def on_mount(self) -> None:
        """Focus the main menu button."""
        self.query_one("#menu-button", Button).focus()

    def on_key(self, event: events.Key) -> None:
        """Handle arrow key navigation between buttons."""
        buttons = [
            self.query_one("#open-button", Button),
            self.query_one("#browse-button", Button),
            self.query_one("#another-button", Button),
            self.query_one("#menu-button", Button),
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
            label = str(button.label)
            if label.startswith("→ "):
                button.label = label[2:]

        # Add arrow to focused button
        focused_button = event.button
        label = str(focused_button.label)
        if not label.startswith("→ "):
            focused_button.label = f"→ {label}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "open-button":
            self.action_open_file()
        elif event.button.id == "browse-button":
            self.action_browse_plots()
        elif event.button.id == "another-button":
            self.action_plot_another()
        elif event.button.id == "menu-button":
            self.action_main_menu()

    def action_open_file(self) -> None:
        """Open the generated file with the default application (cross-platform, non-blocking)."""
        try:
            # Get the appropriate open command for the OS
            if platform.system() == "Darwin":  # macOS
                cmd = ["open", str(self.output_path)]
            elif platform.system() == "Linux":
                cmd = ["xdg-open", str(self.output_path)]
            else:  # Windows
                cmd = ["start", str(self.output_path)]

            # Use Popen for non-blocking execution, suppress output
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.app.notify(f"Opening {self.output_path.name}", severity="information")

        except Exception as e:
            self.app.notify(f"Error opening file: {str(e)}", severity="error")

    def action_browse_plots(self) -> None:
        """Open plot browser to view all existing plots."""
        self.app.router.go_to_plot_browser()

    def action_plot_another(self) -> None:
        """Start a new plot of the same type using router."""
        # If we have the required info, update session and jump to experiment selector
        if self.chip_number and self.chip_group and self.plot_type:
            # Update session state
            self.app.session.chip_number = self.chip_number
            self.app.session.chip_group = self.chip_group
            self.app.session.plot_type = self.plot_type

            # Pop all wizard screens to get back to main menu
            while len(self.app.screen_stack) > 2:
                self.app.pop_screen()

            # Navigate to experiment selector using router
            self.app.router.go_to_experiment_selector()

    def action_main_menu(self) -> None:
        """Return to main menu using router."""
        self.app.router.return_to_main_menu()
