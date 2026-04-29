# Scripts Catalog

One-off and utility scripts that live outside the `biotite` CLI. All Python scripts run from the repo root with `python scripts/<name>.py` (some accept `argparse` flags).

Outputs are grouped here as **figures** (`figs/`), **data artifacts** (`data/`), or **text/console**.

---

## 1. Cross-chip comparison plots (`compare_*.py`)

### `compare_ivg_first_72_81.py`
**Goal:** Overlay the very first IVg sweep of Alisson72 (hBN) vs Alisson81 (biotite) for a side-by-side baseline transfer curve.
**Input:** Enriched histories `data/03_derived/chip_histories_enriched/Alisson{72,81}_history.parquet` (`biotite build-all-histories` prereq).
**Output:** `figs/compare/alisson72_vs_81_IVg_first.png` — single linear plot, I (µA) vs Vg (V).

### `compare_ivg_first_67_72_75_81.py`
**Goal:** Same idea as above but extended to four chips: 67 (hBN), 72 (hBN), 75 (biotite), 81 (biotite).
**Output:** `figs/compare/alisson67_72_75_81_IVg_first.png` (linear, µA vs V), distinct color per chip.

### `compare_ivg_first_67_72_74_75_81.py`
**Goal:** Five-chip baseline overlay adding Alisson74 (biotite) to the previous comparison.
**Output:** `figs/compare/alisson67_72_74_75_81_IVg_first.png`.

### `compare_photoresponse_72_81.py`
**Goal:** Overlay same-laser-power wavelength-sweep photoresponse Δi(λ) for Alisson72 (hBN) and Alisson81 (biotite). ΔI extracted from each It trace by `_extract_delta_current_from_its`.
**Input:** Enriched histories for chips 72/81 with hard-coded sequence numbers (seqs 11–36 for chip 72; 4–35 for chip 81).
**Output:**
- `figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength.png` (linear)
- `figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength_semilogy.png` (log y)

### `compare_photoresponse_72_74_75_81.py`
**Goal:** Same-power Δi(λ) overlay for four chips (72 hBN, 74/75/81 biotite). Chip 75 is sparse (only 365/455/565 nm). Internally invokes `biotite plot-its-suite` to ensure per-chip artifacts exist before overlaying.
**Output:**
- `figs/compare/alisson72_74_75_81_ITS_photoresponse_vs_wavelength.png`
- `figs/compare/alisson72_74_75_81_ITS_photoresponse_vs_wavelength_semilogy.png`

### `compare_corrected_photoresponse_72_74_75_81.py`
**Goal:** Drift-corrected photoresponse comparison for chips 72/74/75/81. For each chip: a corrected It overlay and a corrected Δi vs λ figure; then a four-chip comparison figure (linear and semilogy).
**Method:** Stretched-exponential drift fit on t ∈ [20, 60] s, subtracted from full trace. `Δi_corrected = I_corr(120 s) − I_corr(60 s)` (matches the `delta_i_corrected` derived metric, with a fallback `CorrectedDeltaIExtractor`).
**Prereq:** `biotite derive-all-metrics` then `biotite enrich-history <chip>`.
**Output:** Multiple PNGs in `figs/compare/` — one corrected-It overlay per chip, one Δi(λ) per chip, plus the four-chip comparison panels.

### `compare_corrected_It_67_74_uv.py`
**Goal:** Drift-corrected I(t) overlay for chips 67 (hBN) and 74 (biotite) at UV/blue wavelengths 365/385/405/455 nm — eight traces in one figure. Color encodes wavelength, linestyle encodes chip.
**Method:** Stretched-exponential fit on t ∈ [20, 60] s, subtracted; baseline anchored so I_corr(60 s) = 0; trace plotted from t = 20 s onward.
**Output:** PNG in `figs/compare/` (one overlay figure showing both chips at four wavelengths each).

---

## 2. Single-chip analysis plots (`plot_*.py`)

### `plot_cnp.py`
**Goal:** Quick CLI utility to visualize Charge Neutrality Point (CNP) detection for a chip's IVg/VVg measurements.
**Args:** `chip_number` (positional), `--group` (default `Alisson`), `--seq N` (single sequence), `--all` (multiple), `--max N`, `--save`.
**Input:** `data/02_stage/chip_histories/<group><n>_history.parquet`.
**Output:** Either an interactive matplotlib window or PNGs saved to `figs/cnp_analysis/` when `--save` is passed.

### `plot_ivg_photocurrent_alisson74_2026-04-21.py`
**Goal:** IVg photocurrent analysis for Alisson74 measurements taken on 2026-04-21. Hard-coded OFF/ON/OFF triplets at 365, 385, 405, 455 nm.
**Output:** Two figures
1. Photocurrent overlay (I_on − I_off) vs Vg, one trace per wavelength.
2. 2×2 grid showing the OFF→ON→OFF triplet (raw IVg current vs Vg) per wavelength.

