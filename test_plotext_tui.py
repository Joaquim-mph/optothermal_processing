"""
Minimal test for plotext in Textual TUI.

This isolates the plotext display issue.
"""

from textual.app import App, ComposeResult
from textual.widgets import Static, Button
from textual.containers import Vertical, ScrollableContainer
import plotext as plt
import numpy as np
import re


class PlotextTestApp(App):
    """Minimal app to test plotext display."""

    CSS = """
    Screen {
        background: $surface;
    }

    #plot-area {
        height: auto;
        min-height: 30;
        background: $panel;
        color: $text;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }

    ScrollableContainer {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }

    Button {
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Static("Plotext Test - Minimal Example", id="title")

        # Try with ScrollableContainer
        with ScrollableContainer():
            yield Static("Generating plot...", id="plot-area")

        yield Button("Generate Plot", id="gen-plot", variant="primary")
        yield Button("Quit", id="quit-btn", variant="error")

    def on_mount(self) -> None:
        """Generate plot on mount."""
        self.generate_plot()

    def generate_plot(self) -> None:
        """Generate a test plot."""
        # Generate test data
        x = np.linspace(0, 10, 100)
        y = np.sin(x)

        # Configure plotext
        plt.clear_figure()
        plt.plot_size(width=80, height=20)
        plt.plot(x, y)
        plt.title("Test Sin Wave")
        plt.xlabel("X")
        plt.ylabel("Y")
        plt.theme("dark")

        # Get plot as string
        try:
            output = plt.build()
            self.log(f"Plot generated: {len(output)} characters")
        except AttributeError:
            self.log("Using fallback stdout capture")
            import sys
            import io
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            try:
                plt.show()
                output = buffer.getvalue()
            finally:
                sys.stdout = old_stdout
                plt.clear_figure()

        # Strip ANSI codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', output)

        self.log(f"Clean output: {len(clean_output)} characters")
        self.log(f"First 100 chars: {clean_output[:100]}")

        # Update widget
        plot_widget = self.query_one("#plot-area", Static)
        plot_widget.update(clean_output)
        self.log("Widget updated")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "gen-plot":
            self.generate_plot()
        elif event.button.id == "quit-btn":
            self.exit()


if __name__ == "__main__":
    app = PlotextTestApp()
    app.run()
