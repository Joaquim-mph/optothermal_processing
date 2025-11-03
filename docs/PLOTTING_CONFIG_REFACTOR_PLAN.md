# Plotting Module Configuration Refactoring Plan

**Status**: Planning Phase
**Created**: 2025-11-02
**Estimated Time**: 8-10 hours total
**Priority**: Medium

---

## Executive Summary

This document outlines a comprehensive refactoring plan to centralize plotting configuration across the `src/plotting/` module. The current implementation has scattered constants, hardcoded paths, and inconsistent styling. This refactor will introduce a unified `PlotConfig` system that integrates with the existing `CLIConfig` infrastructure.

**Key Goals**:
- Centralize all plotting parameters (output paths, figure sizes, themes, colors)
- Enable CLI control over plot appearance without code changes
- Support multiple themes (paper, presentation, minimal)
- Eliminate code duplication and inconsistencies
- Maintain backward compatibility with current behavior

---

## Current State Analysis

### ✅ Existing Infrastructure (Working Well)

1. **CLI Configuration System** (`src/cli/config.py`)
   - Pydantic-based `CLIConfig` with validation
   - Fields: `output_dir`, `plot_dpi`, `plot_theme`, `default_plot_format`
   - Environment variable support (`CLI_*` prefix)
   - Config file support (`.optothermal_cli_config.json`)
   - Profile system (development, production, testing, high_quality)

2. **Plot Utilities** (`src/plotting/plot_utils.py`)
   - `plot_context()` context manager (theme + output handling)
   - Metadata extractors: `get_wavelength_nm()`, `get_gate_voltage()`, `get_led_voltage()`, `get_irradiated_power()`
   - Column normalization: `ensure_standard_columns()`
   - `ParquetCache` class for efficient data loading
   - Rich console helpers: `print_info()`, `print_warning()`, etc.

3. **Centralized Styles** (`src/plotting/styles.py`)
   - Color palettes: `PRISM_RAIN_PALETTE`, `DEEP_RAIN_PALETTE`, `SCIENTIFIC_PALETTE`, `MINIMAL_PALETTE`
   - Theme system with RC params
   - `set_plot_style()` function

### ❌ Problems & Inconsistencies

| Issue | Current State | Impact | Files Affected |
|-------|---------------|--------|----------------|
| **Hardcoded output paths** | Every module: `FIG_DIR = Path("figs")` | Can't change save location without editing code | All 10+ modules |
| **Inconsistent figure sizes** | ITS: `(24,17)`, CNP: `(36,20)`, IVg: default | Different plot types have mismatched dimensions | its.py, vt.py, cnp_time.py, photoresponse.py |
| **Style locked to prism_rain** | `set_plot_style("prism_rain")` everywhere | Can't switch paper vs presentation styles | All plotting modules |
| **Unused color palettes** | 4 palettes defined, only 1 used | Wasted infrastructure | styles.py |
| **Duplicate code** | `vt.py` has duplicate metadata extractors | Maintenance burden, risk of divergence | vt.py (lines 210-301) |
| **Scattered constants** | `LIGHT_WINDOW_ALPHA=0.15`, `PLOT_START_TIME=20.0` | Hard to configure globally | its.py, vt.py |
| **Inconsistent config adoption** | Only `laser_calibration.py` uses `get_config()` | Other modules ignore config system | 9/10 modules |
| **Hardcoded theme in config** | `plot_theme: Literal["prism_rain"]` | Can't select other themes via config | src/cli/config.py:102 |

---

## Proposed Architecture

### Directory Structure

```
src/plotting/
├── config.py              # NEW: PlotConfig class (plotting-specific config)
├── formatters.py          # NEW: Centralized label/legend formatters
├── styles.py              # ENHANCED: Add paper, presentation, minimal themes
├── plot_utils.py          # ENHANCED: Integrate PlotConfig
├── its.py                 # REFACTOR: Use PlotConfig
├── ivg.py                 # REFACTOR: Use PlotConfig
├── vvg.py                 # REFACTOR: Use PlotConfig
├── vt.py                  # REFACTOR: Use PlotConfig, remove duplicates
├── transconductance.py    # REFACTOR: Use PlotConfig
├── cnp_time.py            # REFACTOR: Use PlotConfig
├── photoresponse.py       # REFACTOR: Use PlotConfig
├── laser_calibration.py   # REFACTOR: Fully integrate PlotConfig
└── overlays.py            # REFACTOR: Use PlotConfig
```

