"""Vt Preset Selector Screen for TUI."""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import SelectorScreen
from src.plotting.vt_presets import PRESETS


class VtPresetSelectorScreen(SelectorScreen):
    """Screen for selecting Vt plot presets (Step 3)."""

    SCREEN_TITLE = "Choose Vt Plot Preset"
    STEP_NUMBER = 3

    BINDINGS = SelectorScreen.BINDINGS + [
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
    ]

    # Preset selector CSS (extends SelectorScreen CSS)
    CSS = SelectorScreen.CSS + """
    #content-scroll {
        width: 100%;
        height: 1fr;
        min-height: 20;
    }

    .preset-button {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    .preset-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }

    .preset-button:hover {
        background: $primary;
        color: $primary-background;
    }

    #button-bar {
        width: 100%;
        layout: horizontal;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, chip_number: int, chip_group: str, plot_type: str = "Vt"):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.selected_preset = None

    def compose_header(self) -> ComposeResult:
        """Compose header with title, chip info, and step indicator."""
        yield Static(self.SCREEN_TITLE, id="title")
        subtitle = f"[bold]{self.chip_group}{self.chip_number}[/bold]"
        if self.plot_type:
            subtitle += f" - {self.plot_type}"

        yield Static(subtitle, id="subtitle")
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose preset selector content."""
        with VerticalScroll(id="content-scroll"):
            # Preset buttons (compact format with color coding)
            for preset_key, preset in PRESETS.items():
                # Build compact button label with color
                if preset.baseline_mode == "none":
                    baseline_info = "[dim]No baseline[/dim]"
                elif preset.baseline_mode == "auto":
                    baseline_info = f"[darkorange]Auto baseline (ON-OFF Period/{preset.baseline_auto_divisor})[/darkorange]"
                else:
                    baseline_info = f"[dim]Fixed baseline: {preset.baseline_value}s[/dim]"

                # Make title bigger and bold (same color as rest of text)
                button_label = (
                    f"[bold]{preset.name.upper()}[/bold]\n"
                    f"{preset.description}\n"
                    f"→ {baseline_info}, legend by [bold]{preset.legend_by}[/bold]"
                )

                yield Button(
                    button_label,
                    id=f"preset-{preset_key}",
                    variant="default",
                    classes="preset-button"
                )

            # Navigation buttons
            with Horizontal(id="button-bar"):
                yield Button("← Back", id="back-btn", variant="default", classes="nav-button")

    def on_mount(self) -> None:
        """Initialize screen - focus first preset button."""
        # Get all preset buttons
        preset_buttons = [btn for btn in self.query(Button).results(Button)
                         if btn.id and btn.id.startswith("preset-")]
        if preset_buttons:
            preset_buttons[0].focus()

    def on_key(self, event) -> None:
        """Handle arrow key navigation."""
        if event.key in ("up", "down"):
            # Get all focusable buttons (presets + back button)
            all_buttons = []

            # Add preset buttons in order
            for preset_key in PRESETS.keys():
                btn = self.query_one(f"#preset-{preset_key}", Button)
                all_buttons.append(btn)

            # Add back button
            all_buttons.append(self.query_one("#back-btn", Button))

            # Find currently focused button
            focused_idx = None
            for idx, btn in enumerate(all_buttons):
                if btn.has_focus:
                    focused_idx = idx
                    break

            if focused_idx is not None:
                if event.key == "up":
                    new_idx = (focused_idx - 1) % len(all_buttons)
                    all_buttons[new_idx].focus()
                    event.prevent_default()
                elif event.key == "down":
                    new_idx = (focused_idx + 1) % len(all_buttons)
                    all_buttons[new_idx].focus()
                    event.prevent_default()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "back-btn":
            self.action_back()
        elif button_id and button_id.startswith("preset-"):
            # Extract preset name from button ID
            preset_name = button_id.replace("preset-", "")
            self.selected_preset = preset_name

            # Store preset in session (replaces app.plot_config)
            self.app.session.preset = preset_name

            # Navigate to config screen using router
            if preset_name == "custom":
                # Show full config screen for custom preset
                self.app.router.go_to_vt_config(preset_mode=False)
            else:
                # Show quick config screen for preset (filters only)
                self.app.router.go_to_vt_config(preset_mode=True)
