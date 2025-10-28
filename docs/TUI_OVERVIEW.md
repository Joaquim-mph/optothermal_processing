# TUI Module Overview

This guide explains how the Textual-based plotting assistant in `src/tui/` is organized. Use it to understand the wizard flow, responsibilities of each file, and where to make changes when extending the interface.

## High-Level Flow
- Entry point: `tui_app.py` instantiates `src/tui/app.py:PlotterApp`, which sets up paths (`stage_dir`, `history_dir`, `output_dir`) and pushes the main menu screen on mount.
- Wizard steps handled by screens:
  1. **Main menu** (`screens/main_menu.py`) – pick new plot, process data, review recents.
  2. **Plot type** (`screens/plot_type_selector.py`) – choose ITS, IVg, or Transconductance.
  3. **Chip selector** (`screens/chip_selector.py`) – list chip histories discovered via `src/tui/utils.py`.
  4. **Mode & configuration** – quick mode uses `screens/experiment_selector.py`; custom mode branches into procedure-specific forms (`screens/its_config.py`, `screens/ivg_config.py`, `screens/transconductance_config.py`) and optional preset selector (`screens/its_preset_selector.py`).
  5. **Preview** (`screens/preview_screen.py`) – summarize selections before plotting.
  6. **Plot generation** (`screens/plot_generation.py`) – run plotting in a worker thread and transition to success/error screens.
- Processing the staging pipeline uses the modal trio `process_confirmation.py`, `process_loading.py`, and result screens (`process_success.py`, `process_error.py`).

## Core Modules
- `src/tui/app.py` – defines `PlotterApp`, manages shared configuration state, keyboard bindings, and theme. Exposes helpers `update_config`, `get_config`, and `reset_config` used across screens.
- `src/tui/config_manager.py` – JSON-backed persistence layer for saving, listing, and loading plot configurations (`~/.lab_plotter_configs.json`). Provides automatic description generation and history trimming.
- `src/tui/utils.py` – discovery helpers (`discover_chips`, `format_chip_display`) used by the chip selector for presenting chip metadata pulled from history parquet files.
- `src/tui/widgets/config_form.py` – reusable container with shared styling for custom configuration screens (RadioSets, Inputs, helper text).

## Screen Catalogue
Screens inherit from `textual.screen.Screen` and rely on `PlotterApp` for navigation and state.

- **Navigation & Selection**
  - `screens/main_menu.py` – hub screen with bindings for quick navigation and config counts.
  - `screens/plot_type_selector.py` – stores the chosen plot type in `app.plot_config` and routes to the chip selector.
  - `screens/chip_selector.py` – asynchronously populates a grid of chips, handles pagination, and forwards selection to the config-mode selector.
  - `screens/config_mode_selector.py` – choose quick vs. custom configuration.
  - `screens/experiment_selector.py` – wraps `src/interactive_selector.py` for quick mode and feeds selected `seq_numbers` back into the app.
  - `screens/its_preset_selector.py` – optional step for ITS presets prior to manual adjustments.
- **Configuration Forms**
  - `screens/its_config.py` – collect ITS-specific filters (legend mode, baseline, wavelength filters, export toggles).
  - `screens/ivg_config.py` – configure IVg sweep ranges, fixed VDS, Savitzky-Golay smoothing toggle, and legend options.
  - `screens/transconductance_config.py` – select experiment indices (interactive, auto, manual) and derivative method settings.
- **Preview & Execution**
  - `screens/preview_screen.py` – displays a summary card of the chosen chip, seq numbers, filters, and target output; stores accepted configs via `ConfigManager`.
  - `screens/plot_generation.py` – drives plotting in a background thread, updates progress UI, and hands control to `PlotSuccessScreen` or `PlotErrorScreen`.
  - `screens/plot_generation.PlotSuccessScreen` and `.PlotErrorScreen` – terminal states showing output paths or error details, with shortcuts to retry or return.
- **Processing Pipeline Screens**
  - `screens/process_confirmation.py` – confirm running the CLI staging pipeline from within the TUI.
  - `screens/process_loading.py` – spinner/progress view while CLI commands execute.
  - `screens/process_success.py` / `screens/process_error.py` – report results of the staging run, including manifest statistics or traceback excerpts.
- **Recent Configurations**
  - `screens/recent_configs.py` – list view backed by `ConfigManager`, allowing load/delete actions and preview of stored parameter sets.

## Supporting Pieces
- `src/tui/__init__.py` re-exports the main app and commonly-used screens for convenience.
- `src/tui/widgets/__init__.py` exposes custom widget classes (`ConfigForm`) to other modules.

## Tips for Extending the TUI
- Use `PlotterApp.update_config` to persist cross-screen state; avoid maintaining local copies.
- Register new screens in `src/tui/screens/__init__.py` if they need to be imported elsewhere.
- Follow existing CSS snippets for consistent styling; reusable classes (`menu-button`, `section-title`, etc.) help keep themes aligned.
- When adding a new plot type:
  1. Extend `plot_type_selector.py` to store the new type.
  2. Provide a dedicated configuration screen or adapt existing ones.
  3. Wire preview and generation steps to supply the required metadata to `plot_generation.py`.
- For persistence, add serialization logic to `ConfigManager._generate_description` if new keys should surface in saved summaries.
