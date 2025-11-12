# TUI Version 3.0 Upgrade Plan

**Document Version:** 1.0
**Date:** 2025-11-09
**Status:** Planning Phase

## Executive Summary

This document outlines the complete upgrade path for modernizing the Terminal User Interface (TUI) from v2.x to v3.0. The upgrade adds support for derived metrics, new plot types (VVg, Vt, CNP time, Photoresponse, Laser Calibration), enriched chip histories, and data pipeline integration.

**Current State:** TUI supports ITS, IVg, and Transconductance plotting only
**Target State:** Full v3.0 feature parity with CLI pipeline

**Estimated Effort:** 3-4 days (20-25 hours)
**Risk Level:** Low (existing architecture is solid, mainly additive changes)

---

## Table of Contents

1. [Architecture Review](#architecture-review)
2. [Gap Analysis](#gap-analysis)
3. [Implementation Phases](#implementation-phases)
4. [Detailed Changes by Phase](#detailed-changes-by-phase)
5. [Testing Strategy](#testing-strategy)
6. [Rollout Plan](#rollout-plan)
7. [Backward Compatibility](#backward-compatibility)

---

## Architecture Review

### Current TUI Architecture (v2.x)

**✅ Strengths:**
- Clean separation of concerns (router, session, config manager)
- Type-safe state management via Pydantic (`PlotSession`)
- Auto-discovery of chips from Parquet histories
- Wizard-style flow with 6 steps
- Background plot generation with error handling
- Configuration persistence and recent configs feature
- Textual-based modern terminal UI

**❌ Current Limitations:**
- Only 3 plot types: ITS (It), IVg, Transconductance
- No derived metrics support (CNP, photoresponse)
- No data pipeline integration (staging, history building, metrics extraction)
- Missing enriched history support with calibration data
- No PlotConfig integration (theme, DPI settings)
- No data export formatters (JSON/CSV output)

**Directory Structure:**
```
src/tui/
├── app.py                      # Main PlotterApp
├── router.py                   # Navigation router
├── session.py                  # PlotSession state (Pydantic)
├── config_manager.py           # Configuration persistence
├── settings_manager.py         # Theme/UI settings
└── screens/
    ├── base.py                 # Base screen classes
    ├── navigation/             # Main menu, recent configs, theme settings
    ├── selection/              # Chip, plot type, config mode, experiment selectors
    ├── configuration/          # ITS, IVg, Transconductance config forms
    ├── processing/             # Plot generation, data processing loaders
    ├── results/                # Success/error screens
    └── analysis/               # History browser
```

---

## Gap Analysis

### Missing Features (by Category)

#### 1. **New Plot Types** (5 missing)
| Plot Type | CLI Command | Data Source | Priority |
|-----------|-------------|-------------|----------|
| VVg (Drain-source voltage vs gate voltage) | `plot-vvg` | `VVg` procedure | HIGH |
| Vt (Voltage vs time) | `plot-vt` | `Vt` procedure | HIGH |
| CNP Time (Dirac point evolution) | `plot-cnp-time` | Derived metrics | HIGH |
| Photoresponse (vs power/wavelength/gate/time) | `plot-photoresponse` | Derived metrics | HIGH |
| Laser Calibration | `plot-laser-calibration` | `LaserCalibration` procedure | MEDIUM |
| ITS Relaxation | `plot-its-relaxation` | `It` procedure | LOW |

#### 2. **Data Pipeline Integration** (3 missing commands)
| Feature | CLI Command | Description | Priority |
|---------|-------------|-------------|----------|
| Full Pipeline | `full-pipeline` | Stage + history generation | HIGH |
| Derive Metrics | `derive-all-metrics` | Extract CNP, photoresponse, calibration power | HIGH |
| Enrich History | `enrich-history` | Join calibrations and metrics to histories | HIGH |

#### 3. **Configuration & Plotting Infrastructure**
- **PlotConfig integration:** TUI doesn't use `src/plotting/config.py` (theme, DPI, format settings)
- **Enriched history support:** Can't read from `data/03_derived/chip_histories_enriched/`
- **Output formatters:** No JSON/CSV export like CLI `--format` option

#### 4. **Session State Updates**
- **PlotSession model:** Missing fields for new plot types (VVg, Vt parameters)
- **PlotSession model:** Missing fields for derived metric plots (CNP, photoresponse parameters)
- **PlotSession model:** Missing data pipeline configuration (staging workers, strict mode, etc.)

---

## Implementation Phases

### **Phase 1: Foundation & Infrastructure** (4-5 hours)
**Goal:** Add support for enriched histories, PlotConfig integration, and extend session state

**Tasks:**
1. Update `PlotSession` model with new plot types and parameters
2. Add enriched history detection and reading logic
3. Integrate `src/plotting/config.py` PlotConfig for consistent theming
4. Update router with new navigation targets

**Risk:** Low (additive changes only)

### **Phase 2: New Measurement Plot Types** (3-4 hours)
**Goal:** Add VVg and Vt plot support (measurement-based, no derived metrics)

**Tasks:**
1. Add VVg and Vt options to PlotTypeSelectorScreen
2. Create VVgConfigScreen and VtConfigScreen
3. Update plot_generation.py to call new plotting functions
4. Test with real chip data

**Risk:** Low (follows existing patterns from IVg/ITS)

### **Phase 3: Derived Metrics Plot Types** (4-5 hours)
**Goal:** Add CNP time and Photoresponse plots (requires enriched histories)

**Tasks:**
1. Add CNP and Photoresponse options to PlotTypeSelectorScreen
2. Create CNPConfigScreen and PhotoresponseConfigScreen
3. Update experiment selector to filter for enriched data availability
4. Update plot_generation.py to call derived metric plotting functions
5. Add warnings when enriched data not available

**Risk:** Medium (depends on enriched history availability)

### **Phase 4: Data Pipeline Integration** (5-6 hours)
**Goal:** Add data processing menu and pipeline commands to TUI

**Tasks:**
1. Create DataPipelineMenuScreen with 3 options:
   - Stage All Data (stage-all)
   - Generate Chip Histories (build-all-histories)
   - Extract Derived Metrics (derive-all-metrics)
   - Enrich Histories (enrich-history -a)
2. Create pipeline loading screens with progress
3. Add pipeline status checks and error handling
4. Update main menu with "Data Pipeline" button

**Risk:** Medium (threading concerns with multiprocessing pipeline)

### **Phase 5: Laser Calibration & ITS Relaxation** (3-4 hours)
**Goal:** Add remaining specialized plot types

**Tasks:**
1. Add Laser Calibration plot option
2. Add ITS Relaxation plot option (individual + batch modes)
3. Create configuration screens
4. Update plot_generation.py

**Risk:** Low (straightforward plotting functions)

### **Phase 6: Polish & Testing** (2-3 hours)
**Goal:** End-to-end testing, documentation, and refinement

**Tasks:**
1. Test all plot types with real data
2. Verify enriched history fallback logic
3. Update help screens and tooltips
4. Add keyboard shortcuts for new features
5. Update TUI_GUIDE.md documentation

**Risk:** Low

---

## Detailed Changes by Phase

### **PHASE 1: Foundation & Infrastructure** 📐

#### 1.1 Update `src/tui/session.py` (PlotSession model)

**Add new plot type fields:**
```python
@field_validator("plot_type")
@classmethod
def validate_plot_type(cls, v: Optional[str]) -> Optional[str]:
    """Validate plot type is one of the supported types."""
    valid_types = [
        "ITS", "IVg", "Transconductance",  # Existing
        "VVg", "Vt",                        # New measurement plots
        "CNP", "Photoresponse",             # New derived metric plots
        "LaserCalibration", "ITSRelaxation" # New specialized plots
    ]
    if v is not None and v not in valid_types:
        raise ValueError(f"Invalid plot_type: {v}. Must be one of {valid_types}")
    return v
```

**Add VVg/Vt-specific parameters:**
```python
# VVg/Vt Plot Parameters
vvg_vt_mode: str = Field(
    default="standard",
    description="Plotting mode: 'standard', 'normalized', or 'derivative'"
)
```

**Add CNP/Photoresponse-specific parameters:**
```python
# CNP Time Plot Parameters
cnp_metric: str = Field(
    default="cnp_voltage",
    description="CNP metric to plot: 'cnp_voltage', 'cnp_current', 'mobility'"
)

cnp_show_illumination: bool = Field(
    default=True,
    description="Show illumination periods on CNP time plot"
)

# Photoresponse Plot Parameters
photoresponse_mode: str = Field(
    default="power",
    description="Photoresponse plot mode: 'power', 'wavelength', 'gate_voltage', or 'time'"
)

photoresponse_filter_vg: Optional[float] = Field(
    default=None,
    description="Filter by gate voltage (for wavelength/power plots)"
)

photoresponse_filter_wl: Optional[int] = Field(
    default=None,
    description="Filter by wavelength in nm (for power/gate plots)"
)

photoresponse_normalize: bool = Field(
    default=False,
    description="Normalize photoresponse to dark current"
)
```

**Add data pipeline parameters:**
```python
# Data Pipeline Parameters
pipeline_staging_workers: int = Field(
    default=6,
    ge=1,
    le=16,
    description="Number of parallel workers for staging"
)

pipeline_strict_mode: bool = Field(
    default=False,
    description="Strict schema validation (fail on errors)"
)

pipeline_force_overwrite: bool = Field(
    default=False,
    description="Force overwrite existing staged data"
)

pipeline_include_calibrations: bool = Field(
    default=True,
    description="Include laser calibration power extraction"
)
```

**Add enriched history support:**
```python
use_enriched_histories: bool = Field(
    default=True,
    description="Use enriched histories with derived metrics if available"
)
```

**Estimated Changes:** ~100 lines added to `session.py`

---

#### 1.2 Create `src/tui/history_detection.py` (New module)

**Purpose:** Detect and read enriched vs. regular chip histories

```python
"""
History Detection and Loading.

Automatically detects whether enriched chip histories (with derived metrics)
are available, and falls back to regular histories if not.
"""

from pathlib import Path
from typing import Tuple, Optional
import polars as pl


def detect_history_availability(
    chip_number: int,
    chip_group: str,
    history_dir: Path,
    enriched_dir: Path,
) -> Tuple[bool, bool, Optional[Path], Optional[Path]]:
    """
    Detect availability of regular and enriched chip histories.

    Parameters
    ----------
    chip_number : int
        Chip number
    chip_group : str
        Chip group (e.g., "Alisson")
    history_dir : Path
        Regular history directory (data/02_stage/chip_histories)
    enriched_dir : Path
        Enriched history directory (data/03_derived/chip_histories_enriched)

    Returns
    -------
    tuple
        (has_regular, has_enriched, regular_path, enriched_path)
    """
    chip_name = f"{chip_group}{chip_number}"

    regular_path = history_dir / f"{chip_name}_history.parquet"
    enriched_path = enriched_dir / f"{chip_name}_history_enriched.parquet"

    has_regular = regular_path.exists()
    has_enriched = enriched_path.exists()

    return (
        has_regular,
        has_enriched,
        regular_path if has_regular else None,
        enriched_path if has_enriched else None
    )


def load_chip_history(
    chip_number: int,
    chip_group: str,
    history_dir: Path,
    enriched_dir: Path,
    prefer_enriched: bool = True,
    require_enriched: bool = False,
) -> Tuple[pl.DataFrame, bool]:
    """
    Load chip history, preferring enriched if available.

    Parameters
    ----------
    chip_number : int
        Chip number
    chip_group : str
        Chip group (e.g., "Alisson")
    history_dir : Path
        Regular history directory
    enriched_dir : Path
        Enriched history directory
    prefer_enriched : bool
        Prefer enriched history if available (default: True)
    require_enriched : bool
        Raise error if enriched history not available (default: False)

    Returns
    -------
    tuple
        (history_df, is_enriched)

    Raises
    ------
    FileNotFoundError
        If no history file found, or if require_enriched=True and enriched not available
    """
    has_regular, has_enriched, regular_path, enriched_path = detect_history_availability(
        chip_number, chip_group, history_dir, enriched_dir
    )

    # Handle require_enriched mode
    if require_enriched and not has_enriched:
        if has_regular:
            raise ValueError(
                f"Enriched history required but not available for {chip_group}{chip_number}. "
                f"Run: python3 process_and_analyze.py enrich-history {chip_number}"
            )
        else:
            raise FileNotFoundError(
                f"No history found for {chip_group}{chip_number}. "
                f"Run: python3 process_and_analyze.py full-pipeline"
            )

    # Load enriched if preferred and available
    if prefer_enriched and has_enriched:
        return pl.read_parquet(enriched_path), True

    # Fallback to regular history
    if has_regular:
        return pl.read_parquet(regular_path), False

    # No history available
    raise FileNotFoundError(
        f"No history found for {chip_group}{chip_number}. "
        f"Run: python3 process_and_analyze.py full-pipeline"
    )


def get_history_status_message(
    chip_number: int,
    chip_group: str,
    history_dir: Path,
    enriched_dir: Path,
) -> str:
    """
    Get human-readable status message about history availability.

    Returns
    -------
    str
        Status message (e.g., "✓ Enriched history available (with derived metrics)")
    """
    has_regular, has_enriched, _, _ = detect_history_availability(
        chip_number, chip_group, history_dir, enriched_dir
    )

    if has_enriched:
        return "✓ Enriched history available (with derived metrics)"
    elif has_regular:
        return "⚠ Regular history only (no derived metrics - run enrich-history)"
    else:
        return "✗ No history found (run full-pipeline)"
```

**Estimated Changes:** ~150 lines new file

---

#### 1.3 Update `src/tui/router.py`

**Add new navigation methods:**
```python
def go_to_vvg_config(self) -> None:
    """Navigate to VVg configuration screen."""
    from src.tui.screens.configuration.vvg_config import VVgConfigScreen
    self.app.push_screen(VVgConfigScreen())

def go_to_vt_config(self) -> None:
    """Navigate to Vt configuration screen."""
    from src.tui.screens.configuration.vt_config import VtConfigScreen
    self.app.push_screen(VtConfigScreen())

def go_to_cnp_config(self) -> None:
    """Navigate to CNP time plot configuration screen."""
    from src.tui.screens.configuration.cnp_config import CNPConfigScreen
    self.app.push_screen(CNPConfigScreen())

def go_to_photoresponse_config(self) -> None:
    """Navigate to Photoresponse configuration screen."""
    from src.tui.screens.configuration.photoresponse_config import PhotoresponseConfigScreen
    self.app.push_screen(PhotoresponseConfigScreen())

def go_to_laser_calibration_config(self) -> None:
    """Navigate to Laser Calibration configuration screen."""
    from src.tui.screens.configuration.laser_calibration_config import LaserCalibrationConfigScreen
    self.app.push_screen(LaserCalibrationConfigScreen())

def go_to_data_pipeline_menu(self) -> None:
    """Navigate to Data Pipeline menu."""
    from src.tui.screens.navigation.data_pipeline_menu import DataPipelineMenuScreen
    self.app.push_screen(DataPipelineMenuScreen())

def go_to_pipeline_loading(self, pipeline_type: str) -> None:
    """Navigate to pipeline loading screen."""
    from src.tui.screens.processing.pipeline_loading import PipelineLoadingScreen
    self.app.push_screen(PipelineLoadingScreen(pipeline_type=pipeline_type))
```

**Update `go_to_config_screen()` for new plot types:**
```python
def go_to_config_screen(self) -> None:
    """
    Navigate to appropriate config screen based on session.plot_type.

    Smart router that dispatches to correct configuration screen.
    """
    plot_type = self.app.session.plot_type

    # Map plot types to config screens
    config_router = {
        "ITS": self.go_to_config_mode_selector,  # ITS has presets
        "IVg": self.go_to_config_mode_selector,
        "Transconductance": self.go_to_config_mode_selector,
        "VVg": self.go_to_vvg_config,           # New
        "Vt": self.go_to_vt_config,             # New
        "CNP": self.go_to_cnp_config,           # New
        "Photoresponse": self.go_to_photoresponse_config,  # New
        "LaserCalibration": self.go_to_laser_calibration_config,  # New
    }

    nav_func = config_router.get(plot_type)
    if nav_func is None:
        self.app.notify(f"Unknown plot type: {plot_type}", severity="error")
        return

    nav_func()
```

**Estimated Changes:** ~80 lines added to `router.py`

---

#### 1.4 Integrate PlotConfig (Optional but Recommended)

**Update `src/tui/app.py` to expose PlotConfig:**
```python
from src.plotting.config import PlotConfig

class PlotterApp(App):
    def __init__(self, ...):
        super().__init__()
        # ... existing code ...

        # Initialize PlotConfig for consistent theming
        self.plot_config = PlotConfig(
            output_dir=output_dir,
            dpi=150,  # TUI default (can be configurable)
            format="png",
            theme="tokyo-night",  # Match TUI theme
        )
```

**Use PlotConfig in plot_generation.py:**
```python
# Replace manual output directory setup with PlotConfig
output_path = self.app.plot_config.get_output_path(
    chip_name=chip_name,
    procedure=self.plot_type,
    tag=plot_tag,
    metadata={"has_light": not all_dark},
    create_dirs=True,
)
```

**Estimated Changes:** ~50 lines modified across `app.py` and `plot_generation.py`

---

### **PHASE 2: New Measurement Plot Types** 📊

#### 2.1 Update `src/tui/screens/selection/plot_type_selector.py`

**Add new plot type options:**
```python
def compose_content(self) -> ComposeResult:
    """Compose plot type selector content."""
    with RadioSet(id="plot-type-radio"):
        # Existing
        yield RadioButton("It (Current vs Time)", id="its-radio")
        yield RadioButton("IVg (Transfer Curves)", id="ivg-radio")
        yield RadioButton("Transconductance", id="transconductance-radio")

        # NEW: Measurement-based plots
        yield RadioButton("VVg (Drain-Source Voltage vs Gate)", id="vvg-radio")
        yield RadioButton("Vt (Voltage vs Time)", id="vt-radio")

        # NEW: Derived metric plots
        yield RadioButton("CNP Time Evolution", id="cnp-radio")
        yield RadioButton("Photoresponse Analysis", id="photoresponse-radio")

        # NEW: Specialized plots
        yield RadioButton("Laser Calibration", id="laser-calibration-radio")

    # Add descriptions for each plot type
    # ... (expand description section with new plot types)
```

**Update plot type mapping:**
```python
plot_type_map = {
    "its-radio": "ITS",
    "ivg-radio": "IVg",
    "transconductance-radio": "Transconductance",
    "vvg-radio": "VVg",  # New
    "vt-radio": "Vt",    # New
    "cnp-radio": "CNP",  # New
    "photoresponse-radio": "Photoresponse",  # New
    "laser-calibration-radio": "LaserCalibration",  # New
}
```

**Estimated Changes:** ~40 lines modified

---

#### 2.2 Create `src/tui/screens/configuration/vvg_config.py` (New file)

**VVg configuration screen (similar to IVg):**
```python
"""
VVg Configuration Screen.

Configure parameters for VVg (drain-source voltage vs gate voltage) plots.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, RadioButton, RadioSet
from src.tui.screens.base import WizardScreen


class VVgConfigScreen(WizardScreen):
    """VVg plot configuration screen."""

    SCREEN_TITLE = "Configure VVg Plot"
    STEP_NUMBER = 3

    def compose_content(self) -> ComposeResult:
        """Compose VVg configuration form."""
        # Simple config for now (can expand later)
        yield Static(
            "VVg plots show drain-source voltage vs gate voltage sweeps.\n"
            "Default settings work for most cases.",
            classes="info-text"
        )

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default")
            yield Button("Next →", id="next-button", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            # Save minimal config and proceed to experiment selector
            self.app.session.config_mode = "quick"
            self.app.router.go_to_experiment_selector()
```

**Estimated Changes:** ~80 lines new file

---

#### 2.3 Create `src/tui/screens/configuration/vt_config.py` (New file)

**Vt configuration screen (similar to VVg):**
```python
"""
Vt Configuration Screen.

Configure parameters for Vt (voltage vs time) plots.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from src.tui.screens.base import WizardScreen


class VtConfigScreen(WizardScreen):
    """Vt plot configuration screen."""

    SCREEN_TITLE = "Configure Vt Plot"
    STEP_NUMBER = 3

    def compose_content(self) -> ComposeResult:
        """Compose Vt configuration form."""
        yield Static(
            "Vt plots show voltage time series.\n"
            "Default settings work for most cases.",
            classes="info-text"
        )

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default")
            yield Button("Next →", id="next-button", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.app.session.config_mode = "quick"
            self.app.router.go_to_experiment_selector()
```

**Estimated Changes:** ~80 lines new file

---

#### 2.4 Update `src/tui/screens/processing/plot_generation.py`

**Add VVg plotting logic:**
```python
elif self.plot_type == "VVg":
    # VVg plot
    from src.plotting import vvg
    logger.info("Setting VVg FIG_DIR")
    vvg.FIG_DIR = output_dir
    logger.info("Calling plot_vvg_sequence()")
    vvg.plot_vvg_sequence(meta, stage_dir, plot_tag)
    logger.info("plot_vvg_sequence() completed")
```

**Add Vt plotting logic:**
```python
elif self.plot_type == "Vt":
    # Vt plot
    from src.plotting import vt
    logger.info("Setting Vt FIG_DIR")
    vt.FIG_DIR = output_dir
    logger.info("Calling plot_vt_sequence()")
    vt.plot_vt_sequence(meta, stage_dir, plot_tag)
    logger.info("plot_vt_sequence() completed")
```

**Update output filename determination:**
```python
if self.plot_type == "VVg":
    filename = f"encap{self.chip_number}_VVg_{plot_tag}.png"
elif self.plot_type == "Vt":
    filename = f"encap{self.chip_number}_Vt_{plot_tag}.png"
```

**Estimated Changes:** ~60 lines added to `plot_generation.py`

---

### **PHASE 3: Derived Metrics Plot Types** 📈

#### 3.1 Create `src/tui/screens/configuration/cnp_config.py` (New file)

**CNP time plot configuration:**
```python
"""
CNP Configuration Screen.

Configure parameters for CNP (Charge Neutrality Point) time evolution plots.
Requires enriched chip histories with derived metrics.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, RadioButton, RadioSet, Checkbox
from src.tui.screens.base import WizardScreen
from src.tui.history_detection import get_history_status_message


class CNPConfigScreen(WizardScreen):
    """CNP time plot configuration screen."""

    SCREEN_TITLE = "Configure CNP Time Plot"
    STEP_NUMBER = 3

    def compose_content(self) -> ComposeResult:
        """Compose CNP configuration form."""
        # Show history status
        status_msg = get_history_status_message(
            self.app.session.chip_number,
            self.app.session.chip_group,
            self.app.session.history_dir,
            Path("data/03_derived/chip_histories_enriched"),
        )
        yield Static(f"History Status: {status_msg}", classes="info-text")

        # CNP metric selection
        yield Static("Select CNP metric to plot:", classes="section-header")
        with RadioSet(id="cnp-metric-radio"):
            yield RadioButton("CNP Voltage (Dirac Point)", id="cnp-voltage-radio", value=True)
            yield RadioButton("CNP Current", id="cnp-current-radio")
            yield RadioButton("Mobility", id="mobility-radio")

        # Options
        yield Checkbox("Show illumination periods", id="show-illumination", value=True)

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default")
            yield Button("Next →", id="next-button", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            # Save config
            radio_set = self.query_one("#cnp-metric-radio", RadioSet)
            metric_map = {
                "cnp-voltage-radio": "cnp_voltage",
                "cnp-current-radio": "cnp_current",
                "mobility-radio": "mobility",
            }
            self.app.session.cnp_metric = metric_map[radio_set.pressed_button.id]

            checkbox = self.query_one("#show-illumination", Checkbox)
            self.app.session.cnp_show_illumination = checkbox.value

            self.app.session.config_mode = "custom"

            # CNP plots don't need experiment selection (use all IVg data)
            # Go directly to preview
            self.app.router.go_to_preview()
```

**Estimated Changes:** ~120 lines new file

---

#### 3.2 Create `src/tui/screens/configuration/photoresponse_config.py` (New file)

**Photoresponse configuration screen:**
```python
"""
Photoresponse Configuration Screen.

Configure parameters for photoresponse analysis plots.
Requires enriched chip histories with derived metrics and laser calibration data.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, RadioButton, RadioSet, Input
from src.tui.screens.base import WizardScreen
from src.tui.history_detection import get_history_status_message


class PhotoresponseConfigScreen(WizardScreen):
    """Photoresponse plot configuration screen."""

    SCREEN_TITLE = "Configure Photoresponse Plot"
    STEP_NUMBER = 3

    def compose_content(self) -> ComposeResult:
        """Compose photoresponse configuration form."""
        # Show history status
        status_msg = get_history_status_message(
            self.app.session.chip_number,
            self.app.session.chip_group,
            self.app.session.history_dir,
            Path("data/03_derived/chip_histories_enriched"),
        )
        yield Static(f"History Status: {status_msg}", classes="info-text")

        # Plot mode selection
        yield Static("Select photoresponse plot mode:", classes="section-header")
        with RadioSet(id="photoresponse-mode-radio"):
            yield RadioButton("Photoresponse vs Power", id="power-radio", value=True)
            yield RadioButton("Photoresponse vs Wavelength", id="wavelength-radio")
            yield RadioButton("Photoresponse vs Gate Voltage", id="gate-voltage-radio")
            yield RadioButton("Photoresponse vs Time", id="time-radio")

        # Filter options
        yield Static("Filters (optional):", classes="section-header")
        yield Input(placeholder="Gate voltage (V) - e.g., -0.4", id="filter-vg-input")
        yield Input(placeholder="Wavelength (nm) - e.g., 660", id="filter-wl-input")

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default")
            yield Button("Next →", id="next-button", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            # Save config
            radio_set = self.query_one("#photoresponse-mode-radio", RadioSet)
            mode_map = {
                "power-radio": "power",
                "wavelength-radio": "wavelength",
                "gate-voltage-radio": "gate_voltage",
                "time-radio": "time",
            }
            self.app.session.photoresponse_mode = mode_map[radio_set.pressed_button.id]

            # Parse filters
            vg_input = self.query_one("#filter-vg-input", Input).value
            if vg_input:
                try:
                    self.app.session.photoresponse_filter_vg = float(vg_input)
                except ValueError:
                    self.app.notify("Invalid gate voltage", severity="warning")

            wl_input = self.query_one("#filter-wl-input", Input).value
            if wl_input:
                try:
                    self.app.session.photoresponse_filter_wl = int(wl_input)
                except ValueError:
                    self.app.notify("Invalid wavelength", severity="warning")

            self.app.session.config_mode = "custom"

            # Photoresponse plots don't need experiment selection (use all enriched data)
            # Go directly to preview
            self.app.router.go_to_preview()
```

**Estimated Changes:** ~150 lines new file

---

#### 3.3 Update `src/tui/screens/processing/plot_generation.py` (Add CNP/Photoresponse)

**Add CNP plotting logic:**
```python
elif self.plot_type == "CNP":
    # CNP time evolution plot
    from src.plotting import cnp_time
    logger.info("Setting CNP FIG_DIR")
    cnp_time.FIG_DIR = output_dir
    logger.info("Calling plot_cnp_time()")

    # Load enriched history
    from src.tui.history_detection import load_chip_history
    history, is_enriched = load_chip_history(
        self.chip_number,
        self.chip_group,
        history_dir,
        Path("data/03_derived/chip_histories_enriched"),
        prefer_enriched=True,
        require_enriched=True,  # CNP requires enriched data
    )

    if not is_enriched:
        raise ValueError("CNP plots require enriched history. Run: enrich-history")

    cnp_time.plot_cnp_time(
        history,
        output_dir,
        f"{self.chip_group}{self.chip_number}",
        metric=self.config.get("cnp_metric", "cnp_voltage"),
        show_illumination=self.config.get("cnp_show_illumination", True),
    )
    logger.info("plot_cnp_time() completed")
```

**Add Photoresponse plotting logic:**
```python
elif self.plot_type == "Photoresponse":
    # Photoresponse analysis plot
    from src.plotting import photoresponse
    logger.info("Setting Photoresponse FIG_DIR")
    photoresponse.FIG_DIR = output_dir
    logger.info("Calling plot_photoresponse()")

    # Load enriched history
    from src.tui.history_detection import load_chip_history
    history, is_enriched = load_chip_history(
        self.chip_number,
        self.chip_group,
        history_dir,
        Path("data/03_derived/chip_histories_enriched"),
        prefer_enriched=True,
        require_enriched=True,  # Photoresponse requires enriched data
    )

    if not is_enriched:
        raise ValueError("Photoresponse plots require enriched history. Run: enrich-history")

    mode = self.config.get("photoresponse_mode", "power")
    photoresponse.plot_photoresponse(
        history,
        output_dir,
        f"{self.chip_group}{self.chip_number}",
        mode=mode,
        filter_vg=self.config.get("photoresponse_filter_vg"),
        filter_wl=self.config.get("photoresponse_filter_wl"),
    )
    logger.info("plot_photoresponse() completed")
```

**Update filename determination:**
```python
elif self.plot_type == "CNP":
    metric = self.config.get("cnp_metric", "cnp_voltage")
    filename = f"encap{self.chip_number}_CNP_{metric}_time.png"
elif self.plot_type == "Photoresponse":
    mode = self.config.get("photoresponse_mode", "power")
    filename = f"encap{self.chip_number}_photoresponse_{mode}.png"
```

**Estimated Changes:** ~120 lines added to `plot_generation.py`

---

### **PHASE 4: Data Pipeline Integration** 🔧

#### 4.1 Create `src/tui/screens/navigation/data_pipeline_menu.py` (New file)

**Data pipeline menu screen:**
```python
"""
Data Pipeline Menu Screen.

Provides access to data processing commands:
- Stage All Data (CSV → Parquet)
- Generate Chip Histories
- Extract Derived Metrics
- Enrich Histories (join calibrations + metrics)
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from src.tui.screens.base import WizardScreen


class DataPipelineMenuScreen(WizardScreen):
    """Data pipeline operations menu."""

    SCREEN_TITLE = "🔧 Data Pipeline"
    STEP_NUMBER = None

    def compose_content(self) -> ComposeResult:
        """Compose pipeline menu buttons."""
        yield Static(
            "Process raw data and extract metrics.\n"
            "Run these commands to prepare data for plotting.",
            classes="info-text"
        )

        with Vertical():
            yield Button(
                "1. Stage All Data (CSV → Parquet)",
                id="stage-all",
                variant="primary",
                classes="menu-button"
            )
            yield Button(
                "2. Generate Chip Histories",
                id="build-histories",
                variant="primary",
                classes="menu-button"
            )
            yield Button(
                "3. Extract Derived Metrics (CNP, Photoresponse)",
                id="derive-metrics",
                variant="primary",
                classes="menu-button"
            )
            yield Button(
                "4. Enrich Histories (Join Calibrations + Metrics)",
                id="enrich-histories",
                variant="primary",
                classes="menu-button"
            )
            yield Button(
                "Run Full Pipeline (All Steps)",
                id="full-pipeline",
                variant="success",
                classes="menu-button"
            )

        with Vertical(id="button-container"):
            yield Button("← Back to Main Menu", id="back-button", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "back-button":
            self.app.pop_screen()
        elif button_id == "stage-all":
            self.app.router.go_to_pipeline_loading("stage-all")
        elif button_id == "build-histories":
            self.app.router.go_to_pipeline_loading("build-histories")
        elif button_id == "derive-metrics":
            self.app.router.go_to_pipeline_loading("derive-metrics")
        elif button_id == "enrich-histories":
            self.app.router.go_to_pipeline_loading("enrich-histories")
        elif button_id == "full-pipeline":
            self.app.router.go_to_pipeline_loading("full-pipeline")
```

**Estimated Changes:** ~110 lines new file

---

#### 4.2 Create `src/tui/screens/processing/pipeline_loading.py` (New file)

**Pipeline loading screen with progress:**
```python
"""
Pipeline Loading Screen.

Shows progress while running data pipeline commands:
- stage-all
- build-all-histories
- derive-all-metrics
- enrich-history -a
- full-pipeline
"""

from pathlib import Path
import time
import threading
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, ProgressBar
from src.tui.screens.base import WizardScreen


class PipelineLoadingScreen(WizardScreen):
    """Loading screen for data pipeline operations."""

    SCREEN_TITLE = "Running Data Pipeline..."
    STEP_NUMBER = None

    def __init__(self, pipeline_type: str):
        """
        Initialize pipeline loading screen.

        Parameters
        ----------
        pipeline_type : str
            Pipeline command: 'stage-all', 'build-histories', 'derive-metrics',
            'enrich-histories', or 'full-pipeline'
        """
        super().__init__()
        self.pipeline_type = pipeline_type
        self.processing_thread = None
        self.start_time = None

    def compose_content(self) -> ComposeResult:
        """Create loading screen widgets."""
        yield Static("⣾ Initializing...", id="status")
        with Horizontal(id="progress-container"):
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
        yield Static("Starting pipeline", id="current-task")
        yield Static("", id="stats")

    def on_mount(self) -> None:
        """Start pipeline when screen loads."""
        self.start_time = time.time()
        self.processing_thread = threading.Thread(target=self._run_pipeline, daemon=True)
        self.processing_thread.start()

    def _run_pipeline(self) -> None:
        """Run the selected pipeline command in background thread."""
        try:
            # Import pipeline modules
            import subprocess
            from pathlib import Path

            # Force matplotlib backend
            import matplotlib
            matplotlib.use('Agg')

            # Map pipeline type to CLI command
            command_map = {
                "stage-all": ["python3", "process_and_analyze.py", "stage-all"],
                "build-histories": ["python3", "process_and_analyze.py", "build-all-histories"],
                "derive-metrics": ["python3", "process_and_analyze.py", "derive-all-metrics"],
                "enrich-histories": ["python3", "process_and_analyze.py", "enrich-history", "-a"],
                "full-pipeline": ["python3", "process_and_analyze.py", "full-pipeline"],
            }

            command = command_map.get(self.pipeline_type)
            if not command:
                raise ValueError(f"Unknown pipeline type: {self.pipeline_type}")

            # Update status
            self.app.call_from_thread(
                self._update_progress,
                10,
                f"⣾ Running: {' '.join(command[2:])}"
            )

            # Run command and capture output
            result = subprocess.run(
                command,
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            # Check result
            if result.returncode != 0:
                raise RuntimeError(
                    f"Pipeline command failed:\n{result.stderr or result.stdout}"
                )

            # Success
            elapsed = time.time() - self.start_time
            self.app.call_from_thread(self._update_progress, 100, "✓ Complete!")
            time.sleep(0.3)
            self.app.call_from_thread(self._on_success, elapsed, result.stdout)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.app.call_from_thread(self._on_error, str(e), type(e).__name__, error_details)

    def _update_progress(self, progress: float, status: str) -> None:
        """Update progress bar and status."""
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=progress)

        status_widget = self.query_one("#status", Static)
        status_widget.update(status)

    def _on_success(self, elapsed: float, output: str) -> None:
        """Handle successful pipeline completion."""
        self.app.pop_screen()
        self.app.notify(
            f"Pipeline completed in {elapsed:.1f}s\n{output[:200]}...",
            severity="information",
            timeout=10
        )

    def _on_error(self, error_msg: str, error_type: str, error_details: str) -> None:
        """Handle pipeline error."""
        self.app.pop_screen()
        self.app.notify(
            f"Pipeline failed: {error_type}\n{error_msg}",
            severity="error",
            timeout=10
        )
```

**Estimated Changes:** ~200 lines new file

---

#### 4.3 Update `src/tui/screens/navigation/main_menu.py`

**Add Data Pipeline button:**
```python
def compose_content(self) -> ComposeResult:
    """Compose main menu buttons."""
    with Vertical():
        yield Button("New Plot", id="new-plot", variant="default", classes="menu-button")
        yield Button("View Chip Histories", id="history", variant="default", classes="menu-button")
        yield Button("Data Pipeline 🔧", id="data-pipeline", variant="default", classes="menu-button")  # NEW
        yield Button("Recent Configurations (0)", id="recent", variant="default", classes="menu-button")
        # ... rest of buttons ...

def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle button presses."""
    # ... existing code ...
    elif button_id == "data-pipeline":  # NEW
        self.action_data_pipeline()

def action_data_pipeline(self) -> None:
    """Show data pipeline menu."""
    self.app.router.go_to_data_pipeline_menu()
```

**Estimated Changes:** ~20 lines added to `main_menu.py`

---

### **PHASE 5: Laser Calibration & ITS Relaxation** 🔬

#### 5.1 Create `src/tui/screens/configuration/laser_calibration_config.py`

**Laser calibration configuration screen:**
```python
"""
Laser Calibration Configuration Screen.

Configure parameters for laser calibration curve plots.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button
from src.tui.screens.base import WizardScreen


class LaserCalibrationConfigScreen(WizardScreen):
    """Laser calibration plot configuration screen."""

    SCREEN_TITLE = "Configure Laser Calibration Plot"
    STEP_NUMBER = 3

    def compose_content(self) -> ComposeResult:
        """Compose laser calibration configuration form."""
        yield Static(
            "Laser calibration plots show power output vs control voltage curves.\n"
            "Automatically finds all LaserCalibration experiments for the selected chip.",
            classes="info-text"
        )

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default")
            yield Button("Generate Plot", id="next-button", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.app.session.config_mode = "quick"
            # Laser calibration doesn't need experiment selection
            # Go directly to plot generation
            self.app.router.go_to_plot_generation()
```

**Estimated Changes:** ~80 lines new file

---

#### 5.2 Update `src/tui/screens/processing/plot_generation.py` (Add LaserCalibration)

**Add laser calibration plotting logic:**
```python
elif self.plot_type == "LaserCalibration":
    # Laser calibration curve plot
    from src.plotting import laser_calibration
    logger.info("Setting LaserCalibration FIG_DIR")
    laser_calibration.FIG_DIR = output_dir
    logger.info("Calling plot_laser_calibration()")

    # Filter for LaserCalibration procedures
    calib_meta = meta.filter(pl.col("proc") == "LaserCalibration")

    if calib_meta.height == 0:
        raise ValueError("No LaserCalibration experiments found for this chip")

    laser_calibration.plot_laser_calibration(
        calib_meta,
        stage_dir,
        f"{self.chip_group}{self.chip_number}",
    )
    logger.info("plot_laser_calibration() completed")
```

**Update filename determination:**
```python
elif self.plot_type == "LaserCalibration":
    filename = f"encap{self.chip_number}_laser_calibration.png"
```

**Estimated Changes:** ~40 lines added to `plot_generation.py`

---

### **PHASE 6: Polish & Testing** ✨

#### 6.1 Testing Checklist

**Manual Testing:**
- [ ] Test VVg plot generation with real data
- [ ] Test Vt plot generation with real data
- [ ] Test CNP plot with enriched history
- [ ] Test CNP plot fallback when enriched history missing
- [ ] Test Photoresponse plot with all 4 modes (power, wavelength, gate, time)
- [ ] Test Photoresponse plot with filters
- [ ] Test Laser Calibration plot
- [ ] Test Data Pipeline menu navigation
- [ ] Test stage-all command from TUI
- [ ] Test full-pipeline command from TUI
- [ ] Test derive-metrics command from TUI
- [ ] Test enrich-histories command from TUI
- [ ] Test plot generation with all new plot types
- [ ] Test error handling for missing enriched histories
- [ ] Verify PlotConfig integration (output paths match CLI)
- [ ] Test backward compatibility with existing ITS/IVg/Transconductance plots

**Automated Testing (if time permits):**
```python
# tests/tui/test_session.py
def test_plot_session_validates_new_plot_types():
    """Test that PlotSession accepts all v3.0 plot types."""
    session = PlotSession(...)

    # Valid plot types
    for plot_type in ["VVg", "Vt", "CNP", "Photoresponse", "LaserCalibration"]:
        session.plot_type = plot_type
        assert session.plot_type == plot_type

    # Invalid plot type
    with pytest.raises(ValueError):
        session.plot_type = "InvalidType"

# tests/tui/test_history_detection.py
def test_detect_history_availability():
    """Test enriched history detection logic."""
    # ... test cases ...
```

---

#### 6.2 Documentation Updates

**Update `docs/TUI_GUIDE.md`:**
```markdown
# TUI User Guide v3.0

## New Features in v3.0

### Plot Types

**Measurement-Based Plots:**
- VVg (Drain-Source Voltage vs Gate Voltage)
- Vt (Voltage vs Time)

**Derived Metrics Plots (requires enriched histories):**
- CNP Time Evolution (Dirac point tracking)
- Photoresponse Analysis (vs power, wavelength, gate voltage, time)

**Specialized Plots:**
- Laser Calibration Curves

### Data Pipeline Integration

The TUI now includes a "Data Pipeline" menu for processing raw data:

1. **Stage All Data:** Convert raw CSVs to Parquet format
2. **Generate Chip Histories:** Build per-chip experiment timelines
3. **Extract Derived Metrics:** Extract CNP, photoresponse, laser power data
4. **Enrich Histories:** Join calibrations and metrics to chip histories
5. **Run Full Pipeline:** Execute all steps in sequence

**When to use:**
- After collecting new experimental data
- Before using CNP or Photoresponse plots
- When enriched history warning appears

### Enriched Histories

**What are enriched histories?**
Enriched histories include derived metrics (CNP voltage, photoresponse, etc.) joined as columns in chip history files. This enables time-series analysis of device parameters.

**How to enable:**
1. Go to Data Pipeline menu
2. Run "Extract Derived Metrics"
3. Run "Enrich Histories"

**Plots requiring enriched histories:**
- CNP Time Evolution
- Photoresponse Analysis

**Automatic fallback:**
If enriched history not available, TUI will:
1. Display warning message
2. Use regular history for compatible plots
3. Show error for plots requiring enriched data (CNP, Photoresponse)

## Plot Type Reference

### VVg (Drain-Source Voltage vs Gate)
... (add documentation for each plot type)
```

---

#### 6.3 Help Screen Improvements

**Update `src/tui/screens/navigation/main_menu.py` help action:**
```python
def action_help(self) -> None:
    """Show help with v3.0 updates."""
    help_text = """
    📖 TUI v3.0 Quick Help

    Keyboard Shortcuts:
    - N: New Plot
    - Ctrl+H: View Chip Histories
    - P: Data Pipeline (NEW!)
    - R: Recent Configurations
    - S: Settings
    - Q: Quit

    New Plot Types:
    - VVg: Drain-source voltage sweeps
    - Vt: Voltage time series
    - CNP: Dirac point evolution (requires enriched history)
    - Photoresponse: Photocurrent analysis (requires enriched history)
    - Laser Calibration: Power calibration curves

    Data Pipeline:
    Run "Data Pipeline" menu to process raw data and extract metrics.
    Required before using CNP or Photoresponse plots.

    For full documentation, see: docs/TUI_GUIDE.md
    """
    self.app.notify(help_text.strip(), timeout=15)
```

---

## Testing Strategy

### Unit Testing Priority

**High Priority:**
1. `PlotSession` validation for new plot types
2. `history_detection.py` enriched history logic
3. Router navigation to new screens

**Medium Priority:**
1. Configuration screen input validation
2. Pipeline command mapping
3. Error message formatting

**Low Priority:**
1. UI styling and layout
2. Keyboard shortcut mappings

### Integration Testing

**End-to-End Flows to Test:**
1. New Plot → VVg → Generate (with real chip data)
2. New Plot → CNP → Missing enriched history → Error message
3. Data Pipeline → Full Pipeline → Success notification
4. Data Pipeline → Derive Metrics → Enrich Histories → CNP Plot → Success

### Performance Testing

**Scenarios:**
1. Loading enriched history with 1000+ experiments
2. Pipeline command with 500+ CSV files
3. Photoresponse plot with 200+ data points

---

## Rollout Plan

### Phase 1-2 (Week 1): Foundation + Measurement Plots
**Goal:** VVg and Vt working, no enriched data required
**Risk:** Low
**User Impact:** Immediate value (2 new plot types)

### Phase 3 (Week 2): Derived Metrics Plots
**Goal:** CNP and Photoresponse working with enriched histories
**Risk:** Medium (dependency on enriched data)
**User Impact:** High value for advanced users

### Phase 4 (Week 2-3): Data Pipeline Integration
**Goal:** Full pipeline accessible from TUI
**Risk:** Medium (threading concerns)
**User Impact:** High (removes CLI dependency for lab users)

### Phase 5-6 (Week 3): Polish
**Goal:** Laser calibration, testing, documentation
**Risk:** Low
**User Impact:** Completeness and robustness

---

## Backward Compatibility

### Guaranteed Compatibility

**Configuration Files:**
- Existing `tui_recent_configs.json` files remain valid
- `PlotSession` model uses `model_dump()` for serialization (no breaking changes)

**Existing Plot Types:**
- ITS, IVg, Transconductance workflows unchanged
- All existing screens remain functional

**Router API:**
- Existing navigation methods unchanged (additive only)

### Deprecation Policy

**No Deprecations Planned**
All existing features remain supported. New features are purely additive.

---

## Risk Mitigation

### Risk: Threading Issues with Multiprocessing Pipeline
**Mitigation:**
- Use `subprocess.run()` instead of direct multiprocessing calls
- Set 10-minute timeout for pipeline commands
- Display user-friendly error messages with CLI fallback instructions

### Risk: Missing Enriched Histories
**Mitigation:**
- `history_detection.py` provides clear status messages
- Configuration screens show enriched history availability
- Automatic fallback to regular history when possible
- Clear error messages with actionable commands

### Risk: Breaking Changes to PlotSession
**Mitigation:**
- Use Pydantic's `Field()` with `default` values for all new fields
- Existing configurations deserialize gracefully (missing fields get defaults)
- Test loading old `tui_recent_configs.json` files

---

## Implementation Estimates

| Phase | Effort | Files Changed | New Files | Lines Changed |
|-------|--------|---------------|-----------|---------------|
| Phase 1 | 4-5h | 3 | 1 | ~300 |
| Phase 2 | 3-4h | 2 | 2 | ~250 |
| Phase 3 | 4-5h | 1 | 2 | ~300 |
| Phase 4 | 5-6h | 2 | 2 | ~400 |
| Phase 5 | 3-4h | 1 | 1 | ~150 |
| Phase 6 | 2-3h | 3 | 0 | ~200 |
| **Total** | **21-27h** | **12** | **8** | **~1600** |

---

## Success Criteria

**Phase Completion Criteria:**
- ✅ All new plot types generate plots successfully
- ✅ Enriched history detection works with clear messaging
- ✅ Data pipeline commands complete without errors
- ✅ Backward compatibility maintained (existing plots work)
- ✅ Documentation updated with screenshots
- ✅ Zero regressions in existing features

**User Acceptance:**
- Lab users can run full pipeline from TUI (no CLI needed)
- CNP and Photoresponse plots accessible to non-technical users
- Error messages are actionable and clear
- Performance remains acceptable (<5s for plot generation, <5min for full pipeline)

---

## Next Steps

1. **Review this plan** with stakeholders for feedback
2. **Create GitHub issues** for each phase (for tracking)
3. **Set up development branch** (`feature/tui-v3-upgrade`)
4. **Begin Phase 1** implementation
5. **Daily standups** to track progress and blockers

---

**Document Status:** Ready for Implementation
**Last Updated:** 2025-11-09
**Owner:** Development Team
**Approvers:** Lab Lead, Senior Developer
