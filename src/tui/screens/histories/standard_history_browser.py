"""
Standard History Browser Screen.

Browse chip experiment history with filtering, sorting, and detailed views.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button, Label, Select, Input, DataTable
from textual.binding import Binding

from src.tui.screens.base import WizardScreen

if TYPE_CHECKING:
    from textual.widgets import Button as ButtonType


class StandardHistoryBrowserScreen(WizardScreen):
    """Standard chip history browser screen."""

    SCREEN_TITLE = "📊 Standard History"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("home", "home", "Home", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("p", "preview", "Preview", show=True),
    ]

    CSS = WizardScreen.CSS + """
    #breadcrumb {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #controls-container {
        height: 12;
        margin: 1 0;
    }

    .control-row {
        height: 3;
        margin: 0 0 1 0;
    }

    #table-container {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
        height: 30;
    }

    #stats-bar {
        color: $text-muted;
        text-style: dim;
        margin: 0 0 1 0;
    }

    DataTable {
        height: 100%;
    }
    """

    def __init__(self) -> None:
        """Initialize standard history browser."""
        super().__init__()
        self.chip_number: int | None = None
        self.chip_group: str = ""
        self.history_df: pl.DataFrame | None = None
        self.filtered_df: pl.DataFrame | None = None

        # Filter state
        self.filter_procedure = "all"
        self.filter_light = "all"
        self.filter_date = "all"

    def compose_header(self) -> ComposeResult:
        """Compose header with breadcrumb and title."""
        yield Static("Main Menu > Histories > Standard History", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose standard history browser."""
        # Chip selector and filters
        with Vertical(id="controls-container"):
            with Horizontal(classes="control-row"):
                yield Label("Chip: ")
                yield Select(
                    options=[("Select chip...", "")],
                    value="",
                    id="chip-select"
                )

            with Horizontal(classes="control-row"):
                yield Label("Procedure: ")
                yield Select(
                    options=[
                        ("All", "all"),
                        ("IVg", "IVg"),
                        ("It", "It"),
                        ("VVg", "VVg"),
                        ("Vt", "Vt"),
                        ("LaserCalibration", "LaserCalibration"),
                    ],
                    value="all",
                    id="procedure-filter"
                )
                yield Label(" Light: ")
                yield Select(
                    options=[
                        ("All", "all"),
                        ("Dark", "dark"),
                        ("Light", "light"),
                    ],
                    value="all",
                    id="light-filter"
                )

            with Horizontal(classes="control-row"):
                yield Label("Search: ")
                yield Input(placeholder="Filter by seq, procedure, etc...", id="search-input")

        # Statistics bar
        yield Static("Select a chip to view history", id="stats-bar")

        # Data table
        with VerticalScroll(id="table-container"):
            table = DataTable(id="history-table")
            table.cursor_type = "row"
            yield table

    def on_mount(self) -> None:
        """Initialize chip selector and table."""
        # Populate chip selector
        self._populate_chip_selector()

        # Set up table columns
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Seq", "Date", "Proc", "VG", "Light", "λ(nm)")

        # Focus chip selector
        self.query_one("#chip-select", Select).focus()

    def _populate_chip_selector(self) -> None:
        """Populate chip selector with available chips."""
        history_dir = Path("data/02_stage/chip_histories")
        if not history_dir.exists():
            return

        chips = []
        for history_file in history_dir.glob("*.parquet"):
            chip_name = history_file.stem  # e.g., "67" from "67.parquet"
            try:
                chip_num = int(chip_name)
                chips.append((f"Chip {chip_num}", str(chip_num)))
            except ValueError:
                # Handle non-numeric chip names
                chips.append((chip_name, chip_name))

        chips.sort(key=lambda x: int(x[1]) if x[1].isdigit() else 0)

        if chips:
            options = [("Select chip...", "")] + chips
            self.query_one("#chip-select", Select).set_options(options)

    def _load_history(self, chip_number: str) -> None:
        """Load chip history from parquet file."""
        history_path = Path(f"data/02_stage/chip_histories/{chip_number}.parquet")

        if not history_path.exists():
            self.app.notify(f"History not found for chip {chip_number}", severity="error")
            return

        try:
            self.history_df = pl.read_parquet(history_path)
            self.chip_number = int(chip_number) if chip_number.isdigit() else None
            self._apply_filters()
            self._update_table()

            self.app.notify(
                f"Loaded {len(self.history_df)} experiments for chip {chip_number}",
                severity="information"
            )
        except Exception as e:
            self.app.notify(f"Error loading history: {e}", severity="error")

    def _apply_filters(self) -> None:
        """Apply filters to history DataFrame."""
        if self.history_df is None:
            return

        df = self.history_df

        # Procedure filter
        if self.filter_procedure != "all":
            df = df.filter(pl.col("procedure") == self.filter_procedure)

        # Light filter
        if self.filter_light != "all":
            light_value = self.filter_light == "light"
            df = df.filter(pl.col("has_light") == light_value)

        self.filtered_df = df

        # Update stats
        total = len(self.history_df)
        filtered = len(self.filtered_df)
        self.query_one("#stats-bar", Static).update(
            f"📊 Showing {filtered} of {total} experiments"
        )

    def _update_table(self) -> None:
        """Update table with filtered data."""
        table = self.query_one("#history-table", DataTable)
        table.clear()

        if self.filtered_df is None or len(self.filtered_df) == 0:
            return

        # Add rows (limit to 100 for performance)
        for row in self.filtered_df.head(100).iter_rows(named=True):
            # Format data
            seq = str(row.get("seq", ""))
            date = str(row.get("date_local", ""))[:10] if row.get("date_local") else ""
            proc = str(row.get("procedure", ""))
            vg = f"{row.get('vg_v', 0):.2f}" if row.get("vg_v") is not None else "---"

            # Light emoji
            has_light = row.get("has_light", False)
            light = "💡" if has_light else "🌙"

            # Wavelength
            wavelength = row.get("wavelength_nm")
            wl_str = f"{int(wavelength)}" if wavelength is not None else "---"

            table.add_row(seq, date, proc, vg, light, wl_str)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selection changes."""
        if event.select.id == "chip-select" and event.value:
            self._load_history(event.value)
        elif event.select.id == "procedure-filter":
            self.filter_procedure = event.value
            self._apply_filters()
            self._update_table()
        elif event.select.id == "light-filter":
            self.filter_light = event.value
            self._apply_filters()
            self._update_table()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            # TODO: Implement search filtering
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle table row selection."""
        if event.row_key is not None:
            # TODO: Show experiment details
            self.app.notify(f"Selected experiment (row {event.cursor_row})", severity="information")

    def action_refresh(self) -> None:
        """Refresh history data."""
        if self.chip_number:
            self._load_history(str(self.chip_number))
            self.app.notify("Refreshed history", severity="information")

    def action_preview(self) -> None:
        """Preview selected experiment."""
        # TODO: Navigate to data preview screen
        self.app.notify("Data preview - Coming soon!", severity="information")

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
