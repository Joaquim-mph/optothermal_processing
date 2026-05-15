# Per-direction CNP / mobility — session note (2026-05-12)

## What was added

### Metrics

Two extractors were re-keyed to emit one row per **sweep direction**, so a looped IVg (`0 → V_start → V_end → V_start → 0`) now yields direction-resolved metrics instead of collapsing both legs into a single number.

- `CNPExtractor` (`src/derived/extractors/cnp_extractor.py`)
  - 3 rows per IVg: `cnp_forward`, `cnp_backward`, `cnp_voltage` (mean — back-compat name).
  - Per-leg parabolic fit on `I(Vg)` in a window = 1% of leg length around `argmin(|I|)`.
  - VVg path fits `Vds(Vg)` directly; no resistance computed inside the extractor.
  - `value_json` carries `v_fwd`, `v_back`, `i_fwd`, `i_back`, `hysteresis_v`, and the per-leg parabola coefficients.

- `MobilityExtractor` (`src/derived/extractors/mobility_extractor.py`)
  - 6 rows per IVg: `mobility_fe_{holes,electrons}_{forward,backward}` plus the back-compat means `mobility_fe_holes` / `mobility_fe_electrons`.
  - Algorithm factored into `peak_gm_on_leg` (`src/derived/algorithms/mobility.py`) which runs Sav-Gol gm + coarse-CNP branch split on one already-monotonic leg; the legacy `peak_gm_signed` is now a thin "longest-segment" wrapper for `scripts/estimate_mobility.py` etc.
  - Mean instance is emitted **only when both directions are present**. Off-pattern sweeps → all six rows are `None` and a `SWEEP_NOT_LOOPED` warning is logged (matches the CNP contract).

Both extractors share the new helper `src/derived/algorithms/cnp_parabola.py::split_full_range_legs` (keeps monotonic legs covering ≥ 95% of the Vg range, tagged forward/backward).

Downstream consumers (`plot_cnp.py`, `export_latex.py`, `scripts/plot_mobility_*`) keep working: the bare names `cnp_voltage` / `mobility_fe_holes` / `mobility_fe_electrons` retain their meaning as the per-direction mean. New columns `cnp_forward`, `cnp_backward`, `mobility_fe_*_forward`, `mobility_fe_*_backward` simply appear alongside after a re-derive.

### Visualizers (Encap 74)

- `scripts/visualize_ivg_cnp_alisson74.py` — IVg with the 3 CNP markers and the two parabolic fits.
- `scripts/visualize_ivg_cnp_mobility_alisson74.py` — adds a second panel of signed gm = dI/dVg per direction with the 4 peak-gm markers (holes × electrons × fwd/back) annotated with µ_FE.

### Tests

All 28 tests in `tests/derived/` pass, including new `TestCNPExtractor` (looped + one-way + flat) and `TestMobilityExtractor` (looped + one-way + missing-vds + dead-sample + truly off-pattern), and the original photoresponse / its-relaxation / pairwise tests.

## What we found — backward mobility vs forward, pooled across 14 Alisson chips

Computed on-the-fly across every IVg in every enriched history (432 looped sweeps).

| branch | median(µ_back / µ_fwd) per chip, then pooled | mean fraction of sweeps with µ_back < µ_fwd |
|---|---|---|
| holes | **1.026** | **37%** |
| electrons | **0.924** | **68%** |

- **Hole branch**: statistically tied. Backward is slightly *faster* by the median; not "usually slower".
- **Electron branch**: a real ~8% asymmetry — backward is the slower leg in ~2/3 of sweeps.

## What's worth investigating — the high-responsivity quartet

A handful of chips show the asymmetry far more strongly than the population, on **both** branches. These are exactly the chips with the largest photoresponse.

| chip | n | hole µ_back / µ_fwd | % back-slower (holes) | electron µ_back / µ_fwd | % back-slower (electrons) |
|---|---|---|---|---|---|
| **74** | 46 | 0.852 | **97.8%** | **0.596** | **100%** |
| **73** | 1 | 0.894 | 100% | 0.742 | 100% |
| **76** | 2 | 0.967 | 100% | 0.673 | 100% |
| **75** | 40 | 1.212 | 7.5% | 0.909 | 57.5% |

- **74** is the cleanest case: ~46 sweeps, backward systematically slower on both branches, with the electron branch dropping ~40%.
- **73, 76** point the same way on both branches but only have 1–2 sweeps each — needs more data.
- **75** is the partial outlier: hole-back is *faster* (1.21×) while electron-back is slower (0.91×). Different physics on the two branches.

The hBN-encapsulated reference chips (67/72) and 71/80/81 show the population behavior (slight electron asymmetry, no hole asymmetry).

### Hypothesis to test

The chips with sharp back-leg mobility deficits — especially 74 (and likely 73, 76 once measured) — are the same chips with the strongest photocurrent. A natural picture is **carrier trapping at the biotite / dielectric interface during the forward sweep**, where the backward sweep transports through a partially-trapped channel and pays a mobility cost. If that's the right picture:

- The hysteresis voltage in the new `cnp_forward` / `cnp_backward` should correlate within-chip with µ_back/µ_fwd.
- The asymmetry should depend on sweep speed (faster = less trapping/de-trapping → smaller asymmetry).
- It should also depend on Vds-step amplitude and on whether the IVg was preceded by an illumination cycle.

### Suggested next steps

1. Re-measure 73 and 76 with the same IVg protocol used on 74/75 so the n is comparable.
2. Re-run `biotite derive-all-metrics` after measurements land — the new per-direction metrics will materialize into enriched histories automatically.
3. Add a scatter / overlay plot: per-IVg `µ_back / µ_fwd` (each branch) vs the same IVg's hysteresis voltage. If the trapping picture is right we should see an anti-correlation: bigger hysteresis ⇒ slower backward.
4. Cross with the photoresponse metrics for the same chips — is `µ_fwd − µ_back` (electron branch) predictive of ΔI per power?

## Files touched

- New: `src/derived/algorithms/cnp_parabola.py`, `scripts/visualize_ivg_cnp_alisson74.py`, `scripts/visualize_ivg_cnp_mobility_alisson74.py`, `scripts/analyze_mobility_fwd_vs_back.py`, this note.
- Rewritten: `src/derived/extractors/cnp_extractor.py`, `src/derived/extractors/mobility_extractor.py`.
- Edited: `src/derived/algorithms/mobility.py` (factored `peak_gm_on_leg`), `src/derived/metric_pipeline.py` (now registers 3 CNP + 6 mobility instances), `tests/derived/test_extractors.py` (`TestCNPExtractor`, `TestMobilityExtractor`).
