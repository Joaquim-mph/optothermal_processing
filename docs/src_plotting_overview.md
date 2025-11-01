# src/plotting Module Overview

## Role in the Pipeline
- Provides the visualization layer for staged optothermal experiments by reading Parquet measurements and chip histories produced in `src/core`.
- Supplies CLI and Textual UI commands with ready-to-save Matplotlib figures and GIF animations so analysts can inspect device behavior after each processing run.

## Data Flow at a Glance
- Plotters expect `polars.DataFrame` metadata subsets (usually chip histories) plus a base directory containing staged Parquet measurements.
- Each function calls `src.core.utils.read_measurement_parquet` to load the numeric traces it needs (current, voltage, power, etc.).
- Styling is applied lazily via `set_plot_style("prism_rain")` to keep Textual threads safe while ensuring plots share a consistent publication theme (`scienceplots`, custom color cycles, DPI).
- Finished assets are written under `figs/` (sometimes inside chip-specific subfolders) using descriptive filenames such as `encap{chip}_ITS_{tag}.png`.

## Shared Infrastructure
- `plot_utils.py` centralizes reusable helpers: light-window detection (`detect_light_on_window` / `calculate_light_window`), baseline interpolation, transconductance calculation, Savitzky–Golay derivatives, sweep segmentation, and cross-day metadata assembly (`combine_metadata_by_seq` + `load_and_prepare_metadata`).
- `styles.py` defines the `prism_rain` Matplotlib theme and several color palettes; plotters call `set_plot_style` rather than importing it globally so TUI sessions can instantiate plots concurrently.
- `its_presets.py` encapsulates common ITS overlay configurations (dark, power sweep, spectral, custom) so the CLI/TUI can present guardrailed defaults for baseline handling, legends, and validation checks.

## Plotters and Their Outputs

| Module | Key Functions | Primary Outputs |
| --- | --- | --- |
| `its.py` | `plot_its_overlay`, `plot_its_dark`, `plot_its_sequential` | Overlayed current-vs-time PNGs with configurable baselines, legend labeling (wavelength, Vg, LED voltage, power, datetime), optional duration checks, raw/dark variants, and sequential time-line plots; files saved as `encap{chip}_ITS_*`. |
| `ivg.py` | `plot_ivg_sequence` | Chronological Id–Vg overlays (µA) with optional charge-neutrality markers pulled from derived metrics; filename `encap{chip}_IVg_{tag}.png`. |
| `transconductance.py` | `plot_ivg_transconductance`, `plot_ivg_transconductance_savgol` | gm (dId/dVg) PNGs computed either with numpy gradients or Savitzky–Golay smoothing, using sweep segmentation to avoid reversal artifacts and highlighting raw vs filtered traces. |
| `vt.py` | `plot_vt_overlay` | Voltage-vs-time overlays mirroring ITS features (baseline modes, LED window shading, legend presets) saved as `encap{chip}_Vt_{tag}.png`. |
| `vvg.py` | `plot_vvg_sequence` | Vds–Vg overlays (mV) with optional CNP annotations, stored as `encap{chip}_VVg_{tag}.png`. |
| `cnp_time.py` | `plot_cnp_vs_time` | Temporal Dirac-point evolution plots (datetime vs CNP voltage) with light/dark styling, summary statistics, and auto-formatted date axes; saved as `{chip}_cnp_vs_time.png`. |
| `photoresponse.py` | `plot_photoresponse` | Photoresponse trends vs power, wavelength, gate bias, or experiment time with optional filtering, log-scale power sweeps, wavelength grouping, and annotated statistics; saved as `{chip}_photoresponse_* .png`. |
| `laser_calibration.py` | `plot_laser_calibration`, `plot_laser_calibration_comparison` | Calibration curves mapping laser drive voltage to optical power, themed via CLI config and grouped by wavelength or fiber; outputs live in `figs/{tag}/` with configurable formats/DPI. |
| `overlays.py` | `ivg_sequence_gif` | Animated GIFs (or per-frame PNGs fallback) that replay IVg sweeps sequentially or cumulatively using `imageio`; filenames `Encap{chip}_IVg_sequence_{tag}.gif`. |

## Produced Artifacts
- Static figures reside in `figs/`, adopting the repo-wide `encap{chip}_<procedure>_<tag>.png` naming to simplify downstream sharing.
- Laser calibration plots create chip-scoped subfolders (`figs/{chip_group}/`) and honor CLI-configured export formats/DPI.
- Animated assets extend GIF coverage for IVg sequences; if GIF writing fails, individual PNG frames are dropped alongside a warning.

Together, these components let the CLI (`process_and_analyze.py` commands) and Textual UI (`PlotterApp`) render consistent, metadata-rich visual summaries of staged measurements without duplicating plotting logic.
