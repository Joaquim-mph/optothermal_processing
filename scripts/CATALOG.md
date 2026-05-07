# Scripts Catalog

One-off and utility scripts that live outside the `biotite` CLI. All Python scripts run from the repo root with `python scripts/<name>.py` (some accept positional args / flags).

Outputs are grouped here as **figures** (`figs/`), **data artifacts** (`data/`), or **text/console**.

Directory layout:

```
scripts/
├── *.py                 # comparison + per-chip analysis plots
├── benchmarks/          # performance benchmarks
├── chip_utilities/      # ad-hoc chip-level utilities (CNP, raw inventory)
└── latex/               # LaTeX/Beamer post-processing helpers
```

---

## 1. Cross-chip IVg overlays (`compare_ivg_*.py`)

### `compare_ivg_first_with_vg_lines.py`
**Goal:** First-IVg overlay for six Alisson chips (67/72 hBN, 74/75/80/81 biotite), with the IVg picked from the same calendar day as that chip's wavelength-sweep It traces (seq lists from `compare_corrected_It_67_72_74_75_80_81_pairs.py`). Also emits a Sav-Gol dI/dVg derivative figure and per-pair panels (67|72, 74|75, 80|81).
**Input:** `data/03_derived/chip_histories_enriched/Alisson{67,72,74,75,80,81}_history.parquet`.
**Output (all in `figs/compare/`):**
- `alisson67_72_74_75_80_81_IVg_first.png` (plain, I in µA vs Vg).
- `alisson67_72_74_75_80_81_IVg_first_with_Vg.png` (adds dashed Vg lines).
- `alisson67_72_74_75_80_81_dIdVg_first.png` (transconductance).
- `alisson{a}_{b}_IVg_first_with_Vg.png` per pair.

---

## 2. Cross-chip photoresponse comparisons (`compare_photoresponse_*.py`, `compare_corrected_*.py`)

### `compare_photoresponse_72_81.py`
**Goal:** Same-laser-power wavelength-sweep raw photoresponse Δi(λ) overlay for Alisson72 (hBN) and Alisson81 (biotite). ΔI extracted from each It trace by `_extract_delta_current_from_its`.
**Input:** Enriched histories for chips 72/81 with hard-coded sequence numbers (seqs 11–36 for 72; 4–35 for 81).
**Output:**
- `figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength.png`
- `figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength_semilogy.png`

### `compare_photoresponse_72_74_75_81.py`
**Goal:** Same-power Δi(λ) overlay for four chips (72 hBN, 74/75/81 biotite). Chip 75 is sparse (only 365/455/565 nm). Internally invokes `biotite plot-its-suite` to ensure per-chip artifacts exist before overlaying.
**Output:**
- `figs/compare/alisson72_74_75_81_ITS_photoresponse_vs_wavelength.png`
- `figs/compare/alisson72_74_75_81_ITS_photoresponse_vs_wavelength_semilogy.png`

### `compare_corrected_photoresponse_67_72_74_75.py`
**Goal:** Drift-corrected photoresponse for chips 67/72/74/75. Per chip: corrected It overlay + corrected Δi vs λ figure; then a four-chip comparison (linear and semilogy).
**Method:** Stretched-exponential drift fit on t ∈ [20, 60] s, subtracted from full trace. `Δi_corrected = I_corr(120 s) − I_corr(60 s)` (matches the `delta_i_corrected` derived metric, with a `CorrectedDeltaIExtractor` fallback).
**Prereq:** `biotite derive-all-metrics` then `biotite enrich-history <chip>`.
**Output:** Multiple PNGs in `figs/compare/`.

### `compare_80_81_ivg_and_corrected_photoresponse.py`
**Goal:** Encap-pair (80 vs 81) bundle: first-IVg overlay, drift-corrected It overlay per chip, corrected Δi vs λ per chip, plus a combined corrected Δi(λ) comparison (linear and semilogy).
**Method:** Stretched-exp drift fit on t ∈ [fit_t_start, 60] s; `Δi_corrected = I_corr(120) − I_corr(60)`.
**Prereq:** `biotite full-pipeline && biotite derive-all-metrics && biotite enrich-history 80 && biotite enrich-history 81`.
**Output:** Multiple PNGs in `figs/compare/`.

### `compare_corrected_It_67_74_uv.py`
**Goal:** Drift-corrected I(t) overlay for chips 67 (hBN) and 74 (biotite) at UV/blue 365/385/405/455 nm — eight traces in one figure. Color encodes wavelength, linestyle encodes chip.
**Method:** Stretched-exp fit on t ∈ [20, 60] s; baseline anchored so I_corr(60 s) = 0; trace plotted from t = 20 s onward.
**Output:** PNG in `figs/compare/`.