### Configuration Hierarchy

```
┌─────────────────────────────────────────────┐
│          CLI Overrides (Highest)            │
│   --theme paper --dpi 600 --format pdf      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│        Project Config File (High)           │
│   .optothermal_cli_config.json              │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│       User Config File (Medium)             │
│   ~/.optothermal_cli_config.json            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│    Environment Variables (Low)              │
│   CLI_PLOT_THEME=paper                      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│          Hardcoded Defaults (Lowest)        │
│   PlotConfig() with prism_rain theme        │
└─────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Foundation (2-3 hours)

**Objective**: Create new configuration infrastructure

**Tasks**:

1. **Create `src/plotting/config.py`** (1 hour)
   ```python
   class PlotConfig(BaseModel):
       """Centralized plotting configuration."""

       # Output configuration
       output_dir: Path = Path("figs")
       format: Literal["png", "pdf", "svg", "jpg"] = "png"
       dpi: int = 300
       use_proc_subdirs: bool = True

       # Style configuration
       theme: Literal["prism_rain", "paper", "presentation", "minimal"] = "prism_rain"
       palette: Literal["prism_rain", "deep_rain", "scientific", "minimal", "vivid"] = "prism_rain"

       # Figure sizes (by plot type)
       figsize_timeseries: Tuple[float, float] = (24.0, 17.0)
       figsize_voltage_sweep: Tuple[float, float] = (20.0, 20.0)
       figsize_derived: Tuple[float, float] = (36.0, 20.0)
       figsize_transconductance: Tuple[float, float] = (20.0, 20.0)

       # Common parameters
       light_window_alpha: float = 0.15
       plot_start_time: float = 20.0
       padding_fraction: float = 0.02

       # Legend configuration
       legend_default_position: str = "best"
       legend_font_scale: float = 1.0

       # Label formatters
       wavelength_format: str = "{:.0f} nm"
       voltage_format: str = "{:g} V"
       power_auto_unit: bool = True
       datetime_format: str = "%Y-%m-%d %H:%M"

       # Grid & styling
       show_grid: bool = False
       show_cnp_markers: bool = True

       @classmethod
       def from_cli_config(cls, cli_config) -> "PlotConfig":
           """Create PlotConfig from CLIConfig."""
           return cls(
               output_dir=cli_config.output_dir,
               format=cli_config.default_plot_format,
               dpi=cli_config.plot_dpi,
               theme=cli_config.plot_theme,
           )
   ```

2. **Create `src/plotting/formatters.py`** (30 min)
   - `format_wavelength(wl_nm: float, config: PlotConfig) -> str`
   - `format_voltage(voltage: float, config: PlotConfig) -> str`
   - `format_power(power_w: float, config: PlotConfig) -> tuple[float, str]`
   - `format_datetime(dt_str: str, config: PlotConfig) -> str`
   - `LEGEND_FORMATTERS` dict mapping legend_by values to formatters

3. **Update `src/cli/config.py`** (15 min)
   - Change `plot_theme` from `Literal["prism_rain"]` to `Literal["prism_rain", "paper", "presentation", "minimal"]`
   - Add docstring explaining each theme

4. **Enhance `src/plotting/styles.py`** (1 hour)
   - Add `"paper"` theme (serif, small fonts, high DPI, SCIENTIFIC_PALETTE)
   - Add `"presentation"` theme (sans-serif, large fonts, VIVID_PALETTE)
   - Add `"minimal"` theme (sans-serif, MINIMAL_PALETTE)
   - Update docstrings

**Deliverables**:
- [ ] `src/plotting/config.py` created
- [ ] `src/plotting/formatters.py` created
- [ ] `src/cli/config.py` updated
- [ ] `src/plotting/styles.py` enhanced with 3 new themes
- [ ] Unit tests for PlotConfig validation

**Validation**:
```bash
# Test PlotConfig instantiation
python3 -c "from src.plotting.config import PlotConfig; print(PlotConfig())"

