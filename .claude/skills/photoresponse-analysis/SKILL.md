---
name: photoresponse-analysis
description: Use whenever the user asks for an ad-hoc biotite analysis script that (a) pulls measurements from chip histories by chip/date/seq, (b) computes a photoresponse-like quantity — raw photocurrent (I_on − I_off), drift-corrected ΔI, corrected I(t) trace, etc. — and (c) overlays the result vs wavelength, laser power, gate voltage, or time, optionally across multiple chips. Trigger on phrasing like "photocurrent overlay", "subtract the IVg off from the IVg on", "corrected delta i vs wavelength / power", "ΔI vs power for encap 67 and 75", "compare IVg first sweep across chips", "raw vs corrected It for seq N", "use the same color for the same encap", "legend = wavelength / power / Vg", or any request that names specific chips + dates + seq ranges and asks for a comparison plot. Do NOT use for things that already have a first-class `biotite plot-*` command (ordinary It / IVg / Vt overlays of sequential seqs on one chip).
---

# Photoresponse analysis scripts

This skill covers the family of **one-off analysis scripts** under `scripts/` that combine chip-history filtering, a physical correction (subtraction or stretched-exponential drift removal), and a comparison plot. They are always written as standalone `scripts/<name>.py` files, not as CLI commands, because their chip/date/seq/Vg/wavelength/power structure is specific to a given experimental session.

`scripts/` contains many worked examples. Start there — do not write from scratch.

## Pick the closest reference script first

Before writing anything, pattern-match the user's request against the existing scripts and **copy the closest one**. Editing a known-good script is faster and safer than assembling pieces.

| Request shape | Reference script |
|---|---|
| IVg OFF/ON subtraction, one chip, one day, overlay per wavelength | `plot_ivg_photocurrent_alisson74_2026-04-21.py` |
| Corrected ΔI vs wavelength, one chip, grouped by Vg | `plot_corrected_deltai_vs_wl_alisson74_vg.py` |
| Corrected ΔI vs power, multi-chip, shared color per chip, grouped by Vg | `plot_corrected_deltai_vs_power_67_75_vg.py` (455 nm) or `..._365nm.py` |
| Raw vs drift-corrected I(t) diagnostic for a single seq | `plot_raw_vs_corrected_it_encap75_seq85.py` |
| Multi-chip IVg first-sweep overlay | `compare_ivg_first_67_72_74_75_81.py` |
| Full cross-chip corrected photoresponse report | `compare_corrected_photoresponse_72_74_75_81.py` |

If the task shape is new, pick the script whose *output* is closest, not whose *title* is closest. e.g. "ΔI vs power, one chip, grouped by wavelength" is the power script with the `CHIPS` list of length 1 and wavelength taking the role of the Vg grouping.

Before writing, list `scripts/` — new variants may have appeared since this skill was written.

## The universal recipe

Every script in this family follows the same five-step skeleton. Keep the user's script on this rail.

### 1. Load the right history parquet

```python
hist = pl.read_parquet(f"data/02_stage/chip_histories/Alisson{chip}_history.parquet")
```

Use the **enriched** history (`data/03_derived/chip_histories_enriched/...`) when the user asks about derived metrics (e.g. the `delta_i_corrected` column, `irradiated_power_w`, CNP) — those columns are only present after `biotite enrich-history`. Use the plain history when you only need raw measurements. If unsure, try enriched first; it is a superset.

Never glob CSVs under `data/01_raw/` and never read measurement Parquet paths by hand — always go through `read_measurement_parquet(row["parquet_path"])` from `src/core/utils.py`.

### 2. Describe the experiment as data, not control flow

The reference scripts all start with a top-level literal describing *what* to plot, e.g.:

```python
CHIPS: list[dict] = [
    {"chip": 67, "label": "hBN",     "color": "#377eb8", "date": "2025-10-14",
     "vg_groups": [{"vg_v": -0.35, "seqs": [4, 5, 6, 7]},
                   {"vg_v": +0.2,  "seqs": [9, 10, 11, 12]}]},
    {"chip": 75, "label": "Biotite", "color": "#e41a1c", "date": "2025-09-12",
     "vg_groups": [{"vg_v": -3.0,  "seqs": [18, 19, 20, 21]},
                   {"vg_v": +3.0,  "seqs": [24, 25, 26, 27]}]},
]
```

Treat this literal as the single source of truth for the figure. The user almost always hands you these numbers directly ("encap 67 is hBN, encap 75 is Biotite, seq 4–12 / 18–28, Vg ±, wavelength 455 nm"). Transcribe them faithfully; do not try to auto-derive seq lists from filters unless the user explicitly asks — mis-pairing OFF/ON or grabbing a stray calibration seq is the single most common failure mode.

Confirm the plan by printing the filtered rows before plotting, e.g. `hist.filter(pl.col("seq").is_in(group["seqs"])).select(["seq","has_light","wavelength_nm","irradiated_power_w","vg_fixed_v"])`, so the user can catch a wrong seq early.

### 3. Apply the correction

Three correction modes, in increasing complexity:

**a. Pointwise subtraction (raw photocurrent).** OFF and ON are two sibling measurements with the same sweep axis. Verify sample-index alignment and subtract — see `plot_ivg_photocurrent_alisson74_2026-04-21.py`. Pair each ON with the **immediately preceding** `has_light == False` row by seq, unless the user hands you explicit triplets.

