# Compare Photoresponse 72 vs 81 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One standalone script that overlays the same-power wavelength-sweep photoresponse (Δcurrent vs wavelength) of Alisson72 (hBN dielectric) and Alisson81 (biotite dielectric), producing a linear and a semilogy PNG.

**Architecture:** A single file at `scripts/compare_photoresponse_72_81.py`. Hardcoded chip numbers and seq lists at module level. Loads enriched chip histories via polars, filters to the wavelength-sweep seqs, reuses `src.plotting.its_photoresponse._extract_delta_current_from_its` as a fallback when `delta_current` is missing, then draws two figures with matplotlib using the repo's `PlotConfig` / `set_plot_style`.

**Tech Stack:** Python 3.11+, polars, numpy, matplotlib, existing `src.plotting.*` and `src.core.utils` modules. No tests (out of scope per spec).

**Spec:** `docs/superpowers/specs/2026-04-13-compare-photoresponse-72-81-design.md`

---

## File Structure

- **Create:** `scripts/compare_photoresponse_72_81.py` — the entire feature. One file with module-level constants, two helpers (`load_chip_curve`, `make_figure`), and a `main()`.
- **Read (no modifications):**
  - `data/03_derived/chip_histories_enriched/Alisson72_history.parquet`
  - `data/03_derived/chip_histories_enriched/Alisson81_history.parquet`
  - `src/plotting/its_photoresponse.py` (import `_extract_delta_current_from_its`)
  - `src/plotting/config.py` (import `PlotConfig`)
  - `src/plotting/styles.py` (import `set_plot_style`)
  - `src/core/utils.py` (reached transitively via the fallback extractor)
- **Write (output):** `figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength.png` and `..._semilogy.png`

Verified against the enriched history schema: columns `seq` (u32), `proc` (str), `has_light` (bool), `wavelength_nm` (f64), `delta_current` (str — stored as Utf8, must be cast to Float64), `parquet_path` (str) all exist.

---

## Task 1: Create the script skeleton and module-level constants

**Files:**
- Create: `scripts/compare_photoresponse_72_81.py`

- [ ] **Step 1: Create the file with imports, constants, and a no-op `main`**