### `compare_corrected_It_67_72_74_75_80_81_pairs.py`
**Goal:** Unified six-chip drift-corrected It comparison laid out as three side-by-side pair panels with shared y-axis: (72|67), (74|75), (80|81). Each panel overlays one corrected I(t) per wavelength. Additionally fits a linear drift on the same window for every (chip, λ) and compares window-RMSE against the stretched-exponential model.
**Method:** Stretched-exp fit on t ∈ [30, 60] s; baseline anchored so I_corr(60 s) = 0; plotted from t = 20 s.
**Output:** Pair figures in `figs/compare/`, LaTeX comparison table on disk, markdown summary printed to stdout.

### `compare_corrected_It_72_74_80_385nm.py`
**Goal:** Drift-corrected It overlay at 385 nm for three chips: 72 (hBN), 74, 80 (biotite) — one trace per chip on a single figure. Picks the seq with `wavelength_nm == 385` automatically from candidate seqs.
**Output:** PNG in `figs/compare/`.

### `compare_corrected_It_74_80_385nm.py`
**Goal:** Same-wavelength (385 nm) corrected It comparison restricted to two biotite chips with conditions matched as closely as possible: chip 74 seq 24 (Vg = −0.5 V, P = 6 µW) vs chip 80 seq 111 (Vg = 0.0 V, P = 6 µW).
**Output:** PNG in `figs/compare/`.

---

## 3. Single-chip analysis plots (`plot_*.py`)

### `plot_ivg_photocurrent_triplets.py`
**Goal:** Unified IVg photocurrent / triplet plotter for any configured chip+date with OFF → ON → OFF wavelength sweeps. Currently bundles Alisson74 (2026-04-21), Alisson72 (2026-04-28), Alisson80 (2026-05-04). Per chip: photocurrent overlay (I_on − I_off vs Vg, one trace per λ) and 2×2 OFF→ON→OFF triplet grid.
**Args:** Optional positional chip numbers (e.g. `… 72 80`) to filter.
**Output:** PNGs per chip+date in `figs/compare/` (or chip-scoped figs).

### `plot_ivg_365nm_triplet_compare.py`
**Goal:** Per-chip 365 nm IVg triplet figures for three chips (one figure each, OFF → ON → OFF raw I_ds vs Vg) plus a single cross-chip overlay of photocurrent (I_on − I_off) vs Vg at 365 nm. Material labels read from `config/encap_characteristics.yaml`. Includes an inset zoom near Vg = −2.6 V.
**Output:** 4 PNGs (3 per-chip triplets + 1 overlay).

### `plot_corrected_deltai_vs_wl_alisson74_vg.py`
**Goal:** Drift-corrected |Δi| vs wavelength for Alisson74 at three gate voltages (Vg = −0.5 V from 2026-04-16; +0.5 V and +2.5 V from 2026-04-21). Restricted to wavelengths common to 2026-04-21 (365–505 nm).
**Method:** Stretched-exp fit on [20, 60] s; |Δi_corrected| = |I_corr(120) − I_corr(60)|.
**Output:** PNG in `figs/compare/` — corrected Δi(λ) curves, one per Vg.

### `plot_corrected_deltai_vs_power_67_75_vg.py`
**Goal:** Corrected (signed) ΔI vs laser power for Alisson67 (hBN) and Alisson75 (biotite) at λ = 455 nm, two gate voltages each (negative and positive). Uses the lowest 4 powers common to both chips.
**Output:** PNG in `figs/compare/`.

### `plot_corrected_deltai_vs_power_67_75_vg_365nm.py`
**Goal:** Same as above but at λ = 365 nm (different sequence ranges per chip).
**Output:** PNG in `figs/compare/`.

### `plot_iteration_decay_alisson81.py`
**Goal:** Iteration-decay diagnostic for Alisson81: repeated It at fixed (λ = 455 nm, P = 6 µW, period = 120 s) at several Vg clusters. Shows that |Δi_corrected| decays monotonically with iteration index — replicates are not exchangeable; the chip's trap state evolves between runs.
**Prereq:** `biotite enrich-history 81`.
**Output:** PNG of |Δi_corrected| vs iteration, one curve per Vg cluster.

### `plot_raw_vs_corrected_it_encap75_seq85.py`
**Goal:** Diagnostic figure showing raw I(t), the stretched-exp drift fit, and the corrected trace for Encap75 / seq 85, illustrating the `delta_i_corrected` correction recipe on one example.
**Output:** PNG in `figs/compare/`.