# Test theme loading
python3 -c "from src.plotting.styles import set_plot_style; set_plot_style('paper')"
```

---

### Phase 2: CLI Integration (1 hour)

**Objective**: Enable CLI control of plotting configuration

**Tasks**:

1. **Update `src/cli/main.py`** (30 min)
   - Import `PlotConfig` from `src.plotting.config`
   - Create global `PlotConfig` instance from `CLIConfig`
   - Add accessor function: `get_plot_config() -> PlotConfig`

2. **Add CLI flags to plotting commands** (30 min)
   - Add to all `src/cli/commands/plot_*.py` files:
     - `--theme` / `-t`: Override plot theme
     - `--format` / `-f`: Override output format
     - `--dpi`: Override DPI
     - `--figsize`: Override figure size (optional)
   - Pass `PlotConfig` to plotting functions

**Deliverables**:
- [ ] `src/cli/main.py` updated with `get_plot_config()`
- [ ] All plotting commands support `--theme`, `--format`, `--dpi` flags

**Validation**:
```bash
# Test CLI flag parsing
python3 process_and_analyze.py plot-its 67 --auto --theme paper --format pdf --dpi 600 --help
```

---

### Phase 3: Module Migration (3-4 hours)

**Objective**: Refactor all plotting modules to use `PlotConfig`

**Priority order** (refactor in this sequence):

1. **`its.py`** (1 hour) - Most complex, serves as reference
2. **`ivg.py`, `vvg.py`** (30 min) - Similar structure
3. **`vt.py`** (45 min) - Remove duplicate functions
4. **`transconductance.py`** (30 min)
5. **`cnp_time.py`, `photoresponse.py`** (45 min)
6. **`laser_calibration.py`** (15 min) - Already partially integrated
7. **`overlays.py`** (15 min)

**Refactoring Checklist** (apply to each module):

- [ ] Remove `FIG_DIR = Path("figs")` constant
- [ ] Remove `FIGSIZE` constant
- [ ] Add `config: PlotConfig = None` parameter to plotting functions
- [ ] Add `config = config or PlotConfig()` default initialization
- [ ] Replace `set_plot_style("prism_rain")` → `set_plot_style(config.theme)`
- [ ] Replace `plt.figure(figsize=FIGSIZE)` → `plt.figure(figsize=config.figsize_*)`
- [ ] Replace hardcoded output paths with `config.output_dir`
- [ ] Use `config.use_proc_subdirs` for procedure-specific folders
- [ ] Replace `LIGHT_WINDOW_ALPHA` → `config.light_window_alpha`
- [ ] Replace `PLOT_START_TIME` → `config.plot_start_time`
- [ ] Replace `padding=0.02` → `padding=config.padding_fraction`
- [ ] Use formatters from `formatters.py` for labels
- [ ] Update docstrings to document `config` parameter

**Example Refactoring** (`its.py`):

**Before**:
```python
FIG_DIR = Path("figs")
FIGSIZE = (24.0, 17.0)
LIGHT_WINDOW_ALPHA = 0.15
PLOT_START_TIME = 20.0

def plot_its_overlay(df, base_dir, tag, baseline_t=60.0, ...):
    set_plot_style("prism_rain")
    plt.figure(figsize=FIGSIZE)
    # ...
    out = FIG_DIR / f"encap{chipnum}_ITS_{tag}.png"
    plt.savefig(out)
```

**After**:
```python
from src.plotting.config import PlotConfig
from src.plotting.formatters import LEGEND_FORMATTERS

def plot_its_overlay(df, base_dir, tag, baseline_t=60.0, config: PlotConfig = None, ...):
    config = config or PlotConfig()

    set_plot_style(config.theme)
    plt.figure(figsize=config.figsize_timeseries)

    # Use formatters
    formatter = LEGEND_FORMATTERS.get(legend_by, lambda x, c: f"#{x['seq']}")

    # ...

    # Output with config
    output_dir = config.output_dir / "ITS" if config.use_proc_subdirs else config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"encap{chipnum}_ITS_{tag}.{config.format}"
    plt.savefig(out, dpi=config.dpi)
