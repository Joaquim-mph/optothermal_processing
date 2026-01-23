"""
Enriched History Browser Screen.

Browse chip history WITH derived metrics (CNP, photoresponse, relaxation times).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button, Label, Select, DataTable
from textual.binding import Binding

from src.tui.screens.base import WizardScreen

if TYPE_CHECKING:
    from textual.widgets import Button as ButtonType


class EnrichedHistoryBrowserScreen(WizardScreen):
    """Enriched chip history browser screen (with derived metrics)."""

    SCREEN_TITLE = "✨ Enriched History"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("home", "home", "Home", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = WizardScreen.CSS + """
    #breadcrumb {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #controls-container {
        height: 10;
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

    .warning-banner {
        background: $warning;
        color: $text;
        padding: 1;
        margin: 1 0;
    }

    DataTable {
        height: 100%;
    }
    """

    def __init__(self) -> None:
        """Initialize enriched history browser."""
        super().__init__()
        self.chip_number: int | None = None
        self.history_df: pl.DataFrame | None = None
        self.has_enriched = False

    def compose_header(self) -> ComposeResult:
        """Compose header with breadcrumb and title."""
        yield Static("Main Menu > Histories > Enriched History", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        """Compose enriched history browser."""
        # Chip selector
        with Vertical(id="controls-container"):
            with Horizontal(classes="control-row"):
                yield Label("Select Chip: ")
                yield Select(
                    options=[("Select chip...", "")],
                    value="",
                    id="chip-select"
                )

            # Enrichment status (will be updated dynamically)
            yield Static("", id="enrichment-status")

        # Statistics bar
        yield Static("Select a chip to view enriched history", id="stats-bar")

        # Data table
        with VerticalScroll(id="table-container"):
            table = DataTable(id="history-table")
            table.cursor_type = "row"
            yield table

        # Actions
        with Vertical():
            yield Button(
                "🔄 Refresh Metrics",
                id="refresh-metrics",
                variant="primary",
                classes="action-button"
            )

    def on_mount(self) -> None:
        """Initialize chip selector and table."""
        self._populate_chip_selector()

        # Set up table columns with metrics
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Seq", "Date", "Proc", "CNP(V)", "PR(µA)", "τ(s)")

        self.query_one("#chip-select", Select).focus()

    def _populate_chip_selector(self) -> None:
        """Populate chip selector with available chips."""
        history_dir = Path("data/02_stage/chip_histories")
        if not history_dir.exists():
            return

        chips = []
        for history_file in history_dir.glob("*.parquet"):
            chip_name = history_file.stem
            try:
                chip_num = int(chip_name)
                chips.append((f"Chip {chip_num}", str(chip_num)))
            except ValueError:
                chips.append((chip_name, chip_name))

        chips.sort(key=lambda x: int(x[1]) if x[1].isdigit() else 0)

        if chips:
            options = [("Select chip...", "")] + chips
            self.query_one("#chip-select", Select).set_options(options)

    def _load_enriched_history(self, chip_number: str) -> None:
        """Load enriched chip history."""
        enriched_path = Path(f"data/03_derived/chip_histories_enriched/{chip_number}.parquet")

        if not enriched_path.exists():
            # Show warning and offer to run enrichment
            self.has_enriched = False
            self.query_one("#enrichment-status", Static).update(
                "⚠️  No enriched history found. Run enrichment to see derived metrics."
            )
            self.query_one("#enrichment-status", Static).add_class("warning-banner")
            return

        try:
            self.history_df = pl.read_parquet(enriched_path)
            self.chip_number = int(chip_number) if chip_number.isdigit() else None
            self.has_enriched = True

            # Update status
            self.query_one("#enrichment-status", Static).update(
                "✅ Enriched history available"
            )
            self.query_one("#enrichment-status", Static).remove_class("warning-banner")

            # Update table
            self._update_table()

            self.app.notify(
                f"Loaded enriched history for chip {chip_number}",
                severity="information"
            )
        except Exception as e:
            self.app.notify(f"Error loading enriched history: {e}", severity="error")

    def _update_table(self) -> None:
        """Update table with enriched data."""
        table = self.query_one("#history-table", DataTable)
        table.clear()

        if self.history_df is None or len(self.history_df) == 0:
            return

        # Update stats
        total = len(self.history_df)
        with_cnp = self.history_df.filter(pl.col("cnp_voltage_v").is_not_null()).height if "cnp_voltage_v" in self.history_df.columns else 0
        with_pr = self.history_df.filter(pl.col("photoresponse_ua").is_not_null()).height if "photoresponse_ua" in self.history_df.columns else 0

        self.query_one("#stats-bar", Static).update(
            f"📊 Total: {total} | CNP: {with_cnp} | Photoresponse: {with_pr}"
        )

        # Add rows (limit to 100 for performance)
        for row in self.history_df.head(100).iter_rows(named=True):
            seq = str(row.get("seq", ""))
            date = str(row.get("date_local", ""))[:10] if row.get("date_local") else ""
            proc = str(row.get("procedure", ""))

            # Derived metrics
            cnp = row.get("cnp_voltage_v")
            cnp_str = f"{cnp:.3f}" if cnp is not None else "---"

            pr = row.get("photoresponse_ua")
            pr_str = f"{pr:.2f}" if pr is not None else "---"

            tau = row.get("tau_s")
            tau_str = f"{tau:.1f}" if tau is not None else "---"

            table.add_row(seq, date, proc, cnp_str, pr_str, tau_str)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle chip selection."""
        if event.select.id == "chip-select" and event.value:
            self._load_enriched_history(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh-metrics":
            self._refresh_metrics()

    def _refresh_metrics(self) -> None:
        """Run enrichment for current chip."""
        if not self.chip_number:
            self.app.notify("Select a chip first", severity="warning")
            return

        self.app.notify(
            f"Running enrichment for chip {self.chip_number}...",
            severity="information"
        )

        # TODO: Launch enrich-history command
        self.app.notify(
            "Metric enrichment - Coming soon! Use CLI: enrich-history <chip>",
            severity="information"
        )

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
