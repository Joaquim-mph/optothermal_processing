"""
Multi-theme QSS system for Biotite GUI.

Provides palette-driven stylesheet generation with 6 built-in themes.
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════
# Theme Palettes
# ═══════════════════════════════════════════════════════════════════

THEME_PALETTES: dict[str, dict[str, str]] = {
    "tokyo-night": {
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
    },
    "nord": {
        "bg": "#2e3440",
        "bg_dark": "#272c36",
        "bg_highlight": "#3b4252",
        "bg_sidebar": "#2e3440",
        "fg": "#d8dee9",
        "fg_dark": "#c2c8d2",
        "fg_gutter": "#4c566a",
        "comment": "#616e88",
        "blue": "#81a1c1",
        "cyan": "#88c0d0",
        "green": "#a3be8c",
        "magenta": "#b48ead",
        "orange": "#d08770",
        "red": "#bf616a",
        "yellow": "#ebcb8b",
        "border": "#4c566a",
        "selection": "#434c5e",
    },
    "dracula": {
        "bg": "#282a36",
        "bg_dark": "#21222c",
        "bg_highlight": "#44475a",
        "bg_sidebar": "#282a36",
        "fg": "#f8f8f2",
        "fg_dark": "#e0e0da",
        "fg_gutter": "#6272a4",
        "comment": "#6272a4",
        "blue": "#8be9fd",
        "cyan": "#8be9fd",
        "green": "#50fa7b",
        "magenta": "#ff79c6",
        "orange": "#ffb86c",
        "red": "#ff5555",
        "yellow": "#f1fa8c",
        "border": "#44475a",
        "selection": "#44475a",
    },
    "gruvbox": {
        "bg": "#282828",
        "bg_dark": "#1d2021",
        "bg_highlight": "#3c3836",
        "bg_sidebar": "#282828",
        "fg": "#ebdbb2",
        "fg_dark": "#d5c4a1",
        "fg_gutter": "#504945",
        "comment": "#928374",
        "blue": "#83a598",
        "cyan": "#8ec07c",
        "green": "#b8bb26",
        "magenta": "#d3869b",
        "orange": "#fe8019",
        "red": "#fb4934",
        "yellow": "#fabd2f",
        "border": "#504945",
        "selection": "#3c3836",
    },
    "catppuccin-mocha": {
        "bg": "#1e1e2e",
        "bg_dark": "#181825",
        "bg_highlight": "#313244",
        "bg_sidebar": "#1e1e2e",
        "fg": "#cdd6f4",
        "fg_dark": "#bac2de",
        "fg_gutter": "#45475a",
        "comment": "#6c7086",
        "blue": "#89b4fa",
        "cyan": "#94e2d5",
        "green": "#a6e3a1",
        "magenta": "#cba6f7",
        "orange": "#fab387",
        "red": "#f38ba8",
        "yellow": "#f9e2af",
        "border": "#45475a",
        "selection": "#313244",
    },
    "catppuccin-latte": {
        "bg": "#eff1f5",
        "bg_dark": "#e6e9ef",
        "bg_highlight": "#ccd0da",
        "bg_sidebar": "#e6e9ef",
        "fg": "#4c4f69",
        "fg_dark": "#5c5f77",
        "fg_gutter": "#9ca0b0",
        "comment": "#8c8fa1",
        "blue": "#1e66f5",
        "cyan": "#179299",
        "green": "#40a02b",
        "magenta": "#8839ef",
        "orange": "#fe640b",
        "red": "#d20f39",
        "yellow": "#df8e1d",
        "border": "#bcc0cc",
        "selection": "#ccd0da",
    },
}

# Backward compatibility: COLORS is always the Tokyo Night palette
COLORS = THEME_PALETTES["tokyo-night"]


def build_stylesheet(colors: dict[str, str]) -> str:
    """
    Build a complete QSS stylesheet from a color palette dict.

    Parameters
    ----------
    colors : dict[str, str]
        Color palette with keys: bg, bg_dark, bg_highlight, bg_sidebar,
        fg, fg_dark, fg_gutter, comment, blue, cyan, green, magenta,
        orange, red, yellow, border, selection.

    Returns
    -------
    str
        Complete QSS stylesheet string.
    """
    return f"""
/* ═══════════════════════════════════════════
   Global
   ═══════════════════════════════════════════ */

QMainWindow {{
    background-color: {colors['bg']};
}}

QWidget {{
    background-color: {colors['bg']};
    color: {colors['fg']};
    font-family: "Segoe UI", "Ubuntu", "Noto Sans", sans-serif;
    font-size: 13px;
}}

