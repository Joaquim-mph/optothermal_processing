# Matplotlib Plot Display Implementation Guide
## Textual TUI Integration - Comprehensive Implementation Document

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Architecture Context](#architecture-context)
4. [Implementation Plan](#implementation-plan)
5. [Component Specifications](#component-specifications)
6. [Integration Points](#integration-points)
7. [Testing Strategy](#testing-strategy)
8. [Troubleshooting](#troubleshooting)
9. [Future Enhancements](#future-enhancements)

---

## 1. Overview

### Objective
Add the ability to display static matplotlib plots within the Textual TUI application, allowing users to preview and review generated plots without leaving the terminal interface.

### Scope
- Create reusable `MatplotlibImageWidget` component
- Implement `PlotReviewScreen` for post-generation plot viewing
- Integrate with existing plot generation workflow (Step 7)
- Support kitty terminal graphics protocol for high-quality image display
- Maintain consistency with existing "Tokyo Night" theme

### Key Features
- Display generated PNG plots in-terminal
- Show plot metadata (filename, size, location)
- Action buttons (Save Config, New Plot, Exit)
- Keyboard shortcuts for navigation
- Seamless integration with existing router system

---

## 2. Prerequisites

### Required Dependencies

Add to `requirements.txt` or `pyproject.toml`:

```txt
textual>=0.40.0
pillow>=10.0.0
textual-image>=0.3.0  # For kitty graphics protocol support
matplotlib>=3.7.0
rich>=13.0.0
```

Install command:
```bash
pip install textual-image pillow
```

### Terminal Requirements
- **Primary:** kitty terminal (supports graphics protocol)
- **Fallback:** Display ASCII art representation or file path if graphics not supported

### Existing Codebase Context
This implementation builds upon:
- `src/tui/app.py` - Main PlotterApp class
- `src/tui/session.py` - PlotSession state management
- `src/tui/router.py` - Navigation system
- `src/tui/screens/processing/plot_generation.py` - Plot generation workflow
- Tokyo Night theme (background: #1a1b26)

---

## 3. Architecture Context

### Current TUI Flow (Pre-Implementation)

```
Step 1: Chip Selector
    ↓
Step 2: Plot Type Selector
    ↓
Step 3: Config Mode Selector
    ↓
Step 4: Configuration Screen (ITS/IVg/Transconductance)
    ↓
Step 5: Experiment Selector
    ↓
Step 6: Preview Screen
    ↓
Step 7: Plot Generation
    ↓
    ├→ PlotSuccessScreen (shows metadata only)
    └→ PlotErrorScreen
```

### New Flow (Post-Implementation)

```
Step 7: Plot Generation
    ↓
    ├→ PlotSuccessScreen
    │       ↓ [View Plot button]
    │   PlotReviewScreen ← NEW!
    │       ↓
    │   [Save Config / New Plot / Exit]
    │
    └→ PlotErrorScreen
```

### File Structure

```
src/tui/
├── widgets/
│   ├── __init__.py
│   └── plot_image.py              ← NEW: MatplotlibImageWidget
├── screens/
│   ├── review/
│   │   ├── __init__.py
│   │   └── plot_review_screen.py  ← NEW: PlotReviewScreen
│   └── processing/
│       └── plot_generation.py     ← MODIFY: Add view plot transition
├── router.py                       ← MODIFY: Add go_to_plot_review()
└── app.py                          ← MODIFY: Register new screen
```

---

## 4. Implementation Plan

### Phase 1: Create MatplotlibImageWidget (Core Component)
**Estimated Time:** 30-45 minutes

1. Create `src/tui/widgets/plot_image.py`
2. Implement base widget with image path reactive property
3. Add kitty graphics protocol support via textual-image
4. Implement fallback for non-kitty terminals
5. Add error handling for missing/invalid images
6. Style with Tokyo Night theme

### Phase 2: Create PlotReviewScreen
**Estimated Time:** 45-60 minutes

1. Create `src/tui/screens/review/plot_review_screen.py`
2. Implement screen layout with:
   - Header with title
   - MatplotlibImageWidget for plot display
   - Metadata section (file info)
   - Action buttons
   - Footer with keybindings
3. Add event handlers for buttons
4. Implement keyboard shortcuts
5. Add CSS styling

### Phase 3: Router Integration
**Estimated Time:** 15-20 minutes

1. Add `go_to_plot_review()` method to router
2. Update imports
3. Test navigation flow

### Phase 4: Modify PlotSuccessScreen
**Estimated Time:** 20-30 minutes

1. Add "View Plot" button to PlotSuccessScreen
2. Wire up button to router.go_to_plot_review()
3. Ensure plot_path is passed correctly

### Phase 5: Testing & Polish
**Estimated Time:** 30-45 minutes

1. Unit tests for MatplotlibImageWidget
2. Integration tests for screen transitions
3. Manual testing in kitty terminal
4. Error handling verification
5. Documentation updates

**Total Estimated Time:** 2.5-3.5 hours

---

## 5. Component Specifications

### 5.1 MatplotlibImageWidget

**File:** `src/tui/widgets/plot_image.py`

```python
"""
MatplotlibImageWidget - Display matplotlib plots in Textual TUI.

This widget handles displaying static matplotlib PNG images within a Textual
application, with support for kitty terminal graphics protocol.
"""

from textual.widget import Widget
from textual.reactive import reactive
from textual.app import ComposeResult
from rich.console import RenderableType
from rich.text import Text
from rich.panel import Panel
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MatplotlibImageWidget(Widget):
    """
    Widget to display matplotlib plots as images in terminals with graphics support.
    
    Supports:
    - Kitty graphics protocol (via textual-image)
    - Fallback to file path display for unsupported terminals
    
    Attributes:
        image_path: Path to the PNG image file to display
        show_filename: Whether to show the filename below the image
    """
    
    image_path: reactive[str | None] = reactive(None)
    show_filename: reactive[bool] = reactive(True)
    
    DEFAULT_CSS = """
    MatplotlibImageWidget {
        width: 100%;
        height: auto;
        border: solid $primary;
        padding: 1;
        background: $surface;
    }
    
    MatplotlibImageWidget > Image {
        width: 100%;
        height: auto;
    }
    
    MatplotlibImageWidget .filename {
        width: 100%;
        text-align: center;
        color: $text-muted;
        padding-top: 1;
    }
    
    MatplotlibImageWidget .error {
        width: 100%;
        height: 100%;
        text-align: center;
        color: $error;
        padding: 2;
    }
    
    MatplotlibImageWidget .placeholder {
        width: 100%;
        height: 100%;
        text-align: center;
        color: $text-muted;
        padding: 2;
    }
    """
    
    def __init__(
        self, 
        image_path: str | None = None, 
        show_filename: bool = True,
        **kwargs
    ):
        """
        Initialize the matplotlib image widget.
        
        Args:
            image_path: Path to the PNG image to display
            show_filename: Whether to show filename below image
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.image_path = image_path
        self.show_filename = show_filename
        self._has_graphics_support = self._check_graphics_support()
    
    def _check_graphics_support(self) -> bool:
        """
        Check if the terminal supports graphics protocol.
        
        Returns:
            True if kitty graphics protocol is available
        """
        import os
        # Check for kitty terminal
        term = os.environ.get('TERM', '')
        return 'kitty' in term.lower()
    
    def compose(self) -> ComposeResult:
        """Compose the widget's child components."""
        if not self.image_path:
            yield self._render_placeholder()
            return
        
        path = Path(self.image_path)
        if not path.exists():
            yield self._render_error(f"Image not found: {path}")
            return
        
        if self._has_graphics_support:
            yield self._render_image_kitty(path)
        else:
            yield self._render_image_fallback(path)
    
    def _render_image_kitty(self, path: Path) -> Widget:
        """
        Render image using kitty graphics protocol.
        
        Args:
            path: Path to the image file
            
        Returns:
            Image widget for kitty terminals
        """
        try:
            from textual_image.widget import Image
            return Image(str(path))
        except ImportError:
            logger.warning(
                "textual-image not installed, falling back to path display"
            )
            return self._render_image_fallback(path)
        except Exception as e:
            logger.error(f"Error rendering image with kitty protocol: {e}")
            return self._render_error(f"Error loading image: {e}")
    
    def _render_image_fallback(self, path: Path) -> Widget:
        """
        Render fallback display for terminals without graphics support.
        
        Args:
            path: Path to the image file
            
        Returns:
            Static widget with image information
        """
        from textual.widgets import Static
        
        size_mb = path.stat().st_size / (1024 * 1024)
        text = f"""
📊 Plot Image

File: {path.name}
Size: {size_mb:.2f} MB
Path: {path.parent}

(Graphics display not supported in this terminal)
Use kitty terminal for in-line plot viewing.
        """.strip()
        
        return Static(text, classes="placeholder")
    
    def _render_placeholder(self) -> Widget:
        """Render placeholder when no image is set."""
        from textual.widgets import Static
        return Static(
            "No plot image loaded\n📊", 
            classes="placeholder"
        )
    
    def _render_error(self, error_msg: str) -> Widget:
        """
        Render error message.
        
        Args:
            error_msg: Error message to display
            
        Returns:
            Static widget with error message
        """
        from textual.widgets import Static
        return Static(f"❌ {error_msg}", classes="error")
    
    def update_image(self, new_path: str) -> None:
        """
        Update the displayed image.
        
        Args:
            new_path: Path to new image file
        """
        logger.info(f"Updating plot image to: {new_path}")
        self.image_path = new_path
        self.refresh(recompose=True)
    
    def watch_image_path(self, old_path: str | None, new_path: str | None) -> None:
        """
        React to image_path changes.
        
        Args:
            old_path: Previous image path
            new_path: New image path
        """
        if old_path != new_path:
            self.refresh(recompose=True)
```

**Key Features:**
- Automatic detection of kitty terminal support
- Graceful fallback for unsupported terminals
- Reactive image path updates
- Error handling and logging
- Tokyo Night theme styling

---

### 5.2 PlotReviewScreen

**File:** `src/tui/screens/review/plot_review_screen.py`

```python
"""
PlotReviewScreen - Review generated matplotlib plots in the TUI.

This screen displays the generated plot with metadata and action buttons
for saving configuration, creating new plots, or exiting.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.binding import Binding
from pathlib import Path
import logging
from datetime import datetime

from ...widgets.plot_image import MatplotlibImageWidget

logger = logging.getLogger(__name__)


class PlotReviewScreen(Screen):
    """
    Screen to review generated plots with metadata and action options.
    
    Displays:
    - Generated plot image (via MatplotlibImageWidget)
    - Plot metadata (filename, size, location, generation time)
    - Configuration summary
    - Action buttons (Save Config, New Plot, Exit)
    
    Attributes:
        plot_path: Path to the generated plot file
        config: Configuration dictionary used to generate the plot
        generation_time: Time taken to generate the plot (optional)
    """
    
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("s", "save_config", "Save Config"),
        Binding("n", "new_plot", "New Plot"),
        Binding("q", "quit_app", "Quit"),
    ]
    
    CSS = """
    PlotReviewScreen {
        background: $surface;
    }
    
    #review-container {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }
    
    #review-header {
        width: 100%;
        height: auto;
        padding: 1 0;
        background: $panel;
        border: solid $primary;
    }
    
    #review-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $primary;
        padding: 1;
    }
    
    #plot-container {
        width: 100%;
        height: auto;
        padding: 1 0;
    }
    
    #plot-display {
        width: 100%;
        height: 50vh;
        min-height: 20;
    }
    
    #metadata-container {
        width: 100%;
        height: auto;
        padding: 1 0;
    }
    
    #plot-info {
        width: 100%;
        padding: 1 2;
        background: $panel;
        border: solid $accent;
    }
    
    #plot-info Static {
        padding: 0 1;
    }
    
    #config-summary {
        width: 100%;
        padding: 1 2;
        margin-top: 1;
        background: $panel;
        border: solid $accent;
    }
    
    #config-summary Static {
        padding: 0 1;
    }
    
    #action-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 2 0;
    }
    
    #action-buttons Button {
        margin: 0 1;
        min-width: 20;
    }
    
    .success-text {
        color: $success;
        text-style: bold;
    }
    
    .info-label {
        color: $text-muted;
        text-style: italic;
    }
    """
    
    def __init__(
        self, 
        plot_path: str, 
        config: dict,
        generation_time: float | None = None,
        **kwargs
    ):
        """
        Initialize the plot review screen.
        
        Args:
            plot_path: Path to the generated plot file
            config: Configuration dictionary used for plot generation
            generation_time: Time taken to generate plot in seconds
            **kwargs: Additional screen arguments
        """
        super().__init__(**kwargs)
        self.plot_path = plot_path
        self.config = config
        self.generation_time = generation_time
        
        logger.info(f"Initializing PlotReviewScreen with plot: {plot_path}")
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header(show_clock=True)
        
        with ScrollableContainer(id="review-container"):
            # Header section
            with Container(id="review-header"):
                yield Static("📊 Plot Review", id="review-title")
                yield Static(
                    "✓ Plot generated successfully", 
                    classes="success-text"
                )
            
            # Plot display section
            with Container(id="plot-container"):
                yield MatplotlibImageWidget(
                    image_path=self.plot_path,
                    show_filename=True,
                    id="plot-display"
                )
            
            # Metadata section
            with Container(id="metadata-container"):
                yield from self._create_plot_info()
                yield from self._create_config_summary()
            
            # Action buttons
            with Horizontal(id="action-buttons"):
                yield Button(
                    "💾 Save Configuration", 
                    id="save-btn", 
                    variant="success"
                )
                yield Button(
                    "➕ New Plot", 
                    id="new-btn", 
                    variant="primary"
                )
                yield Button(
                    "🚪 Exit", 
                    id="exit-btn",
                    variant="default"
                )
        
        yield Footer()
    
    def _create_plot_info(self) -> ComposeResult:
        """
        Create plot information section.
        
        Yields:
            Static widgets with plot metadata
        """
        with Vertical(id="plot-info"):
            yield Static("📁 Plot Information", classes="info-label")
            
            plot_file = Path(self.plot_path)
            
            # File information
            if plot_file.exists():
                size_mb = plot_file.stat().st_size / (1024 * 1024)
                modified_time = datetime.fromtimestamp(
                    plot_file.stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M:%S")
                
                yield Static(f"Filename: {plot_file.name}")
                yield Static(f"Size: {size_mb:.2f} MB")
                yield Static(f"Location: {plot_file.parent}")
                yield Static(f"Modified: {modified_time}")
                
                if self.generation_time:
                    yield Static(
                        f"Generation Time: {self.generation_time:.2f}s"
                    )
            else:
                yield Static(
                    f"⚠️ Warning: Plot file not found at {plot_file}",
                    classes="error"
                )
    
    def _create_config_summary(self) -> ComposeResult:
        """
        Create configuration summary section.
        
        Yields:
            Static widgets with configuration details
        """
        with Vertical(id="config-summary"):
            yield Static("⚙️ Configuration Used", classes="info-label")
            
            # Key configuration parameters
            chip = self.config.get('chip_number', 'Unknown')
            plot_type = self.config.get('plot_type', 'Unknown')
            
            yield Static(f"Chip: {chip}")
            yield Static(f"Plot Type: {plot_type}")
            
            # Plot-specific parameters
            if plot_type == "ITS":
                legend_by = self.config.get('legend_by', 'N/A')
                baseline = self.config.get('baseline', 'N/A')
                yield Static(f"Legend By: {legend_by}")
                yield Static(f"Baseline Correction: {baseline}")
            elif plot_type == "IVg":
                legend_by = self.config.get('legend_by', 'N/A')
                yield Static(f"Legend By: {legend_by}")
            elif plot_type == "Transconductance":
                method = self.config.get('method', 'N/A')
                yield Static(f"Method: {method}")
            
            # Experiment count
            seq_numbers = self.config.get('seq_numbers', [])
            yield Static(f"Experiments: {len(seq_numbers)} selected")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        Handle button press events.
        
        Args:
            event: Button press event
        """
        button_id = event.button.id
        
        logger.info(f"Button pressed: {button_id}")
        
        if button_id == "save-btn":
            self.action_save_config()
        elif button_id == "new-btn":
            self.action_new_plot()
        elif button_id == "exit-btn":
            self.action_quit_app()
    
    def action_save_config(self) -> None:
        """Save the current configuration to persistent storage."""
        logger.info("Saving configuration")
        
        try:
            from ...config_manager import ConfigurationManager
            
            config_manager = ConfigurationManager()
            config_manager.save_configuration(
                config=self.config,
                description=None  # Will auto-generate
            )
            
            self.notify(
                "✓ Configuration saved successfully",
                severity="information",
                timeout=3
            )
            
            logger.info("Configuration saved successfully")
            
        except Exception as e:
            error_msg = f"Failed to save configuration: {e}"
            logger.error(error_msg)
            self.notify(
                f"❌ {error_msg}",
                severity="error",
                timeout=5
            )
    
    def action_new_plot(self) -> None:
        """Start a new plot generation workflow."""
        logger.info("Starting new plot workflow")
        
        # Navigate back to chip selector (Step 1)
        self.app.router.go_to_chip_selector()
    
    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        logger.info("Going back from plot review")
        self.app.pop_screen()
    
    def action_quit_app(self) -> None:
        """Exit the application."""
        logger.info("Quitting application from plot review")
        self.app.exit()
```

**Key Features:**
- Comprehensive plot metadata display
- Configuration summary for reference
- Multiple action buttons with keyboard shortcuts
- Scrollable container for long content
- Error handling for missing files
- Integration with ConfigurationManager
- Notification system for user feedback

---

### 5.3 Router Integration

**File:** `src/tui/router.py`

**Modifications needed:**

```python
# Add import at the top of the file
from .screens.review.plot_review_screen import PlotReviewScreen

class Router:
    """Centralized navigation system for the TUI."""
    
    def __init__(self, app):
        self.app = app
    
    # ... existing methods ...
    
    def go_to_plot_review(
        self, 
        plot_path: str,
        generation_time: float | None = None
    ) -> None:
        """
        Navigate to the plot review screen.
        
        Args:
            plot_path: Path to the generated plot file
            generation_time: Optional time taken to generate the plot
        """
        logger.info(f"Navigating to plot review: {plot_path}")
        
        self.app.push_screen(
            PlotReviewScreen(
                plot_path=plot_path,
                config=self.app.session.to_config_dict(),
                generation_time=generation_time
            )
        )
```

---

### 5.4 PlotSuccessScreen Modification

**File:** `src/tui/screens/processing/plot_generation.py`

**Modifications to PlotSuccessScreen:**

```python
class PlotSuccessScreen(Screen):
    """Screen displayed after successful plot generation."""
    
    # ... existing code ...
    
    def compose(self) -> ComposeResult:
        """Compose the success screen layout."""
        yield Header()
        
        with Container(id="success-container"):
            yield Static("✓ Plot Generated Successfully!", id="success-title")
            
            # ... existing metadata display ...
            
            with Horizontal(id="success-actions"):
                # NEW: Add View Plot button
                yield Button(
                    "👁️ View Plot", 
                    id="view-plot-btn", 
                    variant="primary"
                )
                yield Button(
                    "💾 Save Config", 
                    id="save-config-btn", 
                    variant="success"
                )
                yield Button(
                    "➕ New Plot", 
                    id="new-plot-btn", 
                    variant="default"
                )
        
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "view-plot-btn":
            # NEW: Navigate to plot review screen
            self.app.router.go_to_plot_review(
                plot_path=self.plot_path,
                generation_time=self.elapsed_time
            )
        elif button_id == "save-config-btn":
            self.action_save_config()
        elif button_id == "new-plot-btn":
            self.app.router.go_to_chip_selector()
        # ... rest of handlers ...
```

---

## 6. Integration Points

### 6.1 Session State (No Changes Required)

The existing `PlotSession` in `src/tui/session.py` already provides all necessary configuration data via `to_config_dict()`. No modifications needed.

### 6.2 App Registration (src/tui/app.py)

Ensure screens are importable (Python will handle this via __init__.py files):

```python
# In src/tui/widgets/__init__.py
from .plot_image import MatplotlibImageWidget

__all__ = ['MatplotlibImageWidget']
```

```python
# In src/tui/screens/review/__init__.py
from .plot_review_screen import PlotReviewScreen

__all__ = ['PlotReviewScreen']
```

### 6.3 Configuration Manager Integration

The existing `ConfigurationManager` in `src/tui/config_manager.py` will work as-is for saving configurations from the PlotReviewScreen.

### 6.4 Plot Generation Integration

Ensure plot generation saves files to predictable locations:

```python
# In plot generation logic
output_path = Path(output_dir) / f"{chip_name}_{plot_type}_{timestamp}.png"

# Save with matplotlib
plt.savefig(
    output_path,
    format='png',
    dpi=150,
    bbox_inches='tight',
    facecolor='#1a1b26',  # Tokyo Night background
    edgecolor='none'
)
plt.close()

return str(output_path)  # Return path for PlotReviewScreen
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

**File:** `tests/test_plot_image_widget.py`

```python
"""Unit tests for MatplotlibImageWidget."""

import pytest
from pathlib import Path
from src.tui.widgets.plot_image import MatplotlibImageWidget
from textual.app import App


@pytest.fixture
def sample_plot(tmp_path):
    """Create a sample plot image for testing."""
    import matplotlib.pyplot as plt
    
    plot_path = tmp_path / "test_plot.png"
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 2])
    plt.savefig(plot_path)
    plt.close()
    
    return str(plot_path)


def test_widget_initialization():
    """Test widget can be initialized."""
    widget = MatplotlibImageWidget()
    assert widget.image_path is None
    assert widget.show_filename is True


def test_widget_with_image_path(sample_plot):
    """Test widget initialization with image path."""
    widget = MatplotlibImageWidget(image_path=sample_plot)
    assert widget.image_path == sample_plot


def test_update_image(sample_plot):
    """Test updating widget image."""
    widget = MatplotlibImageWidget()
    assert widget.image_path is None
    
    widget.update_image(sample_plot)
    assert widget.image_path == sample_plot


def test_nonexistent_image():
    """Test widget handles nonexistent image gracefully."""
    widget = MatplotlibImageWidget(image_path="/nonexistent/path.png")
    # Should not raise exception during initialization
    assert widget.image_path == "/nonexistent/path.png"
```

### 7.2 Integration Tests

**File:** `tests/test_plot_review_screen.py`

```python
"""Integration tests for PlotReviewScreen."""

import pytest
from pathlib import Path
from src.tui.screens.review.plot_review_screen import PlotReviewScreen
from textual.app import App


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        'chip_number': 'Test123',
        'plot_type': 'ITS',
        'legend_by': 'vg',
        'baseline': 'auto',
        'seq_numbers': [1, 2, 3]
    }


@pytest.fixture
def sample_plot(tmp_path):
    """Create a sample plot for testing."""
    import matplotlib.pyplot as plt
    
    plot_path = tmp_path / "test_plot.png"
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 2])
    plt.savefig(plot_path)
    plt.close()
    
    return str(plot_path)


async def test_screen_initialization(sample_plot, sample_config):
    """Test screen can be initialized with required parameters."""
    screen = PlotReviewScreen(
        plot_path=sample_plot,
        config=sample_config
    )
    
    assert screen.plot_path == sample_plot
    assert screen.config == sample_config


async def test_screen_with_generation_time(sample_plot, sample_config):
    """Test screen handles generation time."""
    screen = PlotReviewScreen(
        plot_path=sample_plot,
        config=sample_config,
        generation_time=2.5
    )
    
    assert screen.generation_time == 2.5


async def test_screen_composition(sample_plot, sample_config):
    """Test screen composes without errors."""
    class TestApp(App):
        pass
    
    app = TestApp()
    async with app.run_test() as pilot:
        screen = PlotReviewScreen(
            plot_path=sample_plot,
            config=sample_config
        )
        
        # Should compose without errors
        list(screen.compose())
```

### 7.3 Manual Testing Checklist

**Test in kitty terminal:**

- [ ] Plot displays correctly with graphics
- [ ] Image scales appropriately to terminal size
- [ ] Metadata displays correctly (filename, size, location)
- [ ] Configuration summary shows correct parameters
- [ ] "Save Config" button works and shows notification
- [ ] "New Plot" button navigates to chip selector
- [ ] "Exit" button closes application
- [ ] Keyboard shortcuts work (s, n, q, escape)
- [ ] Scrolling works for long content
- [ ] Error handling for missing plot files
- [ ] Theme consistency (Tokyo Night colors)

**Test in non-kitty terminal:**

- [ ] Fallback display shows file information
- [ ] Message indicates graphics not supported
- [ ] All other functionality works normally

---

## 8. Troubleshooting

### Common Issues and Solutions

#### Issue 1: Image Not Displaying in Kitty

**Symptoms:** Plot shows placeholder or error message despite kitty terminal

**Solutions:**
1. Verify textual-image is installed: `pip show textual-image`
2. Check TERM environment variable: `echo $TERM` (should contain "kitty")
3. Test kitty graphics: `kitty +kitten icat /path/to/image.png`
4. Check image file exists and is readable
5. Verify image is PNG format (not SVG or other)

#### Issue 2: Import Errors

**Symptoms:** `ModuleNotFoundError` for widgets or screens

**Solutions:**
1. Ensure `__init__.py` files exist in all directories
2. Check import paths are correct
3. Verify relative imports use correct number of dots
4. Try absolute imports if relative imports fail

#### Issue 3: Router Navigation Fails

**Symptoms:** Screen doesn't change or raises AttributeError

**Solutions:**
1. Verify router method is called: `self.app.router.go_to_plot_review(...)`
2. Check plot_path is passed as string, not Path object
3. Ensure app.session.to_config_dict() returns valid dict
4. Add logging to router method to trace execution

#### Issue 4: Plot File Not Found

**Symptoms:** Error message on PlotReviewScreen

**Solutions:**
1. Verify plot generation returns correct path
2. Check file permissions
3. Ensure path is absolute, not relative
4. Verify plot wasn't deleted between generation and review
5. Check output directory exists

#### Issue 5: Styling Issues

**Symptoms:** Layout broken or colors wrong

**Solutions:**
1. Verify CSS property names are correct
2. Check for typos in widget IDs
3. Test with default Textual theme first
4. Use `textual console` for live CSS debugging
5. Check for conflicting CSS rules

---

## 9. Future Enhancements

### Phase 2 Enhancements (After Initial Implementation)

#### 9.1 Live Preview in Configuration Screens

Add real-time plot preview as users adjust parameters:

```python
class ITSConfigScreen(Screen):
    """ITS configuration with live preview."""
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Regenerate preview when parameters change."""
        if self.preview_enabled:
            self.update_preview()
    
    async def update_preview(self) -> None:
        """Generate and display preview plot."""
        preview_path = await self.generate_quick_preview()
        preview_widget = self.query_one(MatplotlibImageWidget)
        preview_widget.update_image(preview_path)
```

#### 9.2 Plot Comparison View

Allow side-by-side comparison of multiple plots:

```python
class PlotComparisonScreen(Screen):
    """Compare multiple plots side-by-side."""
    
    def compose(self) -> ComposeResult:
        with Horizontal():
            for plot_path in self.plot_paths:
                yield MatplotlibImageWidget(image_path=plot_path)
```

#### 9.3 Plot Annotations

Add ability to annotate plots before saving:

```python
class AnnotatedPlotWidget(MatplotlibImageWidget):
    """Widget with annotation capabilities."""
    
    def add_text_annotation(self, text: str, x: int, y: int) -> None:
        """Add text annotation to plot."""
        # Reload matplotlib figure, add annotation, re-save
        pass
```

#### 9.4 Export Options

Add multiple export formats:

```python
class PlotExportDialog(Screen):
    """Dialog for exporting plots in different formats."""
    
    formats = ["PNG", "PDF", "SVG", "EPS"]
    resolutions = [150, 300, 600]  # DPI options
```

#### 9.5 Plot History Browser

Browse previously generated plots:

```python
class PlotHistoryScreen(Screen):
    """Browse and review historical plots."""
    
    def compose(self) -> ComposeResult:
        # Gallery view of previous plots
        # Filter by chip, date, plot type
        pass
```

---

## 10. Implementation Checklist

### Pre-Implementation

- [ ] Review current codebase structure
- [ ] Verify all dependencies are compatible
- [ ] Test kitty terminal graphics protocol
- [ ] Backup current working code
- [ ] Create feature branch: `git checkout -b feature/plot-review-screen`

### Phase 1: MatplotlibImageWidget

- [ ] Create `src/tui/widgets/plot_image.py`
- [ ] Implement base widget class
- [ ] Add kitty graphics support
- [ ] Add fallback rendering
- [ ] Add error handling
- [ ] Write unit tests
- [ ] Test in kitty and non-kitty terminals

### Phase 2: PlotReviewScreen

- [ ] Create `src/tui/screens/review/` directory
- [ ] Create `plot_review_screen.py`
- [ ] Implement screen layout
- [ ] Add metadata display
- [ ] Add configuration summary
- [ ] Implement action buttons
- [ ] Add keyboard shortcuts
- [ ] Write integration tests
- [ ] Test screen navigation

### Phase 3: Router Integration

- [ ] Add import to `router.py`
- [ ] Implement `go_to_plot_review()` method
- [ ] Test navigation from PlotSuccessScreen
- [ ] Verify session data passing

### Phase 4: PlotSuccessScreen Modification

- [ ] Add "View Plot" button
- [ ] Wire button to router method
- [ ] Pass generation time to review screen
- [ ] Test button functionality

### Phase 5: Testing & Documentation

- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Manual testing in kitty
- [ ] Manual testing in non-kitty terminal
- [ ] Update user documentation
- [ ] Update developer documentation
- [ ] Code review
- [ ] Merge to main branch

---

## 11. Code Review Checklist

Before considering implementation complete:

### Functionality
- [ ] All specified features work as expected
- [ ] Error handling covers edge cases
- [ ] Fallback behavior works for non-kitty terminals
- [ ] Keyboard shortcuts function correctly
- [ ] Navigation flow is intuitive

### Code Quality
- [ ] Code follows project style guidelines
- [ ] No hardcoded paths or magic numbers
- [ ] Proper logging throughout
- [ ] Type hints on all function signatures
- [ ] Docstrings for all classes and methods

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Edge cases covered
- [ ] Performance is acceptable

### Documentation
- [ ] Code is well-commented
- [ ] Docstrings are comprehensive
- [ ] README updated if needed
- [ ] Architecture diagram updated if needed

---

## 12. Performance Considerations

### Image Loading Optimization

```python
def optimize_plot_for_display(self, source_path: Path) -> Path:
    """
    Optimize plot image for terminal display.
    
    Args:
        source_path: Path to original high-resolution plot
        
    Returns:
        Path to optimized image
    """
    from PIL import Image
    
    optimized_path = source_path.with_suffix('.optimized.png')
    
    with Image.open(source_path) as img:
        # Resize for terminal display (typical terminal ~200 chars wide)
        # Assuming ~10 pixels per character
        max_width = 2000  # pixels
        
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Optimize PNG compression
        img.save(
            optimized_path,
            'PNG',
            optimize=True,
            compress_level=9
        )
    
    return optimized_path
```

### Lazy Loading

```python
class MatplotlibImageWidget(Widget):
    """Widget with lazy loading support."""
    
    _loaded: bool = False
    
    def on_mount(self) -> None:
        """Load image when widget is mounted."""
        if not self._loaded and self.image_path:
            self._load_image_async()
    
    async def _load_image_async(self) -> None:
        """Load image asynchronously."""
        await asyncio.sleep(0)  # Yield control
        # Load image in background
        self._loaded = True
        self.refresh(recompose=True)
```

---

## 13. Accessibility Considerations

### Screen Reader Support

```python
# Add ARIA labels and descriptions
class PlotReviewScreen(Screen):
    def compose(self) -> ComposeResult:
        # Add descriptive labels for screen readers
        yield Static(
            "Plot review screen. Use tab to navigate between elements.",
            id="screen-description",
            classes="sr-only"  # Screen reader only
        )
```

### Keyboard Navigation

```python
# Ensure all interactive elements are keyboard accessible
BINDINGS = [
    Binding("tab", "focus_next", "Next Element"),
    Binding("shift+tab", "focus_previous", "Previous Element"),
    Binding("enter", "activate", "Activate"),
    # ... other bindings
]
```

---

## 14. Contact and Support

### Questions During Implementation

If you encounter issues or have questions:

1. **Check logs:** `tui_plot_generation.log`
2. **Textual devtools:** `textual console` for live debugging
3. **Textual docs:** https://textual.textualize.io/
4. **textual-image docs:** https://github.com/adamviola/textual-image

### Post-Implementation

After successful implementation:

1. Update this document with any deviations or improvements
2. Add implementation notes to project wiki
3. Document any gotchas or lessons learned
4. Create demo video or screenshots for documentation

---

## Appendix A: Complete File Structure

```
src/tui/
├── app.py
├── router.py                          # MODIFY: Add go_to_plot_review()
├── session.py
├── config_manager.py
├── widgets/
│   ├── __init__.py                    # NEW: Export MatplotlibImageWidget
│   └── plot_image.py                  # NEW: Create this file
├── screens/
│   ├── selection/
│   │   ├── chip_selector.py
│   │   ├── plot_type_selector.py
│   │   ├── config_mode_selector.py
│   │   └── experiment_selector.py
│   ├── configuration/
│   │   ├── its_config.py
│   │   ├── ivg_config.py
│   │   ├── transconductance_config.py
│   │   └── preview_screen.py
│   ├── processing/
│   │   └── plot_generation.py         # MODIFY: Add View Plot button
│   └── review/
│       ├── __init__.py                # NEW: Export PlotReviewScreen
│       └── plot_review_screen.py      # NEW: Create this file
└── utils/
    └── plot_utils.py                  # Optional: Plot helper functions

tests/
├── test_plot_image_widget.py          # NEW: Unit tests
└── test_plot_review_screen.py         # NEW: Integration tests
```

---

## Appendix B: Dependencies Reference

```toml
# pyproject.toml or requirements.txt

[project]
dependencies = [
    "textual>=0.40.0",
    "textual-image>=0.3.0",
    "matplotlib>=3.7.0",
    "pillow>=10.0.0",
    "rich>=13.0.0",
    "polars>=0.19.0",  # Existing
    "pydantic>=2.0.0", # Existing
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "textual-dev>=1.0.0",
]
```

---

## Appendix C: Example Complete Test Session

```python
"""Complete test session for plot review functionality."""

import pytest
from pathlib import Path
import matplotlib.pyplot as plt
from src.tui.app import PlotterApp


@pytest.fixture
def app_with_data(tmp_path):
    """Create app instance with test data."""
    # Create test directories
    stage_dir = tmp_path / "stage"
    history_dir = tmp_path / "histories"
    output_dir = tmp_path / "output"
    
    stage_dir.mkdir()
    history_dir.mkdir()
    output_dir.mkdir()
    
    # Create test app
    app = PlotterApp(
        stage_dir=str(stage_dir),
        history_dir=str(history_dir),
        output_dir=str(output_dir),
        chip_group="TestGroup"
    )
    
    return app, output_dir


@pytest.fixture
def generated_plot(tmp_path):
    """Generate a test plot."""
    plot_path = tmp_path / "test_plot.png"
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot([1, 2, 3, 4], [1, 4, 2, 3])
    ax.set_title("Test Plot")
    ax.set_xlabel("X Axis")
    ax.set_ylabel("Y Axis")
    
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return str(plot_path)


async def test_full_plot_review_workflow(app_with_data, generated_plot):
    """Test complete workflow from generation to review."""
    app, output_dir = app_with_data
    
    async with app.run_test() as pilot:
        # Simulate navigation to plot review
        app.router.go_to_plot_review(
            plot_path=generated_plot,
            generation_time=2.5
        )
        
        # Wait for screen to load
        await pilot.pause()
        
        # Verify screen is displayed
        screen = app.screen
        assert screen.__class__.__name__ == "PlotReviewScreen"
        
        # Test keyboard shortcut
        await pilot.press("s")  # Save config
        await pilot.pause()
        
        # Verify notification appeared
        # (Implementation specific)
        
        # Test button navigation
        await pilot.click("#new-btn")
        await pilot.pause()
        
        # Should navigate back to chip selector
        assert app.screen.__class__.__name__ == "ChipSelectorScreen"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-09 | Claude | Initial comprehensive implementation guide |

---

**End of Implementation Guide**

This document provides complete specifications for implementing matplotlib plot display functionality in the Textual TUI. Follow the phases sequentially, test thoroughly, and refer to the troubleshooting section as needed.

Good luck with the implementation! 🚀
