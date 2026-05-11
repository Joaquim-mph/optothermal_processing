# Field-Effect Mobility Estimator

**Last Updated:** 2026-05-11
**Status:** Prototype (script-level: `scripts/estimate_mobility.py`). Not yet a `DerivedMetric` extractor.

## Overview

Produces a rough estimate of the graphene field-effect mobility μ_FE per chip from existing dark IVg sweeps and the per-device gate stack recorded in `config/encap_characteristics.yaml`. Intended as a sanity check / cross-chip comparison, not a publication-grade number — geometry is assumed (L/W ≈ 2 by default), peak-gm is taken from a single sweep, and contact resistance is ignored.

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
| Material | ε_r | Source |
|---|---|---|
| hBN | 3.5 | Laturia et al., *npj 2D Mater.* 2018 (out-of-plane) |
| biotite | 6.0 | Mica-group phyllosilicate, typical perpendicular value |

Stored in the `materials:` block of `config/encap_characteristics.yaml`.

### Channel aspect ratio

Per-device L/W is not measured yet. The script reads a global default from `config/encap_characteristics.yaml`:

```yaml
geometry:
  aspect_ratio_LW: 2.0
```

A chip can override by adding `aspect_ratio_LW: <value>` inside its own entry.

## Algorithm

For each chip in `config/encap_characteristics.yaml`:

### 1. Pick the IVg sweep
- Load `data/03_derived/chip_histories_enriched/Alisson{N}_history.parquet` (or the staged history if no enriched exists).
- Filter `proc == "IVg"` AND `has_light == False`, sort by `seq`, take the **first row**.
- Pull `vds_v` from the history row (manifest-level field).
- Load the measurement parquet from `parquet_path` via `read_measurement_parquet`.

### 2. Segment the sweep
`segment_voltage_sweep` (in `src/plotting/plot_utils.py`) splits the sweep into monotonic sections. We keep only the **longest segment** — typically the forward branch, from `vg_start_v` to `vg_end_v` — to avoid the turnaround artifact at the sweep apex.

### 3. Compute |g_m| = |dI/dV_g|
Savitzky-Golay derivative via `_savgol_derivative_corrected` (same routine used by `src/plotting/transconductance.py`):
- Median-spacing `Δ` (sign-preserved) so reverse sweeps wouldn't invert the derivative if encountered.
- Auto-clamped window length (`9` default), polynomial order `3`.
- `mode="interp"` so edge points are still defined.

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
  aspect_ratio_LW: 2.0            # central
  aspect_ratio_LW_range: [1.0, 3.0]
materials:
  hBN:
    epsilon_r: 3.5
    epsilon_r_range: [3.0, 4.0]
  biotite:
    epsilon_r: 6.0
    epsilon_r_range: [6.0, 10.0]
```

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
| L/W ≈ 2, same for all chips | Lithography masks were nominally identical | Real per-device L/W not yet measured |
| Top dielectric is always hBN | YAML stack convention | If a device uses a different top layer |
| Out-of-plane ε_r literature values | Bounds propagated to μ: hBN ∈ [3, 4], biotite ∈ [6, 10] | If actual ε_r falls outside these ranges, widen `epsilon_r_range` in the YAML |
| Plausible-range bounds on L/W and ε_r | μ is monotonic in each input, so reporting the [min, max] of μ over the parameter box is exact for the declared ranges | If a per-chip value of any input is measured, pin it in the YAML (only the unfixed inputs then contribute to the bounds) |
| Contact resistance ignored | μ_FE peak-gm is conventional in the literature, even though it under-estimates true μ | When R_contact is a sizable fraction of R_channel |
| First dark IVg is "representative" | One number per device for a comparison table | Device drift / history dependence (see [[project_alisson81_photoresponse_history_dependence]]) — use multiple sweeps then |
| Coarse CNP via min(|I|) | Just used to split into hole/electron branches; peak gm is robust to a small CNP offset | Strongly hysteretic sweeps where forward/reverse CNPs differ a lot — the picked branch boundary will be slightly wrong |

## Outputs

`scripts/estimate_mobility.py` writes:

- Rich console table: chip, bottom material, t_top, t_bot, C_ox [nF/cm²], V_ds, |gm|_h, |gm|_e, μ_h and μ_e each printed as `central [min–max]`, plus a flag (μ outside [10, 10⁵] cm²/V·s).
- `figs/mobility/mobility_estimates.csv` — same columns, machine-readable, including `mu_*_min/max` and `cox_min/max`.
- `figs/mobility/mobility_estimates.png` — left panel: μ bars per chip with min–max whiskers, colored by bottom dielectric; right panel: |g_m|(V_g) overlay for all chips.
- `figs/mobility/per_chip/gm_chip{N}.png` — one figure per chip: |g_m|(V_g) trace, coarse CNP, hole/electron peak markers with `central [min–max]` μ in the legend, and the C_ox range in the title.

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

## Promotion to a CLI command / `DerivedMetric` extractor

When the numbers are validated and the workflow stabilizes:

1. Move `peak_gm_branches` and `cox_per_area` into `src/derived/algorithms/mobility.py`.
2. Add a `MobilityExtractor` in `src/derived/extractors/mobility_extractor.py` (pattern: `cnp_extractor.py`). Returns one `DerivedMetric` per IVg measurement, with `value_float = μ_peak`, plus per-branch values in `flags`/extras.
3. Wire into `MetricPipeline._default_extractors()`.
4. Add a `biotite plot-mobility` CLI command (under `src/cli/commands/`) for the chip-comparison figure, replacing the script.
5. (Optional) Replace the coarse `argmin(|I|)` CNP with the value already computed by `CNPExtractor` (joinable via `chip_histories_enriched`).

Until then, the script-level prototype lives at `scripts/estimate_mobility.py` and is documented here.
