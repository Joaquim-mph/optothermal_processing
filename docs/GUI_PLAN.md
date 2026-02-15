# PyQt6 GUI Implementation Plan for Biotite

## 1. Architecture Decisions

**Navigation: QStackedWidget with sidebar, NOT QWizard.**

QWizard is a poor fit here for three reasons: (a) the flow is not strictly linear -- users can jump from main menu to history browser, plot browser, settings, or recent configs without following the wizard path; (b) the wizard step count varies by plot type (some have preset selection, some do not); (c) QWizard's commit/non-commit page model makes it awkward to support the "back" behavior in this project where each screen independently writes to session state. A QStackedWidget with a custom sidebar or breadcrumb strip gives full control over navigation and matches the existing Router pattern.

**State Management: Reuse PlotSession, ConfigManager, SettingsManager directly.**

These three classes from `src/tui/` have no Textual dependency. `PlotSession` is a pure Pydantic model. `ConfigManager` and `SettingsManager` read/write JSON files. `history_detection.py` and `utils.py` use only Polars and `pathlib`. All five modules can be imported directly into `src/gui/` with zero modifications.

**Threading: QThread subclasses for long-running operations.**

Plot generation (which calls matplotlib in Agg mode from a background thread today) and pipeline execution will each use a dedicated `QThread` subclass that emits signals for progress updates. This mirrors the current `threading.Thread` + `call_from_thread` pattern in the Textual TUI but uses Qt's signal/slot mechanism, which is thread-safe by design.

**Matplotlib Integration: FigureCanvasQTAgg for plot preview.**

The `matplotlib.backends.backend_qtagg.FigureCanvasQTAgg` widget will embed matplotlib figures directly inside the Qt window. This allows real-time plot preview before saving, which the terminal TUI cannot do. The matplotlib backend must be set to `QtAgg` at import time (before any `pyplot` calls).

## 2. Directory and File Structure

```
src/gui/
    __init__.py
    app.py                          # QApplication, MainWindow, entry point
    router.py                       # Navigation controller (port of tui/router.py)
    theme.py                        # QSS stylesheet + color palette
    workers.py                      # QThread subclasses for plot gen + pipeline

    pages/                          # One QWidget per "screen" (stacked pages)
        __init__.py
        main_menu.py                # Main menu with button list
        chip_selector.py            # Grid of chip buttons
        plot_type_selector.py       # Plot type selection
        config_mode_selector.py     # Quick/Custom/Preset/Recent
        its_preset_selector.py      # ITS preset list (from its_presets.PRESETS)
        vt_preset_selector.py       # Vt preset list (from vt_presets.PRESETS)
        experiment_selector.py      # QTableView with checkboxes
        preview.py                  # Config summary before generation
        plot_generation.py          # Progress bar + status
        plot_success.py             # Success result with matplotlib preview
        plot_error.py               # Error result with traceback
        process_confirmation.py     # Confirm before pipeline execution
        process_success.py          # Pipeline success
        process_error.py            # Pipeline error
        history_browser.py          # QTableView with filters
        plot_browser.py             # QTreeView + image preview
        recent_configs.py           # QListWidget with config entries
        log_viewer.py               # QPlainTextEdit with log content
        settings.py                 # Theme selector, UI prefs
        data_pipeline_menu.py       # Pipeline operation buttons
        pipeline_loading.py         # Pipeline progress
        batch_plot.py               # YAML batch config + multi-plot generation

    config_pages/                   # One QWidget per config form
        __init__.py
        base_config.py              # Base class with form layout helpers
        its_config.py
        ivg_config.py
        vvg_config.py
        vt_config.py
        transconductance_config.py
        cnp_config.py
        photoresponse_config.py
        laser_calibration_config.py
        its_relaxation_config.py

    widgets/                        # Reusable custom widgets
        __init__.py
        chip_grid.py                # Flow layout of chip buttons
        plot_canvas.py              # Matplotlib FigureCanvasQTAgg wrapper
        progress_panel.py           # Animated progress with status text
        form_helpers.py             # Labeled input row, labeled combo box, etc.
```

## 3. Core Module Details

### 3.1 `app.py` -- MainWindow and Entry Point

The `MainWindow` class owns the application state (same four objects the Textual `PlotterApp` owns):

- `self.session: PlotSession` -- imported directly from `src.tui.session`
- `self.config_manager: ConfigManager` -- imported directly from `src.tui.config_manager`
- `self.settings_manager: SettingsManager` -- imported directly from `src.tui.settings_manager`
- `self.router: Router` -- new Qt-aware router

