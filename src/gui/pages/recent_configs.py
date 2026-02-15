"""
Recent Configurations Page.

Lists saved plot configurations with load/delete actions.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class RecentConfigsPage(QWidget):
    """Recent plot configurations with load/delete actions."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._config_ids: list[str] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Recent Configurations")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Load previously saved plot configurations")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        self._stats_label = QLabel("")
        self._stats_label.setObjectName("info-label")
        layout.addWidget(self._stats_label)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Table
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Date", "Time", "Description", "Type"])
        self._table.doubleClicked.connect(lambda: self._load_selected())
        layout.addWidget(self._table, stretch=1)

        # Action buttons
        btn_row = QHBoxLayout()

        load_btn = QPushButton("Load Config")
        load_btn.setObjectName("primary-btn")
        load_btn.clicked.connect(self._load_selected)
        btn_row.addWidget(load_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("danger-btn")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        btn_row.addWidget(back_btn)

        layout.addLayout(btn_row)

    def on_enter(self, **kwargs) -> None:
        self._populate_table()
        self._update_stats()

    def _populate_table(self) -> None:
        configs = self._window.config_manager.get_recent_configs()
        self._config_ids.clear()
        self._table.setRowCount(len(configs))

        for row_idx, entry in enumerate(configs):
            self._config_ids.append(entry["id"])

            timestamp = entry.get("timestamp", "")
            date_part = timestamp[:10]
            time_part = timestamp[11:19]
            description = entry.get("description", "")
            plot_type = entry.get("config", {}).get("plot_type", "?")

            for col_idx, text in enumerate([date_part, time_part, description, plot_type]):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._table.setItem(row_idx, col_idx, item)

        for col in range(4):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )

    def _update_stats(self) -> None:
        try:
            stats = self._window.config_manager.get_stats()
            total = stats.get("total_count", 0)
            by_type = stats.get("by_plot_type", {})
            types_str = ", ".join(f"{k}: {v}" for k, v in by_type.items())
            self._stats_label.setText(f"Total: {total} configs" + (f" ({types_str})" if types_str else ""))
        except Exception:
            self._stats_label.setText("")

    def _load_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._config_ids):
            return

        config_id = self._config_ids[row]
        config = self._window.config_manager.load_config(config_id)
        if config is None:
            return

        # Apply config to session
        for key, value in config.items():
            if hasattr(self._window.session, key):
                setattr(self._window.session, key, value)

        self._window.router.navigate_to("preview")

    def _delete_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._config_ids):
            return

        config_id = self._config_ids[row]
        self._window.config_manager.delete_config(config_id)
        self._populate_table()
        self._update_stats()
