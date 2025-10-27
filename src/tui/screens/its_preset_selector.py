"""ITS Preset Selector Screen for TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Button
from textual.screen import Screen
from textual.binding import Binding

from src.plotting.its_presets import PRESETS
from src.tui.screens.its_config import ITSConfigScreen


class ITSPresetSelectorScreen(Screen):
    """Screen for selecting ITS plot presets."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+b", "cancel", "Back", show=False),
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
    ]

    CSS = """
    ITSPresetSelectorScreen {
        align: center middle;
    }

    #main-container {
        width: 80;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
        overflow-y: auto;
    }

    #header-container {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
    }

    #subtitle {
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

    .nav-button {
        width: 1fr;
        margin: 0 1;
    }

    .nav-button:focus {
        background: $primary;
        border: tall $accent;
        color: $primary-background;
        text-style: bold;
    }

    .nav-button:hover {
        background: $primary;
        color: $primary-background;
    }
    """

    def __init__(self, chip_number: int, chip_group: str):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.selected_preset = None

    def compose(self) -> ComposeResult:
        """Compose the preset selector screen."""
        yield Header()

        with Container(id="main-container"):
            with Vertical(id="header-container"):
                yield Static("Choose It Plot Preset", id="title")
                yield Static(
                    f"[bold]{self.chip_group}{self.chip_number}[/bold] - ITS",
                    id="subtitle"
                )
                yield Static("[Step 4/8]", id="step-indicator")

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

        yield Footer()

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
            self.action_cancel()
        elif button_id and button_id.startswith("preset-"):
            # Extract preset name from button ID
            preset_name = button_id.replace("preset-", "")
            self.selected_preset = preset_name

            # Store preset in app config
            self.app.plot_config["preset"] = preset_name

            # Navigate to config screen (different behavior based on preset)
            if preset_name == "custom":
                # Show full config screen for custom preset
                self._push_full_config_screen()
            else:
                # Show quick config screen for preset (filters only)
                self._push_quick_config_screen()

    def _push_full_config_screen(self) -> None:
        """Push full ITS config screen for custom preset."""
        self.app.push_screen(
            ITSConfigScreen(
                chip_number=self.chip_number,
                chip_group=self.chip_group,
                preset_mode=False  # Full config
            )
        )

    def _push_quick_config_screen(self) -> None:
        """Push quick config screen for preset (filters only)."""
        self.app.push_screen(
            ITSConfigScreen(
                chip_number=self.chip_number,
                chip_group=self.chip_group,
                preset_mode=True  # Quick config (preset-based)
            )
        )

    def action_cancel(self) -> None:
        """Cancel and go back."""
        self.app.pop_screen()
