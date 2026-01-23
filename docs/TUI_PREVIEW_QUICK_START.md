# TUI Experiment Preview - Quick Start

## 🚀 Installation (1 minute)

```bash
# Activate environment
source .venv/bin/activate

# Install plotext
pip install plotext>=5.0.0

# Verify
python3 -c "import plotext; print('✓ plotext installed')"
```

## 📦 What's Included

- ✅ **ExperimentPreviewScreen** - Main preview screen (`src/tui/screens/analysis/experiment_preview.py`)
- ✅ **Procedure renderers** - IVg, It/ITS, VVg, Vt, LaserCalibration
- ✅ **Interactive navigation** - Arrow keys to browse experiments
- ✅ **Metadata display** - Shows experiment parameters
- ✅ **Documentation** - Complete guides in `docs/`

## 🎯 Basic Usage

```python
from src.tui.screens.analysis import ExperimentPreviewScreen

# Create preview
preview = ExperimentPreviewScreen(
    chip_number=67,
    chip_group="Alisson",
    plot_type="ITS",
    seq_numbers=[52, 57, 58]
)

# Show in TUI
app.push_screen(preview)
```

## 🔌 Router Integration (Copy-Paste)

Add to `src/tui/router.py`:

```python
def go_to_experiment_preview(self) -> None:
    """Navigate to experiment data preview screen."""
    from src.tui.screens.analysis import ExperimentPreviewScreen

    if self.app.session.chip_number is None:
        raise ValueError("chip_number must be set")
    if not self.app.session.seq_numbers:
        raise ValueError("seq_numbers must be non-empty")

    self.app.push_screen(ExperimentPreviewScreen(
        chip_number=self.app.session.chip_number,
        chip_group=self.app.session.chip_group,
        plot_type=self.app.session.plot_type,
        seq_numbers=self.app.session.seq_numbers,
        history_dir=self.app.session.history_dir,
        stage_dir=self.app.session.stage_dir
    ))
```

## 🎨 Add to Experiment Selector

In `src/tui/screens/selection/experiment_selector.py`, add preview button:

```python
def compose_footer(self) -> ComposeResult:
    with Horizontal(id="button-container"):
        yield Button("← Back", id="back-button")
        yield Button("👁 Preview", id="preview-button")  # NEW!
        yield Button("Next →", id="next-button", variant="primary")

def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "preview-button":
        selected = self._get_selected_experiments()
        self.app.session.seq_numbers = selected
        self.app.router.go_to_experiment_preview()  # NEW!
    # ... rest of handlers ...
```

## ⌨️ Keyboard Controls

| Key | Action |
|-----|--------|
| `←` / `h` | Previous experiment |
| `→` / `l` | Next experiment |
| `r` | Refresh plot |
| `Enter` | Continue |
| `Esc` | Back |

## 📊 Supported Procedures

- ✅ **It/ITS** - Current vs Time (photoresponse)
- ✅ **IVg** - Current vs Gate Voltage
- ✅ **VVg** - Voltage vs Gate Voltage
- ✅ **Vt** - Voltage vs Time
- ✅ **LaserCalibration** - Power calibration curves

## 🔧 Adding New Procedures

1. Add renderer method in `experiment_preview.py`:

```python
def _render_my_procedure_plot(self, df: pl.DataFrame, exp: dict) -> str:
    """Render MyProcedure plot."""
    x = df["x_col"].to_numpy()
    y = df["y_col"].to_numpy()

    plt.plot_size(width=100, height=25)
    plt.plot(x, y)
    plt.title(f"My Plot - Seq {exp['seq']}")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.theme("dark")

    return self._capture_plotext_output()
```

2. Add to router in `_render_plot_for_procedure()`:

```python
elif procedure == 'MyProcedure':
    return self._render_my_procedure_plot(measurement, exp)
```

## 📚 Documentation

- **Complete Guide**: `docs/TUI_EXPERIMENT_PREVIEW_GUIDE.md`
- **Router Integration**: `docs/TUI_PREVIEW_ROUTER_INTEGRATION.md`
- **This Quick Start**: `docs/TUI_PREVIEW_QUICK_START.md`

## 🐛 Troubleshooting

### Plot not showing?
```bash
# Check terminal size (needs 80+ columns)
python3 -c "import shutil; print(shutil.get_terminal_size())"
```

### Import error?
```bash
pip install plotext polars
```

### Data not found?
```bash
# Run staging pipeline first
python3 process_and_analyze.py stage-all
python3 process_and_analyze.py build-all-histories
```

## ✅ Test It

```bash
# Run TUI
python3 tui_app.py

# Navigate: Main Menu → Generate Plot → Chip → Plot Type → Config → Experiments
# Click "Preview Data" button
# Use ← → to browse experiments
```

## 🎉 You're Done!

The preview screen is fully implemented and documented. Just:
1. Install plotext
2. Add router method
3. Add preview button to experiment selector
4. Test!

Enjoy fast terminal-based data previews! 🚀
