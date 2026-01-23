# Router Integration for Experiment Preview Screen

## Quick Start - Add to Router

Add this method to `src/tui/router.py`:

```python
def go_to_experiment_preview(self) -> None:
    """
    Navigate to experiment data preview screen.

    Shows terminal-based plots of selected experiments using plotext.
    Allows interactive navigation through experiments before final plot generation.

    Requires:
    - session.chip_number
    - session.chip_group
    - session.plot_type
    - session.seq_numbers (non-empty list)

    Raises
    ------
    ValueError
        If required session fields not set or seq_numbers is empty
    """
    from src.tui.screens.analysis import ExperimentPreviewScreen

    # Validate session state
    if self.app.session.chip_number is None:
        raise ValueError("chip_number must be set")
    if self.app.session.plot_type is None:
        raise ValueError("plot_type must be set")
    if not self.app.session.seq_numbers:
        raise ValueError("seq_numbers must be non-empty list")

    # Create and push preview screen
    self.app.push_screen(ExperimentPreviewScreen(
        chip_number=self.app.session.chip_number,
        chip_group=self.app.session.chip_group,
        plot_type=self.app.session.plot_type,
        seq_numbers=self.app.session.seq_numbers,
        history_dir=self.app.session.history_dir,
        stage_dir=self.app.session.stage_dir
    ))
```

## Integration Points

### Option 1: Add as Optional Step (Recommended)

Add a "Preview Data" button in the **ExperimentSelectorScreen**:

```python
# In src/tui/screens/selection/experiment_selector.py

def compose_footer(self) -> ComposeResult:
    """Add footer with navigation buttons."""
    with Horizontal(id="button-container"):
        yield Button("← Back", id="back-button", variant="default")
        yield Button("👁 Preview Data", id="preview-button", variant="default")  # NEW!
        yield Button("Next →", id="next-button", variant="primary")

def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle button presses."""
    if event.button.id == "back-button":
        self.action_back()

    elif event.button.id == "preview-button":
        # NEW: Go to data preview
        selected = self._get_selected_experiments()
        if not selected:
            self.app.notify("Please select at least one experiment", severity="warning")
            return

        # Update session
        self.app.session.seq_numbers = selected

        # Navigate to preview
        self.app.router.go_to_experiment_preview()

    elif event.button.id == "next-button":
        # Continue to regular flow (skip preview)
        selected = self._get_selected_experiments()
        self.app.session.seq_numbers = selected
        self.app.router.go_to_preview()  # Original flow
```

### Option 2: Make Preview Mandatory

Replace the current flow to **always** show preview:

```python
# In src/tui/screens/selection/experiment_selector.py

def action_next(self) -> None:
    """Save selection and go to data preview."""
    selected = self._get_selected_experiments()

    if not selected:
        self.app.notify("Please select at least one experiment", severity="warning")
        return

    # Update session
    self.app.session.seq_numbers = selected

    # CHANGED: Always go to data preview first
    self.app.router.go_to_experiment_preview()
```

Then update the **ExperimentPreviewScreen** "Continue" button to go to the next step:

```python
# In src/tui/screens/analysis/experiment_preview.py

def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle button presses."""
    if event.button.id == "back-button":
        self.action_back()
    elif event.button.id == "next-button":
        # Continue to config preview (original next step)
        self.app.router.go_to_preview()
```

### Option 3: Quick Access from Main Menu

Add a "Browse & Preview Data" option in the main menu:

```python
# In src/tui/screens/navigation/main_menu.py

def compose_content(self) -> ComposeResult:
    """Compose main menu options."""
    yield Static("What would you like to do?", classes="section-title")

    with Container(id="menu-container"):
        yield Button("📊 Generate New Plot", id="new-plot-button", variant="primary")
        yield Button("👁 Browse & Preview Data", id="browse-data-button", variant="default")  # NEW!
        yield Button("📂 Recent Configurations", id="recent-button", variant="default")
        # ... other buttons ...

def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle button presses."""
    if event.button.id == "new-plot-button":
        self.app.router.go_to_chip_selector(mode="plot")

    elif event.button.id == "browse-data-button":
        # NEW: Quick preview flow
        self.app.router.go_to_chip_selector(mode="preview")
```

Then update ChipSelector to handle "preview" mode:

```python
# In src/tui/screens/selection/chip_selector.py

def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle chip selection."""
    chip_number = self._extract_chip_number(event.button.label)
    self.app.session.chip_number = chip_number

    if self.mode == "preview":
        # NEW: Go directly to experiment browser for preview
        self.app.router.go_to_experiment_browser()
    else:
        # Normal plot flow
        self.app.router.go_to_plot_type_selector()
```

