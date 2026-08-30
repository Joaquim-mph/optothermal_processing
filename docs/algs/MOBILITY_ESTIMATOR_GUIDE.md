# Field-Effect Mobility Estimator

**Last Updated:** 2026-08-30
**Status:** Production. Available as both a `DerivedMetric` extractor (`MobilityExtractor`, runs on every IVg measurement during `biotite derive-all-metrics`) and an ad-hoc script (`scripts/estimate_mobility.py`, summary figures + table). Both share pure-function primitives in `src/derived/algorithms/mobility.py`.

## Overview

Produces a rough estimate of the graphene field-effect mobility μ_FE per chip from existing dark IVg sweeps and the per-device gate stack recorded in `config/encap_characteristics.yaml`. Intended as a sanity check / cross-chip comparison, not a publication-grade number — L/W is measured per device for 8 chips and assumed (3.5) for the rest, peak-gm is taken from a single sweep, and contact resistance is ignored.

## Physics

For a long-channel FET in the linear regime,

```
I_d = (W/L) · μ · C_ox · (V_g − V_T) · V_ds
```

so the transconductance at fixed V_ds is

```
g_m = dI_d / dV_g = (W/L) · μ · C_ox · V_ds
```

which we invert to

```
μ_FE = (L/W) · |g_m| / (C_ox · |V_ds|)         [m² V⁻¹ s⁻¹]
```

For graphene this is not a true threshold-voltage model — but `g_m` still has clear peaks on the hole branch (V_g < V_CNP) and electron branch (V_g > V_CNP), and the peak value is the conventional rough estimate of the carrier mobility on each branch.

### Gate capacitance (series stack)

Top hBN (thickness `t_top`, ε_r,top) + bottom dielectric (thickness `t_bot`, ε_r,bot) in series with the graphene channel:

```
C_ox = ε₀ / (t_top / ε_r,top  +  t_bot / ε_r,bot)         [F/m²]
```

with ε₀ = 8.854 × 10⁻¹² F/m. Bottom dielectric is `hBN` or `biotite`, distinguished per chip in the YAML.

### Material constants (literature, out-of-plane)
| Material | ε_r range | central ε_r | Source |
|---|---|---|---|
| hBN | [3.3, 3.7] | 3.5 | Laturia et al., *npj 2D Mater.* 2018 (out-of-plane) |
| biotite | [5, 6] | 5.5 | Mica-group phyllosilicate, typical perpendicular value |

Stored in the `materials:` block of `config/encap_characteristics.yaml`. The YAML
declares only `epsilon_r_range`; the central value is **derived as the midpoint**
of that range by `_resolve_central_range`. A bare `epsilon_r` is honoured only
when no range is given, in which case the range collapses to that single value.

> These are the values in the config as of 2026-08-30. The config is the source
> of truth — it is tuned as new data arrives, so re-read it rather than quoting
> this table in a methods section.

### Channel aspect ratio

L/W is resolved per chip, with a global fallback in `config/encap_characteristics.yaml`:

```yaml
geometry:
  # Central is derived as the midpoint of `_range` (see _resolve_central_range).
  aspect_ratio_LW_range: [3.0, 4.0]        # -> fallback central L/W = 3.5
```

A chip overrides it with `aspect_ratio_LW: <value>` (or `aspect_ratio_LW_range`)
in its own entry. A bare scalar **pins** that chip: `_resolve_central_range`
collapses its range to `(v, v)`, so L/W drops out of that chip's uncertainty box
and only ε_r contributes to the bounds.

**Measured per-device values** (as of 2026-08-30):

| chip | L/W | | chip | L/W |
|---|---|---|---|---|
| 67 | 4/1 = 4 | | 68 | 3/1 = 3 |
| 72 | 1/1 = 1 | | 74 | 2/1 = 2 |
| 80 | 1/2 = 0.5 | | 75 | 5/4 = 1.25 |
| 81 | 7/3 ≈ 2.3333333333 | | 76 | 7/4 = 1.75 |

Chips **69, 71, 73, 79, 100, 101** have no measured L/W and still fall back to
3.5 with range [3.0, 4.0] — their mobilities remain placeholder-scaled and are
not comparable in absolute terms with the eight above.

Because μ is linear in L/W, switching a chip from the 3.5 placeholder to its
measured value rescales that chip's μ by `L/W_measured / 3.5` exactly — from
0.14x (chip 80) to 1.14x (chip 67).

