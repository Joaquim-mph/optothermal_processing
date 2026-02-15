"""
Preview Page.

Read-only summary of the current configuration before plot generation.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QFrame,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class PreviewPage(QWidget):
    """Configuration preview before generation."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Review Configuration")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Verify settings before generating the plot")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Summary text
        self._summary = QPlainTextEdit()
        self._summary.setReadOnly(True)
        layout.addWidget(self._summary, stretch=1)

        # Navigation
        nav_row = QHBoxLayout()

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)

        nav_row.addStretch()

        generate_btn = QPushButton("Generate Plot")
        generate_btn.setObjectName("primary-btn")
        generate_btn.clicked.connect(self._on_generate)
        nav_row.addWidget(generate_btn)

        layout.addLayout(nav_row)

    def on_enter(self, **kwargs) -> None:
        """Build and display the configuration summary."""
        s = self._window.session
        lines = []
        lines.append(f"Chip:           {s.chip_group}{s.chip_number}")
        lines.append(f"Plot Type:      {s.plot_type}")
        lines.append(f"Experiments:    {len(s.seq_numbers)} selected")
        lines.append(f"Seq Numbers:    {', '.join(map(str, s.seq_numbers[:20]))}")
        if len(s.seq_numbers) > 20:
            lines.append(f"                ... and {len(s.seq_numbers) - 20} more")
        lines.append("")

        if s.plot_type == "ITS":
            lines.append("─── ITS Settings ───")
            lines.append(f"Legend by:       {s.legend_by}")
            lines.append(f"Baseline mode:   {s.baseline_mode}")
            if s.baseline_mode == "fixed":
                lines.append(f"Baseline time:   {s.baseline} s")
            elif s.baseline_mode == "auto":
                lines.append(f"Auto divisor:    {s.baseline_auto_divisor}")
            lines.append(f"Plot start:      {s.plot_start_time} s")
            lines.append(f"Y padding:       {s.padding}")
            lines.append(f"Duration check:  {s.check_duration_mismatch}")

        elif s.plot_type == "Transconductance":
            lines.append("─── Transconductance Settings ───")
            lines.append(f"Method:          {s.method}")
            if s.method == "savgol":
                lines.append(f"Window length:   {s.window_length}")
                lines.append(f"Poly order:      {s.polyorder}")

        elif s.plot_type in ("VVg", "Vt"):
            lines.append(f"─── {s.plot_type} Settings ───")
            lines.append(f"Mode:            {s.vvg_vt_mode}")
            if s.plot_type == "Vt":
                lines.append(f"Legend by:       {s.legend_by}")
                lines.append(f"Baseline mode:   {s.baseline_mode}")

        elif s.plot_type == "CNP":
            lines.append("─── CNP Settings ───")
            lines.append(f"Metric:          {s.cnp_metric}")
            lines.append(f"Show illumination: {s.cnp_show_illumination}")

        elif s.plot_type == "Photoresponse":
            lines.append("─── Photoresponse Settings ───")
            lines.append(f"Mode:            {s.photoresponse_mode}")
            lines.append(f"Filter Vg:       {s.photoresponse_filter_vg or 'None'}")
            lines.append(f"Filter WL:       {s.photoresponse_filter_wl or 'None'}")
            lines.append(f"Normalize:       {s.photoresponse_normalize}")

        lines.append("")
        lines.append(f"Output dir:     {s.output_dir}")
        lines.append(f"History dir:    {s.history_dir}")
        lines.append(f"Stage dir:      {s.stage_dir}")

        self._summary.setPlainText("\n".join(lines))

    def _on_generate(self) -> None:
        """Start plot generation."""
        self._window.router.navigate_to("plot_generation")