The window layout is:

```
QMainWindow
  +-- QWidget (central)
       +-- QHBoxLayout
            +-- QFrame (sidebar, ~200px fixed width)
            |    +-- QVBoxLayout
            |         +-- QLabel ("Biotite")
            |         +-- QPushButton ("New Plot")
            |         +-- QPushButton ("History")
            |         +-- QPushButton ("Plot Browser")
            |         +-- QPushButton ("Process Data")
            |         +-- QPushButton ("Recent Configs")
            |         +-- QPushButton ("Settings")
            |         +-- QSpacerItem (stretch)
            |         +-- QPushButton ("Quit")
            +-- QStackedWidget (main content area)
                 +-- page_0: MainMenuPage
                 +-- page_1: ChipSelectorPage
                 +-- page_2: PlotTypeSelectorPage
                 +-- ... (all pages registered by index)
```

The sidebar provides persistent navigation to top-level features (New Plot, History, Plot Browser, etc.). During the wizard flow, the sidebar buttons remain accessible but the QStackedWidget shows the current wizard step. A breadcrumb bar at the top of the content area (e.g., "Chip 67 > ITS > Custom Config") shows wizard progress.

### 3.2 `router.py` -- Navigation Controller

Ports the existing 43-method `Router` class from `src/tui/router.py`. Instead of `self.app.push_screen(SomeScreen(...))`, each method calls `self.main_window.show_page("page_name")` which sets the active index on the `QStackedWidget`. Pages are lazily constructed on first navigation (avoiding upfront creation of all 30+ pages).

Key difference from the TUI router: the Qt router maintains a navigation history stack (list of page names) to support Back navigation without the Textual screen stack. `go_back()` pops the stack and shows the previous page.

```python
class Router:
    def __init__(self, main_window: MainWindow):
        self.main_window = main_window
        self._history: list[str] = []

    def navigate_to(self, page_name: str, **kwargs):
        """Navigate to a page, pushing current onto history stack."""
        self._history.append(self.main_window.current_page_name)
        self.main_window.show_page(page_name, **kwargs)

    def go_back(self):
        if self._history:
            prev = self._history.pop()
            self.main_window.show_page(prev)

    def return_to_main_menu(self):
        self._history.clear()
        self.main_window.session.reset_wizard_state()
        self.main_window.show_page("main_menu")

    # ... same method signatures as tui/router.py ...
    def go_to_chip_selector(self, mode="plot"):
        self.navigate_to("chip_selector", mode=mode)

    def go_to_config_screen(self):
        """Smart routing based on session.plot_type (same logic as TUI router)."""
        ...
```

### 3.3 `workers.py` -- QThread Workers

Two worker classes:

```python
class PlotWorker(QThread):
    """Runs plot generation in background thread."""
    progress = Signal(int, str)           # (percent, status_message)
    finished = Signal(Path, float, float) # (output_path, file_size_mb, elapsed_s)
    error = Signal(str, str, str)         # (error_type, error_msg, traceback)

    def __init__(self, session: PlotSession, config: dict):
        ...

    def run(self):
        """Port of PlotGenerationScreen._generate_plot() logic."""
        import matplotlib
        matplotlib.use('Agg')
        # ... same logic as plot_generation.py ...
```

```python
class PipelineWorker(QThread):
    """Runs data pipeline commands in background thread."""
    progress = Signal(int, str)
    finished = Signal(dict)  # result stats
    error = Signal(str, str, str)

    def __init__(self, pipeline_type: str):
        ...
```

The plot generation logic (the long `_generate_plot` method in `src/tui/screens/processing/plot_generation.py`) should be extracted into a shared function in a new utility module or kept as the worker's `run()` method body. The existing code is ~500 lines of plot-type dispatching logic; it can be refactored into a standalone `execute_plot_generation(session, config) -> Path` function that both the TUI and GUI call, but that refactoring is optional for the initial implementation and can be done later.

### 3.4 `theme.py` -- Qt Stylesheet

A dark theme inspired by Tokyo Night (matching the TUI default). This will be a QSS (Qt Style Sheet) string applied to the QApplication:

```python
TOKYO_NIGHT_QSS = """
QMainWindow { background-color: #1a1b26; }
QWidget { color: #a9b1d6; font-family: "JetBrains Mono", monospace; }
QPushButton {
    background-color: #24283b;
    border: 1px solid #414868;
    border-radius: 4px;
    padding: 8px 16px;
    color: #c0caf5;
}
QPushButton:hover { background-color: #414868; }
QPushButton:pressed { background-color: #7aa2f7; color: #1a1b26; }
QTableView { gridline-color: #414868; selection-background-color: #7aa2f7; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #24283b;
    border: 1px solid #414868;
    border-radius: 3px;
    padding: 4px;
}
...
"""
```

