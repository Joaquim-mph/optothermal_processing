"""
History Browser Screen.

Provides a tabular view of all staged experiments for the selected chip,
similar to the CLI `show-history` command, with hooks for procedure filtering
and downstream actions (plot, inspect metadata, etc.).
"""

from __future__ import annotations

from typing import Optional, Iterable, Tuple, Any, Dict, List
from pathlib import Path

import polars as pl

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Label, Select, Static, Header, Footer
from textual.binding import Binding
from textual.screen import ModalScreen, Screen

from src.cli.history_utils import (
    filter_history,
    summarize_history,
    HistoryFilterError,
)


class HistoryBrowserScreen(Screen):
    """
    Display chip history in a full-width table with filtering controls.

    Features keyboard shortcuts, procedure filtering, and light status filters.
    """

    BINDINGS = [
        Binding("escape", "back", "Back", priority=True),
        Binding("q", "back", "Quit", show=False),
        Binding("enter", "inspect", "Inspect", priority=True),
        Binding("ctrl+p", "plot", "Plot", show=False),
        Binding("f", "focus_filter", "Filter", show=False),
        # Light filter shortcuts
        Binding("1", "filter_all", "All", show=False),
        Binding("2", "filter_light", "Light", show=False),
        Binding("3", "filter_dark", "Dark", show=False),
    ]

    CSS = """
    HistoryBrowserScreen {
        background: $surface;
    }

    #main-container {
        width: 100%;
        height: 100%;
        layout: vertical;
    }

    #screen-title {
        text-align: center;
        text-style: bold;
        color: cyan;
        height: 1;
        padding: 0 2;
        margin-top: 1;
    }

    #header-line {
        text-align: left;
        height: 1;
        padding: 0 2;
    }

    #controls-text {
        text-align: left;
        color: $accent;
        height: 1;
        padding: 0 2;
    }

    #spacer {
        height: 1;
    }

    #filter-bar {
        height: auto;
        padding: 0 2;
        margin-bottom: 1;
        layout: horizontal;
        align: left middle;
    }

    #procedure-select {
        width: 25;
        height: 3;
        margin-right: 2;
    }

    .light-filter-button {
        min-width: 14;
        height: 3;
        margin-right: 1;
    }

    #table-container {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        margin: 0;
    }

    #history-table {
        width: 100%;
        height: auto;
    }

    #status-bar {
        dock: bottom;
        text-align: center;
        height: 1;
        background: $panel;
        color: $text-muted;
        border-top: solid $primary;
        padding: 0 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.table: DataTable | None = None
        self.history_df: pl.DataFrame | None = None
        self.filtered_df: pl.DataFrame | None = None
        self.history_path: Path | None = None
        self.available_procs: list[str] = []
        self.extract_light: bool = False
        self.proc_filter: str = "All"
        self.light_filter: str = "all"
        self.history_summary: Dict[str, Any] | None = None
        self.filtered_summary: Dict[str, Any] | None = None
        self.applied_filters: List[str] = []

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()

        with Container(id="main-container"):
            # Get chip info for title
            chip_group = getattr(self.app.session, "chip_group", "Chip")
            chip_number = getattr(self.app.session, "chip_number", None)
            chip_label = f"{chip_group}{chip_number}" if chip_number is not None else "Unknown"

            # Centered title
            yield Static(f"Chip Experiment Timeline - {chip_label}", id="screen-title")

            # Header line (stats, populated on mount)
            yield Static("", id="header-line")

            # Controls
            yield Static(
                "[bold]Controls:[/bold] Enter=Inspect  Esc=Back  1/2/3=Light Filters",
                id="controls-text"
            )

            # Spacer
            yield Static("", id="spacer")

            # Filter bar (procedure + light filters)
            with Horizontal(id="filter-bar"):
                yield Select(
                    options=[("All", "All")],
                    id="procedure-select",
                    value="All"
                )
                yield Button("All", id="light-all", variant="primary", classes="light-filter-button")
                yield Button("💡 Light", id="light-light", classes="light-filter-button")
                yield Button("🌙 Dark", id="light-dark", classes="light-filter-button")

            # Main table wrapped in scroll container
            with VerticalScroll(id="table-container"):
                yield DataTable(id="history-table", cursor_type="row", zebra_stripes=True)

            # Status bar at bottom (shows filter status)
            yield Static("", id="status-bar")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize table and load chip history."""
        self.table = self.query_one("#history-table", DataTable)
        self._setup_table()
        self._load_history()
        self.table.focus()

    def _setup_table(self) -> None:
        """Define the table columns."""
        if not self.table:
            return

        self.table.clear(columns=True)
        self.table.add_columns(
            "Light",
            "Seq",
            "Date",
            "Time",
            "Proc",
            "VG",
            "LED V",
            "λ (nm)",
            "VDS (V)",
        )

    def _load_history(self) -> None:
        """Load the chip history parquet into memory and populate the table."""
        chip_number = getattr(self.app.session, "chip_number", None)
        chip_group = getattr(self.app.session, "chip_group", None)
        history_dir: Path = getattr(self.app.session, "history_dir", Path("data/02_stage/chip_histories"))

        if chip_number is None or not chip_group:
            self.notify("Chip information missing; cannot load history", severity="error", timeout=4)
            return

        chip_name = f"{chip_group}{chip_number}"
        history_file = Path(history_dir) / f"{chip_name}_history.parquet"
        self.history_path = history_file

        if not history_file.exists():
            self.notify(f"No history found for {chip_name}", severity="error", timeout=4)
            return

        try:
            self.history_df = pl.read_parquet(history_file)
        except Exception as exc:
            self.notify(f"Failed to load history: {exc}", severity="error", timeout=4)
            self.history_df = None
            return

        self.available_procs = sorted(self.history_df.get_column("proc").unique().to_list())
        self.extract_light = "has_light" in self.history_df.columns
        self.history_summary = summarize_history(self.history_df)

        self._populate_procedure_options()
        self._set_light_controls_state()
        self._highlight_light_filter(self.light_filter)
        self._update_stats()
        self.filtered_df = self.history_df
        self.filtered_summary = self.history_summary
        self.applied_filters = []
        self._apply_filters()

    def _update_stats(self) -> None:
        """Update the header line with stats summary."""
        if self.history_df is None:
            return

        header_widget = self.query_one("#header-line", Static)

        # Get chip info
        chip_group = getattr(self.app.session, "chip_group", "Chip")
        chip_number = getattr(self.app.session, "chip_number", None)
        chip_label = f"{chip_group}{chip_number}" if chip_number is not None else "Unknown"

        # Build stats
        total = len(self.history_df)
        proc_counts = self.history_df.group_by("proc").agg(
            pl.count().alias("count")
        ).sort("count", descending=True)

        # Format as single line: "Alisson67 | Total: 90 | IVg: 39  It: 51"
        proc_parts = []
        for row in proc_counts.iter_rows(named=True):
            proc_parts.append(f"{row['proc']}: {row['count']}")

        stats_text = f"[bold]{chip_label}[/bold]  |  Total: {total}  |  " + "  ".join(proc_parts)
        header_widget.update(stats_text)

    def _update_status_bar(self) -> None:
        """Update status bar with current filter status."""
        status_widget = self.query_one("#status-bar", Static)

        if self.filtered_df is None or self.history_df is None:
            return

        total = len(self.history_df)
        filtered = len(self.filtered_df)

        if self.applied_filters:
            filter_text = ", ".join(self.applied_filters)
            status_widget.update(f"Showing {filtered} of {total} experiments — Filters: {filter_text}")
        else:
            status_widget.update(f"Showing all {total} experiments")

    def _populate_table(self, df: pl.DataFrame) -> None:
        """Fill the data table from a history DataFrame."""
        if not self.table:
            return

        self.table.clear()

        for row in df.iter_rows(named=True):
            self.table.add_row(
                self._format_light(row),
                str(row.get("seq", "")),
                str(row.get("date", "")),
                str(row.get("time_hms", "")),
                str(row.get("proc", "")),
                self._format_vg(row),
                self._format_led(row),
                self._format_wavelength(row),
                self._format_vds(row),
            )

        if self.table.row_count > 0:
            self.table.move_cursor(row=0)

        self._update_status_bar()

    @staticmethod
    def _format_summary(row: dict) -> str:
        summary = row.get("summary")
        if summary:
            return str(summary)
        proc = row.get("proc", "")
        chip = row.get("chip_name", "")
        return f"{proc} {chip}".strip()

    def _format_light(self, row: dict) -> str:
        if not self.extract_light:
            return ""
        value = row.get("has_light")
        if value is True:
            return "💡"
        if value is False:
            return "🌙"
        return "❔"

    @staticmethod
    def _format_vds(row: dict) -> str:
        value = row.get("vds_v")
        if value is None:
            return "-"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _format_vg(row: dict) -> str:
        vg_start = row.get("vg_start_v")
        vg_end = row.get("vg_end_v")
        vg_fixed = row.get("vg_fixed_v")

        def fmt(val: float) -> str:
            return f"{val:.2f}"

        if vg_start is not None and vg_end is not None:
            return f"{fmt(vg_start)} → {fmt(vg_end)}"

        if vg_fixed is not None:
            try:
                return fmt(float(vg_fixed))
            except (TypeError, ValueError):
                return str(vg_fixed)

        return "-"

    @staticmethod
    def _format_wavelength(row: dict) -> str:
        value = row.get("wavelength_nm")
        if value is None:
            return "-"
        try:
            return f"{float(value):.0f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _format_led(row: dict) -> str:
        value = row.get("laser_voltage_v")
        if value is None:
            return "-"
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    def _populate_procedure_options(self) -> None:
        """Populate the procedure Select with available values."""
        select = self.query_one("#procedure-select", Select)
        options = [("All", "All")]
        options.extend((proc, proc) for proc in self.available_procs)
        if hasattr(select, "set_options"):
            select.set_options(options)
        else:  # Fallback for older Textual versions
            select.options = options
        select.value = self.proc_filter

    def _set_light_controls_state(self) -> None:
        """Disable light filters if the history lacks light metadata."""
        for button_id in ["light-all", "light-light", "light-dark"]:
            btn = self.query_one(f"#{button_id}", Button)
            btn.disabled = not self.extract_light
        if not self.extract_light:
            self.light_filter = "all"

    def _highlight_light_filter(self, target: str) -> None:
        """Visually indicate the active light filter."""
        mapping = {
            "light-all": "all",
            "light-light": "light",
            "light-dark": "dark",
        }
        for button_id, value in mapping.items():
            btn = self.query_one(f"#{button_id}", Button)
            if btn.disabled:
                btn.variant = "default"
            else:
                btn.variant = "primary" if value == target else "default"

    def _apply_filters(self) -> None:
        """Filter cached DataFrame by procedure and light selections."""
        if self.history_df is None:
            return

        previous_count = self.filtered_df.height if self.filtered_df is not None else None

        proc_value = None if self.proc_filter == "All" else self.proc_filter
        light_value = None
        if self.extract_light:
            if self.light_filter == "light":
                light_value = "light"
            elif self.light_filter == "dark":
                light_value = "dark"
            elif self.light_filter == "unknown":
                light_value = "unknown"

        try:
            filtered, applied = filter_history(
                self.history_df,
                proc_filter=proc_value,
                light_filter=light_value,
                limit=None,
                strict=False,
            )
        except HistoryFilterError as exc:
            self.notify(str(exc), severity="error", timeout=4)
            filtered = self.history_df.head(0)
            applied = []

        self.filtered_df = filtered
        self.filtered_summary = summarize_history(filtered)
        self.applied_filters = applied
        self._populate_table(filtered)

        if filtered.height == 0 and (previous_count or 0) > 0:
            self.notify("No experiments match current filters", severity="warning", timeout=3)

    # ───── Actions ──────────────────────────────────────────────────────────────

    def action_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()

    def action_focus_filter(self) -> None:
        """Focus the procedure select control."""
        select = self.query_one("#procedure-select", Select)
        select.focus()

    def action_filter_all(self) -> None:
        """Set light filter to All."""
        if self.extract_light:
            self.light_filter = "all"
            self._highlight_light_filter(self.light_filter)
            self._apply_filters()

    def action_filter_light(self) -> None:
        """Set light filter to Light only."""
        if self.extract_light:
            self.light_filter = "light"
            self._highlight_light_filter(self.light_filter)
            self._apply_filters()

    def action_filter_dark(self) -> None:
        """Set light filter to Dark only."""
        if self.extract_light:
            self.light_filter = "dark"
            self._highlight_light_filter(self.light_filter)
            self._apply_filters()

    def action_inspect(self) -> None:
        """Display detailed metadata for the selected history row."""
        row = self._get_row_at_cursor()
        if row is None:
            self.notify("Select an experiment row first", severity="warning", timeout=3)
            return

        proc = row.get("proc", "Experiment")
        seq = row.get("seq", "?")
        title = f"{proc} – Seq {seq}"
        self.app.push_screen(HistoryDetailModal(title, row))

    def action_plot(self) -> None:
        """Send the selected experiment to the preview flow."""
        row = self._get_row_at_cursor()
        if row is None:
            self.notify("Select an experiment row first", severity="warning", timeout=3)
            return

        seq = row.get("seq")
        proc = str(row.get("proc", "") or "")
        plot_type = self._map_proc_to_plot_type(proc)

        if seq is None:
            self.notify("Selected row is missing a sequence number", severity="error", timeout=4)
            return
        if plot_type is None:
            self.notify(f"Unsupported procedure '{proc}' for plotting", severity="error", timeout=4)
            return

        try:
            seq_int = int(seq)
        except (TypeError, ValueError):
            self.notify(f"Invalid sequence value '{seq}'", severity="error", timeout=4)
            return

        # Update session state for preview
        self.app.session.seq_numbers = [seq_int]
        self.app.session.selection_mode = "filtered"
        self.app.session.plot_type = plot_type

        try:
            self.app.router.go_to_preview()
        except Exception as exc:
            self.notify(str(exc), severity="error", timeout=4)

    # ───── Event Handlers ───────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id in {"light-all", "light-light", "light-dark"}:
            mapping = {
                "light-all": "all",
                "light-light": "light",
                "light-dark": "dark",
            }
            self.light_filter = mapping[button_id]
            self._highlight_light_filter(self.light_filter)
            self._apply_filters()

    def on_select_changed(self, event: Select.Changed) -> None:
        """React to procedure selection changes."""
        if event.select.id == "procedure-select":
            # Explicitly check for Select.BLANK since it's a truthy enum value
            from textual.widgets import Select
            self.proc_filter = event.value if event.value is not Select.BLANK else "All"
            self._apply_filters()

    # ───── Helpers ──────────────────────────────────────────────────────────────

    def _get_row_at_cursor(self) -> Optional[dict]:
        """Return the history row corresponding to the current cursor."""
        if not self.table or self.table.cursor_row is None:
            return None
        if self.filtered_df is None:
            return None
        row_idx = self.table.cursor_row
        if row_idx < 0 or row_idx >= self.filtered_df.height:
            return None
        return self.filtered_df.row(row_idx, named=True)

    @staticmethod
    def _map_proc_to_plot_type(proc: str) -> Optional[str]:
        """Map manifest procedure names to UI plot types."""
        mapping = {
            "It": "ITS",
            "ITS": "ITS",
            "IVg": "IVg",
            "IVG": "IVg",
            "Transconductance": "Transconductance",
        }
        return mapping.get(proc.strip())