---

## 4. Subdirectory utilities

### `chip_utilities/plot_cnp.py`
**Goal:** CLI utility to visualize Charge Neutrality Point (CNP) detection for a chip's IVg/VVg measurements.
**Args:** `chip_number` (positional), `--group` (default `Alisson`), `--seq N` (single sequence), `--all` (multiple), `--max N`, `--save`.
**Input:** `data/02_stage/chip_histories/<group><n>_history.parquet`.
**Output:** Interactive matplotlib window or PNGs under `figs/cnp_analysis/` when `--save` is passed.

### `chip_utilities/list_chip_combinations.py`
**Goal:** Scan all CSVs under `data/01_raw/` (recursively), parse `# Key: Value` headers, emit a sorted list of unique `(chip_group, chip_number)` combinations.
**Args:** `--raw-root PATH`, `--format {table|json|yaml}`.
**Output:** Console — Rich table by default, or JSON / YAML.

### `benchmarks/benchmark_consecutive_sweep_diff.py`
**Goal:** Benchmark `ConsecutiveSweepDifferenceExtractor` implementations — scipy cubic interp, scipy linear interp, Numba-accelerated linear — on synthetic IVg sweeps and on real staged measurements.
**Output:** Console timing comparison; reports speedup vs baseline and Numba availability.

### `latex/fix_latex_underscores.py`
**Goal:** Walk LaTeX files generated under `data/04_exports/latex/` and escape unescaped `_` characters inside `\texttt{...}` commands so `pdflatex` doesn't break.
**Output:** Modifies `.tex` files in place; prints which files changed.

### `latex/compile_latex_tables.py`
**Goal:** Batch-compile every `.tex` under `data/04_exports/latex/` to PDF using `pdflatex`, in parallel via `ProcessPoolExecutor`. Two passes for cross-references; cleans up `.aux/.log/.out`.
**Output:** PDFs alongside their source `.tex` files.

### `latex/compile_all_latex.sh`
**Goal:** Convenience wrapper running, in order: `fix_latex_underscores.py` → `compile_latex_tables.py`.
**Output:** Same as the two scripts above; prints a banner per step.

### `latex/generate_beamer_frames.py`
**Goal:** For each subdirectory of `figs/` (configurable), emit a `.txt` file containing one Beamer `\begin{frame}…\end{frame}` snippet per image (PNG/JPG/PDF). Image titles derived from filenames with LaTeX-escaping. Snippets reference images via paths relative to the project root.
**Output:** One `.txt` per figure subdirectory (location controlled by `--output-dir`).

### `latex/README_latex.md`
Documentation for the LaTeX-related scripts (not executable).

---

## Quick reference

| Category | Scripts | Output target |
|---|---|---|
| Cross-chip IVg overlays | `compare_ivg_first_with_vg_lines` | `figs/compare/alisson*_IVg_first*.png`, `*_dIdVg_first.png` |
| Cross-chip raw photoresponse | `compare_photoresponse_72_81`, `compare_photoresponse_72_74_75_81` | `figs/compare/*photoresponse*.png` |
| Cross-chip corrected photoresponse | `compare_corrected_photoresponse_67_72_74_75`, `compare_80_81_ivg_and_corrected_photoresponse` | `figs/compare/*corrected*.png` |
| Cross-chip corrected It | `compare_corrected_It_67_74_uv`, `compare_corrected_It_67_72_74_75_80_81_pairs`, `compare_corrected_It_72_74_80_385nm`, `compare_corrected_It_74_80_385nm` | `figs/compare/*.png` (+ LaTeX table for the 6-chip pairs script) |
| Per-chip IVg photocurrent / triplets | `plot_ivg_photocurrent_triplets`, `plot_ivg_photocurrent_alisson{72,74,80}_*`, `plot_ivg_365nm_triplet_compare` | `figs/compare/*.png` |
| Single-chip Δi analyses | `plot_corrected_deltai_*`, `plot_iteration_decay_alisson81`, `plot_raw_vs_corrected_it_encap75_seq85` | `figs/compare/*.png` |
| CNP diagnostics | `chip_utilities/plot_cnp` | `figs/cnp_analysis/*.png` (with `--save`) |
| Dev utilities | `benchmarks/benchmark_consecutive_sweep_diff`, `chip_utilities/list_chip_combinations` | console |
| LaTeX / Beamer | `latex/fix_latex_underscores`, `latex/compile_latex_tables`, `latex/compile_all_latex.sh`, `latex/generate_beamer_frames` | `data/04_exports/latex/*.pdf`, `figs/**/*.txt` |