Multiple themes can be stored in a dict and selected via `SettingsManager`. The SettingsManager's theme names will need a mapping from Textual theme names to Qt QSS variants.

## 4. Page-by-Page Mapping

| TUI Screen | Qt Page | Key Qt Widgets |
|---|---|---|
| `MainMenuScreen` | `pages/main_menu.py` | QPushButton list in QVBoxLayout (sidebar handles this; page shows welcome + stats) |
| `ChipSelectorScreen` | `pages/chip_selector.py` | QFlowLayout with QPushButtons (chip grid), calls `discover_chips()` from `src.tui.utils` |
| `PlotTypeSelectorScreen` | `pages/plot_type_selector.py` | QListWidget or QPushButton list with descriptions |
| `ConfigModeSelectorScreen` | `pages/config_mode_selector.py` | QPushButton group (Quick/Custom/Preset/Recent) |
| `ITSConfigScreen` | `config_pages/its_config.py` | QFormLayout with QComboBox (legend_by), QDoubleSpinBox (baseline, padding), QCheckBox (duration mismatch) |
| `IVgConfigScreen` | `config_pages/ivg_config.py` | QFormLayout with QCheckBox (conductance, absolute) |
| `ExperimentSelectorScreen` | `pages/experiment_selector.py` | QTableView + QStandardItemModel with checkboxes, filter controls |
| `PreviewScreen` | `pages/preview.py` | QFormLayout showing read-only config summary + "Generate" button |
| `PlotGenerationScreen` | `pages/plot_generation.py` | QProgressBar + QLabel (status), driven by PlotWorker signals |
| `PlotSuccessScreen` | `pages/plot_success.py` | FigureCanvasQTAgg showing the generated plot image, file info labels |
| `PlotErrorScreen` | `pages/plot_error.py` | QLabel (error), QTextEdit (traceback), navigation buttons |
| `HistoryBrowserScreen` | `pages/history_browser.py` | QTableView + QSortFilterProxyModel, QComboBox filters (proc, light) |
| `PlotBrowserScreen` | `pages/plot_browser.py` | QTreeView (file system model) + QLabel/QPixmap (image preview) |
| `DataPipelineMenuScreen` | `pages/data_pipeline_menu.py` | QPushButton list for pipeline operations |
| `PipelineLoadingScreen` | `pages/pipeline_loading.py` | QProgressBar + QLabel, driven by PipelineWorker |
| `RecentConfigsScreen` | `pages/recent_configs.py` | QListWidget, loads from ConfigManager |
| `LogViewerScreen` | `pages/log_viewer.py` | QPlainTextEdit (read-only) |
| `ThemeSettingsScreen` | `pages/settings.py` | QComboBox (theme), QCheckBox (animations) |
| `ConfigModeSelectorScreen` | `pages/config_mode_selector.py` | QPushButton group (Quick/Custom/Preset/Recent) with descriptions |
| `ITSPresetSelectorScreen` | `pages/its_preset_selector.py` | QListWidget with preset names + descriptions from `its_presets.PRESETS` |
| `VtPresetSelectorScreen` | `pages/vt_preset_selector.py` | QListWidget with preset names + descriptions from `vt_presets.PRESETS` |
| `ProcessConfirmationScreen` | `pages/process_confirmation.py` | QLabel (description) + QPushButton (Confirm/Cancel) |
| *(no TUI equivalent)* | `pages/batch_plot.py` | QFileDialog for YAML selection, QTableView (plot list), QProgressBar (aggregate) |

### 4.1 Config Pages -- Shared Pattern

All config pages follow the same pattern using a `BaseConfigPage` that provides:

```python
class BaseConfigPage(QWidget):
    """Base class for all config form pages."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window
        self.layout = QVBoxLayout(self)

        # Header
        self.title_label = QLabel()
        self.chip_info_label = QLabel()
        self.step_label = QLabel()

        # Scrollable form area
        self.scroll = QScrollArea()
        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)

        # Navigation buttons
        self.btn_back = QPushButton("Back")
        self.btn_next = QPushButton("Next: Select Experiments")

    def add_combo_row(self, label: str, options: list, default: str) -> QComboBox: ...
    def add_spin_row(self, label: str, min_v, max_v, default, decimals=0) -> QDoubleSpinBox: ...
    def add_check_row(self, label: str, default: bool) -> QCheckBox: ...

    def populate_from_session(self):
        """Read session state into form widgets. Override per config page."""
        raise NotImplementedError

    def save_to_session(self):
        """Write form values back to session. Override per config page."""
        raise NotImplementedError
```

