# Plot Browser Screen Implementation Plan
## TUI Plot Viewer - Standalone Screen Design

---

## Table of Contents

1. [Overview](#overview)
2. [Design Approach](#design-approach)
3. [Implementation Plan](#implementation-plan)
4. [File Structure](#file-structure)
5. [Component Specifications](#component-specifications)
6. [Integration Points](#integration-points)
7. [Testing Strategy](#testing-strategy)
8. [Future Enhancements](#future-enhancements)

---

## 1. Overview

### Objective
Create a standalone plot browser screen that allows users to browse and preview existing plots from the `figs/` directory, independent of the wizard plot generation flow.

### Scope
- Browse `figs/` directory hierarchy (chip folders, plot types)
- Display PNG plots in-terminal using kitty graphics protocol
- Show file metadata (path, size, modified date)
- Navigate with keyboard shortcuts and directory tree
- Foundation for future wizard integration

### Key Features
- Two-pane layout (directory tree + plot viewer)
- Real-time plot preview on file selection
- Filter by plot type through directory navigation
- Metadata display panel
- Keyboard shortcuts for navigation
- Tokyo Night theme consistency

### Phase Strategy
**Phase 0 (Current):** Build standalone plot browser screen
**Phase 1 (Future):** Integrate with plot generation success screen
**Phase 2 (Future):** Add plot manifest system with experiment relations

---

## 2. Design Approach

### Screen: `PlotBrowserScreen`

**Purpose:** Browse and view existing plots from the `figs/` directory independently of the wizard flow.

**Features (Minimal v1):**
1. **Directory browser** - Navigate chip folders and plot types
2. **File list** - Show available PNG plots in selected folder
3. **Plot display** - Show selected plot using `MatplotlibImageWidget`
4. **Metadata display** - File info (size, date, path)
5. **Simple navigation** - Back button, keyboard shortcuts

**Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Header: Plot Browser                                            │
├──────────────────────┬──────────────────────────────────────────┤
│  Navigation Tree     │   Selected Plot Display                  │
│  (30% width)         │   (70% width)                            │
│                      │                                          │
│  📁 figs/            │   ┌────────────────────────────────────┐ │
│    📁 Encap81        │   │                                    │ │
│      📁 It           │   │   [Plot Image Widget]              │ │
│        📁 Dark_It    │   │                                    │ │
│        📁 Light_It   │   │   (Kitty Graphics Display)         │ │
│      📁 Vt           │   │                                    │ │
│      📁 VVg          │   │                                    │ │
│    📁 Alisson81      │   └────────────────────────────────────┘ │
│      📁 It           │                                          │
│                      │   ┌────────────────────────────────────┐ │
│                      │   │ 📁 File: seq050_It_relaxation.png  │ │
│                      │   │ 📏 Size: 0.52 MB                   │ │
│                      │   │ 📅 Modified: 2025-11-10 04:19:15  │ │
│                      │   │ 📂 Path: figs/Encap81/It/...      │ │
│                      │   └────────────────────────────────────┘ │
└──────────────────────┴──────────────────────────────────────────┘
│ Footer: [↑↓] Navigate [Enter] Select [Esc] Back [q] Quit       │
└─────────────────────────────────────────────────────────────────┘
```

**Design Decisions:**
- ✅ Two-pane layout (directory tree + plot viewer)
- ✅ Filter by plot type through directory navigation (It, IVg, VVg, etc.)
- ✅ Accessible from main menu AND plot success screen
- ✅ Use textual-image for kitty graphics (primary), fallback for non-kitty
- ✅ Basic file metadata (path, size, modified date) - No plot manifest yet

---

## 3. Implementation Plan

### Phase 1: Create MatplotlibImageWidget (30-45 minutes)
**File:** `src/tui/widgets/plot_image.py`

**Tasks:**
1. Create base widget class
2. Add reactive `image_path` property
3. Implement kitty graphics support via `textual-image`
4. Add fallback rendering for non-kitty terminals
5. Error handling for missing/invalid images
6. Tokyo Night theme CSS styling
7. Unit tests for widget

**Dependencies:**
```bash
pip install textual-image pillow
```

### Phase 2: Create PlotBrowserScreen (60-90 minutes)
**File:** `src/tui/screens/analysis/plot_browser.py`

**Tasks:**
1. Implement two-column layout (Horizontal container)
2. Add DirectoryTree widget for `figs/` navigation
3. Add MatplotlibImageWidget for plot display
4. Add Static widget for metadata display
5. Implement file selection event handler
6. Add keyboard shortcuts (Esc, q, arrows)
7. CSS styling for layout and theme
8. Error handling for empty directories

### Phase 3: Router Integration (15-20 minutes)
**File:** `src/tui/router.py`

**Tasks:**
1. Add `go_to_plot_browser()` method
2. Add import for PlotBrowserScreen
3. Test navigation flow

### Phase 4: Main Menu Integration (10-15 minutes)
**File:** `src/tui/screens/navigation/main_menu.py`

**Tasks:**
1. Add "Browse Plots" menu option
2. Wire to `router.go_to_plot_browser()`
3. Position between "Generate Plots" and "View Chip History"
4. Update menu layout and styling

### Phase 5: Testing & Polish (30-45 minutes)
**Tasks:**
1. Manual testing in kitty terminal
2. Manual testing in non-kitty terminal
3. Error scenario testing (empty dirs, missing files)
4. Performance testing (large images, deep trees)
5. Keyboard shortcut validation
6. Theme consistency check
7. Documentation updates

**Total Estimated Time:** 2.5-3.5 hours

---

## 4. File Structure

```
src/tui/
├── widgets/
│   ├── __init__.py                    # MODIFY: Export MatplotlibImageWidget
│   ├── config_form.py                 # Existing
│   └── plot_image.py                  # NEW: Image display widget
├── screens/
│   ├── analysis/
│   │   ├── __init__.py                # MODIFY: Export PlotBrowserScreen
│   │   ├── history_browser.py         # Existing
│   │   └── plot_browser.py            # NEW: Plot browser screen
│   └── navigation/
│       └── main_menu.py               # MODIFY: Add Browse Plots option
├── router.py                          # MODIFY: Add go_to_plot_browser()
└── app.py                             # No changes needed

docs/
└── PLOT_BROWSER_IMPLEMENTATION_PLAN.md  # This document

tests/
├── test_plot_image_widget.py          # NEW: Widget unit tests
└── test_plot_browser_screen.py        # NEW: Screen integration tests
```

---

## 5. Component Specifications

### 5.1 MatplotlibImageWidget

**File:** `src/tui/widgets/plot_image.py`

**Purpose:** Display matplotlib PNG plots in Textual TUI with kitty graphics support.

**Key Features:**
- Reactive `image_path` property (updates display when changed)
- Automatic kitty terminal detection
- Graceful fallback for non-kitty terminals (shows file info)
- Error handling for missing/corrupt files
- Lazy loading for performance
- Tokyo Night theme styling

**Public API:**
```python
class MatplotlibImageWidget(Widget):
    """Display matplotlib plots in terminal."""

    image_path: reactive[str | None] = reactive(None)
    show_filename: reactive[bool] = reactive(True)

    def __init__(self, image_path: str | None = None, **kwargs):
        """Initialize with optional image path."""

    def update_image(self, new_path: str) -> None:
        """Update displayed image."""

    def _check_graphics_support(self) -> bool:
        """Check if terminal supports kitty graphics."""
```

**CSS Styling:**
```css
MatplotlibImageWidget {
    width: 100%;
    height: auto;
    border: solid $primary;
    padding: 1;
    background: $surface;
}

MatplotlibImageWidget .error {
    color: $error;
    text-align: center;
}

MatplotlibImageWidget .placeholder {
    color: $text-muted;
    text-align: center;
}
```

**Fallback Display (Non-Kitty Terminals):**
```
📊 Plot Image

File: seq050_It_relaxation.png
Size: 0.52 MB
Path: figs/Encap81/It/

(Graphics display not supported in this terminal)
Use kitty terminal for in-line plot viewing.
```

**Dependencies:**
- `textual-image>=0.3.0` - Kitty graphics protocol
- `pillow>=10.0.0` - Image processing
- `textual>=0.40.0` - Base widget framework

---

### 5.2 PlotBrowserScreen

**File:** `src/tui/screens/analysis/plot_browser.py`

**Purpose:** Main screen for browsing and viewing plots from `figs/` directory.

**Layout Structure:**
```python
PlotBrowserScreen
├── Header (show_clock=True)
├── Horizontal (id="browser-container")
│   ├── Container (id="tree-panel") [30% width]
│   │   └── DirectoryTree (id="plot-tree")
│   └── Container (id="viewer-panel") [70% width]
│       ├── ScrollableContainer (id="plot-display-container")
│       │   └── MatplotlibImageWidget (id="plot-display")
│       └── Container (id="metadata-panel")
│           └── Static (id="metadata-text")
└── Footer
```

**Event Handlers:**
```python
def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
    """Handle file selection - update image and metadata."""

def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
    """Handle directory expansion."""

def action_go_back(self) -> None:
    """Return to previous screen (Escape key)."""

def action_quit_app(self) -> None:
    """Quit application (q key)."""
```

**Keyboard Shortcuts:**
```python
BINDINGS = [
    Binding("escape", "go_back", "Back", priority=True),
    Binding("q", "quit_app", "Quit"),
    Binding("r", "refresh", "Refresh"),  # Reload directory tree
]
```

**CSS Styling:**
```css
PlotBrowserScreen {
    background: $surface;
}

#browser-container {
    width: 100%;
    height: 100%;
}

#tree-panel {
    width: 30%;
    height: 100%;
    border-right: solid $primary;
    padding: 1;
}

#plot-tree {
    width: 100%;
    height: 100%;
}

#viewer-panel {
    width: 70%;
    height: 100%;
    padding: 1;
}

#plot-display-container {
    width: 100%;
    height: 75%;
    border: solid $accent;
    margin-bottom: 1;
}

#plot-display {
    width: 100%;
    height: 100%;
}

#metadata-panel {
    width: 100%;
    height: 25%;
    border: solid $accent;
    padding: 1;
    background: $panel;
}

#metadata-text {
    width: 100%;
    padding: 1;
}
```

**State Management:**
- `current_plot_path: Path | None` - Currently displayed plot
- `figs_dir: Path` - Root directory for plot browsing

**Error Handling:**
- Empty `figs/` directory → Show message "No plots found. Generate plots first."
- Missing file after selection → Show error in metadata panel
- Corrupted PNG file → Show error in image widget
- Non-PNG file selected → Ignore (only handle .png files)

---

### 5.3 Router Integration

**File:** `src/tui/router.py`

**New Method:**
```python
def go_to_plot_browser(self) -> None:
    """
    Navigate to plot browser screen.

    Opens standalone plot viewer for browsing existing plots
    in the figs/ directory.

    No session state requirements - accessible from main menu.
    """
    from src.tui.screens.analysis.plot_browser import PlotBrowserScreen
    self.app.push_screen(PlotBrowserScreen())
