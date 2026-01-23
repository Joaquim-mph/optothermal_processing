# TUI Experiment Preview Screen - Implementation Guide

## Overview

The `ExperimentPreviewScreen` provides **terminal-based data visualization** for selected experiments before generating final plots. It uses **plotext** to render plots directly in the terminal, allowing users to quickly check data quality and verify their selection.

## Features

✅ **Procedure-wise rendering** - Different plot types for each procedure (IVg, It, VVg, Vt, LaserCalibration)
✅ **Interactive navigation** - Use arrow keys to browse through experiments
✅ **Fast preview** - Terminal plots render instantly (no file I/O)
✅ **Metadata display** - Shows experiment parameters alongside plots
✅ **Wizard integration** - Fits seamlessly into existing TUI workflow

## Installation

First, install plotext:

```bash
source .venv/bin/activate
pip install plotext>=5.0.0

# Or with uv
uv pip install plotext
```

## Usage

### Basic Usage

```python
from pathlib import Path
from src.tui.screens.analysis import ExperimentPreviewScreen

# Create preview screen
preview = ExperimentPreviewScreen(
    chip_number=67,
    chip_group="Alisson",
    plot_type="ITS",
    seq_numbers=[52, 57, 58],
    history_dir=Path("data/02_stage/chip_histories"),
    stage_dir=Path("data/02_stage/raw_measurements")
)

# Push to app
app.push_screen(preview)
```

### Integration into Wizard Flow

The preview screen fits **between experiment selection and plot generation**:

**Current Flow:**
```
ChipSelector → PlotTypeSelector → ConfigMode → ExperimentSelector → PreviewScreen → PlotGeneration
```

**With Data Preview:**
```
ChipSelector → PlotTypeSelector → ConfigMode → ExperimentSelector →
    ExperimentPreviewScreen (NEW!) → PreviewScreen → PlotGeneration
```

### Example Integration in Router

Update `src/tui/router.py` to add the preview step:

```python
def go_to_experiment_preview(self) -> None:
    """Navigate to experiment data preview screen."""
    from src.tui.screens.analysis import ExperimentPreviewScreen

    preview = ExperimentPreviewScreen(
        chip_number=self.app.session.chip_number,
        chip_group=self.app.session.chip_group,
        plot_type=self.app.session.plot_type,
        seq_numbers=self.app.session.seq_numbers,
        history_dir=self.app.session.history_dir,
        stage_dir=self.app.session.stage_dir
    )

    self.app.push_screen(preview)
```

Then update the experiment selector to call this:

```python
# In ExperimentSelectorScreen
def action_next(self) -> None:
    """Save selection and go to data preview."""
    selected = self._get_selected_experiments()
    self.app.session.seq_numbers = selected

    # NEW: Go to data preview instead of config preview
    self.app.router.go_to_experiment_preview()
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| `←` / `h` | Previous experiment |
| `→` / `l` | Next experiment |
| `r` | Refresh current plot |
| `Enter` | Continue to next step |
| `Esc` | Go back |
| `Ctrl+Q` | Quit application |

## Procedure-Specific Plots

### 1. ITS / It Plots (Current vs Time)

```
┌─ Current vs Time - Seq 52 ─────────────────┐
│                                             │
│  2.5 ┤                    ╭───────╮         │
│      │                   ╭╯       ╰╮        │
│  2.0 ┤                  ╭╯         ╰╮       │
│      │                 ╭╯           ╰╮      │
│  1.5 ┤────────────────╯              ╰─────│
│                                             │
│           Time (s) →                        │
└─────────────────────────────────────────────┘

Seq: 52 | Procedure: It
VG: -0.4 V | VDS: 0.1 V | Wavelength: 365 nm
Light: 💡 light
```

### 2. IVg Plots (Current vs Gate Voltage)

```
┌─ IVg Curve - Seq 2 ────────────────────────┐
│                                             │
│      ┤           ╭──╮                       │
│      │          ╭╯  ╰╮                      │
│      ┤         ╭╯    ╰╮                     │
│      │        ╭╯      ╰╮                    │
│      ┤───────╯        ╰────────             │
│                                             │
│           VG (V) →                          │
└─────────────────────────────────────────────┘

Seq: 2 | Procedure: IVg
VDS: 0.1 V
Light: 🌙 dark
```

### 3. VVg Plots (Voltage vs Gate Voltage)

Shows drain-source voltage response as gate voltage is swept.

### 4. Vt Plots (Voltage vs Time)

Shows drain-source voltage dynamics over time.

### 5. LaserCalibration Plots (Power vs Laser Voltage)

Shows calibration curve for power interpolation.

## Customization

### Adding New Procedures

To add support for a new procedure type, add a renderer method:

```python
def _render_my_procedure_plot(self, df: pl.DataFrame, exp: dict) -> str:
    """Render plot for MyProcedure."""
    # Extract data from dataframe
    x = df["x_column"].to_numpy()
    y = df["y_column"].to_numpy()

    # Configure plot size
    plt.plot_size(width=100, height=25)
    plt.plotsize(100, 25)

    # Plot data
    plt.plot(x, y)

    # Labels
    plt.title(f"My Plot - Seq {exp['seq']}")
    plt.xlabel("X Axis")
    plt.ylabel("Y Axis")

    # Theme (dark/light/matrix/etc.)
    plt.theme("dark")

    # Capture and return
    return self._capture_plotext_output()
```

Then update the router in `_render_plot_for_procedure()`:

```python
def _render_plot_for_procedure(self, exp: dict) -> str:
    procedure = exp['procedure']

    # ... existing code ...

    elif procedure == 'MyProcedure':
        return self._render_my_procedure_plot(measurement, exp)
