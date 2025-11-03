# Phase 2 Implementation Complete ✅

**Date**: 2025-11-02
**Status**: COMPLETE
**Time Taken**: ~45 minutes
**Dependencies**: Phase 1 (COMPLETE ✅)

---

## Summary

Phase 2 CLI integration is complete! The CLI now supports both global and command-specific plotting configuration flags. Commands can create `PlotConfig` instances with user overrides, ready for Phase 3 integration with plotting modules.

---

## Deliverables

### ✅ 1. Updated `src/cli/main.py`

**Added Functions**:

```python
def get_plot_config() -> PlotConfig:
    """Get or create global PlotConfig instance from CLIConfig."""
    # Creates PlotConfig from current CLIConfig
    # Inherits: output_dir, plot_dpi, plot_theme, default_plot_format

def set_plot_config(config: PlotConfig) -> None:
    """Set global PlotConfig instance for command-specific overrides."""
```

**Added Global Flags** (in `@app.callback()`):

- `--plot-theme TEXT`: Override plot theme globally
  - Options: `prism_rain`, `paper`, `presentation`, `minimal`
  - Example: `python3 process_and_analyze.py --plot-theme paper plot-its 67 --auto`

- `--plot-dpi INTEGER`: Override plot DPI globally
  - Range: 72-1200
  - Example: `python3 process_and_analyze.py --plot-dpi 600 plot-its 67 --auto`

- `--plot-format TEXT`: Override plot format globally
  - Options: `png`, `pdf`, `svg`, `jpg`
  - Example: `python3 process_and_analyze.py --plot-format pdf plot-its 67 --auto`

**Reset Logic**:
```python
# Reset plot config to pick up new CLI config changes
global _plot_config
_plot_config = None
```
This ensures `get_plot_config()` recreates from updated `CLIConfig` after global flag processing.

---

### ✅ 2. Updated `src/cli/commands/plot_its.py`

**Added Command-Specific Flags**:

```python
theme: Optional[str] = typer.Option(
    None,
    "--theme",
    help="Plot theme override (prism_rain, paper, presentation, minimal). Overrides global --plot-theme."
)

format: Optional[str] = typer.Option(
    None,
    "--format",
    help="Output format override (png, pdf, svg, jpg). Overrides global --plot-format."
)

dpi: Optional[int] = typer.Option(
    None,
    "--dpi",
    help="DPI override (72-1200). Overrides global --plot-dpi."
)
```

**Added PlotConfig Creation Logic**:

```python
from src.cli.main import get_plot_config

# Get base plot config from global CLI config
plot_config = get_plot_config()

# Apply command-specific overrides
plot_overrides = {}
if theme is not None:
    plot_overrides["theme"] = theme
if format is not None:
    plot_overrides["format"] = format
if dpi is not None:
    plot_overrides["dpi"] = dpi

if plot_overrides:
    plot_config = plot_config.copy(**plot_overrides)
    if ctx.verbose:
        overrides_str = ", ".join([f"{k}={v}" for k, v in plot_overrides.items()])
        ctx.print(f"[dim]Plot config overrides: {overrides_str}[/dim]")
```

**Note**: `plot-its` serves as the **reference implementation** for other plotting commands. Phase 3 will apply this pattern to all plotting commands and wire PlotConfig to plotting functions.

---

## Validation Results

All tests passed successfully:

### ✅ get_plot_config() Integration

```python
>>> from src.cli.main import get_config, get_plot_config
>>> cli_config = get_config()
>>> plot_config = get_plot_config()
>>> print(plot_config.theme, plot_config.dpi, plot_config.format)
prism_rain 300 png

>>> # Test copy with overrides
>>> paper_config = plot_config.copy(theme="paper", dpi=600)
>>> print(paper_config.theme, paper_config.dpi)
paper 600
```

### ✅ Global Flags Appear in Help

```bash
$ python3 process_and_analyze.py --help

Options:
  --plot-theme           TEXT     Override plot theme (prism_rain, paper,
                                  presentation, minimal)
  --plot-dpi             INTEGER  Override plot DPI (72-1200)
  --plot-format          TEXT     Override plot format (png, pdf, svg, jpg)
```

### ✅ Command-Specific Flags Appear in Help

```bash
$ python3 process_and_analyze.py plot-its --help

Options:
  --theme                TEXT     Plot theme override (prism_rain, paper,
                                  presentation, minimal). Overrides global
                                  --plot-theme.
  --format               TEXT     Output format override (png, pdf, svg, jpg).
                                  Overrides global --plot-format.
  --dpi                  INTEGER  DPI override (72-1200). Overrides global
                                  --plot-dpi.
```

---

## Usage Examples

### Example 1: Global Theme Override

Apply theme to all plotting commands in a session:

```bash
python3 process_and_analyze.py --plot-theme paper --plot-dpi 600 plot-its 67 --auto
```

This sets:
- Theme: `paper` (publication quality)
- DPI: `600` (high resolution)
- Format: `png` (default)

### Example 2: Command-Specific Override

Override theme just for one plot:

```bash
python3 process_and_analyze.py plot-its 67 --auto --theme presentation --dpi 150
```

This uses:
- Theme: `presentation` (slides/posters)
- DPI: `150` (lower for file size)
- Format: `png` (default)

### Example 3: Global + Command Override

Global flag sets baseline, command flag overrides for specific plot:

```bash
# Set global PDF output for all commands
python3 process_and_analyze.py --plot-format pdf plot-its 67 --auto --theme paper --dpi 600
```

This produces:
- Theme: `paper` (command override)
- DPI: `600` (command override)
- Format: `pdf` (global override)

### Example 4: Verbose Mode

See config overrides in action:

```bash
python3 process_and_analyze.py --verbose plot-its 67 --auto --theme paper --dpi 600

# Output includes:
# [dim]Plot config overrides: theme=paper, dpi=600[/dim]
```

---

## Configuration Priority

The system respects the following priority order (highest to lowest):

1. **Command-specific flags** (e.g., `plot-its --theme paper`)
2. **Global CLI flags** (e.g., `--plot-theme paper`)
3. **Project config file** (`./.optothermal_cli_config.json`)
4. **User config file** (`~/.optothermal_cli_config.json`)
5. **Environment variables** (`CLI_PLOT_THEME=paper`)
6. **Hardcoded defaults** (`PlotConfig()` defaults)

**Example**:

```bash
# User config: theme=minimal
# Global flag: --plot-theme=paper
# Command flag: --theme=presentation

# Result: theme=presentation (command flag wins)
```

---

## Integration Pattern for Other Commands

For Phase 3, other plotting commands should follow this pattern:

### Step 1: Add Command Flags

```python
@cli_command(name="plot-<type>", group="plotting")
def plot_command(
    # ... existing parameters ...
    theme: Optional[str] = typer.Option(None, "--theme"),
    format: Optional[str] = typer.Option(None, "--format"),
    dpi: Optional[int] = typer.Option(None, "--dpi"),
):
```

### Step 2: Create PlotConfig with Overrides

```python
from src.cli.main import get_plot_config

plot_config = get_plot_config()

plot_overrides = {}
if theme is not None:
    plot_overrides["theme"] = theme
if format is not None:
    plot_overrides["format"] = format
if dpi is not None:
    plot_overrides["dpi"] = dpi

if plot_overrides:
    plot_config = plot_config.copy(**plot_overrides)
```

### Step 3: Pass to Plotting Function (Phase 3)

```python
# Phase 3: After plotting modules refactored
from src.plotting.ivg import plot_ivg_overlay

plot_ivg_overlay(
    history,
    base_dir,
    tag,
    config=plot_config,  # Pass config
    # ... other parameters ...
)
```

---

## Remaining Work (Phase 3)

**Not yet implemented** (deferred to Phase 3):

1. **Plotting module refactoring** (`src/plotting/*.py`)
   - Accept `config: PlotConfig` parameter
   - Use `config.theme`, `config.dpi`, `config.format`
   - Use `config.get_output_path()` for file paths
   - Use `config.figsize_*` for figure sizes

2. **Apply pattern to all plotting commands**
   - `plot-ivg.py`
   - `plot-vvg.py`
   - `plot-vt.py`
   - `plot-transconductance.py`
   - `plot-cnp.py`
   - `plot-photoresponse.py`
   - `plot-laser-calibration.py`

3. **Wire PlotConfig to plotting functions**
   - Replace `FIG_DIR = output_dir` with `config.output_dir`
   - Replace `set_plot_style("prism_rain")` with `set_plot_style(config.theme)`
   - Replace `figsize=(24, 17)` with `figsize=config.figsize_timeseries`

---

## Files Modified

### Modified:
1. `src/cli/main.py` (+50 lines)
   - Added `get_plot_config()` and `set_plot_config()` functions
   - Added global plotting flags (`--plot-theme`, `--plot-dpi`, `--plot-format`)
   - Added plot config reset logic

2. `src/cli/commands/plot_its.py` (+20 lines)
   - Added command-specific plotting flags
   - Added PlotConfig creation with overrides
   - Documented as reference implementation

---

## Backward Compatibility

✅ **Fully backward compatible**:
- All flags are optional (default to None)
- No behavior changes without explicit flags
- Existing commands work exactly as before
- Config system is opt-in

---

## Known Issues

None! All validation tests passed.

---

## Next Steps (Phase 3)

**Phase 3: Module Migration** (3-4 hours estimated)

1. Refactor `its.py` (reference implementation)
   - Accept `config: PlotConfig = None` parameter
   - Use config for theme, output paths, figure sizes
   - Replace hardcoded constants

2. Apply pattern to remaining 8 plotting modules
   - `ivg.py`, `vvg.py`, `vt.py`, `transconductance.py`
   - `cnp_time.py`, `photoresponse.py`
   - `laser_calibration.py` (already partially integrated)
   - `overlays.py`

3. Update all CLI commands to pass PlotConfig
   - Follow `plot-its.py` reference pattern
   - Add flags to all plotting commands

4. Test end-to-end with all themes
   - Verify plots generate correctly
   - Compare visual quality across themes
   - Regression testing

**Ready to proceed to Phase 3!** 🎯

---

## Documentation

- **Planning Document**: `docs/PLOTTING_CONFIG_REFACTOR_PLAN.md`
- **Phase 1 Summary**: `docs/PLOTTING_CONFIG_PHASE1_COMPLETE.md`
- **This Document**: `docs/PLOTTING_CONFIG_PHASE2_COMPLETE.md`

---

**Phase 2 Complete! CLI infrastructure ready for plotting module integration.** 🚀