```

**Deliverables**:
- [ ] All 10 plotting modules refactored
- [ ] No hardcoded `FIG_DIR` or `FIGSIZE` constants
- [ ] All modules accept `config: PlotConfig` parameter
- [ ] Formatters used consistently

**Validation**:
```bash
# Test each refactored module
python3 process_and_analyze.py plot-its 67 --auto --theme paper
python3 process_and_analyze.py plot-ivg 81 --auto --theme presentation
python3 process_and_analyze.py plot-cnp-time 67 --theme minimal
```

---

### Phase 4: CLI Commands Update (1 hour)

**Objective**: Update CLI command modules to pass `PlotConfig` to plotting functions

**Tasks**:

1. **Update `src/cli/commands/plot_its.py`** (15 min)
   - Import `get_plot_config` from `src.cli.main`
   - Create `PlotConfig` instance with CLI overrides
   - Pass to `plot_its_overlay()`

2. **Update remaining commands** (45 min)
   - `src/cli/commands/plot_ivg.py`
   - `src/cli/commands/plot_vvg.py`
   - `src/cli/commands/plot_vt.py`
   - `src/cli/commands/plot_transconductance.py`
   - `src/cli/commands/plot_cnp.py`
   - `src/cli/commands/plot_photoresponse.py`
   - `src/cli/commands/plot_laser_calibration.py`

**Example Pattern**:

```python
from src.cli.main import get_plot_config
from src.plotting.config import PlotConfig

@cli_command(name="plot-its", group="plotting")
def plot_its_command(
    chip_number: int,
    theme: str = typer.Option(None, "--theme", "-t"),
    format: str = typer.Option(None, "--format", "-f"),
    dpi: int = typer.Option(None, "--dpi"),
    ...
):
    """Generate ITS plots."""

    # Get base config from CLI
    base_config = get_plot_config()

    # Apply command-specific overrides
    overrides = {}
    if theme:
        overrides["theme"] = theme
    if format:
        overrides["format"] = format
    if dpi:
        overrides["dpi"] = dpi

    config = base_config.copy(update=overrides) if overrides else base_config

    # Call plotting function with config
    plot_its_overlay(history, base_dir, tag, config=config, ...)
```

**Deliverables**:
- [ ] All CLI plotting commands updated
- [ ] Support for `--theme`, `--format`, `--dpi` flags
- [ ] Config properly passed to plotting functions

**Validation**:
```bash
# Test CLI overrides
python3 process_and_analyze.py plot-its 67 --auto --theme paper --dpi 600 --format pdf
```

---

### Phase 5: Testing & Documentation (1-2 hours)

**Objective**: Validate refactoring and document new features

**Tasks**:

1. **Integration Testing** (45 min)
   - Test all themes: `prism_rain`, `paper`, `presentation`, `minimal`
   - Test all formats: `png`, `pdf`, `svg`
   - Test DPI settings: `150`, `300`, `600`
   - Test with/without `use_proc_subdirs`
   - Test config file loading
   - Test environment variable overrides

2. **Create Example Configs** (15 min)
   - `config/plotting_defaults.json` (project defaults)
   - `config/paper_quality.json` (publication settings)
   - `config/presentation_slides.json` (slide settings)

3. **Update Documentation** (30 min)
   - Update `CLAUDE.md` with new plotting config options
   - Update `docs/PLOTTING_IMPLEMENTATION_GUIDE.md`
   - Add `docs/PLOTTING_CONFIG_GUIDE.md` (new file)
   - Update CLI help text

4. **Regression Testing** (30 min)
   - Verify existing plots still generate correctly
   - Compare output with/without config changes
   - Check for performance regressions

**Deliverables**:
- [ ] All tests passing
- [ ] Example config files created
- [ ] Documentation updated
- [ ] No regressions in plot quality

**Validation**:
```bash
# Regression test suite
python3 -m pytest tests/test_plotting_config.py -v

# Manual visual inspection
python3 process_and_analyze.py plot-its 67 --auto --theme prism_rain  # Original
python3 process_and_analyze.py plot-its 67 --auto --theme paper        # New
```

---

## Configuration Examples

### Use Case 1: Paper-Quality Plots

**CLI Flags**:
```bash
python3 process_and_analyze.py plot-its 67 --auto \
    --theme paper --dpi 600 --format pdf
