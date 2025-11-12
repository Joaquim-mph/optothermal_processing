"""
Log Viewer Screen.

Displays recent log entries from the TUI log file for debugging and troubleshooting.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen
from src.tui.logging_config import read_recent_logs, get_log_file_path


class LogViewerScreen(WizardScreen):
    """Screen for viewing TUI log entries."""

    SCREEN_TITLE = "TUI Logs"
    STEP_NUMBER = None  # Not part of wizard flow

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = WizardScreen.CSS + """
    #log-container {
        width: 100%;
        height: 1fr;
        border: tall $primary;
        background: $panel;
        padding: 1;
    }

    #log-content {
        width: 100%;
        height: 100%;
    }

    .log-line {
        width: 100%;
        color: $text;
    }

    .log-line-error {
        color: $error;
        text-style: bold;
    }

    .log-line-warning {
        color: $warning;
    }

    .log-line-info {
        color: $text;
    }

    .log-line-debug {
        color: $text-muted;
        text-style: dim;
    }

    #log-path {
        width: 100%;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
        content-align: center middle;
    }

    #log-count {
        width: 100%;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
        content-align: center middle;
    }

    #button-bar {
        width: 100%;
        layout: horizontal;
        height: auto;
        margin-top: 1;
    }
    """

    def compose_content(self) -> ComposeResult:
        """Compose log viewer content."""
        # Show log file path
        log_file = get_log_file_path()
        yield Static(f"Log file: {log_file}", id="log-path")
        yield Static("", id="log-count")

        # Scrollable log container
        with VerticalScroll(id="log-container"):
            yield Static("", id="log-content")

        # Buttons
        with Horizontal(id="button-bar"):
            yield Button("Refresh", id="refresh-button", variant="primary", classes="nav-button")
            yield Button("← Back", id="back-button", variant="default", classes="nav-button")

    def on_mount(self) -> None:
        """Load logs when screen mounts."""
        self._load_logs()

    def _load_logs(self) -> None:
        """Load and display recent log entries."""
        # Read recent logs
        log_lines = read_recent_logs(max_lines=500)

        # Count entries
        log_count = len(log_lines)
        count_widget = self.query_one("#log-count", Static)
        count_widget.update(f"Showing last {log_count} log entries")

        # Format log lines with color coding
        formatted_lines = []
        for line in log_lines:
            line = line.rstrip()  # Remove trailing newline

            # Determine log level and apply styling
            if "ERROR" in line:
                formatted_lines.append(f"[red]{line}[/red]")
            elif "WARNING" in line:
                formatted_lines.append(f"[yellow]{line}[/yellow]")
            elif "INFO" in line:
                formatted_lines.append(f"[white]{line}[/white]")
            elif "DEBUG" in line:
                formatted_lines.append(f"[dim]{line}[/dim]")
            else:
                formatted_lines.append(line)

        # Update log content
        log_content = self.query_one("#log-content", Static)
        log_content.update("\n".join(formatted_lines))

        # Scroll to bottom
        log_container = self.query_one("#log-container", VerticalScroll)
        log_container.scroll_end(animate=False)

    def action_refresh(self) -> None:
        """Refresh log display."""
        self._load_logs()
        self.notify("Logs refreshed", timeout=2)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "refresh-button":
            self.action_refresh()