/* ═══════════════════════════════════════════
   Sidebar
   ═══════════════════════════════════════════ */

QWidget#sidebar {{
    background-color: {colors['bg_sidebar']};
    border-right: 1px solid {colors['border']};
    min-width: 180px;
    max-width: 180px;
}}

QPushButton#sidebar-btn {{
    background-color: transparent;
    color: {colors['fg_dark']};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    margin: 2px 8px;
}}

QPushButton#sidebar-btn:hover {{
    background-color: {colors['bg_highlight']};
    color: {colors['fg']};
}}

QPushButton#sidebar-btn:checked {{
    background-color: {colors['selection']};
    color: {colors['blue']};
    font-weight: bold;
}}

QPushButton#sidebar-btn-quit {{
    background-color: transparent;
    color: {colors['comment']};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    margin: 2px 8px;
}}

QPushButton#sidebar-btn-quit:hover {{
    background-color: {colors['red']};
    color: {colors['bg']};
}}

/* ═══════════════════════════════════════════
   Breadcrumb
   ═══════════════════════════════════════════ */

QLabel#breadcrumb {{
    background-color: {colors['bg_dark']};
    color: {colors['comment']};
    padding: 8px 16px;
    font-size: 12px;
    border-bottom: 1px solid {colors['border']};
}}

/* ═══════════════════════════════════════════
   Page Content
   ═══════════════════════════════════════════ */

QWidget#page-content {{
    background-color: {colors['bg']};
    padding: 24px;
}}

QLabel#page-title {{
    font-size: 22px;
    font-weight: bold;
    color: {colors['fg']};
    padding-bottom: 4px;
}}

QLabel#page-subtitle {{
    font-size: 14px;
    color: {colors['comment']};
    padding-bottom: 16px;
}}

QLabel#section-header {{
    font-size: 15px;
    font-weight: bold;
    color: {colors['blue']};
    padding: 12px 0 6px 0;
}}

QLabel#stat-value {{
    font-size: 28px;
    font-weight: bold;
    color: {colors['blue']};
}}

QLabel#stat-label {{
    font-size: 12px;
    color: {colors['comment']};
}}

/* ═══════════════════════════════════════════
   Buttons
   ═══════════════════════════════════════════ */

QPushButton {{
    background-color: {colors['bg_highlight']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {colors['selection']};
    border-color: {colors['blue']};
}}

QPushButton:pressed {{
    background-color: {colors['blue']};
    color: {colors['bg']};
}}

QPushButton:disabled {{
    background-color: {colors['bg_dark']};
    color: {colors['fg_gutter']};
    border-color: {colors['bg_dark']};
}}

QPushButton#primary-btn {{
    background-color: {colors['blue']};
    color: {colors['bg']};
    border: none;
    font-weight: bold;
    padding: 10px 28px;
}}

QPushButton#primary-btn:hover {{
    background-color: {colors['cyan']};
}}

QPushButton#primary-btn:pressed {{
    background-color: {colors['fg_dark']};
}}

QPushButton#danger-btn {{
    background-color: transparent;
    color: {colors['red']};
    border: 1px solid {colors['red']};
}}

QPushButton#danger-btn:hover {{
    background-color: {colors['red']};
    color: {colors['bg']};
}}

/* ═══════════════════════════════════════════
   Chip Cards
   ═══════════════════════════════════════════ */

QPushButton#chip-card {{
    background-color: {colors['bg_highlight']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 8px;
    padding: 16px;
    text-align: left;
    min-width: 160px;
    min-height: 80px;
}}

QPushButton#chip-card:hover {{
    border-color: {colors['blue']};
    background-color: {colors['selection']};
}}

/* ═══════════════════════════════════════════
   Tables
   ═══════════════════════════════════════════ */