```

**Location in File:**
Add to "Utility Navigation" section (around line 680), after `go_to_history_browser()`.

---

### 5.4 Main Menu Integration

**File:** `src/tui/screens/navigation/main_menu.py`

**Menu Option Addition:**
```python
# Add to menu options list (after "Generate Plots" option)
{
    "key": "3",
    "label": "Browse Plots",
    "description": "View existing plots from figs/ directory",
    "icon": "📊",
    "action": lambda: self.app.router.go_to_plot_browser()
}
```

**Menu Layout (Updated):**
```
Main Menu
─────────────────────────────
1. Generate Plots          🎨
2. View Chip History       📈
3. Browse Plots            📊  ← NEW
4. Recent Configurations   📋
5. Data Pipeline           ⚙️
6. Settings                🛠️
7. Quit                    🚪
```

---

## 6. Integration Points

### 6.1 Dependencies Installation

**Add to requirements.txt:**
```txt
textual>=0.40.0
textual-image>=0.3.0
pillow>=10.0.0
```

**Installation:**
```bash
source .venv/bin/activate
uv pip install textual-image pillow
# OR
pip install textual-image pillow
```

### 6.2 Widget Exports

**File:** `src/tui/widgets/__init__.py`

```python
from .config_form import ConfigForm
from .plot_image import MatplotlibImageWidget  # NEW

