"""
Chip Selector Page.

Displays a flow-layout grid of chip cards using discover_chips().
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from src.gui.app import MainWindow


class ChipSelectorPage(QWidget):
    """Chip selection page with auto-discovered chip cards."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self._window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # Header
        title = QLabel("Select Chip")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("Choose a chip to generate plots for")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        # Scrollable grid area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._grid_container)

        layout.addWidget(scroll, stretch=1)

        # Back button
        nav_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._window.router.go_back)
        nav_row.addWidget(back_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

    def on_enter(self, **kwargs) -> None:
        """Load chip list and populate the grid."""
        # Reset wizard state for a new plot
        self._window.session.reset_wizard_state()
        self._populate_chips()

    def _populate_chips(self) -> None:
        """Discover chips and create cards."""
        # Clear existing cards
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            from src.tui.utils import discover_chips
            chips = discover_chips(
                self._window.session.history_dir,
                self._window.session.chip_group,
            )
        except Exception:
            chips = []

        if not chips:
            empty_label = QLabel("No chips found. Run 'biotite full-pipeline' first.")
            empty_label.setObjectName("warning-label")
            self._grid_layout.addWidget(empty_label, 0, 0)
            return

        cols = 4
        for i, chip in enumerate(chips):
            row, col = divmod(i, cols)
            card = self._make_chip_card(chip)
            self._grid_layout.addWidget(card, row, col)

    def _make_chip_card(self, chip) -> QPushButton:
        """Create a chip card button."""
        text = (
            f"{chip.chip_group}{chip.chip_number}\n"
            f"{chip.total_experiments} experiments\n"
            f"{chip.its_count} ITS, {chip.ivg_count} IVg"
        )
        if chip.last_experiment_date:
            text += f"\nLast: {chip.last_experiment_date}"

        btn = QPushButton(text)
        btn.setObjectName("chip-card")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, c=chip: self._select_chip(c))
        return btn

    def _select_chip(self, chip) -> None:
        """Handle chip selection."""
        self._window.session.chip_number = chip.chip_number
        self._window.router.navigate_to("plot_type_selector")