## Algorithm

For each chip in `config/encap_characteristics.yaml`:

### 1. Pick the IVg sweep
- Load `data/03_derived/chip_histories_enriched/Alisson{N}_history.parquet` (or the staged history if no enriched exists).
- Filter `proc == "IVg"` AND `has_light == False`, sort by `seq`.
- Walk the sorted sweeps and take the **first non-clipped one**: a sweep is rejected if more than `SATURATION_FRAC_THRESHOLD = 10%` of its current points lie within 1% of the global `max|I|` (signature of source-meter compliance limit). Such sweeps under-estimate peak `gm` and the resulting mobility. If every dark IVg fails the test, the first one is used and a warning prints — μ is then a lower bound.
- Pull `vds_v` from the history row (manifest-level field).
- Load the measurement parquet from `parquet_path` via `read_measurement_parquet`.

### 2. Segment the sweep
`segment_voltage_sweep` (in `src/plotting/plot_utils.py`) splits the sweep into monotonic sections. We keep only the **longest segment** — typically the forward branch, from `vg_start_v` to `vg_end_v` — to avoid the turnaround artifact at the sweep apex.

### 3. Compute |g_m| = |dI/dV_g|
Two filters run in sequence, in `src/derived/algorithms/mobility.py::smoothed_gm_on_leg`:

**3a. Derivative** — Savitzky-Golay via `_savgol_derivative_corrected` (same routine used by `src/plotting/transconductance.py`):
- Median-spacing `Δ` (sign-preserved) so reverse sweeps wouldn't invert the derivative if encountered.
- Auto-clamped window length (`9` default), polynomial order `3`.
- `mode="interp"` so edge points are still defined.

**3b. Edge trim** — the first and last `GM_EDGE_TRIM = 4` samples (half the derivative window) are dropped. There the derivative comes from a one-sided polynomial fit and undershoots toward zero on a curved trace.

**3c. Smoothing** — the *signed* `g_m` is then Sav-Gol smoothed with the data-driven window/order from `auto_select_savgol_params(..., "auto")`, the same picker the IVg plotting code uses for `I_ph`. Raw peak `g_m` on a cusped graphene sweep sits on a single sample and is noise-sensitive; smoothing makes the reported peak reproducible and makes stored metrics equal what the mobility figures plot. Signed (not `|g_m|`) is smoothed so the hole branch stays negative and the electron branch positive through the CNP sign change.

Smoothing lowers reported μ by ~2% on average (worst case ~7% on the noisiest legs). A leg whose CNP sits within 4 samples of the sweep edge now yields `None` for that branch instead of a peak read off a handful of one-sided edge points.

`auto_select_savgol_params` lives in `src/plotting/shared/plot_utils.py` (matplotlib-free, so the derived pipeline can import it) and is re-exported from `src/plotting/transconductance.py` for existing callers.

### 4. Find CNP and split branches
Coarse CNP: V_g at `argmin(|I|)`. This is intentionally simple — for a rough mobility number we don't need the full hysteresis-aware CNP extractor used elsewhere in the pipeline. We then take

- `gm_h_peak = max( |g_m|  for V_g < V_CNP )`   (hole branch)
- `gm_e_peak = max( |g_m|  for V_g > V_CNP )`   (electron branch)

### 5. Compute μ (central estimate)
```python
mu_si  = (L/W) * gm_peak / (C_ox * |V_ds|)     # m²/V·s
mu_cgs = mu_si * 1e4                            # cm²/V·s
```

### 6. Min/max bounds over parameter ranges

The big sources of uncertainty are **not** the measured `gm` (clean Vg-resolution sweeps give a sharp peak) but the *geometric/material* inputs: L/W, ε_r,top, ε_r,bot. Plausible ranges live in the YAML:

```yaml
geometry:
  aspect_ratio_LW_range: [3.0, 4.0]     # central 3.5 = midpoint
materials:
  hBN:
    epsilon_r_range: [3.3, 3.7]         # central 3.5
  biotite:
    epsilon_r_range: [5, 6]             # central 5.5
```

For a chip with a **measured** L/W the range is pinned, so the band comes from
ε_r alone: a 1.12-1.18x max/min span, roughly -8%/+8%. For a chip still on the
**placeholder**, L/W adds its own 1.33x span and dominates, widening the band to
roughly -19%/+21%.

