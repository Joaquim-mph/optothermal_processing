"""
Chip Selector Screen.

Step 1 of the wizard: Select which chip to plot from auto-discovered chips.

Auto-discovers chips from chip_histories/ directory and displays them
with experiment counts and procedure breakdowns.
"""

from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Grid
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import SelectorScreen
from src.tui.utils import discover_chips, ChipInfo


class ChipSelectorScreen(SelectorScreen):
    """Chip selection screen with auto-discovery (Step 1 of wizard)."""

    SCREEN_TITLE = "Select Chip"
    STEP_NUMBER = 1

    BINDINGS = SelectorScreen.BINDINGS + [
        Binding("enter", "select_chip", "Select", priority=True),
        Binding("up", "navigate_up", "Up", priority=True),
        Binding("down", "navigate_down", "Down", priority=True),
        Binding("left", "navigate_left", "Left", priority=True),
        Binding("right", "navigate_right", "Right", priority=True),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    # Chip-specific CSS (extends SelectorScreen CSS)
    CSS = SelectorScreen.CSS + """
    #chip-group-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        history_dir: Path,
        chip_group: str,
        mode: str = "plot",
    ):
        super().__init__()
        self.history_dir = history_dir
        self.chip_group = chip_group
        self.chips: list[ChipInfo] = []
        self.selected_chip: ChipInfo | None = None
        self.mode = mode

    def compose_content(self) -> ComposeResult:
        """Compose chip selector content."""
        yield Static("Discovering chips...", id="loading-text")
        yield Static("", id="chip-group-title")

        with Container(id="chip-grid-container"):
            yield Grid(id="chip-grid")

        yield Static("", id="error-text")

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default", classes="nav-button")
            yield Button("Refresh", id="refresh-button", variant="default", classes="nav-button")

    def on_mount(self) -> None:
        """Discover chips when screen loads."""
        self._discover_and_populate()

    def _discover_and_populate(self) -> None:
        """Discover chips and populate the grid."""
        loading = self.query_one("#loading-text", Static)
        error_text = self.query_one("#error-text", Static)
        group_title = self.query_one("#chip-group-title", Static)
        chip_grid = self.query_one("#chip-grid", Grid)

        try:
            # Discover chips
            loading.update("⣾ Scanning chip histories...")
            self.chips = discover_chips(
                self.history_dir,
                self.chip_group
            )

            # Clear loading text
            loading.update("")
            error_text.update("")

            # Remove all existing chip buttons
            chip_grid.remove_children()

            if not self.chips:
                error_text.update(f"⚠ No chips found in {self.history_dir}")
                return

            # Sort chips by chip number in ascending order
            sorted_chips = sorted(self.chips, key=lambda c: c.chip_number)

            # Set group title
            if sorted_chips:
                group_title.update(f"[bold]{sorted_chips[0].chip_group} Group[/bold]")

            # Create chip buttons in grid
            for chip in sorted_chips:
                chip_button = Button(
                    str(chip.chip_number),
                    id=f"chip-{chip.chip_number}",
                    classes="chip-button",
                    variant="default"
                )
                chip_grid.mount(chip_button)

            # Focus the first chip button
            if sorted_chips:
                first_button = self.query_one(f"#chip-{sorted_chips[0].chip_number}", Button)
                first_button.focus()

        except Exception as e:
            loading.update("")
            error_text.update(f"⚠ Error discovering chips: {e}\nHistory dir: {self.history_dir}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "refresh-button":
            self.action_refresh()
        elif event.button.id and event.button.id.startswith("chip-"):
            # Chip button pressed - extract chip number and proceed
            chip_number = int(event.button.id.replace("chip-", ""))
            self._select_and_proceed(chip_number)

    def action_refresh(self) -> None:
        """Refresh chip grid."""
        self._discover_and_populate()

    def action_select_chip(self) -> None:
        """Select the currently focused chip button and proceed."""
        chip_number = self._get_focused_chip_number()
        if chip_number is not None:
            self._select_and_proceed(chip_number)
        else:
            self.app.notify("Focus a chip first", severity="warning")

    def _select_and_proceed(self, chip_number: int) -> None:
        """
        Select a chip by number and proceed to next screen.

        Uses session to store chip selection and router for navigation.
        """
        if self._store_chip_selection(chip_number):
            if self.mode == "history":
                try:
                    self.app.router.go_to_history_browser()
                except Exception as exc:
                    self.app.notify(str(exc), severity="error")
            else:
                self.app.router.go_to_plot_type_selector()

    # ═══════════════════════════════════════════════════════════════════
    # Grid Navigation Helpers
    # ═══════════════════════════════════════════════════════════════════

    def _get_chip_buttons(self) -> list[Button]:
        """Get all chip buttons in order."""
        return list(self.query(".chip-button").results(Button))

    def _get_current_button_index(self) -> int:
        """Get index of currently focused button."""
        focused = self.focused
        if not isinstance(focused, Button) or not focused.id or not focused.id.startswith("chip-"):
            return -1

        buttons = self._get_chip_buttons()
        for i, button in enumerate(buttons):
            if button.id == focused.id:
                return i
        return -1

    def _get_focused_chip_number(self) -> int | None:
        focused = self.focused
        if isinstance(focused, Button) and focused.id and focused.id.startswith("chip-"):
            try:
                return int(focused.id.replace("chip-", ""))
            except ValueError:
                return None
        return None

    def _store_chip_selection(self, chip_number: int) -> bool:
        """Persist selected chip into session state."""
        selected_chip = next((chip for chip in self.chips if chip.chip_number == chip_number), None)
        if not selected_chip:
            self.app.notify(f"Chip {chip_number} not found", severity="error")
            return False

        self.selected_chip = selected_chip
        self.app.session.chip_number = selected_chip.chip_number
        self.app.session.chip_group = selected_chip.chip_group
        return True

    def action_navigate_up(self) -> None:
        """Navigate up in grid (5 columns)."""
        buttons = self._get_chip_buttons()
        current_index = self._get_current_button_index()

        if current_index >= 0:
            # Move up by 5 (one row up in 5-column grid)
            new_index = current_index - 5
            if new_index >= 0:
                buttons[new_index].focus()

    def action_navigate_down(self) -> None:
        """Navigate down in grid (5 columns)."""
        buttons = self._get_chip_buttons()
        current_index = self._get_current_button_index()

        if current_index >= 0:
            # Move down by 5 (one row down in 5-column grid)
            new_index = current_index + 5
            if new_index < len(buttons):
                buttons[new_index].focus()

    def action_navigate_left(self) -> None:
        """Navigate left in grid."""
        buttons = self._get_chip_buttons()
        current_index = self._get_current_button_index()

        if current_index > 0:
            buttons[current_index - 1].focus()

    def action_navigate_right(self) -> None:
        """Navigate right in grid."""
        buttons = self._get_chip_buttons()
        current_index = self._get_current_button_index()

        if current_index >= 0 and current_index < len(buttons) - 1:
            buttons[current_index + 1].focus()
