"""
Interactive experiment selector using Textual TUI.

Provides a terminal-based UI for browsing and selecting experiments
from chip history for plotting commands.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional

import polars as pl
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Input,
    Static,
    Label,
    Button,
)
from textual.binding import Binding
from textual.screen import Screen


class ExperimentSelectorScreen(Screen):
    """Screen for selecting experiments interactively."""

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select", priority=True),
        Binding("space", "toggle", "Toggle"),
        Binding("ctrl+a", "select_all", "Select All"),
        Binding("ctrl+d", "deselect_all", "Deselect All"),
        Binding("ctrl+f", "focus_search", "Search"),
        Binding("slash", "focus_search", "Search", show=False),
    ]

    CSS = """
    #main-container {
        width: 100%;
        height: 100%;
        layout: vertical;
        padding: 0;
    }

    #title {
        text-align: left;
        text-style: bold;
        color: cyan;
        height: 1;
        padding: 0 2;
    }

    #stats {
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

    #search-bar {
        height: auto;
        padding: 0 2;
        margin-bottom: 1;
    }

    #search-label {
        width: 10;
    }

    #search-input {
        width: 1fr;
    }

    #light-filter-bar {
        height: auto;
        padding: 0 2;
        margin: 0 0 1 0;
        layout: horizontal;
    }

    #light-filter-label {
        width: 16;
    }

    .light-filter-button {
        min-width: 14;
        margin-right: 1;
    }

    #table-container {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        margin: 0;
    }

    #experiments-table {
        width: 100%;
        height: auto;
    }

    #selection-count {
        text-align: center;
        height: 1;
        dock: bottom;
    }
    """

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        history_df: pl.DataFrame,
        proc_filter: Optional[str] = None,
        title: str = "Select Experiments",
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.history_df = history_df
        self.proc_filter = proc_filter
        self.title_text = title
        self.selected_rows: set[int] = set()  # Track selected row indices
        self.row_to_seq: dict[int, int] = {}  # Map table row to seq number
        self.light_filter: Optional[str] = None  # Track light filter: None, "light", "dark"

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()

        with Container(id="main-container"):
            # Title and stats
            yield Static(self.title_text, id="title")
            yield Static("", id="stats")

            # Controls (always visible at top)
            yield Static(
                "[bold]Controls:[/bold] Space=Toggle  Enter=Select  Esc=Cancel  Ctrl+A=All  Ctrl+D=Clear  Ctrl+F=Search",
                id="controls-text"
            )

            # Spacer for visual separation
            yield Static("", id="spacer")

            # Search bar
            with Horizontal(id="search-bar"):
                yield Label("Filter:", id="search-label")
                yield Input(placeholder="Type to filter...", id="search-input")

            # Light filter buttons (show for time-series experiments: It, Vt)
            # These are procedures with light/dark cycling capabilities
            is_time_series = self.proc_filter in ["ITS", "It", "Vt"]
            if is_time_series and "has_light" in self.history_df.columns:
                with Horizontal(id="light-filter-bar"):
                    yield Label("Light Filter:", id="light-filter-label")
                    yield Button("All", id="light-filter-all", classes="light-filter-button", variant="primary")
                    yield Button("💡 Light Only", id="light-filter-light", classes="light-filter-button")
                    yield Button("🌙 Dark Only", id="light-filter-dark", classes="light-filter-button")

            # Main data table wrapped in scroll container
            with VerticalScroll(id="table-container"):
                yield DataTable(id="experiments-table", cursor_type="row")

            # Selection count
            yield Static("", id="selection-count")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the table when mounted."""
        self._populate_table()
        self._update_stats()
        self._update_selection_count()

        # Focus the table by default (not the search input)
        table = self.query_one("#experiments-table", DataTable)
        table.focus()

    def _is_time_series_proc(self) -> bool:
        """Check if current procedure is a time-series measurement (It/ITS, Vt)."""
        return self.proc_filter in ["ITS", "It", "Vt"]

    def _populate_table(self, filter_text: str = "") -> None:
        """Populate the data table with experiments."""
        table = self.query_one("#experiments-table", DataTable)
        table.clear(columns=True)

        # Get the scroll container and scroll to top when repopulating
        try:
            scroll_container = self.query_one("#table-container", VerticalScroll)
            scroll_container.scroll_home(animate=False)
        except Exception:
            pass

        # Filter data first to check available columns
        df = self.history_df

        # Apply procedure filter if specified
        if self.proc_filter:
            # Handle both "ITS" and "It" for current vs time measurements
            # Note: chip history uses "It" but plotting commands use "ITS"
            if self.proc_filter == "ITS":
                df = df.filter(pl.col("proc").is_in(["ITS", "It"]))
            else:
                df = df.filter(pl.col("proc") == self.proc_filter)

        # Apply light filter (for time-series experiments with has_light column)
        if self.light_filter and "has_light" in df.columns:
            if self.light_filter == "light":
                # Filter for light experiments (has_light == True)
                # Handle both boolean and string representations
                df = df.filter(
                    (pl.col("has_light") == True) |
                    (pl.col("has_light").cast(pl.Utf8).str.to_lowercase() == "true")
                )
            elif self.light_filter == "dark":
                # Filter for dark experiments (has_light == False)
                df = df.filter(
                    (pl.col("has_light") == False) |
                    (pl.col("has_light").cast(pl.Utf8).str.to_lowercase() == "false")
                )

        # Apply text filter
        if filter_text:
            filter_lower = filter_text.lower()
            # Filter by multiple columns
            mask = (
                pl.col("summary").cast(pl.Utf8).str.to_lowercase().str.contains(filter_lower) |
                pl.col("proc").cast(pl.Utf8).str.to_lowercase().str.contains(filter_lower) |
                pl.col("date").cast(pl.Utf8).str.contains(filter_lower)
            )
            df = df.filter(mask)

        # Sort by seq
        df = df.sort("seq")

        # Add columns (different based on procedure type)
        table.add_column("✓", width=3)

        # Add light indicator column for time-series experiments (if has_light exists)
        if self._is_time_series_proc() and "has_light" in df.columns:
            table.add_column("💡", width=3)

        table.add_column("Seq", width=5)
        table.add_column("Date", width=12)
        table.add_column("Time", width=10)

        # For IVg experiments, VG is swept so show VDS instead
        # For time-series experiments (It, Vt), show VG (gate bias during measurement)
        if self.proc_filter == "IVg":
            table.add_column("VDS (V)", width=8)
        else:
            table.add_column("VG (V)", width=8)

        table.add_column("λ (nm)", width=8)
        table.add_column("LED V", width=7)

        # Add Duration column for time-series experiments (It, Vt)
        if self._is_time_series_proc():
            table.add_column("Duration", width=10)

        # Clear row mappings
        self.row_to_seq.clear()

        # Add rows
        for idx, row in enumerate(df.iter_rows(named=True)):
            seq = int(row["seq"])
            self.row_to_seq[idx] = seq

            # Extract data
            date_str = str(row.get("date", ""))
            time_str = str(row.get("time_hms", ""))
            summary = str(row.get("summary", ""))

            # Get voltage info based on procedure type
            # For IVg: show VDS (since VG is swept)
            # For ITS: show VG (gate bias during measurement)
            if self.proc_filter == "IVg":
                voltage_val = self._extract_vds(row)
            else:
                voltage_val = self._extract_vg(row)
            voltage_str = f"{voltage_val:.2f}" if voltage_val is not None else "-"

            # Get wavelength
            wl_val = self._extract_wavelength(row)
            wl_str = f"{int(wl_val)}" if wl_val is not None else "-"

            # Get LED voltage
            led_val = self._extract_led_voltage(row)
            led_str = f"{led_val:.2f}" if led_val is not None else "-"

            # Check mark if selected
            check = "✓" if idx in self.selected_rows else " "

            # Get light indicator if column exists (for time-series experiments)
            has_light_col = self._is_time_series_proc() and "has_light" in df.columns
            if has_light_col:
                has_light = row.get("has_light")
                # Convert string representation back to boolean for comparison
                if isinstance(has_light, str):
                    if has_light.lower() == "true":
                        has_light = True
                    elif has_light.lower() == "false":
                        has_light = False
                    else:
                        has_light = None

                if has_light is True:
                    light_icon = "💡"
                elif has_light is False:
                    light_icon = "🌙"
                else:
                    light_icon = "[red]❗[/red]"

            # Build row data based on procedure type
            row_data = [check]

            # Add light indicator for time-series experiments if column exists
            if has_light_col:
                row_data.append(light_icon)

            # Add common columns
            row_data.extend([
                str(seq),
                date_str,
                time_str,
                voltage_str,
                wl_str,
                led_str,
            ])

            # Add Duration for time-series experiments (It, Vt)
            if self._is_time_series_proc():
                duration = self._extract_duration(row)
                row_data.append(duration)

            table.add_row(*row_data, key=str(idx))

    def _extract_vds(self, row: dict) -> Optional[float]:
        """Extract VDS value from row."""
        if "vds_v" in row and row["vds_v"] is not None:
            try:
                return float(row["vds_v"])
            except (TypeError, ValueError):
                pass

        # Try direct VDS/VSD columns
        for key in ["VDS", "VSD", "Vds", "Vsd", "VDS (V)", "VSD (V)"]:
            if key in row:
                try:
                    val = float(row[key])
                    return val
                except (TypeError, ValueError):
                    pass

        # Try parsing from summary
        summary = str(row.get("summary", ""))
        import re
        m = re.search(r"VDS=([-+]?\d+\.?\d*)", summary)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

        return None

    def _extract_vg(self, row: dict) -> Optional[float]:
        """Extract VG value from row."""
        if "vg_fixed_v" in row and row["vg_fixed_v"] is not None:
            try:
                return float(row["vg_fixed_v"])
            except (TypeError, ValueError):
                pass

        # Try direct VG column
        for key in ["VG", "Vg", "VG (V)", "Gate voltage"]:
            if key in row:
                try:
                    val = float(row[key])
                    return val
                except (TypeError, ValueError):
                    pass

        # Try parsing from summary
        summary = str(row.get("summary", ""))
        import re
        m = re.search(r"VG=([-+]?\d+\.?\d*)", summary)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

        return None

    def _extract_wavelength(self, row: dict) -> Optional[float]:
        """Extract wavelength from row."""
        if "wavelength_nm" in row and row["wavelength_nm"] is not None:
            try:
                return float(row["wavelength_nm"])
            except (TypeError, ValueError):
                pass

        # Try summary first (most reliable for this dataset)
        summary = str(row.get("summary", ""))
        import re
        m = re.search(r"λ=([\d.]+)\s*nm", summary)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

        # Try metadata columns
        for key in ["Laser wavelength", "Wavelength", "lambda"]:
            if key in row:
                try:
                    val = float(row[key])
                    if val > 0:
                        return val
                except (TypeError, ValueError):
                    pass

        return None

    def _extract_led_voltage(self, row: dict) -> Optional[float]:
        """Extract LED/Laser voltage from row."""
        if "laser_voltage_v" in row and row["laser_voltage_v"] is not None:
            try:
                return float(row["laser_voltage_v"])
            except (TypeError, ValueError):
                pass

        # Try summary first
        summary = str(row.get("summary", ""))
        import re
        m = re.search(r"VL=([\d.]+)", summary)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

        # Try metadata columns
        for key in ["Laser voltage", "LED voltage", "VL"]:
            if key in row:
                try:
                    val = float(row[key])
                    return val
                except (TypeError, ValueError):
                    pass

        return None

    def _extract_duration(self, row: dict) -> str:
        """Extract and calculate duration from time-series experiment (It, Vt).

        Duration = (Laser ON+OFF period) * 1.5

        The "Laser ON+OFF period" is the sum of ON time + OFF time.
        Duration is calculated as 1.5x this period.
        """
        if "laser_period_s" in row and row["laser_period_s"] is not None:
            try:
                period = float(row["laser_period_s"])
                if period > 0:
                    duration = period * 1.5
                    if duration == int(duration):
                        return f"{int(duration)}s"
                    return f"{duration:.1f}s"
            except (TypeError, ValueError):
                pass

        # Try to get "Laser ON+OFF period" from metadata
        for key in ["Laser ON+OFF period", "Laser ON+OFF period (s)", "ON+OFF period"]:
            if key in row:
                try:
                    period = float(row[key])
                    if period > 0:
                        duration = period * 1.5
                        # Format nicely (remove .0 if whole number)
                        if duration == int(duration):
                            return f"{int(duration)}s"
                        else:
                            return f"{duration:.1f}s"
                except (TypeError, ValueError):
                    pass

        # Try to extract from summary field as fallback
        summary = str(row.get("summary", ""))
        import re

        # Look for pattern like "120s period" or "period: 120s"
        m = re.search(r"(?:period|ON\+OFF)[:=\s]+(\d+\.?\d*)s?", summary, re.IGNORECASE)
        if m:
            try:
                period = float(m.group(1))
                duration = period * 1.5
                if duration == int(duration):
                    return f"{int(duration)}s"
                else:
                    return f"{duration:.1f}s"
            except ValueError:
                pass

        # Default: unknown
        return "-"

    def _update_stats(self) -> None:
        """Update the statistics display."""
        total = self.history_df.height
        proc_counts = self.history_df.group_by("proc").agg(pl.count()).sort("proc")

        proc_str = "  ".join([
            f"{row['proc']}: {row['count']}"
            for row in proc_counts.iter_rows(named=True)
        ])

        stats_widget = self.query_one("#stats", Static)
        stats_widget.update(
            f"[bold]{self.chip_group}{self.chip_number}[/bold]  |  "
            f"Total: {total}  |  {proc_str}"
        )

    def _update_selection_count(self) -> None:
        """Update the selection count display."""
        count_widget = self.query_one("#selection-count", Static)
        count = len(self.selected_rows)
        if count > 0:
            seq_nums = sorted([self.row_to_seq[idx] for idx in self.selected_rows])
            seq_str = ", ".join(map(str, seq_nums[:10]))
            if len(seq_nums) > 10:
                seq_str += f", ... ({len(seq_nums) - 10} more)"
            count_widget.update(f"[bold green]Selected: {count}[/bold green]  |  Seq: {seq_str}")
        else:
            count_widget.update("[dim]No experiments selected[/dim]")

    def _refresh_table_checkmarks(self) -> None:
        """Refresh the checkmarks in the table."""
        # Instead of updating individual cells, we need to rebuild the rows
        # because DataTable doesn't support easy cell updates by column name
        table = self.query_one("#experiments-table", DataTable)

        # Save cursor position
        cursor_row = table.cursor_row

        # Get current filter from search input
        search_input = self.query_one("#search-input", Input)
        filter_text = search_input.value if search_input else ""

        # Repopulate table (which will use current selection state)
        self._populate_table(filter_text=filter_text)

        # Restore cursor position if possible
        if cursor_row is not None and cursor_row < len(self.row_to_seq):
            table.move_cursor(row=cursor_row)

    def action_toggle(self) -> None:
        """Toggle selection of the current row."""
        table = self.query_one("#experiments-table", DataTable)
        if table.cursor_row is not None:
            row_idx = table.cursor_row
            if row_idx in self.selected_rows:
                self.selected_rows.remove(row_idx)
            else:
                self.selected_rows.add(row_idx)

            self._refresh_table_checkmarks()
            self._update_selection_count()

    def action_select_all(self) -> None:
        """Select all rows."""
        self.selected_rows = set(range(len(self.row_to_seq)))
        self._refresh_table_checkmarks()
        self._update_selection_count()

    def action_deselect_all(self) -> None:
        """Deselect all rows."""
        self.selected_rows.clear()
        self._refresh_table_checkmarks()
        self._update_selection_count()

    def action_select(self) -> None:
        """Confirm selection and return."""
        if not self.selected_rows:
            self.app.bell()  # Beep if nothing selected
            return

        # Get selected seq numbers
        selected_seqs = sorted([self.row_to_seq[idx] for idx in self.selected_rows])
        self.dismiss(selected_seqs)

    def action_cancel(self) -> None:
        """Cancel and return None."""
        self.dismiss(None)

    def action_quit(self) -> None:
        """Quit the app."""
        self.app.exit()

    def action_focus_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            # Save current selections
            selected_seqs = {self.row_to_seq[idx] for idx in self.selected_rows}

            # Repopulate table with filter
            self._populate_table(filter_text=event.value)

            # Restore selections
            self.selected_rows.clear()
            for idx, seq in self.row_to_seq.items():
                if seq in selected_seqs:
                    self.selected_rows.add(idx)

            self._refresh_table_checkmarks()
            self._update_selection_count()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle light filter button presses."""
        button_id = event.button.id

        if button_id in ["light-filter-all", "light-filter-light", "light-filter-dark"]:
            # Save current selections
            selected_seqs = {self.row_to_seq[idx] for idx in self.selected_rows}

            # Update filter state
            if button_id == "light-filter-all":
                self.light_filter = None
            elif button_id == "light-filter-light":
                self.light_filter = "light"
            elif button_id == "light-filter-dark":
                self.light_filter = "dark"

            # Update button variants to show active state
            try:
                all_btn = self.query_one("#light-filter-all", Button)
                light_btn = self.query_one("#light-filter-light", Button)
                dark_btn = self.query_one("#light-filter-dark", Button)

                all_btn.variant = "primary" if self.light_filter is None else "default"
                light_btn.variant = "primary" if self.light_filter == "light" else "default"
                dark_btn.variant = "primary" if self.light_filter == "dark" else "default"
            except Exception:
                pass  # Buttons might not exist if not ITS procedure

            # Get current search text
            search_input = self.query_one("#search-input", Input)
            filter_text = search_input.value

            # Repopulate table with filters
            self._populate_table(filter_text=filter_text)

            # Restore selections
            self.selected_rows.clear()
            for idx, seq in self.row_to_seq.items():
                if seq in selected_seqs:
                    self.selected_rows.add(idx)

            self._refresh_table_checkmarks()
            self._update_selection_count()


class ExperimentSelectorApp(App):
    """Main application for experiment selection."""

    CSS = """
    #main-container {
        height: 100%;
        layout: vertical;
    }

    #title {
        text-align: left;
        text-style: bold;
        color: cyan;
        height: 1;
        padding: 0 2;
    }

    #stats {
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

    #search-bar {
        height: 1;
        padding: 0 2;
    }

    #search-label {
        width: 10;
    }

    #search-input {
        width: 1fr;
    }

    #table-container {
        height: 1fr;
        border: solid $primary;
        margin: 0 2;
    }

    #experiments-table {
        height: auto;
    }

    #selection-count {
        text-align: center;
        height: 1;
        dock: bottom;
    }
    """

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        history_dir: Path,
        proc_filter: Optional[str] = None,
        title: str = "Select Experiments",
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.history_dir = history_dir
        self.proc_filter = proc_filter
        self.title_text = title
        self.selected_seqs: Optional[List[int]] = None

    def on_mount(self) -> None:
        """Load history and show selector screen."""

        self.theme = "tokyo-night"

        # Load chip history from Parquet file
        chip_name = f"{self.chip_group}{self.chip_number}"
        history_file = self.history_dir / f"{chip_name}_history.parquet"

        if not history_file.exists():
            self.exit(message=f"History file not found: {history_file}")
            return

        history_df = pl.read_parquet(history_file)

        if history_df.height == 0:
            self.exit(message=f"No experiments found for {self.chip_group}{self.chip_number}")
            return

        # Push the selector screen
        screen = ExperimentSelectorScreen(
            self.chip_number,
            self.chip_group,
            history_df,
            self.proc_filter,
            self.title_text
        )

        self.push_screen(screen, callback=self._on_selection)

    def _on_selection(self, result: Optional[List[int]]) -> None:
        """Handle selection result."""
        self.selected_seqs = result
        self.exit()


def select_experiments_interactive(
    chip_number: int,
    chip_group: str = "Alisson",
    metadata_dir: Path = Path("metadata"),
    raw_dir: Path = Path("."),
    proc_filter: Optional[str] = None,
    title: str = "Select Experiments",
) -> Optional[List[int]]:
    """
    Launch interactive experiment selector.

    Parameters
    ----------
    chip_number : int
        Chip number to browse
    chip_group : str
        Chip group name (default: "Alisson")
    metadata_dir : Path
        Metadata directory path
    raw_dir : Path
        Raw data directory path
    proc_filter : str, optional
        Filter by procedure type (e.g., "ITS", "IVg")
    title : str
        Title to display in the selector

    Returns
    -------
    List[int] or None
        List of selected seq numbers, or None if cancelled

    Example
    -------
    >>> seq_nums = select_experiments_interactive(67, proc_filter="ITS")
    >>> if seq_nums:
    ...     print(f"Selected: {seq_nums}")
    """
    app = ExperimentSelectorApp(
        chip_number,
        chip_group,
        metadata_dir,
        raw_dir,
        proc_filter,
        title
    )
    app.run()
    return app.selected_seqs