Because μ is monotonic in each input — linear in L/W, decreasing in both ε_r,top and ε_r,bot via `C_ox = ε₀/(t_top/ε_top + t_bot/ε_bot)` — the extremes within the parameter box are attained at corners, and we evaluate them analytically:

```python
C_ox_min = ε₀ / (t_top/ε_top_min + t_bot/ε_bot_min)
C_ox_max = ε₀ / (t_top/ε_top_max + t_bot/ε_bot_max)
μ_max    = (L/W)_max · gm_peak / (C_ox_min · |V_ds|)   # largest L/W, smallest C_ox
μ_min    = (L/W)_min · gm_peak / (C_ox_max · |V_ds|)   # smallest L/W, largest C_ox
```

No Monte-Carlo is needed — the bounds are exact for the declared ranges. Reported: central μ (from the YAML central values) plus `[μ_min, μ_max]`. The CSV exposes `mu_*_min/max` and `cox_min/max` so downstream analyses can use the band directly.

A per-chip override of `aspect_ratio_LW` (when measured) pins L/W to that value — only ε_r then contributes to the bounds.

Returned per chip: `(mu_h, mu_e)` central plus min/max bounds. The CSV also includes the raw `gm_peak` and `C_ox` so the user can recompute with a different L/W or contact-resistance correction later.

## Assumptions and known limitations

| Assumption | Why it's fine for a rough estimate | When it breaks |
|---|---|---|
| Long-channel linear-regime FET model | Vds = 0.1 V on these devices is well below pinch-off | If Vds becomes a sizable fraction of (V_g − V_CNP) |
| L/W measured for 8 chips; 3.5 placeholder for the other 6 | Measured devices carry no L/W assumption at all | The 6 unmeasured chips keep a placeholder — don't compare their absolute μ with the measured ones |
| Top dielectric is always hBN | YAML stack convention | If a device uses a different top layer |
| Out-of-plane ε_r literature values | Bounds propagated to μ: hBN ∈ [3.3, 3.7], biotite ∈ [5, 6] | If actual ε_r falls outside these ranges, widen `epsilon_r_range` in the YAML |
| Plausible-range bounds on L/W and ε_r | μ is monotonic in each input, so reporting the [min, max] of μ over the parameter box is exact for the declared ranges | If a per-chip value of any input is measured, pin it in the YAML (only the unfixed inputs then contribute to the bounds) |
| Contact resistance ignored | μ_FE peak-gm is conventional in the literature, even though it under-estimates true μ | When R_contact is a sizable fraction of R_channel |
| First dark IVg is "representative" | One number per device for a comparison table | Device drift / history dependence (see [[project_alisson81_photoresponse_history_dependence]]) — use multiple sweeps then |
| Coarse CNP via min(|I|) | Just used to split into hole/electron branches; peak gm is robust to a small CNP offset | Strongly hysteretic sweeps where forward/reverse CNPs differ a lot — the picked branch boundary will be slightly wrong |

## Outputs

`scripts/estimate_mobility.py` writes:

- Rich console table: chip, bottom material, t_top, t_bot, C_ox [nF/cm²], V_ds, |gm|_h, |gm|_e, μ_h and μ_e each printed as `central [min–max]`, plus a flag (μ outside [10, 10⁵] cm²/V·s).
- `figs/mobility/mobility_estimates.csv` — same columns, machine-readable, including `mu_*_min/max` and `cox_min/max`.
- `figs/mobility/mobility_estimates.png` — left panel: μ bars per chip with min–max whiskers, colored by bottom dielectric; right panel: |g_m|(V_g) overlay for all chips.
- `figs/mobility/per_chip/ivg_gm_chip{N}.png` — one stacked 2-row figure per chip with shared V_g axis: **top** the source-drain current I_ds(V_g) from the same dark IVg sweep; **bottom** the signed transconductance g_m(V_g) = dI/dV_g (negative on the hole branch, positive on the electron branch). Both panels mark the coarse CNP; the g_m panel adds the hole and electron peak markers with `central [min–max]` μ in the legend, and the C_ox range is in the title.

## Reuse map

| Concern | Function | File |
|---|---|---|
| Load YAML stack | `load_encap_config` | `scripts/estimate_mobility.py` |
| Load measurement | `read_measurement_parquet` | `src/core/utils.py` |
| Sweep segmentation | `segment_voltage_sweep` | `src/plotting/plot_utils.py:376` |
| Savgol gm | `_savgol_derivative_corrected` | `src/plotting/plot_utils.py:404` |
| (Future) Hysteresis-aware CNP | `CNPExtractor` | `src/derived/extractors/cnp_extractor.py` |