__all__ = ['ConfigForm', 'MatplotlibImageWidget']
```

### 6.3 Screen Exports

**File:** `src/tui/screens/analysis/__init__.py`

```python
from .history_browser import HistoryBrowserScreen
from .plot_browser import PlotBrowserScreen  # NEW

__all__ = ['HistoryBrowserScreen', 'PlotBrowserScreen']
```

### 6.4 App Configuration

**File:** `src/tui/app.py`

No changes needed - screens are lazy-loaded via router.

### 6.5 Session State

No session state required for standalone plot browser. It operates independently of wizard flow.

---

## 7. Testing Strategy

### 7.1 Unit Tests

**File:** `tests/test_plot_image_widget.py`

**Test Coverage:**
- Widget initialization with/without image path
- `update_image()` method
- Reactive property changes
- Error handling for missing files
- Kitty terminal detection
- Fallback rendering

**Example Test:**
```python
def test_widget_initialization():
    """Test widget can be initialized."""
    widget = MatplotlibImageWidget()
    assert widget.image_path is None
    assert widget.show_filename is True

def test_widget_with_image_path(sample_plot):
    """Test widget initialization with image path."""
    widget = MatplotlibImageWidget(image_path=sample_plot)
    assert widget.image_path == sample_plot
```

### 7.2 Integration Tests

**File:** `tests/test_plot_browser_screen.py`

**Test Coverage:**
- Screen initialization
- Directory tree population
- File selection updates image widget
- Metadata display updates
- Keyboard shortcuts work
- Error scenarios

**Example Test:**
```python
async def test_screen_initialization():
    """Test screen initializes with figs directory."""
    screen = PlotBrowserScreen()
    assert screen.figs_dir.exists()