```

**Config File** (`~/.optothermal_cli_config.json`):
```json
{
  "plot_theme": "paper",
  "plot_dpi": 600,
  "default_plot_format": "pdf",
  "output_dir": "publication_figures"
}
```

**Result**:
- High-resolution PDF (600 DPI)
- Serif fonts, publication palette
- Small figure size (3.5" × 2.5" for single-column)
- Saved to `publication_figures/ITS/`

---

### Use Case 2: Presentation Slides

**CLI Flags**:
```bash
python3 process_and_analyze.py plot-ivg 81 --auto \
    --theme presentation --dpi 150
```

**Config File** (`config/presentation_slides.json`):
```json
{
  "plot_theme": "presentation",
  "plot_dpi": 150,
  "default_plot_format": "png",
  "output_dir": "presentation_figs"
}
```

**Result**:
- Large fonts (18pt), sans-serif
- Vivid color palette
- Large figure size (10" × 7")
- Optimized for projectors (150 DPI)

---

### Use Case 3: Batch Processing (Environment Variables)

**Shell**:
```bash
export CLI_PLOT_THEME=minimal
export CLI_PLOT_DPI=300
export CLI_OUTPUT_DIR=/tmp/batch_plots

python3 process_and_analyze.py full-pipeline
python3 process_and_analyze.py plot-its 67 --auto
python3 process_and_analyze.py plot-ivg 67 --auto
```

**Result**:
- All plots use minimal theme
- 300 DPI PNG
- Saved to `/tmp/batch_plots/`

---

## Theme Comparison

| Theme | Font | Font Size | Use Case | Palette | DPI | Fig Size |
|-------|------|-----------|----------|---------|-----|----------|
| **prism_rain** (current) | Serif | 35pt (large) | Lab notebooks, internal reports | PRISM_RAIN | 300 | 20×20 |
| **paper** (new) | Serif | 10pt (small) | Journal publications (Nature, IEEE) | SCIENTIFIC | 600 | 3.5×2.5 |
| **presentation** (new) | Sans-serif | 18pt (XL) | Conference slides, posters | VIVID | 150 | 10×7 |
| **minimal** (new) | Sans-serif | 12pt (medium) | Web dashboards, interactive | MINIMAL | 300 | 8×6 |

---

## Key Benefits

1. **🎯 Single Source of Truth**: All plotting config in `PlotConfig` class
2. **⚡ CLI Control**: Change styles without editing code (`--theme paper`)
3. **📏 Consistent Output**: Same figure size for all plots of the same type
4. **🔄 Flexible Workflows**: Switch between paper/presentation modes instantly
5. **🛡️ Backward Compatible**: Defaults match current behavior exactly
6. **🎨 Future-Proof**: Easy to add new themes/palettes
7. **♻️ DRY Principle**: Formatters eliminate duplication

---

## Migration Checklist

### Phase 1: Foundation
- [ ] Create `src/plotting/config.py`
- [ ] Create `src/plotting/formatters.py`
- [ ] Update `src/cli/config.py`
- [ ] Enhance `src/plotting/styles.py` (add 3 themes)
- [ ] Write unit tests for `PlotConfig`

### Phase 2: CLI Integration
- [ ] Update `src/cli/main.py` with `get_plot_config()`
- [ ] Add `--theme`, `--format`, `--dpi` flags to plotting commands

### Phase 3: Module Migration
- [ ] Refactor `its.py`
- [ ] Refactor `ivg.py`
- [ ] Refactor `vvg.py`
- [ ] Refactor `vt.py` (remove duplicates)
- [ ] Refactor `transconductance.py`
- [ ] Refactor `cnp_time.py`
- [ ] Refactor `photoresponse.py`
- [ ] Refactor `laser_calibration.py`
- [ ] Refactor `overlays.py`

### Phase 4: CLI Commands
- [ ] Update `plot_its.py`
- [ ] Update `plot_ivg.py`
- [ ] Update `plot_vvg.py`
- [ ] Update `plot_vt.py`
- [ ] Update `plot_transconductance.py`
- [ ] Update `plot_cnp.py`
- [ ] Update `plot_photoresponse.py`
- [ ] Update `plot_laser_calibration.py`

### Phase 5: Testing & Documentation
- [ ] Integration tests (all themes × formats)
- [ ] Create example config files
- [ ] Update `CLAUDE.md`
- [ ] Create `docs/PLOTTING_CONFIG_GUIDE.md`
- [ ] Regression testing
- [ ] Visual inspection of outputs

---

## Rollback Plan

If issues arise during migration:

1. **Partial Rollback**: Keep new files (`config.py`, `formatters.py`), revert individual modules
2. **Full Rollback**: Restore from git commit before Phase 1
3. **Hybrid Approach**: Use feature flag `USE_NEW_CONFIG = False` to disable new system

**Git Strategy**:
- Each phase = separate commit
- Tag stable milestones: `plotting-config-v1.0-phase1`, etc.
- Create branch `feature/plotting-config-refactor` for all work

---

## Performance Considerations

**No Performance Impact Expected**:
- `PlotConfig` instantiation is cached (singleton pattern possible)
- Formatters are simple string operations (negligible overhead)
- No changes to core plotting algorithms
- Config loading happens once per CLI invocation

**Memory Impact**:
- `PlotConfig` object: ~1KB
- Formatters module: ~5KB
- Total overhead: <10KB (negligible)

---

## Future Enhancements (Post-Refactor)

1. **Interactive Config Builder** (TUI)
   ```bash
   python3 process_and_analyze.py config-wizard --plotting
   ```

2. **Per-Chip Config Overrides**
   ```yaml
   # chip_params.yaml
   chip_67:
     plot_theme: paper
     figsize_timeseries: [10, 8]
   ```

3. **Plot Templates**
   ```bash
   python3 process_and_analyze.py plot-its 67 --preset "Nature_style"
   ```

4. **Config Validation UI**
   ```bash
   python3 process_and_analyze.py config-validate --plotting
   ```

5. **Theme Preview**
   ```bash
   python3 process_and_analyze.py preview-theme paper
   ```

---

## Success Criteria

✅ **Definition of Done**:

1. All 10 plotting modules use `PlotConfig`
2. No hardcoded `FIG_DIR` or `FIGSIZE` constants
3. CLI flags `--theme`, `--format`, `--dpi` work on all plot commands
4. All 4 themes (prism_rain, paper, presentation, minimal) render correctly
5. Config files and environment variables override defaults
6. Documentation updated with examples
7. No regressions in plot quality (visual inspection)
8. All tests passing

**Acceptance Test**:
```bash
# Generate same plot in all 4 themes
for theme in prism_rain paper presentation minimal; do
    python3 process_and_analyze.py plot-its 67 --auto --theme $theme