### `plot_corrected_deltai_vs_wl_alisson74_vg.py`
**Goal:** Drift-corrected |Δi| vs wavelength for Alisson74 at three gate voltages (Vg = −0.5 V from 2026-04-16; +0.5 V and +2.5 V from 2026-04-21). Restricted to wavelengths common to 2026-04-21 (365–505 nm).
**Method:** Stretched-exp fit on [20, 60] s; |Δi_corrected| = |I_corr(120) − I_corr(60)|.
**Output:** PNG in `figs/compare/` — corrected Δi(λ) curves, one per Vg.

### `plot_corrected_deltai_vs_power_67_75_vg.py`
**Goal:** Corrected (signed) ΔI vs laser power for Alisson67 (hBN) and Alisson75 (Biotite) at λ = 455 nm and at two gate voltages each (negative and positive). Uses the lowest 4 powers common to both chips.
**Output:** PNG in `figs/compare/` (signed Δi vs laser power, two Vg per chip).

### `plot_corrected_deltai_vs_power_67_75_vg_365nm.py`
**Goal:** Same as above but at λ = 365 nm (different sequence ranges per chip).
**Output:** PNG in `figs/compare/` for the 365 nm comparison.

### `plot_raw_vs_corrected_it_encap75_seq85.py`
**Goal:** Diagnostic figure showing raw I(t), the stretched-exp drift fit, and the corrected trace for Encap75 / seq 85, illustrating the `delta_i_corrected` correction recipe on one example.
**Output:** PNG in `figs/compare/`.

### `diagram_wavelength_sweep_protocol.py`
**Goal:** Explanatory diagram of the same-power wavelength-sweep measurement protocol used on Alisson72/81.
**Output:** `figs/compare/wavelength_sweep_protocol.png`. Top panel: a real It trace (chip 72 / 81 reference) annotated with 60 s dark / 60 s light / 60 s relaxation. Bottom panel: the 10 wavelengths in measurement order, colored by λ, annotated with per-wavelength laser drive voltage V_L from calibration.

---

## 3. Performance / development utilities

### `benchmark_consecutive_sweep_diff.py`
**Goal:** Benchmark the `ConsecutiveSweepDifferenceExtractor` implementations — scipy cubic interp, scipy linear interp, Numba-accelerated linear — on synthetic IVg sweeps and on real staged measurements.
**Output:** Console timing comparison (no files written). Reports speedup vs baseline and verifies Numba availability.

### `list_chip_combinations.py`
**Goal:** Scan all CSVs under `data/01_raw/` (recursively), parse `# Key: Value` headers and emit a sorted list of unique `(chip_group, chip_number)` combinations encountered.
**Args:** `--raw-root PATH`, `--format {table|json|yaml}`.
**Output:** Console — Rich table by default, or JSON / YAML for programmatic consumption.

---

## 4. LaTeX / Beamer support

### `fix_latex_underscores.py`
**Goal:** Walk LaTeX files generated under `data/04_exports/latex/` and escape unescaped `_` characters inside `\texttt{...}` commands, which otherwise break `pdflatex`.
**Output:** Modifies `.tex` files in place; prints which files were changed.

### `compile_latex_tables.py`
**Goal:** Batch-compile every `.tex` under `data/04_exports/latex/` to PDF using `pdflatex`, in parallel via `ProcessPoolExecutor`. Runs two passes for cross-references and cleans up `.aux/.log/.out` afterwards.
**Output:** PDFs alongside their source `.tex` files in `data/04_exports/latex/`.

### `compile_all_latex.sh`
**Goal:** Convenience wrapper running, in order: `fix_latex_underscores.py` then `compile_latex_tables.py`.
**Output:** Same as the two scripts above; prints a banner per step.

### `generate_beamer_frames.py`
**Goal:** For each subdirectory of `figs/` (configurable), emit a `.txt` file containing one Beamer `\begin{frame}…\end{frame}` snippet per image (PNG/JPG/PDF). Image titles are derived from filenames with LaTeX-escaping. Snippets reference images via paths relative to the project root, so they can be pasted directly into a Beamer presentation.
**Output:** One `.txt` per figure subdirectory (location controlled by `--output-dir`).

### `README_latex.md`
Documentation for the LaTeX-related scripts (not executable).

---

## Quick reference

| Category | Scripts | Output target |
|---|---|---|
| Cross-chip IVg overlays | `compare_ivg_first_*` | `figs/compare/alisson*_IVg_first.png` |
| Cross-chip photoresponse | `compare_photoresponse_*`, `compare_corrected_photoresponse_*`, `compare_corrected_It_67_74_uv` | `figs/compare/*photoresponse*.png`, corrected-It overlays |
| Single-chip Δi analyses | `plot_corrected_deltai_*`, `plot_ivg_photocurrent_*`, `plot_raw_vs_corrected_it_*` | `figs/compare/*.png` |
| Protocol / pedagogy | `diagram_wavelength_sweep_protocol` | `figs/compare/wavelength_sweep_protocol.png` |
| CNP diagnostics | `plot_cnp` | `figs/cnp_analysis/*.png` (with `--save`) |
| Dev utilities | `benchmark_consecutive_sweep_diff`, `list_chip_combinations` | console |
| LaTeX / Beamer | `fix_latex_underscores`, `compile_latex_tables`, `compile_all_latex.sh`, `generate_beamer_frames` | `data/04_exports/latex/*.pdf`, `figs/**/*.txt` |