async def test_file_selection_updates_display(app_with_plots):
    """Test selecting PNG file updates display."""
    # Simulate file selection
    # Verify image widget updated
    # Verify metadata updated
```

### 7.3 Manual Testing Checklist

**Kitty Terminal Testing:**
- [ ] Plot displays correctly with graphics
- [ ] Image scales to fit viewer panel
- [ ] Multiple plots can be selected sequentially
- [ ] Large plots (>1MB) load without lag
- [ ] Image quality is acceptable

**Non-Kitty Terminal Testing:**
- [ ] Fallback shows file information
- [ ] Message indicates graphics not supported
- [ ] All navigation still works

**Navigation Testing:**
- [ ] Directory tree expands/collapses
- [ ] Arrow keys navigate tree
- [ ] Enter key selects files
- [ ] Escape returns to main menu
- [ ] Q key quits application
- [ ] Tree scrolls for deep hierarchies

**Error Scenario Testing:**
- [ ] Empty `figs/` directory shows helpful message
- [ ] Missing file after selection handled gracefully
- [ ] Corrupted PNG shows error (not crash)
- [ ] Non-PNG files ignored
- [ ] Permission errors handled

**Layout & Theme Testing:**
- [ ] Two-pane layout renders correctly
- [ ] Panels sized properly (30/70 split)
- [ ] Scrollbars appear when needed
- [ ] Tokyo Night colors consistent
- [ ] Borders and padding correct
- [ ] Responsive to terminal resize

**Performance Testing:**
- [ ] 100+ plots in tree loads quickly
- [ ] Switching between plots is responsive
- [ ] Memory usage acceptable
- [ ] No memory leaks on repeated selections

### 7.4 Test Data Setup

**Create test plots:**
```bash
# Create test plot structure
mkdir -p figs/TestChip/It
mkdir -p figs/TestChip/IVg