class HistoryDetailModal(ModalScreen[None]):
    """Modal dialog showing detailed metadata for a history row."""

    CSS = """
    HistoryDetailModal {
        align: center middle;
    }

    #modal-container {
        width: 90%;
        max-width: 120;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 2 3;
    }

    #modal-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #modal-scroll {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    .detail-line {
        margin-bottom: 0;
    }

    #modal-actions {
        dock: bottom;
        width: 100%;
        height: auto;
        padding: 1 0 0 0;
        align: center middle;
    }
    """

    def __init__(self, title: str, row: dict):
        super().__init__()
        self.modal_title = title
        self.row = row

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Static(self.modal_title, id="modal-title")
            with VerticalScroll(id="modal-scroll"):
                for k, v in self._iter_details():
                    yield Static(self._format_detail(k, v), classes="detail-line")
            with Horizontal(id="modal-actions"):
                yield Button("Close", id="modal-close", variant="primary")

    def on_mount(self) -> None:
        close_button = self.query_one("#modal-close", Button)
        close_button.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-close":
            self.dismiss()

    def _iter_details(self) -> Iterable[Tuple[str, str]]:
        for key in sorted(self.row.keys()):
            value = self.row[key]
            yield key, self._stringify(value)

    @staticmethod
    def _stringify(value) -> str:
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    @staticmethod
    def _format_detail(key: str, value: str) -> str:
        return f"[bold]{key}:[/bold] {value}"