```

### Customizing Plot Appearance

Plotext supports several themes and customization options:

```python
# Themes
plt.theme("dark")      # Dark background (default)
plt.theme("clear")     # Light background
plt.theme("matrix")    # Matrix green
plt.theme("windows")   # Windows classic

# Size
plt.plot_size(width=120, height=30)  # Wider plot
plt.plotsize(80, 20)                 # Compact plot

# Colors
plt.plot(x, y, color="red")
plt.plot(x, y, marker="braille")  # High-res markers

# Grid
plt.grid(True, True)  # Horizontal and vertical grids
```

### Making It Optional

You can make the preview screen **optional** in the wizard flow:

```python
# In ExperimentSelectorScreen
def compose_footer(self) -> ComposeResult:
    """Add preview option."""
    with Horizontal(id="button-container"):
        yield Button("← Back", id="back-button")
        yield Button("Preview Data", id="preview-button", variant="default")
        yield Button("Continue →", id="next-button", variant="primary")

def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle button presses."""
    if event.button.id == "preview-button":
        # Go to preview
        self.app.router.go_to_experiment_preview()
    elif event.button.id == "next-button":
        # Skip preview, go directly to confirmation
        self.app.router.go_to_preview()
```

## Performance Considerations

### Memory Usage

- plotext renders plots in memory (no file I/O)
- Each plot is ~2-5 KB of text
- Recommended: limit to 100 experiments per preview session

### Rendering Speed

- Terminal plots render **instantly** (~10-50ms per plot)
- Much faster than matplotlib (100-500ms)
- No disk writes needed

### Data Loading

The screen caches:
- ✅ Chip history DataFrame (loaded once)
- ✅ Experiment metadata list (converted to dicts)
- ❌ Measurement data (loaded on-demand per experiment)

For better performance with many experiments:

```python
def _load_history(self) -> None:
    """Load and cache all measurement data."""
    # ... existing code ...

    # Optional: pre-load all measurement data
    self._measurement_cache = {}
    for exp in self._experiments:
        parquet_path = Path(exp['parquet_path'])
        self._measurement_cache[exp['seq']] = read_measurement_parquet(parquet_path)
```

## Troubleshooting

### Plot Not Rendering

**Issue:** Plot shows as blank or garbled text

**Solution:** Check terminal width (plotext needs min 80 columns):
```python
import shutil
width, height = shutil.get_terminal_size()
print(f"Terminal size: {width}x{height}")  # Should be at least 80x24
```

### ImportError: plotext not found

**Solution:** Install plotext in the active virtual environment:
```bash
source .venv/bin/activate
pip install plotext>=5.0.0
```

### Data File Not Found

**Issue:** `parquet_path` points to non-existent file

**Solution:** Ensure staging pipeline has run:
```bash
python3 process_and_analyze.py stage-all
python3 process_and_analyze.py build-all-histories
```

### Slow Navigation

**Issue:** Switching experiments is slow

**Solution:** Enable measurement caching (see Performance section above)

## Examples

### Example 1: Preview ITS Experiments

```python
from src.tui.screens.analysis import ExperimentPreviewScreen

# Preview photoresponse measurements
preview = ExperimentPreviewScreen(
    chip_number=67,
    chip_group="Alisson",
    plot_type="ITS",
    seq_numbers=[52, 57, 58, 59, 60],  # Multiple experiments
)

app.push_screen(preview)
```

### Example 2: Preview IVg Sweeps

```python
# Preview gate voltage sweeps
preview = ExperimentPreviewScreen(
    chip_number=81,
    chip_group="Alisson",
    plot_type="IVg",
    seq_numbers=[2, 8, 14, 20],
)

app.push_screen(preview)
```

### Example 3: Preview VVg Measurements

```python
# Preview voltage vs gate measurements
preview = ExperimentPreviewScreen(
    chip_number=75,
    chip_group="Encap",
    plot_type="VVg",
    seq_numbers=[100, 101, 102],
)

app.push_screen(preview)
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  ExperimentPreviewScreen                    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   Header     │  │ Experiment   │  │  Plot Display   │  │
│  │  (Chip Info) │  │  Metadata    │  │  (plotext)      │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │          Navigation Controls (← → R)                  │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────┐                     ┌──────────────────┐ │
│  │  ← Back      │                     │  Continue →      │ │
│  └──────────────┘                     └──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                         ↓
                ┌────────────────────┐
                │  Data Flow:        │
                │                    │
                │  1. Load history   │
                │  2. Filter by seq  │
                │  3. Load parquet   │
                │  4. Render plot    │
                │  5. Display text   │
                └────────────────────┘
```

## Future Enhancements

Possible improvements for future versions:

1. **Multi-experiment overlay preview** - Show all experiments on one plot
2. **Statistical summary** - Show mean, std, min/max before plotting
3. **Export preview** - Save terminal plot to text file
4. **Zoom controls** - Interactive zoom for detailed inspection
5. **Plot annotations** - Mark features (peaks, plateaus, etc.)
6. **Comparison mode** - Side-by-side plots of two experiments
7. **Colorized plots** - Use ANSI colors for better visualization

## Related Documentation

- [Textual Documentation](https://textual.textualize.io/)
- [plotext Documentation](https://github.com/piccolomo/plotext)
- [TUI Architecture](../src/tui/README.md)
- [Plotting Implementation Guide](./PLOTTING_IMPLEMENTATION_GUIDE.md)

## Summary

The `ExperimentPreviewScreen` provides:
- ✅ **Fast terminal-based visualization** using plotext
- ✅ **Procedure-specific rendering** for all measurement types
- ✅ **Interactive navigation** with keyboard controls
- ✅ **Easy integration** into existing wizard flow
- ✅ **Extensible design** for adding new procedures

Use it to **preview data quality** before generating final plots, saving time and avoiding unnecessary plot generation!
