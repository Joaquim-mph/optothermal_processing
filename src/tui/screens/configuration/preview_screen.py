"""
Preview Screen.

Step 5/6 of the wizard: Review configuration and selected experiments before generating plot.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Button
from textual.binding import Binding
from textual import events

from src.tui.screens.base import WizardScreen

try:
    import polars as pl
except ImportError:
    pl = None


class PreviewScreen(WizardScreen):
    """Preview screen showing configuration before plot generation (Step 6)."""

    SCREEN_TITLE = "Preview - Plot Configuration"
    STEP_NUMBER = 6

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        plot_type: str,
        seq_numbers: List[int],
        config: dict,
        history_dir: Optional[Path] = None,
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.seq_numbers = seq_numbers
        self.config = config
        self.history_dir = history_dir or Path("data/02_stage/chip_histories")

    BINDINGS = WizardScreen.BINDINGS + []

    # Preview-specific CSS (extends WizardScreen CSS)
    CSS = WizardScreen.CSS + """
    .info-text {
        color: $text;
        margin-left: 2;
        margin-bottom: 0;
    }

    .warning-text {
        color: $warning;
        text-style: italic;
        margin-left: 2;
        margin-bottom: 1;
    }

    .success-text {
        color: $success;
        margin-left: 2;
        margin-bottom: 1;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with title, chip info, and step indicator."""
        yield Static(f"{self.SCREEN_TITLE} - {self.plot_type}", id="title")
        yield Static(
            f"Chip: [bold]{self.chip_group}{self.chip_number}[/bold]",
            id="chip-info"
        )
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose preview content."""
        # Experiments Section
        yield Static("─── Experiments ────────────────────────", classes="section-title")
        yield Static(
            f"Selected: [bold]{len(self.seq_numbers)}[/bold] experiments",
            classes="info-text"
        )

        # Format seq numbers nicely
        seq_str = ", ".join(map(str, self.seq_numbers[:20]))
        if len(self.seq_numbers) > 20:
            seq_str += f", ... ({len(self.seq_numbers) - 20} more)"
        yield Static(f"Seq numbers: {seq_str}", classes="info-text")

        # Check for duration warnings (ITS only)
        duration_warning = self._check_duration_warnings()
        if duration_warning:
            yield Static(
                f"⚠ {duration_warning}",
                classes="warning-text"
            )

        # Configuration Section
        yield Static("─── Configuration ──────────────────────", classes="section-title")

        # Build config summary
        config_lines = self._build_config_summary()
        for line in config_lines:
            yield Static(line, classes="info-text")

        # Output Section
        yield Static("─── Output ─────────────────────────────", classes="section-title")

        # Generate output filename and directory (with automatic chip subdirectory)
        output_filename = self._generate_filename()
        base_output_dir = self.config.get("output_dir", "figs")

        # Apply same logic as plot_generation.py: always append chip subdirectory
        base_str = str(base_output_dir)
        chip_subdir_name = f"{self.chip_group}{self.chip_number}"

        # Check if the path already ends with the chip subdirectory
        if base_str.endswith(f"/{chip_subdir_name}") or base_str.endswith(f"/{chip_subdir_name}/"):
            output_dir = base_output_dir
        elif base_str.endswith(chip_subdir_name):
            output_dir = base_output_dir
        else:
            # Append chip subdirectory
            output_dir = f"{base_output_dir}/{chip_subdir_name}"

        yield Static(f"Directory: {output_dir}", classes="info-text")
        yield Static(f"Filename: {output_filename}", classes="info-text")

        # Check if file exists
        output_path = Path(output_dir) / output_filename
        if output_path.exists():
            yield Static(
                "⚠ Warning: File exists and will be overwritten",
                classes="warning-text"
            )
        else:
            yield Static(
                "✓ Ready to generate (file does not exist)",
                classes="success-text"
            )

        # Buttons
        with Horizontal(id="button-container"):
            yield Button("← Edit Config", id="back-button", variant="default", classes="nav-button")
            yield Button("Generate Plot", id="generate-button", variant="primary", classes="nav-button")
            yield Button("Save & Exit", id="save-button", variant="default", classes="nav-button")

    def on_mount(self) -> None:
        """Initialize screen."""
        # Focus the generate button
        generate_btn = self.query_one("#generate-button", Button)
        generate_btn.focus()

    def on_button_focus(self, event: Button.Focus) -> None:
        """Update button labels to show arrow on focused button."""
        # Remove arrows from all buttons
        for button in self.query(".nav-button").results(Button):
            label = str(button.label)
            if label.startswith("→ "):
                button.label = label[2:]  # Remove arrow

        # Add arrow to focused button
        focused_button = event.button
        label = str(focused_button.label)
        if not label.startswith("→ "):
            focused_button.label = f"→ {label}"

    def on_key(self, event: events.Key) -> None:
        """Handle arrow key navigation between buttons."""
        buttons = [
            self.query_one("#back-button", Button),
            self.query_one("#generate-button", Button),
            self.query_one("#save-button", Button),
        ]

        # Find currently focused button
        focused_idx = None
        for idx, button in enumerate(buttons):
            if button.has_focus:
                focused_idx = idx
                break

        if focused_idx is not None:
            if event.key in ("left", "up"):
                # Move focus left/up (previous button)
                new_idx = (focused_idx - 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()
            elif event.key in ("right", "down"):
                # Move focus right/down (next button)
                new_idx = (focused_idx + 1) % len(buttons)
                buttons[new_idx].focus()
                event.prevent_default()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "generate-button":
            self.action_generate()
        elif event.button.id == "save-button":
            self.action_save_exit()

    def action_generate(self) -> None:
        """Generate the plot using router."""
        # Navigate to plot generation screen using router
        self.app.router.go_to_plot_generation()

    def action_save_exit(self) -> None:
        """Save configuration and return to main menu."""
        # Save config to ConfigManager
        try:
            config_to_save = {
                **self.config,
                "chip_number": self.chip_number,
                "chip_group": self.chip_group,
                "plot_type": self.plot_type,
                "seq_numbers": self.seq_numbers,
            }
            config_id = self.app.config_manager.save_config(config_to_save)
            self.app.notify(
                f"✓ Configuration saved (ID: {config_id})",
                severity="information",
                timeout=3
            )
        except Exception as e:
            self.app.notify(
                f"Failed to save configuration: {e}",
                severity="error",
                timeout=3
            )

        # Return to main menu using router
        self.app.router.return_to_main_menu()

    def _build_config_summary(self) -> List[str]:
        """Build configuration summary lines."""
        lines = []

        # Selection mode
        mode = self.config.get("mode", "quick")
        selection_mode = self.config.get("selection_mode", "interactive")
        if mode == "quick":
            lines.append("• Mode: Quick Plot")
        else:
            lines.append(f"• Selection mode: {selection_mode.title()}")

        # Plot-specific options
        if self.plot_type == "ITS":
            # Show preset name if used
            preset_name = self.config.get("preset")
            if preset_name:
                from src.plotting.its_presets import get_preset
                preset = get_preset(preset_name)
                if preset:
                    lines.append(f"• Preset: {preset.name}")

            legend_by = self.config.get("legend_by", "led_voltage")
            legend_map = {
                "led_voltage": "LED Voltage",
                "wavelength": "Wavelength",
                "vg": "Gate Voltage"
            }
            lines.append(f"• Legend by: {legend_map.get(legend_by, legend_by)}")

            # Show baseline mode
            baseline_mode = self.config.get("baseline_mode", "fixed")
            if baseline_mode == "none":
                lines.append("• Baseline: None (RAW DATA - no correction)")
            elif baseline_mode == "auto":
                divisor = self.config.get("baseline_auto_divisor", 2.0)
                lines.append(f"• Baseline: Auto (LED period / {divisor})")
            else:  # fixed
                baseline = self.config.get("baseline", 60.0)
                if baseline == 0.0:
                    lines.append("• Baseline: 0.0 s (subtract value at t=0)")
                else:
                    lines.append(f"• Baseline time: {baseline} s")

            padding = self.config.get("padding", 0.05)
            lines.append(f"• Y-axis padding: {padding * 100:.1f}%")

            # Filters
            filters = []
            if self.config.get("vg_filter") is not None:
                filters.append(f"VG = {self.config['vg_filter']} V")
            if self.config.get("wavelength_filter") is not None:
                filters.append(f"λ = {self.config['wavelength_filter']} nm")
            if self.config.get("date_filter"):
                filters.append(f"Date = {self.config['date_filter']}")

            if filters:
                lines.append(f"• Filters: {', '.join(filters)}")

        elif self.plot_type == "IVg":
            # IVg-specific options
            if self.config.get("vds_filter") is not None:
                lines.append(f"• Filter: VDS = {self.config['vds_filter']} V")

        elif self.plot_type == "Transconductance":
            # Transconductance-specific options
            method = self.config.get("method", "gradient")
            lines.append(f"• Method: {method}")

            if method == "savgol":
                window = self.config.get("window_length", 9)
                polyorder = self.config.get("polyorder", 3)
                lines.append(f"• Savitzky-Golay: window={window}, polyorder={polyorder}")

        return lines

    def _generate_filename(self) -> str:
        """Generate output filename using standardized naming convention.

        Format: encap{N}_plottype_seq_X_Y_Z.png
        """
        # Generate plot tag from seq numbers (same logic as CLI)
        sorted_seqs = sorted(self.seq_numbers)

        if len(sorted_seqs) <= 5:
            # Short lists: readable format
            seq_str = "_".join(str(s) for s in sorted_seqs)
            plot_tag = f"seq_{seq_str}"
        else:
            # Long lists: first 3 + count + hash
            first_three = "_".join(str(s) for s in sorted_seqs[:3])
            import hashlib
            seq_hash = hashlib.md5("_".join(str(s) for s in sorted_seqs).encode()).hexdigest()[:6]
            plot_tag = f"seq_{first_three}_plus{len(sorted_seqs)-3}_{seq_hash}"

        # Standardized format: encap{N}_plottype_tag.png
        if self.plot_type == "ITS":
            # Check if raw data mode (add _raw suffix)
            baseline_mode = self.config.get("baseline_mode", "fixed")
            raw_suffix = "_raw" if baseline_mode == "none" else ""

            filename = f"encap{self.chip_number}_ITS_{plot_tag}{raw_suffix}.png"
        elif self.plot_type == "IVg":
            filename = f"encap{self.chip_number}_IVg_{plot_tag}.png"
        elif self.plot_type == "Transconductance":
            method = self.config.get("method", "gradient")
            if method == "savgol":
                filename = f"encap{self.chip_number}_gm_savgol_{plot_tag}.png"
            else:
                filename = f"encap{self.chip_number}_gm_{plot_tag}.png"
        else:
            # Fallback
            filename = f"encap{self.chip_number}_{self.plot_type}_{plot_tag}.png"

        return filename

    def _check_duration_warnings(self) -> Optional[str]:
        """Check for duration mismatch warnings in ITS experiments.

        Returns warning message if duration mismatch detected, None otherwise.
        """
        # Only check for ITS plots
        if self.plot_type != "ITS":
            return None

        # Only check if enabled in config
        if not self.config.get("check_duration_mismatch", False):
            return None

        # Need polars to load history
        if pl is None:
            return None

        try:
            # Load history file
            chip_name = f"{self.chip_group}{self.chip_number}"
            history_file = self.history_dir / f"{chip_name}_history.parquet"

            if not history_file.exists():
                return None

            # Load and filter history for selected seq numbers
            history = pl.read_parquet(history_file)
            meta = history.filter(pl.col("seq").is_in(self.seq_numbers))

            if meta.height == 0:
                return None

            # Get durations from metadata
            from src.plotting.its import _get_experiment_durations, _check_duration_mismatch

            # Get stage_dir from app config
            stage_dir = self.config.get("stage_dir", Path("data/02_stage/raw_measurements"))

            durations = _get_experiment_durations(meta, stage_dir)

            if not durations:
                return None

            # Check for mismatches
            tolerance = self.config.get("duration_tolerance", 0.10)
            has_mismatch, warning_msg = _check_duration_mismatch(durations, tolerance)

            if has_mismatch:
                return warning_msg

            return None

        except Exception:
            # Silently ignore errors during warning check
            return None