# Generate test plots (can use matplotlib)
python3 -c "
import matplotlib.pyplot as plt
from pathlib import Path

for i in range(5):
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 2])
    ax.set_title(f'Test Plot {i}')
    Path('figs/TestChip/It').mkdir(parents=True, exist_ok=True)
    plt.savefig(f'figs/TestChip/It/test_plot_{i}.png')
    plt.close()
"
```

---

## 8. Future Enhancements

### Phase 1: Wizard Integration (Post-MVP)

**Success Screen Integration:**
- Add "View Plot" button to `PlotSuccessScreen`
- Navigate to `PlotBrowserScreen` with pre-selected plot
- Highlight recently generated plot in tree

**Implementation:**
```python
# In PlotSuccessScreen
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "view-plot-btn":
        self.app.router.go_to_plot_browser(
            initial_plot=self.plot_path  # Pre-select generated plot
        )
```

### Phase 2: Plot Manifest System

**Manifest File:** `figs/.plot_manifest.json`

**Schema:**
```json
{
  "plots": [
    {
      "path": "figs/Encap81/It/seq050_It_relaxation.png",
      "chip_number": 81,
      "chip_group": "Encap",
      "plot_type": "It",
      "seq_numbers": [50],
      "generated_at": "2025-11-10T04:19:15",
      "config": {
        "legend_by": "wl",
        "baseline": "auto"
      }
    }
  ]
}
```

**Features:**
- Track plot generation metadata
- Link plots to experiments
- Show configuration used
- Search plots by chip/type/seq
- Regenerate plots with same config

### Phase 3: Advanced Features

**Plot Comparison:**
- Select multiple plots for side-by-side view
- Diff mode (highlight differences)

**Search & Filter:**
- Search by chip number
- Filter by plot type
- Filter by date range
- Filter by seq numbers

**Plot Actions:**
- Copy path to clipboard
- Open in external viewer
- Delete plot (with confirmation)
- Regenerate with same config
- Export to different format

**Thumbnail Gallery:**
- Grid view of plots
- Quick preview on hover
- Batch selection

**Plot Annotations:**
- Add notes to plots
- Tag plots (good, bad, anomaly)
- Star/favorite system

**Statistics:**
- Total plots generated
- Plots per chip
- Most common plot types
- Storage usage

---

## 9. Implementation Checklist

### Pre-Implementation
- [x] Document review completed
- [ ] Verify kitty terminal available
- [ ] Check textual-image compatibility
- [ ] Review existing TUI codebase
- [ ] Create feature branch

### Phase 1: MatplotlibImageWidget
- [ ] Create `src/tui/widgets/plot_image.py`
- [ ] Implement base widget class
- [ ] Add kitty graphics support
- [ ] Add fallback rendering
- [ ] Add error handling
- [ ] Write CSS styling
- [ ] Write unit tests
- [ ] Test in kitty terminal
- [ ] Test in non-kitty terminal
- [ ] Update `widgets/__init__.py`

### Phase 2: PlotBrowserScreen
- [ ] Create `src/tui/screens/analysis/plot_browser.py`
- [ ] Implement two-column layout
- [ ] Add DirectoryTree widget
- [ ] Add MatplotlibImageWidget
- [ ] Add metadata panel
- [ ] Implement file selection handler
- [ ] Add keyboard shortcuts
- [ ] Write CSS styling
- [ ] Handle empty directory case
- [ ] Write integration tests
- [ ] Update `screens/analysis/__init__.py`

### Phase 3: Router Integration
- [ ] Add `go_to_plot_browser()` to router
- [ ] Add imports
- [ ] Test navigation

### Phase 4: Main Menu Integration
- [ ] Add "Browse Plots" option
- [ ] Wire to router method
- [ ] Update menu layout
- [ ] Test from main menu

### Phase 5: Testing & Polish
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Manual testing (all scenarios)
- [ ] Performance testing
- [ ] Error handling verification
- [ ] Theme consistency check
- [ ] Documentation updates
- [ ] Create user guide

### Post-Implementation
- [ ] Code review
- [ ] Update CLAUDE.md
- [ ] Merge to main branch
- [ ] User acceptance testing
- [ ] Create demo video/screenshots

---

## 10. Troubleshooting

### Issue 1: Kitty Graphics Not Working

**Symptoms:** Plots not displaying despite kitty terminal

**Solutions:**
1. Check TERM variable: `echo $TERM` (should contain "kitty")
2. Verify textual-image installed: `pip show textual-image`
3. Test kitty graphics: `kitty +kitten icat /path/to/image.png`
4. Check file is PNG (not SVG or other format)
5. Try updating textual-image: `pip install --upgrade textual-image`

### Issue 2: Directory Tree Empty

**Symptoms:** Tree shows no files/folders

**Solutions:**
1. Verify `figs/` directory exists: `ls -la figs/`
2. Check directory permissions: `ls -ld figs/`
3. Verify plots exist: `find figs/ -name "*.png"`
4. Check DirectoryTree path is correct
5. Enable logging to see tree population errors

### Issue 3: Image Not Updating on Selection

**Symptoms:** Clicking files doesn't update viewer

**Solutions:**
1. Check event handler is registered
2. Verify file path is correct (.png extension)
3. Add logging to `on_directory_tree_file_selected()`
4. Check `update_image()` is being called
5. Verify reactive property is updating

### Issue 4: Performance Issues

**Symptoms:** Slow response when selecting large plots

**Solutions:**
1. Reduce image resolution in MatplotlibImageWidget
2. Add loading indicator
3. Implement image caching
4. Use PIL to resize before display
5. Add lazy loading for tree

### Issue 5: Layout Issues

**Symptoms:** Panels overlapping or wrong size

**Solutions:**
1. Check CSS width percentages
2. Verify container heights
3. Test in different terminal sizes
4. Use `textual console` for live CSS debugging
5. Check for conflicting CSS rules

---

## 11. Technical Reference

### Textual DirectoryTree API

**Key Methods:**
```python
# Initialize with root path
tree = DirectoryTree(str(path))