**b. Drift-corrected trace (stretched exponential).** Fit on the pre-illumination window (default `t ∈ [FIT_T_START, FIT_T_END]` = `[20, 60]` s) and subtract. Anchor to zero at `t = EVAL_T_PRE` = 60 s. Either import `CorrectedDeltaIExtractor` for the scalar Δi (ΔI = I_corr(120) − I_corr(60)) or reuse the local `corrected_trace()` helper from `plot_corrected_deltai_vs_wl_alisson74_vg.py` for the full curve. `plot_raw_vs_corrected_it_encap75_seq85.py` is the diagnostic version that plots raw, fit, and corrected on one axis — use it whenever you are unsure the fit is sensible.

**c. Signed vs absolute ΔI.** Default to **signed** ΔI (`v * 1e6`) when the user wants a power- or wavelength-dependent curve — the sign carries the physics (electron vs hole response, Vg sign). Use `abs(v) * 1e6` only when the user explicitly says "absolute" or the sign would alias curves of different Vg onto the same y range unreadably. Match the user's phrasing: in this codebase, the wavelength script happens to be absolute and the power scripts signed.

Canonical constants:

```python
FIT_T_START, FIT_T_END = 20.0, 60.0
EVAL_T_PRE, EVAL_T_POST = 60.0, 120.0
```

If a particular trace is unstable early (e.g. Encap75 seq 85), lower `FIT_T_START` to 0 and document why in the module docstring — `plot_raw_vs_corrected_it_encap75_seq85.py` is the pattern.

### 4. Plot with shared styling

- `config = PlotConfig(); set_plot_style(config.theme)`.
- **No grids, ever** — do not call `plt.grid(...)` or `ax.grid(...)`. See CLAUDE.md.
- **Color encodes chip** (or the outermost grouping dimension the user cares about). When the user says "same color for the same encap regardless of Vg", assign one hex color per chip in the `CHIPS` list and re-use it across all that chip's curves.
- **Marker / linestyle encodes the inner dimension** (Vg sign, wavelength, light on/off). Common choices: `marker="o"` + `linestyle="-"` for Vg ≥ 0, `"s"` + `"--"` for Vg < 0.
- Legend labels should combine chip label and inner variable explicitly, e.g. `f"{chip['label']}, $V_g$={group['vg_v']:+g} V"`.
- Add `ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)` on any signed ΔI plot — the zero crossing is often the point of the figure.
- Axis labels use LaTeX: `r"$\Delta i_{\mathrm{corrected}}$ ($\mu$A)"`, `r"Laser power ($\mu$W)"`, `r"Wavelength (nm)"`, `r"$V_g$ (V)"`.
- For IVg photocurrent overlays specifically: thin faded raw trace (`linewidth=0.6, alpha=0.3`) plus a bold (`linewidth=1.8`) Savitzky–Golay smoothed single forward sweep in the same color — see `auto_select_savgol_params` in `src/plotting/transconductance.py`.

### 5. Save through `PlotConfig.get_output_path`

```python
out = config.get_output_path(
    filename,
    chip_number=<primary_chip>,
    procedure="It",                 # or "IVg"
    metadata={"has_light": True},
    special_type="photoresponse",   # or "photocurrent"
    create_dirs=True,
)
plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
```

Never hard-code `figs/...` paths. For a multi-chip figure use the lowest-numbered chip as `chip_number`; the filename carries the full list, e.g. `Alisson67_75_corrected_deltai_vs_power_455nm_by_Vg`.

## Script naming and placement

Place new scripts in `scripts/`, named:

- `plot_<quantity>_<chips>_<qualifier>.py` — e.g. `plot_corrected_deltai_vs_power_67_75_vg.py`, `plot_ivg_photocurrent_alisson74_2026-04-21.py`.
- `compare_<quantity>_<chips>.py` — for multi-chip comparisons, e.g. `compare_ivg_first_67_72_74_75_81.py`.

Keep the module docstring at the top honest and specific: state chips, dates, seq ranges, wavelength/power, the correction method, and how to run (`python scripts/<name>.py`). Future-you and the user both read it.

## Sanity checks before declaring done

1. Did you print the filtered history rows so the user can eyeball the seq list?
2. Does the number of points per curve match what the user described (e.g. "4 power values")?
3. Are chip colors consistent across Vg groups when the user asked for that?
4. Is ΔI signed vs absolute matching the user's wording?
5. Did the figure land under `figs/` via `PlotConfig.get_output_path`, not a hard-coded path?
6. Run the script (`python scripts/<name>.py`) and confirm the `saved …` line — don't report success from code inspection alone.

## Out of scope

- Standard per-chip It / IVg / Vt overlays with sequential seqs — use the existing `biotite plot-its` / `plot-ivg` / `plot-vvg` / `plot-vt` CLI commands.
- Defining a new reusable derived metric — use the extractor plugin system under `src/derived/extractors/` (see `docs/ADDING_NEW_METRICS_GUIDE.md`).
- Changing the drift correction algorithm itself — edit `src/derived/algorithms/stretched_exponential.py` and the extractor, not the script.
