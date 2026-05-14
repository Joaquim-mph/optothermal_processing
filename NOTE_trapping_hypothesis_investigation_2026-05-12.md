# Trapping-hypothesis investigation — session note (2026-05-12)

Follow-up to `NOTE_per_direction_mobility_2026-05-12.md` (the per-direction CNP + mobility extractors). With those metrics in `metrics.parquet`, this session used them to test the natural first-cut hypothesis — that the backward-mobility deficit on the high-responsivity biotite chips is a charge-trapping effect at the biotite/dielectric interface, with the IVg hysteresis acting as a clean proxy for trapped charge.

**Headline:** the simple version of that hypothesis is **wrong**. The data points to (at least) **two trap populations with very different time constants**, and the chip's state evolves across measurement sessions when the chip has been illuminated.

## Encap classification used in this note

- **Biotite-bottom chips:** 68, 71, 74, 75, 76, 79, 80, 81 (and 73 once measured). Variety of top encapsulant.
- **hBN-encap reference chips:** 67, 72.

(Correction relative to the earlier note: **Encap 68 has biotite at the bottom**, not hBN. It is not a reference chip — it's another biotite-stack data point that happens to show a different signature than 74/75. That makes the across-biotite-chips variation a more interesting axis than I initially framed.)

## What was tried

Three scripts, all reading the new per-direction metrics from `data/03_derived/_metrics/metrics.parquet`:

1. **`scripts/correlate_hysteresis_mobility_deficit.py`** — within-chip and cross-chip linear fits of `µ_back/µ_fwd` vs `hysteresis_v = cnp_backward − cnp_forward`. One regression per (chip, branch). Cross-chip overlay colored by `median |delta_i_corrected|`.

2. **`scripts/encap74_context_split_and_cross_chip_responsivity.py`** — drills into Encap 74 (the cleanest case), splits IVgs by date and illumination state. Adds a cross-chip plot of `1 − median(µ_back/µ_fwd)` vs `median |delta_i_corrected|` to test "responsivity tracks µ-deficit".

All sweeps in the dataset for Encap 74 share Vds = 0.1 V, Vg ∈ [−5, +5] V, step 0.05 V — sweep rate and range are constant. The only context that varies is **date** and **has_light during the sweep**.

## What was found

### 1. Within-chip slope is the WRONG sign on biotite chips

Trapping picture predicts **negative** slope (more hysteresis ⇒ more trapped charge ⇒ more channel screening on backward ⇒ smaller µ_back/µ_fwd). Actual within-chip linregress, electron branch:

| chip | n | slope (V⁻¹) | r | p |
|---|---|---|---|---|
| **74** | 46 | **+0.491** | **+0.864** | **1×10⁻¹⁴** |
| **75** | 40 | +0.319 | +0.764 | 1×10⁻⁸ |
| 71 | 28 | +0.241 | +0.708 | 2×10⁻⁵ |
| **68** | 40 | −0.004 | −0.01 | 0.96 |
| 67 | 46 | +0.029 | +0.01 | 0.96 |
| 72 | 65 | −0.460 | −0.13 | 0.30 |

Encap 74 + 75 + 71 show *strongly significant positive* slopes. Bigger hysteresis goes with **smaller** µ-deficit — opposite to the trapping prediction.

Figure: `figs/cross_chip/mobility_deficit_vs_hysteresis/cross_chip_overlay.png` (cross-chip lines colored by responsivity), and per-chip in `per_chip/Encap{N}_mobility_deficit_vs_hysteresis.png`.

### 2. The "two clusters" in Encap 74 split by DATE, not by light-during-sweep

Figure: `figs/cross_chip/mobility_deficit_vs_hysteresis/Encap74_context_split.png`.

| date | n | hyst range | µ_e_back/µ_fwd range | notes |
|---|---|---|---|---|
| 2026-04-16 | 17 | 1.15–1.5 V | 0.45–0.6 | all dark, pre-illumination |
| 2026-04-21 | 27 | 1.35–1.8 V | 0.6–0.8 | 23 dark + 4 light; chip was illuminated this session |

Between sessions the chip moved to **larger hysteresis** AND **smaller µ-deficit**. The 4 light-on-during-sweep IVgs sit *inside* the dark cluster of the same date — so the relevant variable is not illumination at the moment of the sweep, it's the chip's **cumulative illumination history** between sessions.

Within each date the positive slope persists (r ≈ +0.9 on electrons in 04-16, +0.89 in 04-21), so the inversion isn't an artifact of pooling two dates.

### 3. Cross-chip µ-deficit vs responsivity — trend in predicted direction, but not significant

Figure: `figs/cross_chip/mobility_deficit_vs_hysteresis/deficit_vs_responsivity_cross_chip.png`.

Electron branch slope (deficit vs log₁₀ responsivity): +0.19, r = +0.36, **p = 0.55** (n = 9 chips). Encap 74 is the outlier — biggest deficit. Encap 75 has the highest responsivity but only modest deficit. Hole branch: no correlation.

n = 9 is too small to draw conclusions; **need 73 and 76 measured** before this plot is informative.

## Updated hypothesis — two trap populations

The simplest model that fits all the data:

- **Fast traps** (τ_fast ≲ sweep time, ~ tens of meV deep). Set the **CNP hysteresis loop width**. Re-equilibrate within one IVg loop, so they shift CNP but don't persistently screen the channel.
- **Slow traps** (τ_slow ≫ sweep time, ~ 0.1–0.5 eV deep). Don't re-equilibrate within a loop — they sit charged across the backward leg, **screening the gate** and suppressing apparent gm and inferred µ. They drive the µ_back-deficit.
- The two populations **evolve inversely under illumination** on Encap 74. Light loads the fast manifold (loop widens) while emptying / passivating the slow manifold (deficit shrinks). The 2026-04-21 vs 2026-04-16 cluster shift is exactly this redistribution.
- Both populations are at the **biotite/dielectric interface or in the biotite itself** — biotite-bottom chips (74, 75, 71 to a lesser degree) show the effect; hBN reference chips (67, 72) and biotite chip 68 with very different fab/processing don't.
- The slow population is likely the **same trap manifold that hosts the photogating component** of the photoresponse. Photogenerated carriers fall into the same states.

This connects directly to the existing project memory about Encap 81 photoresponse history-dependence — same fingerprint (chip state evolves across sessions, evolution is monotonic-not-random) on a different observable.

### Predictions the new picture makes that the old one didn't

1. Hysteresis and µ-deficit have **separable** sweep-rate dependence — different inflection points on a sweep-rate ladder.
2. Holding at the apex of an IVg loads slow traps disproportionately — µ-deficit grows with apex-hold time, hysteresis doesn't.
3. Illumination step-changes µ-deficit much more than it step-changes hysteresis (within seconds of light off).
4. Biotite chips with strong photoresponse should *all* show the effect — 73, 76 are the natural test cases.
5. Encap 68 (biotite-bottom but no µ-deficit / no hysteresis-deficit correlation) might be a clue about which biotite-stack property kills the slow-trap manifold. Look at its top encapsulant and processing vs 74/75.

## Proposed experiments

Detailed proposals in the response to the user during this session. Summary table by priority. All on the standard baseline (Vg ∈ [−5, +5] V, step 0.05 V, Vds = 0.1 V, dark unless noted).

| # | Experiment | Time cost | What it tests |
|---|---|---|---|
| 1 | **Sweep-rate ladder** (5 rates, 2 decades, 10ms→100s per-step dwell) | Single morning | Two-timescale picture (different inflections for hyst vs deficit) |
| 2 | **Apex-hold ladder** (t_hold ∈ {0,1,10,100,1000}s at V_g = ±5 V) | Single afternoon | Slow-trap *filling* timescale |
| 3 | **Light-bracketed triplets** (`dark / light / dark` at 4 wavelengths × 3 powers) | ~ half day | Photo-induced step change in µ-deficit |
| 4 | **Pre-conditioning Vg-stress ladder** (60 s at Vg ∈ {−5,−3,−1,+1,+3,+5}, then IVg) | Single morning | Bias-driven slow-trap occupancy |
| 5 | **Vds control** (rerun #1 at Vds ∈ {0.01,0.05,0.1,0.5} V) | Single day | Rule out Joule self-heating |
| 6 | **T dependence** (#1 at multiple T) | Multi-day, needs cryostat/heater | Arrhenius for both populations → trap energies |
| 7 | **Replication on 75, 73, 76, 68** | Repeat protocols | Biotite specificity; 68 as biotite-chips-can-differ test |
| 8 | **Long-dark anneal of 74** (1 week dark + 350 K anneal) | Slow, one-shot | Long-time bound on τ_slow, reversibility |

Recommended ordering: **1 → 2 → 5 → 3 → 4 → 7 → 6 → 8**. Tier-1 (1+2+5) is enough for a defensible result if it comes out as predicted.

## What this session left in the repo

New scripts:
- `scripts/analyze_mobility_fwd_vs_back.py` — per-chip + pooled µ_back/µ_fwd summary across all chips.
- `scripts/correlate_hysteresis_mobility_deficit.py` — per-chip linregress of µ_back/µ_fwd vs hysteresis_v, plus cross-chip overlay.
- `scripts/encap74_context_split_and_cross_chip_responsivity.py` — Encap 74 context split + cross-chip deficit vs responsivity.

New figures (all under `figs/cross_chip/mobility_deficit_vs_hysteresis/`):
- `per_chip/Encap{N}_mobility_deficit_vs_hysteresis.png` (×9)
- `cross_chip_overlay.png`
- `Encap74_context_split.png`
- `deficit_vs_responsivity_cross_chip.png`

No changes to extractors or pipeline this session — all read from existing metrics.