QTableView {{
    background-color: {colors['bg_dark']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 4px;
    gridline-color: {colors['bg_highlight']};
    selection-background-color: {colors['selection']};
    selection-color: {colors['fg']};
    alternate-background-color: {colors['bg']};
}}

QTableView::item {{
    padding: 6px 8px;
}}

QHeaderView::section {{
    background-color: {colors['bg_sidebar']};
    color: {colors['fg_dark']};
    padding: 8px;
    border: none;
    border-bottom: 2px solid {colors['blue']};
    font-weight: bold;
}}

/* ═══════════════════════════════════════════
   Form Inputs
   ═══════════════════════════════════════════ */

QComboBox {{
    background-color: {colors['bg_highlight']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {colors['blue']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {colors['bg_highlight']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    selection-background-color: {colors['selection']};
    selection-color: {colors['blue']};
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {colors['bg_highlight']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 20px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {colors['blue']};
}}

QCheckBox {{
    color: {colors['fg']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {colors['border']};
    border-radius: 3px;
    background-color: {colors['bg_highlight']};
}}

QCheckBox::indicator:checked {{
    background-color: {colors['blue']};
    border-color: {colors['blue']};
}}

QRadioButton {{
    color: {colors['fg']};
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {colors['border']};
    border-radius: 9px;
    background-color: {colors['bg_highlight']};
}}

QRadioButton::indicator:checked {{
    background-color: {colors['blue']};
    border-color: {colors['blue']};
}}

/* ═══════════════════════════════════════════
   Progress Bar
   ═══════════════════════════════════════════ */

QProgressBar {{
    background-color: {colors['bg_dark']};
    border: 1px solid {colors['border']};
    border-radius: 6px;
    text-align: center;
    color: {colors['fg']};
    min-height: 24px;
}}

QProgressBar::chunk {{
    background-color: {colors['blue']};
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
    background-color: {colors['bg_dark']};
    width: 10px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {colors['fg_gutter']};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {colors['comment']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {colors['bg_dark']};
    height: 10px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {colors['fg_gutter']};
    border-radius: 5px;
    min-width: 30px;
}}

/* ═══════════════════════════════════════════
   Text Areas
   ═══════════════════════════════════════════ */

QPlainTextEdit {{
    background-color: {colors['bg_dark']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 4px;
    padding: 8px;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
}}

/* ═══════════════════════════════════════════
   Separator
   ═══════════════════════════════════════════ */

QFrame#separator {{
    background-color: {colors['border']};
    max-height: 1px;
    margin: 8px 0;
}}

/* ═══════════════════════════════════════════
   Status/Info Labels
   ═══════════════════════════════════════════ */

QLabel#success-label {{
    color: {colors['green']};
    font-size: 16px;
    font-weight: bold;
}}

QLabel#error-label {{
    color: {colors['red']};
    font-size: 16px;
    font-weight: bold;
}}

QLabel#info-label {{
    color: {colors['cyan']};
    font-size: 13px;
}}

QLabel#warning-label {{
    color: {colors['yellow']};
    font-size: 13px;
}}

/* ═══════════════════════════════════════════
   Tree Views (Plot Browser)
   ═══════════════════════════════════════════ */

QTreeView {{
    background-color: {colors['bg_dark']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 4px;
    selection-background-color: {colors['selection']};
    selection-color: {colors['fg']};
    alternate-background-color: {colors['bg']};
}}

QTreeView::item {{
    padding: 4px 6px;
}}

QTreeView::item:hover {{
    background-color: {colors['bg_highlight']};
}}

QTreeView::item:selected {{
    background-color: {colors['selection']};
    color: {colors['blue']};
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
    background-color: {colors['border']};
    width: 2px;
}}

QSplitter::handle:hover {{
    background-color: {colors['blue']};
}}

/* ═══════════════════════════════════════════
   QTableWidget (reuse QTableView styles)
   ═══════════════════════════════════════════ */

QTableWidget {{
    background-color: {colors['bg_dark']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 4px;
    gridline-color: {colors['bg_highlight']};
    selection-background-color: {colors['selection']};
    selection-color: {colors['fg']};
    alternate-background-color: {colors['bg']};
}}

QTableWidget::item {{
    padding: 6px 8px;
}}

/* ═══════════════════════════════════════════
   Line Edit (search fields)
   ═══════════════════════════════════════════ */

QLineEdit {{
    background-color: {colors['bg_highlight']};
    color: {colors['fg']};
    border: 1px solid {colors['border']};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 20px;
}}

QLineEdit:hover {{
    border-color: {colors['blue']};
}}

QLineEdit:focus {{
    border-color: {colors['blue']};
    border-width: 2px;
}}
"""


def get_stylesheet(theme_id: str) -> str:
    """
    Get the QSS stylesheet for a given theme ID.

    Parameters
    ----------
    theme_id : str
        Theme identifier (e.g., "tokyo-night", "nord", "dracula").
        Falls back to Tokyo Night if the theme ID is not found.

    Returns
    -------
    str
        Complete QSS stylesheet string.
    """
    palette = THEME_PALETTES.get(theme_id, THEME_PALETTES["tokyo-night"])
    return build_stylesheet(palette)


# Backward compatibility: default stylesheet is Tokyo Night
STYLESHEET = build_stylesheet(COLORS)
