"""
Batch Plot Page.

YAML config file selection with preview panel and run button.
Scans config/batch_plots/ for available batch configurations.
"""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QSizePolicy,
    QGraphicsDropShadowEffect, QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

if TYPE_CHECKING:
    from src.gui.app import MainWindow

BATCH_DIR = Path("config/batch_plots")


def _make_shadow(parent: QWidget | None = None) -> QGraphicsDropShadowEffect:
    shadow = QGraphicsDropShadowEffect(parent)
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 60))
    return shadow


class BatchPlotPage(QWidget):
    """YAML config selector with preview for batch plot generation."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._selected_path: Path | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Batch Plot")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Select a YAML config to generate multiple plots at once")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        # Main content: file list + preview
        content = QHBoxLayout()
        content.setSpacing(16)

        # Left panel: YAML file list
        left = QVBoxLayout()
        left.setSpacing(8)

        list_header = QLabel("Available Configs")
        list_header.setObjectName("section-header")
        left.addWidget(list_header)

        self._file_list = QListWidget()
        self._file_list.currentItemChanged.connect(self._on_selection_changed)
        left.addWidget(self._file_list)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._scan_configs)
        left.addWidget(refresh_btn)

        content.addLayout(left, stretch=1)

        # Right panel: preview
        right_frame = QFrame()
        right_frame.setObjectName("pipeline-card")
        right_frame.setGraphicsEffect(_make_shadow(right_frame))
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(8)

        self._preview_title = QLabel("No config selected")
        self._preview_title.setObjectName("card-title")
        right_layout.addWidget(self._preview_title)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        right_layout.addWidget(sep)

        self._preview_info = QLabel("")
        self._preview_info.setWordWrap(True)
        right_layout.addWidget(self._preview_info)

        self._preview_breakdown = QLabel("")
        self._preview_breakdown.setWordWrap(True)
        self._preview_breakdown.setObjectName("info-label")
        right_layout.addWidget(self._preview_breakdown)

        right_layout.addStretch()

        # Parallel execution options
        parallel_row = QHBoxLayout()
        parallel_row.setSpacing(8)

        self._parallel_check = QCheckBox("Parallel")
        self._parallel_check.setToolTip("Use multiple CPU cores for faster batch execution")
        self._parallel_check.toggled.connect(self._on_parallel_toggled)
        parallel_row.addWidget(self._parallel_check)

        workers_label = QLabel("Workers:")
        workers_label.setObjectName("settings-bar-label")
        parallel_row.addWidget(workers_label)

        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(2, 16)
        self._workers_spin.setValue(4)
        self._workers_spin.setEnabled(False)
        self._workers_spin.setToolTip("Number of parallel worker processes")
        parallel_row.addWidget(self._workers_spin)

        parallel_row.addStretch()
        right_layout.addLayout(parallel_row)

        self._run_btn = QPushButton("Run Batch")
        self._run_btn.setObjectName("primary-btn")
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run)
        right_layout.addWidget(self._run_btn)

        content.addWidget(right_frame, stretch=1)
        layout.addLayout(content, stretch=1)

    def on_enter(self, **kwargs) -> None:
        """Scan config directory and populate file list."""
        self._scan_configs()

    def _scan_configs(self) -> None:
        """Find all YAML files in config/batch_plots/."""
        self._file_list.clear()
        self._selected_path = None
        self._run_btn.setEnabled(False)
        self._preview_title.setText("No config selected")
        self._preview_info.setText("")
        self._preview_breakdown.setText("")

        if not BATCH_DIR.exists():
            self._preview_info.setText(f"Directory not found: {BATCH_DIR}")
            return

        yaml_files = sorted(BATCH_DIR.glob("*.yaml")) + sorted(BATCH_DIR.glob("*.yml"))
        if not yaml_files:
            self._preview_info.setText("No YAML configs found")
            return

        for path in yaml_files:
            item = QListWidgetItem(path.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._file_list.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem | None, _previous) -> None:
        """Parse the selected YAML and show preview."""
        if current is None:
            self._selected_path = None
            self._run_btn.setEnabled(False)
            self._preview_title.setText("No config selected")
            self._preview_info.setText("")
            self._preview_breakdown.setText("")
            return

        config_path = Path(current.data(Qt.ItemDataRole.UserRole))
        self._selected_path = config_path

        try:
            from src.plotting.batch import load_batch_config
            chip, chip_group, plot_specs = load_batch_config(config_path)

            self._preview_title.setText(config_path.stem)

            self._preview_info.setText(
                f"Chip: {chip}\n"
                f"Group: {chip_group}\n"
                f"Total plots: {len(plot_specs)}"
            )

            # Type breakdown
            type_counts: dict[str, int] = {}
            for spec in plot_specs:
                type_counts[spec.type] = type_counts.get(spec.type, 0) + 1

            breakdown_lines = []
            for ptype, count in sorted(type_counts.items()):
                breakdown_lines.append(f"  {ptype} ({count})")

            self._preview_breakdown.setText("\n".join(breakdown_lines))
            self._run_btn.setEnabled(True)

        except Exception as e:
            self._preview_title.setText("Error")
            self._preview_info.setText(f"Failed to parse config:\n{e}")
            self._preview_breakdown.setText("")
            self._run_btn.setEnabled(False)

    def _on_parallel_toggled(self, checked: bool) -> None:
        self._workers_spin.setEnabled(checked)

    def _on_run(self) -> None:
        """Navigate to batch progress page."""
        if self._selected_path:
            self._window.router.navigate_to(
                "batch_progress",
                config_path=str(self._selected_path),
                parallel=self._parallel_check.isChecked(),
                workers=self._workers_spin.value(),
            )
