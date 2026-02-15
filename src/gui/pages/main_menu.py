"""
Main Menu Page.

Welcome screen with chip stats and quick-action buttons.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class MainMenuPage(QWidget):
    """Welcome page with chip statistics and navigation shortcuts."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Title
        title = QLabel("Biotite Lab Plotter")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Optothermal semiconductor device characterization")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        # Separator
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Stats row
        stats_header = QLabel("Data Overview")
        stats_header.setObjectName("section-header")
        layout.addWidget(stats_header)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(32)

        self._chip_count_label = self._make_stat("--", "Chips")
        self._experiment_count_label = self._make_stat("--", "Experiments")
        self._config_count_label = self._make_stat("--", "Saved Configs")

        for stat_widget in (self._chip_count_label, self._experiment_count_label, self._config_count_label):
            stats_row.addWidget(stat_widget)
        stats_row.addStretch()

        layout.addLayout(stats_row)

        # Separator
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # Quick actions
        actions_header = QLabel("Quick Actions")
        actions_header.setObjectName("section-header")
        layout.addWidget(actions_header)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        new_plot_btn = QPushButton("New Plot")
        new_plot_btn.setObjectName("primary-btn")
        new_plot_btn.setFixedHeight(44)
        new_plot_btn.clicked.connect(lambda: self._window.router.navigate_to("chip_selector"))
        actions_row.addWidget(new_plot_btn)

        process_btn = QPushButton("Process Data")
        process_btn.setFixedHeight(44)
        process_btn.clicked.connect(lambda: self._window.router.navigate_to("data_pipeline_menu"))
        actions_row.addWidget(process_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        layout.addStretch()

    def _make_stat(self, value: str, label: str) -> QWidget:
        """Create a stat display widget."""
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)

        val_label = QLabel(value)
        val_label.setObjectName("stat-value")
        vbox.addWidget(val_label)

        desc_label = QLabel(label)
        desc_label.setObjectName("stat-label")
        vbox.addWidget(desc_label)

        # Store reference for updating
        container._value_label = val_label
        return container

    def on_enter(self, **kwargs) -> None:
        """Refresh stats when entering the page."""
        try:
            from src.tui.utils import discover_chips
            chips = discover_chips(self._window.session.history_dir, self._window.session.chip_group)
            total_experiments = sum(c.total_experiments for c in chips)
            self._chip_count_label._value_label.setText(str(len(chips)))
            self._experiment_count_label._value_label.setText(str(total_experiments))
        except Exception:
            self._chip_count_label._value_label.setText("?")
            self._experiment_count_label._value_label.setText("?")

        try:
            stats = self._window.config_manager.get_stats()
            self._config_count_label._value_label.setText(str(stats["total_count"]))
        except Exception:
            self._config_count_label._value_label.setText("0")
