"""
Tokyo Night QSS Theme for Biotite GUI.

Provides dark theme styling consistent with the TUI's tokyo-night theme.
"""

# Tokyo Night color palette
COLORS = {
    "bg": "#1a1b26",
    "bg_dark": "#16161e",
    "bg_highlight": "#292e42",
    "bg_sidebar": "#1f2335",
    "fg": "#c0caf5",
    "fg_dark": "#a9b1d6",
    "fg_gutter": "#3b4261",
    "comment": "#565f89",
    "blue": "#7aa2f7",
    "cyan": "#7dcfff",
    "green": "#9ece6a",
    "magenta": "#bb9af7",
    "orange": "#ff9e64",
    "red": "#f7768e",
    "yellow": "#e0af68",
    "border": "#3b4261",
    "selection": "#283457",
}

STYLESHEET = f"""
/* ═══════════════════════════════════════════
   Global
   ═══════════════════════════════════════════ */

QMainWindow {{
    background-color: {COLORS['bg']};
}}

QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['fg']};
    font-family: "Segoe UI", "Ubuntu", "Noto Sans", sans-serif;
    font-size: 13px;
}}

/* ═══════════════════════════════════════════
   Sidebar
   ═══════════════════════════════════════════ */

QWidget#sidebar {{
    background-color: {COLORS['bg_sidebar']};
    border-right: 1px solid {COLORS['border']};
    min-width: 180px;
    max-width: 180px;
}}

QPushButton#sidebar-btn {{
    background-color: transparent;
    color: {COLORS['fg_dark']};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    margin: 2px 8px;
}}

QPushButton#sidebar-btn:hover {{
    background-color: {COLORS['bg_highlight']};
    color: {COLORS['fg']};
}}

QPushButton#sidebar-btn:checked {{
    background-color: {COLORS['selection']};
    color: {COLORS['blue']};
    font-weight: bold;
}}

QPushButton#sidebar-btn-quit {{
    background-color: transparent;
    color: {COLORS['comment']};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    margin: 2px 8px;
}}

QPushButton#sidebar-btn-quit:hover {{
    background-color: {COLORS['red']};
    color: {COLORS['bg']};
}}

/* ═══════════════════════════════════════════
   Breadcrumb
   ═══════════════════════════════════════════ */

QLabel#breadcrumb {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['comment']};
    padding: 8px 16px;
    font-size: 12px;
    border-bottom: 1px solid {COLORS['border']};
}}

/* ═══════════════════════════════════════════
   Page Content
   ═══════════════════════════════════════════ */

QWidget#page-content {{
    background-color: {COLORS['bg']};
    padding: 24px;
}}

QLabel#page-title {{
    font-size: 22px;
    font-weight: bold;
    color: {COLORS['fg']};
    padding-bottom: 4px;
}}

QLabel#page-subtitle {{
    font-size: 14px;
    color: {COLORS['comment']};
    padding-bottom: 16px;
}}

QLabel#section-header {{
    font-size: 15px;
    font-weight: bold;
    color: {COLORS['blue']};
    padding: 12px 0 6px 0;
}}

QLabel#stat-value {{
    font-size: 28px;
    font-weight: bold;
    color: {COLORS['blue']};
}}

QLabel#stat-label {{
    font-size: 12px;
    color: {COLORS['comment']};
}}

/* ═══════════════════════════════════════════
   Buttons
   ═══════════════════════════════════════════ */

QPushButton {{
    background-color: {COLORS['bg_highlight']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {COLORS['selection']};
    border-color: {COLORS['blue']};
}}

QPushButton:pressed {{
    background-color: {COLORS['blue']};
    color: {COLORS['bg']};
}}

QPushButton:disabled {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['fg_gutter']};
    border-color: {COLORS['bg_dark']};
}}

QPushButton#primary-btn {{
    background-color: {COLORS['blue']};
    color: {COLORS['bg']};
    border: none;
    font-weight: bold;
    padding: 10px 28px;
}}

QPushButton#primary-btn:hover {{
    background-color: {COLORS['cyan']};
}}

QPushButton#primary-btn:pressed {{
    background-color: {COLORS['fg_dark']};
}}

QPushButton#danger-btn {{
    background-color: transparent;
    color: {COLORS['red']};
    border: 1px solid {COLORS['red']};
}}

QPushButton#danger-btn:hover {{
    background-color: {COLORS['red']};
    color: {COLORS['bg']};
}}

/* ═══════════════════════════════════════════
   Chip Cards
   ═══════════════════════════════════════════ */

QPushButton#chip-card {{
    background-color: {COLORS['bg_highlight']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 16px;
    text-align: left;
    min-width: 160px;
    min-height: 80px;
}}

QPushButton#chip-card:hover {{
    border-color: {COLORS['blue']};
    background-color: {COLORS['selection']};
}}

/* ═══════════════════════════════════════════
   Tables
   ═══════════════════════════════════════════ */

QTableView {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    gridline-color: {COLORS['bg_highlight']};
    selection-background-color: {COLORS['selection']};
    selection-color: {COLORS['fg']};
    alternate-background-color: {COLORS['bg']};
}}

QTableView::item {{
    padding: 6px 8px;
}}

QHeaderView::section {{
    background-color: {COLORS['bg_sidebar']};
    color: {COLORS['fg_dark']};
    padding: 8px;
    border: none;
    border-bottom: 2px solid {COLORS['blue']};
    font-weight: bold;
}}

/* ═══════════════════════════════════════════
   Form Inputs
   ═══════════════════════════════════════════ */

QComboBox {{
    background-color: {COLORS['bg_highlight']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {COLORS['blue']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_highlight']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['selection']};
    selection-color: {COLORS['blue']};
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_highlight']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 20px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {COLORS['blue']};
}}

QCheckBox {{
    color: {COLORS['fg']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    background-color: {COLORS['bg_highlight']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['blue']};
    border-color: {COLORS['blue']};
}}

QRadioButton {{
    color: {COLORS['fg']};
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    background-color: {COLORS['bg_highlight']};
}}

QRadioButton::indicator:checked {{
    background-color: {COLORS['blue']};
    border-color: {COLORS['blue']};
}}

/* ═══════════════════════════════════════════
   Progress Bar
   ═══════════════════════════════════════════ */

QProgressBar {{
    background-color: {COLORS['bg_dark']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    text-align: center;
    color: {COLORS['fg']};
    min-height: 24px;
}}

QProgressBar::chunk {{
    background-color: {COLORS['blue']};
    border-radius: 5px;
}}

/* ═══════════════════════════════════════════
   Scroll Areas
   ═══════════════════════════════════════════ */

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: {COLORS['bg_dark']};
    width: 10px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['fg_gutter']};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['comment']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {COLORS['bg_dark']};
    height: 10px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['fg_gutter']};
    border-radius: 5px;
    min-width: 30px;
}}

/* ═══════════════════════════════════════════
   Text Areas
   ═══════════════════════════════════════════ */

QPlainTextEdit {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 8px;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
}}

/* ═══════════════════════════════════════════
   Separator
   ═══════════════════════════════════════════ */

QFrame#separator {{
    background-color: {COLORS['border']};
    max-height: 1px;
    margin: 8px 0;
}}

/* ═══════════════════════════════════════════
   Status/Info Labels
   ═══════════════════════════════════════════ */

QLabel#success-label {{
    color: {COLORS['green']};
    font-size: 16px;
    font-weight: bold;
}}

QLabel#error-label {{
    color: {COLORS['red']};
    font-size: 16px;
    font-weight: bold;
}}

QLabel#info-label {{
    color: {COLORS['cyan']};
    font-size: 13px;
}}

QLabel#warning-label {{
    color: {COLORS['yellow']};
    font-size: 13px;
}}

/* ═══════════════════════════════════════════
   Tree Views (Plot Browser)
   ═══════════════════════════════════════════ */

QTreeView {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    selection-background-color: {COLORS['selection']};
    selection-color: {COLORS['fg']};
    alternate-background-color: {COLORS['bg']};
}}

QTreeView::item {{
    padding: 4px 6px;
}}

QTreeView::item:hover {{
    background-color: {COLORS['bg_highlight']};
}}

QTreeView::item:selected {{
    background-color: {COLORS['selection']};
    color: {COLORS['blue']};
}}

QTreeView::branch:has-children:closed {{
    border-image: none;
}}

QTreeView::branch:has-children:open {{
    border-image: none;
}}

/* ═══════════════════════════════════════════
   Splitter
   ═══════════════════════════════════════════ */

QSplitter::handle {{
    background-color: {COLORS['border']};
    width: 2px;
}}

QSplitter::handle:hover {{
    background-color: {COLORS['blue']};
}}

/* ═══════════════════════════════════════════
   QTableWidget (reuse QTableView styles)
   ═══════════════════════════════════════════ */

QTableWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    gridline-color: {COLORS['bg_highlight']};
    selection-background-color: {COLORS['selection']};
    selection-color: {COLORS['fg']};
    alternate-background-color: {COLORS['bg']};
}}

QTableWidget::item {{
    padding: 6px 8px;
}}

/* ═══════════════════════════════════════════
   Line Edit (search fields)
   ═══════════════════════════════════════════ */

QLineEdit {{
    background-color: {COLORS['bg_highlight']};
    color: {COLORS['fg']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 20px;
}}

QLineEdit:hover {{
    border-color: {COLORS['blue']};
}}

QLineEdit:focus {{
    border-color: {COLORS['blue']};
    border-width: 2px;
}}
"""