This eliminates the CSS duplication problem noted in the TUI's `FormScreen` base class. Each config page's `populate_from_session()` and `save_to_session()` methods read/write `self.main_window.session` attributes.

## 5. Reuse vs New Implementation

**Reuse directly (import from `src.tui`):**
- `src/tui/session.py` -- `PlotSession` (zero changes needed)
- `src/tui/config_manager.py` -- `ConfigManager` (zero changes needed)
- `src/tui/settings_manager.py` -- `SettingsManager` (minor: theme name mapping needed, but the class itself is unchanged)
- `src/tui/history_detection.py` -- all functions (zero changes)
- `src/tui/utils.py` -- `discover_chips()`, `ChipInfo`, `format_chip_display()` (zero changes)
- `src/tui/logging_config.py` -- logging setup (zero changes)

**Reuse indirectly (same logic, new UI code):**
- `src/tui/router.py` -- same routing logic, but using QStackedWidget instead of Textual screen stack
- `src/tui/screens/processing/plot_generation.py` -- the `_generate_plot()` method's logic moves into `PlotWorker.run()` with signal-based progress instead of `call_from_thread`

**New implementation (Qt-specific):**
- All page/widget classes (UI layer)
- QSS theming
- QThread workers
- Matplotlib canvas integration
- Entry point

## 6. Entry Point Registration

Add to `pyproject.toml`:

```toml
[project.scripts]
biotite = "src.cli.main:main"
biotite-tui = "src.tui.app:main"
biotite-gui = "src.gui.app:main"
```

Add PyQt6 as an optional dependency:

```toml
[project.optional-dependencies]
gui = ["PyQt6>=6.5.0"]
jupyter = ["ipython>=8.0.0", "jupyter>=1.0.0"]
dev = ["pytest>=9.0.0"]
```

This keeps PyQt6 optional -- users who only need CLI/TUI do not need to install it.

## 7. Phased Implementation Order

**Phase 1 -- Skeleton (gets a window on screen)**
1. `src/gui/__init__.py`
2. `src/gui/app.py` -- MainWindow with QStackedWidget, sidebar, PlotSession/ConfigManager init
3. `src/gui/router.py` -- Navigation with history stack
4. `src/gui/theme.py` -- Tokyo Night QSS
5. `src/gui/pages/__init__.py` + `src/gui/pages/main_menu.py` -- Welcome page
6. Update `pyproject.toml` with entry point and optional dep

**Phase 2 -- Wizard Flow (core functionality)**
1. `src/gui/pages/chip_selector.py` -- Chip grid using `discover_chips()`
2. `src/gui/pages/plot_type_selector.py` -- Plot type buttons
3. `src/gui/pages/config_mode_selector.py` -- Quick/Custom/Preset
4. `src/gui/config_pages/base_config.py` -- Form layout helpers
5. `src/gui/config_pages/its_config.py` -- First config form (ITS, most complex)
6. `src/gui/pages/experiment_selector.py` -- QTableView with checkboxes
7. `src/gui/pages/preview.py` -- Config summary

**Phase 3 -- Plot Generation**
1. `src/gui/workers.py` -- PlotWorker QThread
2. `src/gui/pages/plot_generation.py` -- Progress page with PlotWorker
3. `src/gui/pages/plot_success.py` -- Success with matplotlib canvas preview
4. `src/gui/pages/plot_error.py` -- Error display
5. `src/gui/widgets/plot_canvas.py` -- FigureCanvasQTAgg wrapper

**Phase 4 -- Remaining Config Pages**
1. `src/gui/config_pages/ivg_config.py`
2. `src/gui/config_pages/vvg_config.py`
3. `src/gui/config_pages/vt_config.py`
4. `src/gui/config_pages/transconductance_config.py`
5. `src/gui/config_pages/cnp_config.py`
6. `src/gui/config_pages/photoresponse_config.py`
7. `src/gui/config_pages/laser_calibration_config.py`
8. `src/gui/config_pages/its_relaxation_config.py`