done

# Should produce 4 visually distinct plots with consistent data
```

---

## Timeline Estimate

| Phase | Tasks | Estimated Time | Dependencies |
|-------|-------|----------------|--------------|
| Phase 1 | Foundation | 2-3 hours | None |
| Phase 2 | CLI Integration | 1 hour | Phase 1 |
| Phase 3 | Module Migration | 3-4 hours | Phase 1, Phase 2 |
| Phase 4 | CLI Commands | 1 hour | Phase 3 |
| Phase 5 | Testing & Docs | 1-2 hours | Phase 4 |
| **Total** | | **8-11 hours** | |

**Recommended Schedule**:
- Day 1: Phase 1 + Phase 2 (half day)
- Day 2: Phase 3 (modules 1-5, half day)
- Day 3: Phase 3 (modules 6-9) + Phase 4 (half day)
- Day 4: Phase 5 + buffer (half day)

---

## Contact & Support

**Questions?**
- Review this document
- Check `docs/PLOTTING_IMPLEMENTATION_GUIDE.md`
- Consult Claude Code via `claude.ai/code`

**Found a Bug?**
- Open issue with `[plotting-config]` tag
- Include theme, config file, and error message

---

**Document Version**: 1.0
**Last Updated**: 2025-11-02
**Next Review**: After Phase 3 completion
