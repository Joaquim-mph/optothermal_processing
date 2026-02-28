# How to Replace the Default Qt Look with a Dark Code-Editor Style

## The Core Idea

Qt's default appearance (gray buttons, beveled borders, OS-native widgets) comes from a **style engine** (`QStyle`). You override it completely with a **Qt Style Sheet (QSS)** — Qt's CSS-like system — applied once on the `QApplication` object. After that, every widget in the entire app is re-skinned. You never touch individual widget styles.

The key insight: **define a palette of 16 color tokens first, then write QSS that references only those tokens.** This gives you theme-switching for free.

---

## Step 1: Define Your Color Palette

Pick a base dark theme. Tokyo Night is used here but the structure works for any dark scheme.

```python
PALETTE = {
    # Backgrounds (3 levels of depth)
    "bg":           "#1a1b26",   # main canvas
    "bg_dark":      "#16161e",   # recessed surfaces (inputs, tables)
    "bg_highlight": "#292e42",   # raised surfaces (buttons, hover states)
    "bg_sidebar":   "#1f2335",   # sidebar (slightly different from bg)

    # Text (3 levels of emphasis)
    "fg":           "#c0caf5",   # primary text
    "fg_dark":      "#a9b1d6",   # secondary text
    "comment":      "#565f89",   # muted / placeholder text
    "fg_gutter":    "#3b4261",   # barely-visible (disabled text, faint lines)

    # Semantic accent colors
    "blue":         "#7aa2f7",   # primary accent (active, focus, links)
    "cyan":         "#7dcfff",   # secondary accent
    "green":        "#9ece6a",   # success
    "magenta":      "#bb9af7",   # tertiary accent
    "orange":       "#ff9e64",   # warning
    "red":          "#f7768e",   # error / danger
    "yellow":       "#e0af68",   # alert

    # Structure
    "border":       "#3b4261",   # all borders and dividers
    "selection":    "#283457",   # selected row / checked background
}
```

Other popular palettes that map directly to these 16 keys:

| Theme | Style |
|---|---|
| **Tokyo Night** | Deep navy, blue/purple accents (shown above) |
| **Nord** | Cool arctic blues and grays |
| **Dracula** | Purple-tinted dark |
| **Gruvbox** | Warm earthy browns and oranges |
| **Catppuccin Mocha** | Soft dark pastels |
| **Catppuccin Latte** | Light pastel (only light option listed) |

---

## Step 2: Write the QSS Stylesheet

Build the stylesheet as a Python f-string from the palette dict. Apply it **once** at startup:

```python
app = QApplication(sys.argv)
app.setStyleSheet(build_stylesheet(PALETTE))
```

Here is the complete stylesheet template:

```python
def build_stylesheet(p: dict) -> str:
    return f"""

/* ── Global ── */
QMainWindow  {{ background-color: {p['bg']}; }}
QWidget      {{
    background-color: {p['bg']};
    color: {p['fg']};
    font-family: "Segoe UI", "Ubuntu", "Noto Sans", sans-serif;
    font-size: 13px;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {p['bg_highlight']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 8px 20px;
    min-height: 20px;
}}
QPushButton:hover    {{ background-color: {p['selection']}; border-color: {p['blue']}; }}
QPushButton:pressed  {{ background-color: {p['blue']}; color: {p['bg']}; }}
QPushButton:disabled {{ background-color: {p['bg_dark']}; color: {p['fg_gutter']}; border-color: {p['bg_dark']}; }}

/* Primary (filled) button — use setObjectName("primary-btn") */
QPushButton#primary-btn {{
    background-color: {p['blue']};
    color: {p['bg']};
    border: none;
    font-weight: bold;
    padding: 10px 28px;
}}
QPushButton#primary-btn:hover   {{ background-color: {p['cyan']}; }}
QPushButton#primary-btn:pressed {{ background-color: {p['fg_dark']}; }}

/* Danger button — use setObjectName("danger-btn") */
QPushButton#danger-btn {{
    background-color: transparent;
    color: {p['red']};
    border: 1px solid {p['red']};
}}
QPushButton#danger-btn:hover {{ background-color: {p['red']}; color: {p['bg']}; }}

/* ── Text inputs ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {p['bg_highlight']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 20px;
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {p['blue']};
}}
QLineEdit:focus {{
    border-color: {p['blue']};
    border-width: 2px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: {p['bg_highlight']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    selection-background-color: {p['selection']};
    selection-color: {p['blue']};
}}

/* ── Checkboxes and radio buttons ── */
QCheckBox, QRadioButton {{ color: {p['fg']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {p['border']};
    border-radius: 3px;
    background-color: {p['bg_highlight']};
}}
QRadioButton::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {p['border']};
    border-radius: 9px;
    background-color: {p['bg_highlight']};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {p['blue']};
    border-color: {p['blue']};
}}

/* ── Tables ── */
QTableView, QTableWidget {{
    background-color: {p['bg_dark']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    gridline-color: {p['bg_highlight']};
    selection-background-color: {p['selection']};
    selection-color: {p['fg']};
    alternate-background-color: {p['bg']};
}}
QTableView::item, QTableWidget::item {{ padding: 6px 8px; }}
QHeaderView::section {{
    background-color: {p['bg_sidebar']};
    color: {p['fg_dark']};
    padding: 8px;
    border: none;
    border-bottom: 2px solid {p['blue']};
    font-weight: bold;
}}

/* ── Tree views ── */
QTreeView {{
    background-color: {p['bg_dark']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    selection-background-color: {p['selection']};
    selection-color: {p['fg']};
    alternate-background-color: {p['bg']};
}}
QTreeView::item          {{ padding: 4px 6px; }}
QTreeView::item:hover    {{ background-color: {p['bg_highlight']}; }}
QTreeView::item:selected {{ background-color: {p['selection']}; color: {p['blue']}; }}

/* ── Progress bar ── */
QProgressBar {{
    background-color: {p['bg_dark']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    text-align: center;
    color: {p['fg']};
    min-height: 24px;
}}
QProgressBar::chunk {{ background-color: {p['blue']}; border-radius: 5px; }}

/* ── Scrollbars (thin, no arrows) ── */
QScrollBar:vertical   {{ background-color: {p['bg_dark']}; width: 10px;  border: none; }}
QScrollBar:horizontal {{ background-color: {p['bg_dark']}; height: 10px; border: none; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background-color: {p['fg_gutter']};
    border-radius: 5px;
    min-height: 30px; min-width: 30px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background-color: {p['comment']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

/* ── Plain text / log areas (monospace) ── */
QPlainTextEdit {{
    background-color: {p['bg_dark']};
    color: {p['fg']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 8px;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
}}

/* ── Scroll areas (borderless container) ── */
QScrollArea {{ border: none; background-color: transparent; }}

/* ── Splitter handle ── */
QSplitter::handle       {{ background-color: {p['border']}; width: 2px; }}
QSplitter::handle:hover {{ background-color: {p['blue']}; }}

/* ── Thin separator line ── */
/* Usage: frame.setObjectName("separator"); frame.setFrameShape(QFrame.Shape.HLine) */
QFrame#separator {{ background-color: {p['border']}; max-height: 1px; margin: 8px 0; }}

/* ── Semantic status labels ── */
QLabel#success-label {{ color: {p['green']};  font-size: 16px; font-weight: bold; }}
QLabel#error-label   {{ color: {p['red']};    font-size: 16px; font-weight: bold; }}
QLabel#info-label    {{ color: {p['cyan']};   font-size: 13px; }}
QLabel#warning-label {{ color: {p['yellow']}; font-size: 13px; }}

/* ── Page typography ── */
QLabel#page-title     {{ font-size: 22px; font-weight: bold; color: {p['fg']}; padding-bottom: 4px; }}
QLabel#page-subtitle  {{ font-size: 14px; color: {p['comment']}; padding-bottom: 16px; }}
QLabel#section-header {{ font-size: 15px; font-weight: bold; color: {p['blue']}; padding: 12px 0 6px 0; }}

"""
```

---

## Step 3: The objectName Pattern

QSS selects widgets by **type** (`QPushButton`) and optionally by **object name** (`QPushButton#primary-btn`). Use `setObjectName()` as your only per-widget styling hook — never call `.setStyleSheet()` on individual widgets.

```python
# Plain button — gets default QPushButton style automatically
btn = QPushButton("Cancel")

# Primary action — gets blue filled style
btn = QPushButton("Save")
btn.setObjectName("primary-btn")

# Danger action — gets red outline style
btn = QPushButton("Delete")
btn.setObjectName("danger-btn")

# Page title
title = QLabel("My Page")
title.setObjectName("page-title")

# Muted description under the title
sub = QLabel("Brief explanation of what this page does")
sub.setObjectName("page-subtitle")

# Section divider label
header = QLabel("Settings")
header.setObjectName("section-header")

# Horizontal rule
sep = QFrame()
sep.setObjectName("separator")
sep.setFrameShape(QFrame.Shape.HLine)

# Status messages
msg = QLabel("Saved successfully")
msg.setObjectName("success-label")  # or error-label, info-label, warning-label
```

The only exception to "no inline styles" is one-off dynamic color changes — for example, turning a progress bar chunk green on success. Keep these minimal.

---

## Step 4: Standard Page Structure

Every page should follow this skeleton. The key conventions are generous side padding, consistent spacing, and navigation buttons always anchored to the bottom via `addStretch()`.

