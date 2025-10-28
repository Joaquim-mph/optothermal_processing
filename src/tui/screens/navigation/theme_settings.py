"""
Theme Settings Screen.

Allows users to change the TUI theme with live preview.
Settings are persisted to ~/.lab_plotter_tui.json
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, RadioSet, RadioButton
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class ThemeSettingsScreen(WizardScreen):
    """Theme settings screen with live theme preview."""

    SCREEN_TITLE = "🎨 Theme Settings"
    STEP_NUMBER = None  # Settings screen is not part of the wizard

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("enter", "apply_theme", "Apply", priority=True),
        Binding("r", "reset_defaults", "Reset", show=False),
    ]

    CSS = WizardScreen.CSS + """
    /* Override base padding for more compact layout */
    #main-container {
        padding: 1 4;
    }

    #header-container {
        margin-bottom: 1;
    }

    #theme-container {
        width: 100%;
        height: auto;
        padding: 0;
    }

    #theme-list {
        width: 100%;
        height: auto;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    RadioSet {
        width: 100%;
        height: auto;
    }

    RadioButton {
        width: 100%;
        margin: 0 0;
        padding: 1 2;
    }

    RadioButton:focus {
        background: $primary;
        color: $primary-background;
        text-style: bold;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    .action-button {
        margin: 0 1;
        min-width: 16;
    }

    #info-text {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
        text-style: dim;
    }

    #current-theme {
        width: 100%;
        content-align: center middle;
        color: $accent;
        margin-bottom: 1;
        text-style: bold;
    }
    """

    def compose_content(self) -> ComposeResult:
        """Compose theme selection interface."""
        with Vertical(id="theme-container"):
            # Current theme indicator
            current_theme = self.app.settings_manager.get_theme_display_name(
                self.app.settings_manager.theme
            )
            yield Static(f"Current Theme: {current_theme}", id="current-theme")

            # Theme selection radio buttons
            with Vertical(id="theme-list"):
                with RadioSet(id="theme-radio"):
                    themes = self.app.settings_manager.get_available_themes()
                    current = self.app.settings_manager.theme

                    for theme in themes:
                        display_name = self.app.settings_manager.get_theme_display_name(theme)
                        is_current = theme == current
                        yield RadioButton(
                            display_name,
                            value=is_current,
                            id=f"theme-{theme}",
                            name=theme
                        )

            # Action buttons
            with Horizontal(id="button-container"):
                yield Button("Apply Theme", id="apply", variant="primary", classes="action-button")
                yield Button("Reset to Default", id="reset", variant="default", classes="action-button")
                yield Button("Back", id="back", variant="default", classes="action-button")

            yield Static(
                "Select a theme and press Apply to change (changes are saved automatically)",
                id="info-text"
            )

    def on_mount(self) -> None:
        """Focus the radio set when mounted."""
        try:
            self.query_one(RadioSet).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "apply":
            self.action_apply_theme()
        elif button_id == "reset":
            self.action_reset_defaults()
        elif button_id == "back":
            self.action_back()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Live preview theme when selection changes."""
        if event.pressed:
            # Get the selected theme from the radio button's name attribute
            theme_id = event.pressed.name
            if theme_id:
                # Apply theme for live preview (don't save yet)
                self.app.theme = theme_id
                self.notify(f"Previewing: {self.app.settings_manager.get_theme_display_name(theme_id)}")

    def action_apply_theme(self) -> None:
        """Apply and save the selected theme."""
        try:
            radio_set = self.query_one(RadioSet)
            if radio_set.pressed_button:
                theme_id = radio_set.pressed_button.name
                if theme_id:
                    # Save to settings file
                    self.app.settings_manager.theme = theme_id

                    # Update current theme display
                    display_name = self.app.settings_manager.get_theme_display_name(theme_id)
                    self.query_one("#current-theme", Static).update(
                        f"Current Theme: {display_name}"
                    )

                    self.notify(f"✓ Theme saved: {display_name}", severity="success")
                else:
                    self.notify("No theme selected", severity="warning")
            else:
                self.notify("No theme selected", severity="warning")
        except Exception as e:
            self.notify(f"Error applying theme: {e}", severity="error")

    def action_reset_defaults(self) -> None:
        """Reset theme to default (Tokyo Night)."""
        try:
            # Reset to default theme
            self.app.settings_manager.reset_to_defaults()
            default_theme = self.app.settings_manager.theme

            # Apply the default theme
            self.app.theme = default_theme

            # Update radio selection
            radio_set = self.query_one(RadioSet)
            for button in radio_set.query(RadioButton):
                if button.name == default_theme:
                    radio_set.action_toggle_button(button)
                    break

            # Update current theme display
            display_name = self.app.settings_manager.get_theme_display_name(default_theme)
            self.query_one("#current-theme", Static).update(
                f"Current Theme: {display_name}"
            )

            self.notify(f"✓ Reset to default theme: {display_name}", severity="success")
        except Exception as e:
            self.notify(f"Error resetting theme: {e}", severity="error")

    def action_back(self) -> None:
        """Go back to main menu, restoring saved theme if preview wasn't applied."""
        # Restore saved theme in case user previewed but didn't apply
        saved_theme = self.app.settings_manager.theme
        self.app.theme = saved_theme

        # Pop this screen
        self.app.pop_screen()