**Phase 5 -- Analysis and Utility Pages**
1. `src/gui/pages/history_browser.py` -- QTableView with QSortFilterProxyModel
2. `src/gui/pages/plot_browser.py` -- QTreeView + image preview
3. `src/gui/pages/recent_configs.py` -- Config list
4. `src/gui/pages/data_pipeline_menu.py` + `pipeline_loading.py`
5. `src/gui/pages/log_viewer.py`
6. `src/gui/pages/settings.py`
7. `src/gui/pages/process_success.py` + `process_error.py`

**Phase 6 -- Missing Flows, Polish & Testing**
1. `src/gui/pages/config_mode_selector.py` -- Quick/Custom/Preset/Recent mode selection (TUI parity; currently skipped in wizard flow)
2. `src/gui/pages/its_preset_selector.py` -- Preset list from `src.plotting.its_presets.PRESETS`, navigates to experiment selector with pre-filled config
3. `src/gui/pages/vt_preset_selector.py` -- Preset list from `src.plotting.vt_presets.PRESETS`, same pattern
4. `src/gui/pages/process_confirmation.py` -- Confirmation dialog before pipeline execution (shown from data_pipeline_menu)
5. `src/gui/pages/batch_plot.py` -- YAML batch config selector + multi-plot generation with aggregate progress bar (wraps `biotite batch-plot` logic)
6. `src/gui/widgets/chip_grid.py` -- QFlowLayout for chip buttons (replaces current VBoxLayout in chip_selector with responsive grid)
7. `src/gui/widgets/form_helpers.py` -- Reusable labeled input row, labeled combo box, section header; deduplicate repeated form patterns across config pages
8. Keyboard shortcuts -- Global QShortcut bindings: Ctrl+N (new plot), Ctrl+B (back), Escape (cancel/back), Ctrl+Q (quit), F5 (refresh current page)
9. Session restore -- Persist `PlotSession` state to JSON on close, offer to resume on next launch (optional dialog)
10. `tests/test_gui_smoke.py` -- Headless smoke tests using `QT_QPA_PLATFORM=offscreen`: app startup, page navigation, widget creation, config form round-trip (populate -> save -> verify session)
11. Wire config_mode_selector into router between plot_type_selector and config pages, routing Quick mode directly to experiment_selector, Custom to config page, Preset to preset_selector, Recent to recent_configs filtered by plot type
12. Update `_register_pages()` in `app.py` and `update_breadcrumb()`/`update_sidebar_selection()` for all new pages

## 8. Key Technical Considerations

**Thread Safety for Matplotlib.** The PlotWorker must set `matplotlib.use('Agg')` before importing pyplot, exactly as the current TUI does. The generated PNG file is then loaded into the success page's `QLabel` via `QPixmap`. For live preview (if desired later), a separate `FigureCanvasQTAgg` in the main thread can re-render the figure, but this is not required for parity with the TUI.

**Thread Safety for Polars.** Polars `read_parquet()` is inherently thread-safe for reading. The chip discovery and history loading can happen in the main thread (they are fast for the data sizes in this project -- dozens of chips, hundreds of experiments). If latency becomes an issue, these can be moved to a QThread.

**SettingsManager Theme Mapping.** The SettingsManager stores Textual theme names ("tokyo-night", "nord", etc.). For the GUI, add a mapping dict in `theme.py` that translates these to QSS stylesheet variants. The SettingsManager class itself needs no changes.

**Shared Plot Generation Logic.** The `_generate_plot()` method in `src/tui/screens/processing/plot_generation.py` is ~500 lines of plot-type dispatching. Rather than duplicating it, consider extracting it into `src/core/plot_executor.py` as a standalone function that both TUI and GUI call. This is a recommended refactoring but not strictly required -- the GUI's `PlotWorker.run()` can initially copy the logic and the two can be unified later.

## 9. Implementation Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 -- Skeleton | **Done** | MainWindow, sidebar, router, theme, main_menu, pyproject.toml |
| Phase 2 -- Wizard Flow | **Done** | chip_selector, plot_type_selector, ITS config, experiment_selector, preview |
| Phase 3 -- Plot Generation | **Done** | plot_executor.py extracted, PlotWorker, progress/success/error pages |
| Phase 4 -- Config Pages | **Done** | All 8 remaining config pages + wiring + plot_executor dispatch for all types |
| Phase 5 -- Analysis Pages | **Done** | history_browser, plot_browser, recent_configs, pipeline, logs, settings, process_success/error |
| Phase 6 -- Polish & Testing | **Done** | config_mode_selector, preset selectors, process_confirmation, keyboard shortcuts, PipelineWorker |