```python
class MyPage(QWidget):
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 20, 32, 20)  # generous side padding
        layout.setSpacing(10)

        # 1. Title block
        title = QLabel("Page Title")
        title.setObjectName("page-title")
        layout.addWidget(title)

        subtitle = QLabel("What this page does")
        subtitle.setObjectName("page-subtitle")
        layout.addWidget(subtitle)

        # 2. Separator
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # 3. Content goes here...

        # 4. Push nav buttons to the bottom
        layout.addStretch()

        nav = QHBoxLayout()
        back = QPushButton("Back")
        nav.addWidget(back)
        nav.addStretch()
        primary = QPushButton("Continue")
        primary.setObjectName("primary-btn")
        nav.addWidget(primary)
        layout.addLayout(nav)

    def on_enter(self, **kwargs):
        """Called by the router when navigating to this page."""
        pass
```

---

## Step 5: Sidebar Layout

The sidebar is a plain `QWidget` with a fixed width and vertical layout. Nav buttons are `checkable` so the active one stays highlighted.

```python
sidebar = QWidget()
sidebar.setObjectName("sidebar")   # picks up the QSS border-right rule

layout = QVBoxLayout(sidebar)
layout.setContentsMargins(0, 12, 0, 12)
layout.setSpacing(0)

# App name at top
logo = QLabel("App Name")
logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
logo.setStyleSheet("font-size: 18px; font-weight: bold; padding: 12px 0 16px 0;")
layout.addWidget(logo)

# Nav buttons
for label, target in PAGES:
    btn = QPushButton(label)
    btn.setObjectName("sidebar-btn")
    btn.setCheckable(True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    layout.addWidget(btn)

layout.addStretch()   # push quit button to the bottom

quit_btn = QPushButton("Quit")
quit_btn.setObjectName("sidebar-btn-quit")
quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
layout.addWidget(quit_btn)
```

Add the sidebar to the root `QHBoxLayout` **before** the content area, with no stretch factor. Give the content area `stretch=1`.

Add these QSS rules to the stylesheet:

```css
QWidget#sidebar {
    background-color: {bg_sidebar};
    border-right: 1px solid {border};
    min-width: 180px;
    max-width: 180px;
}
QPushButton#sidebar-btn {
    background-color: transparent;
    color: {fg_dark};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    margin: 2px 8px;
}
QPushButton#sidebar-btn:hover   { background-color: {bg_highlight}; color: {fg}; }
QPushButton#sidebar-btn:checked { background-color: {selection}; color: {blue}; font-weight: bold; }

QPushButton#sidebar-btn-quit {
    background-color: transparent;
    color: {comment};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    margin: 2px 8px;
}
QPushButton#sidebar-btn-quit:hover { background-color: {red}; color: {bg}; }
```

---

## Step 6: Breadcrumb Bar

A single `QLabel` at the top of the content panel, styled as a darker strip with a bottom border.

```python
breadcrumb = QLabel("Home")
breadcrumb.setObjectName("breadcrumb")
```

Add to the stylesheet:

```css
QLabel#breadcrumb {
    background-color: {bg_dark};
    color: {comment};
    padding: 8px 16px;
    font-size: 12px;
    border-bottom: 1px solid {border};
}
```

Update the text on every navigation event:

```python
breadcrumb.setText("  >  ".join(["Home", "Section", "Current Page"]))
```

---

## Step 7: Cursor Hints

Every clickable element that is not a standard button or input should explicitly set a pointer cursor. This is the single biggest improvement to the app's "feel":

```python
widget.setCursor(Qt.CursorShape.PointingHandCursor)
```

Apply this to sidebar buttons, card-style widgets, clickable tiles, and any `QLabel` used as a link.

---

## Step 8: Removing the Last Traces of Native Style

Two calls at startup finish the job:

```python
app = QApplication(sys.argv)
app.setStyle("Fusion")               # consistent cross-platform base
app.setStyleSheet(build_stylesheet(PALETTE))
```

Using `Fusion` as the base style ensures the same rendering on Windows, Linux, and macOS before the QSS takes over. Without this, some widgets (especially `QComboBox` dropdowns and `QScrollBar`) may still render with OS-native parts on certain platforms that QSS cannot fully override.

---

## Summary

| Before | After |
|---|---|
| Gray OS-native buttons with beveled borders | Flat dark buttons, blue glow on hover |
| White/system-color input fields | Dark recessed inputs with blue focus ring |
| Wide system scrollbars with arrows | Thin 10px scrollbars, no arrows, rounded handle |
| Gray table headers | Dark headers with bold blue bottom border |
| System checkbox squares | Custom dark squares with solid blue fill when checked |
| OS-dependent fonts | Consistent `Segoe UI / Ubuntu / Noto Sans` everywhere |
| No visual hierarchy between labels | 4-level type scale driven by `setObjectName()` |

The complete approach in one sentence: **one palette dict → one QSS string → applied once on `QApplication` → zero per-widget inline styles.**
