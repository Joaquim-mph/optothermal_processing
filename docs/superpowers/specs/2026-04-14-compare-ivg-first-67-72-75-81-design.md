# Compare First IVg: Chips 67, 72, 75, 81 — Design

## Goal

Produce one overlay plot of the first IVg sweep of four chips (two hBN, two biotite) so the transfer curves can be compared side-by-side. Visual reference: `figs/compare/alisson72_vs_81_IVg_first.png`.

## Deliverables

- **Script:** `scripts/compare_ivg_first_67_72_75_81.py` (new file; existing `compare_ivg_first_72_81.py` untouched)
- **Figure:** `figs/compare/alisson67_72_75_81_IVg_first.png`

## Data Source

For each chip N in {67, 72, 75, 81}:

1. Read `data/03_derived/chip_histories_enriched/Alisson{N}_history.parquet`
2. Filter `proc == "IVg"`, sort by `seq`, take the first row
3. Resolve `parquet_path` from that row, load via `src.core.utils.read_measurement_parquet`
4. Normalize columns via `src.plotting.plot_utils.ensure_standard_columns`
5. Extract `VG` (V) and `I * 1e6` (µA)

Error if the enriched history is missing, has no IVg, or the measurement Parquet is missing — same pattern as the reference script.

## Plot

- Single linear axes, `figsize=config.figsize_voltage_sweep`
- Four curves, one per chip, using `PlotConfig` + `set_plot_style(config.theme)`
- Colors (hand-picked to group by material):
  - 67 (hBN) — `#8B0000` (dark red)
  - 72 (hBN) — `#d62728` (red; matches reference)
  - 75 (biotite) — `#08306B` (dark blue)
  - 81 (biotite) — `#1f77b4` (blue; matches reference)
- Legend entries: `"67 (hBN)"`, `"72 (hBN)"`, `"75 (biotite)"`, `"81 (biotite)"`
- Axis labels: `Gate Voltage $V_g$ (V)`, `Drain Current $I_d$ (µA)`
- No grid. `plt.tight_layout()`. Save at `config.dpi` with `bbox_inches="tight"`.

## Out of Scope

- Resistance/conductance transforms
- Log-scale variant
- Auto-detection of material from manifest — materials are hard-coded in the script's `CHIPS` list
- Modifying or deleting the existing `compare_ivg_first_72_81.py`

## Validation

- Script runs from repo root without errors
- PNG is written to the expected path
- Visual check: all four curves visible, legend readable, colors grouped as specified
