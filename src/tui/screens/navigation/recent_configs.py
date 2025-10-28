"""
Recent Configurations Screen.

Shows list of recently saved configurations that can be loaded and reused.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path
import glob

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Static, Button, DataTable
from textual.binding import Binding

from src.tui.screens.base import WizardScreen

if TYPE_CHECKING:
    from src.tui.app import PlotterApp


class RecentConfigsScreen(WizardScreen):
    """Recent configurations screen."""

    SCREEN_TITLE = "Recent Configurations"
    STEP_NUMBER = None  # Not part of main wizard flow

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("delete", "delete_config", "Delete", show=False),
        Binding("enter", "load_selected", "Load", priority=True),
    ]

    # Recent configs-specific CSS (extends WizardScreen CSS)
    CSS = WizardScreen.CSS + """
    #main-container {
        max-width: 140;
        max-height: 95%;
    }

    #subtitle {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #stats {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 1;
    }

    #table-container {
        width: 100%;
        height: 25;
        margin-bottom: 1;
    }

    DataTable {
        height: 100%;
    }

    DataTable:focus {
        border: thick $accent;
    }

    .action-button {
        width: 1fr;
        margin: 0 1;
    }

    .action-button:focus {
        background: $primary;
        color: $text;
        text-style: bold;
        border: thick $accent;
    }

    #info-box {
        width: 100%;
        height: auto;
        padding: 1 2;
        background: $panel;
        border: solid $primary;
        margin-bottom: 1;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with title and subtitle."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static("Load previously saved plot configurations", id="subtitle")

    def compose_content(self) -> ComposeResult:
        """Compose recent configs content."""
        # Stats display
        yield Static("", id="stats")

        # Info box
        with Vertical(id="info-box"):
            yield Static("📋 Select a configuration to load")
            yield Static("🔄 Press Enter to load selected config")
            yield Static("🗑️  Press Delete to remove config")
            yield Static("↑↓ Use arrow keys to navigate")

        # Data table
        with ScrollableContainer(id="table-container"):
            yield DataTable(id="configs-table", zebra_stripes=True, cursor_type="row")

        # Action buttons
        with Horizontal(id="button-container"):
            yield Button("Load Config", id="load-button", variant="primary", classes="action-button")
            yield Button("Export", id="export-button", variant="default", classes="action-button")
            yield Button("Import", id="import-button", variant="default", classes="action-button")
            yield Button("Delete", id="delete-button", variant="default", classes="action-button")
            yield Button("← Back", id="back-button", variant="default", classes="action-button")

    def on_mount(self) -> None:
        """Initialize screen and load configurations."""
        self._populate_table()
        self._update_stats()

        # Focus the table
        table = self.query_one("#configs-table", DataTable)
        table.focus()

    def _populate_table(self) -> None:
        """Populate the data table with recent configurations."""
        app: PlotterApp = self.app  # type: ignore
        table = self.query_one("#configs-table", DataTable)

        # Clear existing data
        table.clear(columns=True)

        # Add columns
        table.add_column("Date", width=12)
        table.add_column("Time", width=10)
        table.add_column("Description", width=50)
        table.add_column("Type", width=8)

        # Get recent configs
        configs = app.config_manager.get_recent_configs()

        if not configs:
            # Show message if no configs
            table.add_row("No saved", "configs", "Start plotting to save configurations!", "")
            return

        # Add rows
        for entry in configs:
            # Parse timestamp
            timestamp = entry["timestamp"]
            date_part = timestamp[:10]  # YYYY-MM-DD
            time_part = timestamp[11:19]  # HH:MM:SS

            description = entry["description"]
            plot_type = entry["config"].get("plot_type", "Unknown")

            # Store config_id as row key
            table.add_row(
                date_part,
                time_part,
                description,
                plot_type,
                key=entry["id"]
            )

    def _update_stats(self) -> None:
        """Update statistics display."""
        app: PlotterApp = self.app  # type: ignore
        stats = app.config_manager.get_stats()

        stats_text = f"Total: {stats['total_count']} configs"
        if stats['total_count'] > 0:
            # Add breakdown by type
            types = ", ".join(f"{k}: {v}" for k, v in stats['by_plot_type'].items())
            stats_text += f" ({types})"

        self.query_one("#stats", Static).update(stats_text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "load-button":
            self._load_selected_config()
        elif event.button.id == "export-button":
            self._export_config()
        elif event.button.id == "import-button":
            self._import_config()
        elif event.button.id == "delete-button":
            self.action_delete_config()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter key on row)."""
        self._load_selected_config()

    def action_load_selected(self) -> None:
        """Load selected config (Enter key binding)."""
        self._load_selected_config()

    def _load_selected_config(self) -> None:
        """Load the selected configuration and navigate to appropriate screen."""
        table = self.query_one("#configs-table", DataTable)
        app: PlotterApp = self.app  # type: ignore

        if table.row_count == 0:
            self.notify("No configurations available", severity="warning")
            return

        # Get selected row
        if table.cursor_row is None:
            self.notify("Please select a configuration", severity="warning")
            return

        # Get the row key using the coordinate property
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key is None or row_key.value is None:
            self.notify("No configurations available. Start plotting to save configurations!", severity="warning")
            return

        config_id = str(row_key.value)

        # Load config
        config = app.config_manager.load_config(config_id)
        if config is None:
            self.notify("Failed to load configuration", severity="error")
            return

        # Update session with loaded config (replaces app.plot_config.update)
        for key, value in config.items():
            if hasattr(app.session, key):
                setattr(app.session, key, value)

        chip_number = config.get("chip_number")
        chip_group = config.get("chip_group", app.session.chip_group)
        plot_type = config.get("plot_type", "ITS")
        seq_numbers = config.get("seq_numbers", [])

        self.notify(f"Loaded configuration: {plot_type}", timeout=2)

        # Navigate to preview using router
        app.router.go_to_preview()

    def action_delete_config(self) -> None:
        """Delete the selected configuration."""
        table = self.query_one("#configs-table", DataTable)
        app: PlotterApp = self.app  # type: ignore

        if table.row_count == 0:
            self.notify("No configurations to delete", severity="warning")
            return

        # Get selected row
        if table.cursor_row is None:
            self.notify("Please select a configuration to delete", severity="warning")
            return

        # Get the row key using the coordinate property
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key is None or row_key.value is None:
            self.notify("No configurations available to delete", severity="warning")
            return

        config_id = str(row_key.value)

        # Delete config
        if app.config_manager.delete_config(config_id):
            self.notify("Configuration deleted", severity="information")
            self._populate_table()
            self._update_stats()
        else:
            self.notify("Failed to delete configuration", severity="error")

    def _export_config(self) -> None:
        """Export the selected configuration to a JSON file."""
        table = self.query_one("#configs-table", DataTable)
        app: PlotterApp = self.app  # type: ignore

        if table.row_count == 0:
            self.notify("No configurations to export", severity="warning")
            return

        # Get selected row
        if table.cursor_row is None:
            self.notify("Please select a configuration to export", severity="warning")
            return

        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key is None or row_key.value is None:
            return

        config_id = str(row_key.value)

        # Export to current directory with descriptive filename
        export_path = Path(f"plot_config_{config_id}.json")

        if app.config_manager.export_config(config_id, export_path):
            self.notify(f"✓ Exported to {export_path}", severity="information", timeout=3)
        else:
            self.notify("Failed to export configuration", severity="error")

    def _import_config(self) -> None:
        """Import a configuration from a JSON file."""
        app: PlotterApp = self.app  # type: ignore

        # Check for any plot_config_*.json files in current directory
        config_files = list(Path(".").glob("plot_config_*.json"))

        if config_files:
            # Import the most recent one
            latest_file = max(config_files, key=lambda p: p.stat().st_mtime)
            config_id = app.config_manager.import_config(latest_file)

            if config_id:
                self.notify(f"✓ Imported {latest_file.name}", severity="information", timeout=3)
                self._populate_table()
                self._update_stats()
            else:
                self.notify(f"Failed to import {latest_file.name}", severity="error")
        else:
            self.notify(
                "No plot_config_*.json files found in current directory.\nPlace file here and try again.",
                severity="warning",
                timeout=5
            )

    def on_button_focus(self, event: Button.Focus) -> None:
        """Update button labels when focused."""
        button = event.button

        # Add arrow indicator for focused button
        if button.id == "load-button":
            button.label = "→ Load Config"
        elif button.id == "export-button":
            button.label = "→ Export"
        elif button.id == "import-button":
            button.label = "→ Import"
        elif button.id == "delete-button":
            button.label = "→ Delete"
        elif button.id == "back-button":
            button.label = "→ Back"

    def on_button_blur(self, event: Button.Blur) -> None:
        """Reset button labels when unfocused."""
        button = event.button

        # Remove arrow indicator
        if button.id == "load-button":
            button.label = "Load Config"
        elif button.id == "export-button":
            button.label = "Export"
        elif button.id == "import-button":
            button.label = "Import"
        elif button.id == "delete-button":
            button.label = "Delete"
        elif button.id == "back-button":
            button.label = "← Back"