```python
"""
Overlay same-power wavelength-sweep photoresponse for Alisson72 (hBN)
and Alisson81 (biotite).

Produces two PNGs under figs/compare/:
  * alisson72_vs_81_ITS_photoresponse_vs_wavelength.png          (linear)
  * alisson72_vs_81_ITS_photoresponse_vs_wavelength_semilogy.png (log y)

Run from the repo root:
    python scripts/compare_photoresponse_72_81.py

Prereq: biotite enrich-history 72 and biotite enrich-history 81.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style
from src.plotting.its_photoresponse import _extract_delta_current_from_its

ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_DIR = Path("figs/compare")

CHIPS = [
    {
        "chip_number": 72,
        "label": "72 (hBN)",
        "seqs": [11, 16, 20, 24, 26, 28, 30, 32, 34, 36],
    },
    {
        "chip_number": 81,
        "label": "81 (biotite)",
        "seqs": [4, 6, 8, 10, 12, 14, 16, 18, 33, 35],
    },
]


def main() -> None:
    pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the file imports cleanly**

Run: `python -c "import importlib.util, sys; spec = importlib.util.spec_from_file_location('compare_photoresponse_72_81', 'scripts/compare_photoresponse_72_81.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('ok')"`
Expected: prints `ok` with no traceback.

- [ ] **Step 3: Commit**

```bash
git add scripts/compare_photoresponse_72_81.py
git commit -m "feat(scripts): skeleton for 72 vs 81 photoresponse compare"
```

---

## Task 2: Implement `load_chip_curve`

This loads one chip's enriched history, filters to the wavelength-sweep seqs, resolves `delta_current`, and returns sorted numpy arrays (wavelength nm, |Δi| in µA).

**Files:**
- Modify: `scripts/compare_photoresponse_72_81.py`

- [ ] **Step 1: Add `load_chip_curve` above `main`**

```python
def load_chip_curve(
    chip_number: int,
    seqs: list[int],
    label: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (wavelengths_nm, delta_current_uA) for one chip's wl sweep."""
    history_path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not history_path.exists():
        raise FileNotFoundError(
            f"Enriched history not found for chip {chip_number} at {history_path}. "
            f"Run: biotite enrich-history {chip_number}"
        )

    history = pl.read_parquet(history_path)

    after_seq = history.filter(pl.col("seq").is_in(seqs))
    after_proc = after_seq.filter(pl.col("proc") == "It")
    after_light = after_proc.filter(pl.col("has_light") == True)

    if after_light.height == 0:
        raise ValueError(
            f"[{label}] no rows survived filtering. "
            f"seq match: {after_seq.height}, "
            f"proc==It: {after_proc.height}, "
            f"has_light: {after_light.height}"
        )

    rows = after_light

    if "delta_current" in rows.columns:
        if rows["delta_current"].dtype == pl.Utf8:
            rows = rows.with_columns(pl.col("delta_current").cast(pl.Float64))
        rows = rows.filter(
            pl.col("delta_current").is_not_null() & pl.col("delta_current").is_not_nan()
        )

    if "delta_current" not in rows.columns or rows.height == 0:
        delta_values: list[float | None] = []
        base_rows = after_light
        for row in base_rows.iter_rows(named=True):
            from src.core.utils import read_measurement_parquet

            parquet_path = Path(row.get("parquet_path") or row.get("source_file") or "")
            if not parquet_path.exists():
                delta_values.append(None)
                continue
            measurement = read_measurement_parquet(parquet_path)
            delta_values.append(
                _extract_delta_current_from_its(measurement, row)
            )
        rows = base_rows.with_columns(pl.Series("delta_current", delta_values))
        rows = rows.filter(pl.col("delta_current").is_not_null())

    if rows.height == 0:
        raise ValueError(
            f"[{label}] could not resolve delta_current for any row "
            f"(enriched column empty and fallback extractor returned None for all rows)."
        )

    rows = rows.sort("wavelength_nm")

    wavelengths_nm = rows["wavelength_nm"].to_numpy()
    delta_current_uA = np.abs(rows["delta_current"].to_numpy()) * 1e6

    print(
        f"[{label}] chip={chip_number} n_points={rows.height} "
        f"wl_range=[{wavelengths_nm.min():.0f}, {wavelengths_nm.max():.0f}] nm "
        f"|Δi|_range=[{delta_current_uA.min():.3g}, {delta_current_uA.max():.3g}] µA"
    )

    return wavelengths_nm, delta_current_uA
```

- [ ] **Step 2: Wire `main` to call it for both chips (without plotting yet)**

Replace the `pass` body of `main` with:

```python
def main() -> None:
    curves: list[tuple[str, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        wl, di = load_chip_curve(chip["chip_number"], chip["seqs"], chip["label"])
        curves.append((chip["label"], wl, di))
```

- [ ] **Step 3: Run the script and verify both chips load**

Run: `python scripts/compare_photoresponse_72_81.py`
Expected: two lines printed, one per chip, each reporting `n_points`, `wl_range`, `|Δi|_range`. No traceback. `n_points` should be ≤ 10 for each chip (seq lists are 10 elements).

If `n_points` is unexpectedly small for either chip, inspect `after_seq`, `after_proc`, `after_light` counts by temporarily printing them — the spec requires sanity-checking that the filter chain lines up with the YAML configs.

- [ ] **Step 4: Commit**

```bash
git add scripts/compare_photoresponse_72_81.py
git commit -m "feat(scripts): load wl-sweep photoresponse curves for 72 and 81"
```

---

## Task 3: Implement `make_figure`

**Files:**
- Modify: `scripts/compare_photoresponse_72_81.py`

- [ ] **Step 1: Add `make_figure` above `main`**

```python
def make_figure(
    curves: list[tuple[str, np.ndarray, np.ndarray]],
    axtype: str,
    output_path: Path,
    config: PlotConfig,
) -> Path:
    """Draw one overlay figure and save it. axtype is 'linear' or 'semilogy'."""
    fig, ax = plt.subplots(figsize=config.figsize_derived)

    for label, wl, di_uA in curves:
        ax.plot(wl, di_uA, "o-", label=label)

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Δ Current (µA)")

    if axtype == "semilogy":
        ax.set_yscale("log")
    elif axtype != "linear":
        raise ValueError(f"axtype must be 'linear' or 'semilogy', got {axtype!r}")

    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")
    return output_path
```

- [ ] **Step 2: Extend `main` to apply the style and draw both figures**

Replace `main` with:

```python
def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    curves: list[tuple[str, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        wl, di = load_chip_curve(chip["chip_number"], chip["seqs"], chip["label"])
        curves.append((chip["label"], wl, di))

    base = OUTPUT_DIR / "alisson72_vs_81_ITS_photoresponse_vs_wavelength"
    make_figure(curves, "linear", base.with_suffix(".png"), config)
    make_figure(
        curves,
        "semilogy",
        base.with_name(base.name + "_semilogy").with_suffix(".png"),
        config,
    )
```

- [ ] **Step 3: Run the script end-to-end**

Run: `python scripts/compare_photoresponse_72_81.py`
Expected:
- Two `[72 (hBN)]` / `[81 (biotite)]` summary lines from Task 2.
- Two `saved figs/compare/...png` lines.
- No traceback.

- [ ] **Step 4: Eyeball the outputs**

Run: `open figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength.png figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength_semilogy.png`
Expected: both files open in Preview. Each shows two labelled curves (`72 (hBN)` and `81 (biotite)`), wavelength on x, Δ current (µA) on y, legend visible, no grid, no title. The semilogy version has a log-scale y-axis.

If a curve looks wrong (e.g. a point at a nonsense wavelength, or flat-zero), revisit the filter chain in `load_chip_curve` — the YAML seq list may need confirmation against the actual chip history.

- [ ] **Step 5: Commit**

```bash
git add scripts/compare_photoresponse_72_81.py
git commit -m "feat(scripts): draw 72 vs 81 photoresponse overlay (linear + semilogy)"
```

---

## Self-review

- **Spec coverage:** Script path ✓ (Task 1). Hardcoded seq lists ✓ (Task 1). Enriched history loading ✓ (Task 2). Filter chain proc=It + has_light ✓ (Task 2). Enriched column + on-the-fly fallback via `_extract_delta_current_from_its` ✓ (Task 2). Sort by wavelength and |Δi|·1e6 in µA ✓ (Task 2). Two outputs under `figs/compare/` with the exact filenames ✓ (Task 3). Repo style via `PlotConfig` + `set_plot_style` ✓ (Task 3). No grid, no title, legend at `best` ✓ (Task 3). Loud error on missing enriched file and on empty filtered history, naming the chip and surviving filter counts ✓ (Task 2). Fail if fallback resolves nothing ✓ (Task 2). No tests, no CLI, no YAML ✓ (out of scope per spec).
- **Placeholder scan:** no "TBD" / "similar to" / "add error handling" / empty code blocks. Every step has concrete content.
- **Type/name consistency:** `load_chip_curve` returns `(np.ndarray, np.ndarray)`; `main` unpacks as `wl, di`, stores `(label, wl, di)`, and `make_figure` iterates `for label, wl, di_uA in curves` — matched. `CHIPS` dict keys (`chip_number`, `label`, `seqs`) are used consistently in Task 2. `PlotConfig().figsize_derived` and `PlotConfig().dpi` are real attributes (verified — already used by `src/plotting/its_photoresponse.py`). Output filename in `main` matches the spec exactly.