## Sanity check

For graphene FETs with hBN or biotite gating in the 5–90 nm thickness range, expect μ_FE in the range ~10² to ~10⁴ cm²/V·s. The script flags any chip outside `[10, 1e5]` cm²/V·s as suspicious so the user can inspect the underlying sweep manually.

## DerivedMetric extractor

`src/derived/extractors/mobility_extractor.py` registers `MobilityExtractor` in the metric pipeline. Two instances are wired in `metric_pipeline.py:_default_extractors()` — one per branch — so every IVg measurement produces two rows in `data/03_derived/_metrics/metrics.parquet`:

| `metric_name` | `metric_category` | `unit` | `value_float` |
|---|---|---|---|
| `mobility_fe_holes` | electrical | `cm^2/V/s` | central μ on the hole branch |
| `mobility_fe_electrons` | electrical | `cm^2/V/s` | central μ on the electron branch |

The full per-row breakdown lands in `value_json`:

```json
{
  "branch": "holes",
  "mu_central": 11365.6,
  "mu_min": 4972.5,
  "mu_max": 19889.9,
  "gm_peak_signed_S": -1.84e-05,
  "vg_at_peak_V": -0.20,
  "cnp_v_coarse": 0.40,
  "cox_central_F_per_m2": 3.19e-4,
  "cox_min_F_per_m2": 2.79e-4,
  "cox_max_F_per_m2": 3.71e-4,
  "vds_v": 0.1,
  "has_light": false,
  "saturation_fraction": 0.02,
  "n_points_branch": 28,
  "geometry": {
    "top_hBN_nm": 54.0,
    "bottom_dielectric_nm": 43.0,
    "bottom_material": "hBN",
    "aspect_ratio_LW": 4.0,
    "epsilon_top_central": 3.5,
    "epsilon_bot_central": 3.5
  }
}
```

### Pre-extraction filter: dead-sample skip

Before running, the extractor consults the manifest's `quality_flags` column (populated at staging by `src/core/quality.py`). If the IVg carries any `DEAD_*` flag — `DEAD_OPEN_CIRCUIT`, `DEAD_FLAT_IVG`, or `DEAD_STUCK_SATURATED` — the extractor returns `None` and no mobility row is written. This is the cleanest place to drop unusable measurements: they never pollute metrics.parquet, plots automatically exclude them, and the dropped-but-recoverable parquet trace stays on disk for re-inspection.

### Flags and confidence

`flags` is a comma-separated subset of:

| Flag | Trigger | Penalty |
|---|---|---|
| `NOT_SATURATED` | ≥10% of points within 1% of `max\|I\|` (source-meter clipping likely) | ×0.6 |
| `NOT_HEAVILY_SATURATED` | ≥50% of points clipped — peak gm almost certainly missed | ×0.2 |
| `MU_IN_RANGE` | central μ outside [10, 10⁵] cm²/V·s | ×0.5 |
| `BRANCH_HAS_POINTS` | fewer than 5 points on the requested branch | ×0.3 |

`confidence = product of applicable penalties`. So a chip with `NOT_SATURATED` and `NOT_HEAVILY_SATURATED` both flagged lands at confidence ≈ 0.12 — a clear signal to filter out downstream.

The extractor returns `None` (no metric row) on hard preconditions: missing chip in YAML, missing `vds_v`, missing `Vg`/`I` columns, no peak detectable. These show up as debug logs in the pipeline, not as low-confidence rows.

### Configuration

The extractor loads `config/encap_characteristics.yaml` once at instantiation. To override thresholds, construct it directly when wiring a custom pipeline:

```python
from src.derived.extractors.mobility_extractor import MobilityExtractor
ext = MobilityExtractor(
    branch="holes",
    saturation_warn_threshold=0.05,    # stricter
    saturation_heavy_threshold=0.25,
)
```

## Script

`scripts/estimate_mobility.py` is now a thin caller over the same algorithm primitives (`src/derived/algorithms/mobility.py`). It picks the first non-clipped dark IVg per chip, computes the same μ central + min/max as the extractor, and emits the comparison figure / per-chip diagnostics / CSV described above. Use it for cross-chip comparison plots; use the extractor for per-measurement values landing in metrics.parquet.