## Complete Wizard Flow Examples

### Flow 1: Optional Preview (Recommended)

```
Main Menu
    ↓
Chip Selector (Step 1)
    ↓
Plot Type Selector (Step 2)
    ↓
Config Mode Selector (Step 3)
    ↓
Plot Config (Step 4)
    ↓
Experiment Selector (Step 5)
    ↓ ↓ ↓
    ├─→ [Preview Data Button] → ExperimentPreviewScreen (NEW!)
    │                                ↓
    │                           [Continue]
    │                                ↓
    └─→ [Next Button] ──────────────→ Preview Screen (Step 6)
                                         ↓
                                   Plot Generation (Step 7)
```

### Flow 2: Mandatory Preview

```
Main Menu
    ↓
Chip Selector (Step 1)
    ↓
Plot Type Selector (Step 2)
    ↓
Config Mode Selector (Step 3)
    ↓
Plot Config (Step 4)
    ↓
Experiment Selector (Step 5)
    ↓
ExperimentPreviewScreen (Step 5.5 - NEW!)
    ↓
Preview Screen (Step 6)
    ↓
Plot Generation (Step 7)
```

### Flow 3: Quick Preview Mode

```
Main Menu
    ↓
[Browse & Preview Data]
    ↓
Chip Selector (preview mode)
    ↓
Experiment Browser/Selector
    ↓
ExperimentPreviewScreen (NEW!)
    ↓ ↓
    ├─→ [Export Preview] → Save terminal plot
    └─→ [Generate Plot] → Go to Plot Generation
```

## Testing the Integration

### 1. Install Dependencies

```bash
source .venv/bin/activate
pip install plotext>=5.0.0
```

### 2. Test Standalone

```python
# test_preview.py
from pathlib import Path
from src.tui.screens.analysis import ExperimentPreviewScreen

preview = ExperimentPreviewScreen(
    chip_number=67,
    chip_group="Alisson",
    plot_type="ITS",
    seq_numbers=[52, 57, 58],
    history_dir=Path("data/02_stage/chip_histories"),
    stage_dir=Path("data/02_stage/raw_measurements")
)

# Run in TUI context
from src.tui.app import PlotterApp
app = PlotterApp()
app.push_screen(preview)
app.run()
```

### 3. Test in Full Flow

```bash
python3 tui_app.py
```

Navigate through wizard to experiment selector, then click "Preview Data" button.

## Error Handling

The preview screen includes built-in error handling:

```python
# Missing dependencies
if pl is None or plt is None:
    self.query_one("#plot-display", Static).update(
        "❌ Error: polars or plotext not installed"
    )
    return

# Missing data file
if not parquet_path.exists():
    return f"❌ Data file not found: {parquet_path}"

# Unsupported procedure
if procedure not in SUPPORTED_PROCEDURES:
    return f"⚠ Preview not implemented for procedure: {procedure}"
```

## Configuration

### Enable/Disable Preview

Add a setting to control preview availability:

```python
# In src/tui/settings_manager.py

class Settings(BaseModel):
    # ... existing fields ...

    enable_data_preview: bool = Field(
        default=True,
        description="Enable terminal data preview before plot generation"
    )

# In router.py - check setting before showing preview
def go_to_experiment_preview(self) -> None:
    """Navigate to experiment data preview."""
    if not self.app.settings_manager.enable_data_preview:
        self.app.notify("Data preview disabled", severity="warning")
        return self.go_to_preview()  # Skip to next step

    # ... rest of method ...
```

### Preview Size Configuration

```python
# In src/tui/settings_manager.py

class Settings(BaseModel):
    # ... existing fields ...

    preview_plot_width: int = Field(
        default=100,
        ge=60,
        le=200,
        description="Terminal plot width in characters"
    )

    preview_plot_height: int = Field(
        default=25,
        ge=15,
        le=50,
        description="Terminal plot height in lines"
    )

# In experiment_preview.py - use settings
def _render_its_plot(self, df: pl.DataFrame, exp: dict) -> str:
    """Render with configured size."""
    settings = self.app.settings_manager

    plt.plot_size(
        width=settings.preview_plot_width,
        height=settings.preview_plot_height
    )
    # ... rest of rendering ...
```

## Summary

To integrate the ExperimentPreviewScreen:

1. ✅ **Add dependency**: `pip install plotext`
2. ✅ **Add router method**: `go_to_experiment_preview()`
3. ✅ **Choose integration point**: Optional button, mandatory step, or quick access
4. ✅ **Update navigation flow**: Connect preview screen to wizard
5. ✅ **Test**: Verify data loads and plots render correctly

The preview screen is now ready to use! 🎉