# Events
def on_directory_tree_file_selected(self, event):
    # event.path: Path to selected file

def on_directory_tree_directory_selected(self, event):
    # event.path: Path to selected directory
```

### Textual Image Widget (textual-image)

**Usage:**
```python
from textual_image.widget import Image

# Create image widget
img = Image(str(image_path))

# Update image
img.image_path = str(new_path)
```

**Limitations:**
- Requires kitty terminal
- PNG format recommended
- Large images may be slow

### PIL Image Processing

**Resize for Display:**
```python
from PIL import Image

def optimize_for_display(path: Path, max_width: int = 2000) -> Path:
    """Resize image for faster terminal display."""
    with Image.open(path) as img:
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        optimized_path = path.with_suffix('.display.png')
        img.save(optimized_path, 'PNG', optimize=True)

    return optimized_path
```

---

## 12. Document Version History

| Version | Date       | Author  | Changes                                |
|---------|------------|---------|----------------------------------------|
| 1.0     | 2025-11-12 | Claude  | Initial implementation plan document   |

---

## 13. References

- **Textual Documentation:** https://textual.textualize.io/
- **textual-image GitHub:** https://github.com/adamviola/textual-image
- **Pillow Documentation:** https://pillow.readthedocs.io/
- **Kitty Graphics Protocol:** https://sw.kovidgoyal.net/kitty/graphics-protocol/
- **Project CLAUDE.md:** `/Users/mphstph/optothermal_processing/CLAUDE.md`
- **Matplotlib Implementation Guide:** `matplotlib_plot_display_implementation_guide.md`

---

**End of Document**

This plan provides a complete roadmap for implementing the Plot Browser screen as a standalone feature, with clear paths for future wizard integration and advanced features.

🚀 Ready to implement when you are!
