# Alisson81 — Experimental History Review

**Source:** `data/03_derived/chip_histories_enriched/Alisson81_history.parquet`
**Campaign window:** 2025-09-08 → 2025-10-30 (one IVg sanity-check on Sept 8; main campaign Sept 25 → Oct 30, 36 days)
**Total measurements:** 284 — **137 light-on** (48.2 %) + **147 dark** (51.8 %)
**Reviewer:** Claude
**Generated:** 2026-05-04 (initial); updated 2026-05-04 with `delta_i_corrected`, `delta_current`, `cnp_voltage`, and `delta_voltage` from `biotite derive-all-metrics` + `biotite enrich-history 81`.

> No chip-specific entry exists in `config/chip_params.yaml` for Alisson81 (only the default group entry). Material, encapsulation, and fab-date metadata are therefore not yet captured in the manifest.

---

## 1. At-a-Glance Summary

### 1.1 Procedure breakdown

| Procedure | Total | Light-on | Dark |
|---|---:|---:|---:|
| It (current vs time, photoresponse) | 158 | 105 | 53 |
| IVg (transfer curve) | 64 | 0 | 64 |
| Vt (threshold voltage) | 36 | 31 | 5 |
| VVg (voltage vs gate) | 26 | 1 | 25 |
| **Total** | **284** | **137** | **147** |

**Note:** No light-on IVg sweeps exist — every IVg is dark. Photoresponse characterization is concentrated in **It** (105 traces) and **Vt** (31 traces).

### 1.2 Wavelength coverage (light-on only)

| λ (nm) | Energy (eV) | Color | Count | First seq |
|---:|---:|---|---:|---:|
| 365 | 3.40 | Deep UV | 1 | 35 |
| 385 | 3.22 | Near UV | 1 | 33 |
| 405 | 3.06 | UV-A | 6 | 18 |
| **455** | **2.72** | **Blue** | **123** | 16 |
| 505 | 2.45 | Green | 1 | 14 |
| 565 | 2.19 | Yellow-green | 1 | 12 |
| 590 | 2.10 | Yellow | 1 | 10 |
| 625 | 1.98 | Red | 1 | 8 |
| 680 | 1.82 | Deep red | 1 | 6 |
| 850 | 1.46 | Near-IR | 1 | 4 |

**455 nm dominates: 123 / 137 = 89.8 % of all light-on runs.** Single-shot wavelengths (each n=1) come from the Sept 25 spectral survey.

### 1.3 Power levels (light-on only)

Calibrated `irradiated_power_w` clusters into four groups (small ±1 % jitter from per-run calibration):

| Nominal P | Calibrated range | Count | Phase |
|---:|---:|---:|---|
| 6 µW | 5.97 – 6.03 µW | 128 | Default working point (93.4 %) |
| 12 µW | 11.98 µW | 7 | Stability series + Oct 21 sweep |
| 18 µW | 18.02 µW | 1 | seq 42 (single power sweep point) |
| 24 µW | 24.01 µW | 1 | seq 43 (single power sweep point) |

**Implication:** essentially the whole campaign was run at **6 µW**; only Oct 21 (seq 40–43) and the Oct 24–28 stability series at 12 µW deviate. This means the chip's spectral and gate behavior is sampled at one intensity — power-dependence data is sparse.

### 1.4 Gate voltage spread (light-on only)

21 distinct `vg_fixed_v` values span Vg ∈ [−3.0 V, +2.0 V] (plus one null, which is the seq 204 light-on VVg ramp).

| Vg (V) | Count | Notes |
|---:|---:|---|
| 0.0 | 34 | Largest cluster — **dominated by Vt-under-light measurements (Oct 30)** |
| −1.0 | 24 | Spectral-sweep workhorse + Vt-under-light |
| −0.7 | 19 | Multi-day stability series (Oct 23–28) |
| −1.15 | 14 | Most-sampled negative gate **for It** (Oct 28) |
| −1.5 | 9 | Oct 28 |
| −1.7 | 8 | Oct 28 |
| −0.5 | 4 | Oct 28 |
| −0.3 | 4 | Oct 21 power sweep |
| −0.8 | 5 | Vt-under-light |
| 1.0, 1.2, 1.3, 1.5, 1.65, 2.0 | 1–2 each | Sparse positive-gate excursions |

The picked working points lean **strongly negative** (most measurements at Vg ≤ 0); positive-gate behavior is only briefly sampled.

---

## 2. Experimental Phases

The campaign decomposes cleanly into five phases.

### Phase 0 — Baseline IVg Sanity Check (Sept 8 + Oct 10)

| seq | date | proc | summary |
|---:|---|---|---|
| 1 | 2025-09-08 | IVg (dark) | Initial Vg ramp −5 → +5 V |
| 37 | 2025-10-10 | IVg (dark) | Mid-campaign sanity check (32 days after seq 1) |

Confirms electrical health of the device before/between active phases.

### Phase 1 — Spectral Survey at Vg = −1.0 V  (Sept 25, seq 1–35, ~4 hours)

Single-day broadband wavelength sweep at fixed power = 6 µW, Vds = 0.1 V, Vg = −1.0 V. The descending wavelength order (IR → UV) is intentional: it minimizes carrier accumulation history at higher photon energies.

| seq | time | λ (nm) | Vg (V) | comment |
|---:|---|---:|---:|---|
| 4 | 15:26:55 | 850 | −1.0 | Near-IR start |
| 6 | 15:41:22 | 680 | −1.0 | |
| 8 | 16:07:02 | 625 | −1.0 | |
| 10 | 16:22:17 | 590 | −1.0 | |
| 12 | 16:39:06 | 565 | −1.0 | |
| 14 | 16:49:06 | 505 | −1.0 | |
| 16 | 16:59:10 | 455 | −1.0 | Blue |
| 18 | 17:09:05 | 405 | −1.0 | UV-A |
| **19** | 17:12:12 | **405** | **+1.0** | Embedded gate scan begins |
| **20** | 17:16:27 | **405** | **−1.5** | |
| **21** | 17:19:34 | **405** | **−3.0** | |
| **22** | 17:23:05 | **405** | **+1.0** | repeat |
| **23** | 17:27:28 | **405** | **+2.0** | |
| 33 | 18:27:42 | 385 | −1.0 | |
| 35 | 18:37:21 | 365 | −1.0 | Deepest UV |

**Bracketing pattern:** every It light-on is sandwiched between dark IVg sweeps (seq 2, 3, 5, 7, 9, 11, 13, 15, 17 …). 20 dark IVg sweeps in this single afternoon enable drift correction and CNP tracking.

**Embedded gate scan at 405 nm (seq 19–23):** within the wavelength sweep, the operator paused to probe gate-voltage response at the strongest-photoresponse wavelength found so far (UV-A). Vg sequence: +1.0, −1.5, −3.0, +1.0 (repeat), +2.0 V.

### Phase 2 — Power Sweep at 455 nm  (Oct 21, seq 40–43, 9 minutes)

Fixed λ = 455 nm, Vg = −0.3 V, Vds = 0.1 V. Linear power ramp at 3-minute spacing.

| seq | time | P (µW) | nominal multiplier |
|---:|---|---:|---:|
| 40 | 20:09:26 | 5.97 | 1× |
| 41 | 20:12:27 | 11.98 | 2× |
| 42 | 20:15:27 | 18.02 | 3× |
| 43 | 20:18:27 | 24.01 | 4× |

Bracketed before/after by dark IVg (seq 38, 39, 44, 45, 46) and a dark-It at seq 47.

**Note on baseline drift:** between seq 40 (I₀ ≈ 16.5 µA) and seq 43 (I₀ ≈ 14.9 µA) the dark current shifted by ~10 % over 9 minutes — non-trivial, suggests slow warming or gate hysteresis is active, and complicates a clean responsivity extraction (see § 5).

### Phase 3a — Multi-day Stability Series at Vg = −0.7 V  (Oct 23–28, seq 58–90)

Twelve It runs at fixed (λ = 455 nm, Vg = −0.7 V, Vds = 0.1 V) spread across 5 days. Powers split between **6 µW (early)** and **12 µW (later)**. Note the elongated `laser_period_s = 480 s` (vs 120 s default) — much longer ON/OFF cycles, suited to capturing slow relaxation.

| seq | date | time | P (µW) | Δt from prev |
|---:|---|---|---:|---:|
| 58 | 2025-10-23 | 16:04:02 | 5.97 | — |
| 60 | 2025-10-23 | 18:08:41 | 5.97 | 2 h 04 m |
| 63 | 2025-10-23 | 20:22:12 | 5.97 | 2 h 13 m |
| 65 | 2025-10-23 | 22:27:41 | 5.97 | 2 h 05 m |
| 68 | 2025-10-24 | 00:38:56 | 5.97 | 2 h 11 m |
| 70 | 2025-10-24 | 02:43:34 | 5.97 | 2 h 04 m |
| 72 | 2025-10-24 | 04:48:12 | 5.97 | 2 h 04 m |
| 75 | 2025-10-24 | 16:37:29 | 11.98 | 11 h 49 m  *(power doubled)* |
| 77 | 2025-10-24 | 18:42:07 | 11.98 | 2 h 04 m |
| 81 | 2025-10-25 | 19:16:56 | 11.98 | 1 d 0 h 35 m |
| 83 | 2025-10-26 | 06:44:06 | 11.98 | 11 h 27 m |
| 86 | 2025-10-27 | 05:26:21 | 11.98 | 22 h 42 m |
| 90 | 2025-10-28 | 03:12:15 | 11.98 | 21 h 46 m |

**Pattern:** 7 replicates at 6 µW spaced ≈ 2 hours apart through Oct 23 → Oct 24 morning, then 6 replicates at 12 µW with wider spacing across 4 days. Designed to capture short-term reproducibility and slow drift.

### Phase 3b — Multi-Gate It Scan at 455 nm / 6 µW  (Oct 28, seq 93–172)

The single most intensive day — **46 light-on It traces in ~16 hours.** Same wavelength and power, sweeping Vg across [−1.7 V, +1.65 V] with bracketing dark IVg between every measurement (every odd seq from 94–171 is a dark IVg).

Vg occupancy on Oct 28 (light-on It only):

| Vg (V) | Count | seq examples |
|---:|---:|---|
| −1.7 | 8 | 132–139 |
| −1.5 | 8 | 146–153 |
| −1.15 | 14 | 95, 97, 99, 101, 103, 105, 112, 114, 117, 120–123, 126 |
| −0.5 | 3 | 165, 171, 172 |
| 0.0 | 7 | 157–162, 164 |
| +1.2 | 2 | 128, 130 |
| +1.3 | 1 | 142 |
| +1.5 | 1 | 93 |
| +1.65 | 1 | 115 |

The cluster at **Vg = −1.15 V (14 traces)** suggests this is a specific point of interest (possibly close to maximum transconductance |gₘ| or a chosen operating point for noise/SNR characterization). seq 105 has an anomalous `laser_period_s = 720 s` — a lone long-cycle measurement, likely for relaxation-time fitting at the most-studied operating point.

### Phase 3c — Light-on Finale (Oct 30, seq 193–283)

The final 24 hours of the campaign packed three different procedure types under illumination:

- **It at 455 nm / 6 µW (28 traces, seq 193–236):** mostly Vg = 0.0 V (15 traces, 193–230) with smaller clusters at Vg = +0.1, +0.67, −0.7, −1.0 V. Reads as a final at-the-CNP study with a few side-tests.
- **VVg under light (1 trace, seq 204):** voltage-vs-gate ramp Vg ∈ [−5, +5] V at 455 nm / 6 µW. Single experimental point — likely a "what does a light-on VVg look like" exploration.
- **Vt under light (31 traces, seq 240–283):** threshold-voltage measurements with the laser on, sweeping Vg ∈ {−2.0, −1.0, −0.8, 0.0, +0.6 V}. This is the only systematic light-induced threshold-shift dataset in the campaign.

Bracketed by 25 dark VVg sweeps (seq 203–281, every odd) and 5 dark Vt traces (seq 238–284) — the densest dark-bracketing of the entire campaign.

---

## 3. Light-on Inventory (compact)

### 3.1 By procedure × wavelength × power × Vg

For It (105 rows) — one line per parameter combination:

| seq range | date(s) | proc | λ (nm) | P (µW) | Vg (V) | n | T_period (s) |
|---|---|---|---:|---:|---:|---:|---:|
| 4 | 2025-09-25 | It | 850 | 6 | −1.0 | 1 | 120 |
| 6 | 2025-09-25 | It | 680 | 6 | −1.0 | 1 | 120 |
| 8 | 2025-09-25 | It | 625 | 6 | −1.0 | 1 | 120 |
| 10 | 2025-09-25 | It | 590 | 6 | −1.0 | 1 | 120 |
| 12 | 2025-09-25 | It | 565 | 6 | −1.0 | 1 | 120 |
| 14 | 2025-09-25 | It | 505 | 6 | −1.0 | 1 | 120 |
| 16 | 2025-09-25 | It | 455 | 6 | −1.0 | 1 | 120 |
| 18 | 2025-09-25 | It | 405 | 6 | −1.0 | 1 | 120 |
| 19, 22 | 2025-09-25 | It | 405 | 6 | +1.0 | 2 | 120 |
| 20 | 2025-09-25 | It | 405 | 6 | −1.5 | 1 | 120 |
| 21 | 2025-09-25 | It | 405 | 6 | −3.0 | 1 | 120 |
| 23 | 2025-09-25 | It | 405 | 6 | +2.0 | 1 | 120 |
| 33 | 2025-09-25 | It | 385 | 6 | −1.0 | 1 | 120 |
| 35 | 2025-09-25 | It | 365 | 6 | −1.0 | 1 | 120 |
| 40 | 2025-10-21 | It | 455 | 6 | −0.3 | 1 | 120 |
| 41 | 2025-10-21 | It | 455 | 12 | −0.3 | 1 | 120 |
| 42 | 2025-10-21 | It | 455 | 18 | −0.3 | 1 | 120 |
| 43 | 2025-10-21 | It | 455 | 24 | −0.3 | 1 | 120 |
| 58–72 | 2025-10-23 → 24 | It | 455 | 6 | −0.7 | 7 | 480 |
| 75–90 | 2025-10-24 → 28 | It | 455 | 12 | −0.7 | 6 | 480 |
| 95–126 | 2025-10-28 | It | 455 | 6 | −1.15 | 13 | 120 |
| 105 | 2025-10-28 | It | 455 | 6 | −1.15 | 1 | **720** |
| 132–139 | 2025-10-28 | It | 455 | 6 | −1.7 | 8 | 120 |
| 146–153 | 2025-10-28 | It | 455 | 6 | −1.5 | 8 | 120 |
| 93 | 2025-10-28 | It | 455 | 6 | +1.5 | 1 | 120 |
| 115 | 2025-10-28 | It | 455 | 6 | +1.65 | 1 | 120 |
| 128, 130 | 2025-10-28 | It | 455 | 6 | +1.2 | 2 | 120 |
| 142 | 2025-10-28 | It | 455 | 6 | +1.3 | 1 | 120 |
| 157–164 | 2025-10-28 | It | 455 | 6 | 0.0 | 7 | 120 |
| 165, 171, 172 | 2025-10-28 | It | 455 | 6 | −0.5 | 3 | 120 |
| 193–230 | 2025-10-30 | It | 455 | 6 | 0.0 | 15 | 120 |
| 212 | 2025-10-30 | It | 455 | 6 | +0.1 | 1 | 120 |
| 214–220 | 2025-10-30 | It | 455 | 6 | −0.7 | 6 | 120 |
| 232 | 2025-10-30 | It | 455 | 6 | +0.67 | 1 | 120 |
| 236 | 2025-10-30 | It | 455 | 6 | −1.0 | 1 | 120 |

For Vt (31 light-on rows, all on 2025-10-30, all at 455 nm / 6 µW):

| Vg (V) | n | seq range |
|---:|---:|---|
| 0.0 | 19 | 243–267 (clusters) |
| −0.8 | 5 | 269–283 |
| −1.0 | 3 | 240, 273, plus one in cluster |
| −2.0 | 3 | 276, 278, 280 |
| +0.6 | 1 | within 243–267 |

For VVg (1 light-on row): seq 204 — Vg ramp −5 → +5 V at 455 nm / 6 µW.

> Full per-row inventory is available by reading the parquet directly:
> ```bash
> python3 -c "import polars as pl; pl.read_parquet('data/03_derived/chip_histories_enriched/Alisson81_history.parquet').filter(pl.col('has_light')).write_csv('Alisson81_light_on.csv')"
> ```

---

## 4. Patterns Identified

1. **Wavelength sweep was a one-shot survey, not a careful spectrum.** Each unique non-blue wavelength has n = 1 (no replicates), all on the same afternoon, 1 power, 1 gate. This is enough for qualitative responsivity peak hunting but **not** for publication-grade ΔI(λ) curves with error bars.

2. **455 nm is the chosen working wavelength** for the bulk of the campaign (90 % of light-on runs). Likely chosen because (a) it gave a clean photoresponse on Sept 25, and (b) it is a stable, easily tunable diode-laser line on the lab setup.

3. **6 µW is the standard intensity** (93 % of runs). Power-dependence is essentially measured at one operating point — only seq 41–43 deviate. **Linearity vs intensity is undertested.**

4. **Negative-gate dominance in measurements; positive-gate first-shot peak in physics.** The most-sampled It gates were −1.15, −1.5, −1.7, −0.7, −1.0 V. Naively the metrics suggest the photoresponse peaks at Vg ≈ +1 V (~+4 µA at 405 nm), but see point 9 below — that "peak" only exists on the first measurement after a sign-flipped priming bias.

9. **Photoresponse depends on measurement history, not just (Vg, λ, P).** The repeated It and Vt measurements at the same (Vg, λ, P) are *not* exchangeable replicates — they show monotonic decay with iteration (see § 5.4 and `figs/It/photoresponse/Alisson81_iteration_decay_It_and_Vt.png`). To get a strong response at Vg = +1 V, the operator first "primed" the chip by sitting at a negative Vg (which charges traps); switching to +Vg releases that charge as a transient photoresponse that fades over the next ~5–8 iterations (~15–25 minutes). The same applies symmetrically: the Oct 28 PM cluster at Vg = −1.15 V was dead until a single positive-gate excursion at seq 115 (Vg = +1.65 V) fully reset it to AM-cluster magnitude. This means the campaign's apparent "ΔI(Vg) curve" really mixes (gate, prior priming, iteration index) into one figure. Within-cluster decays at fixed gate are 5–35× over 20 minutes.

5. **Periodic light cycling, not pulsed.** All It traces use square-wave ON/OFF cycling: default `laser_period_s = 120 s` → 60 s OFF / 60 s ON / 60 s OFF (3 minutes total acquisition). Phase 3a uses 480 s (240 s OFF / 240 s ON / 240 s OFF, 12 minutes total) for slow-relaxation studies. seq 105 is a one-off at 720 s (likely the longest single relaxation curve in the campaign).

6. **Dark-bracketing protocol.** Almost every light-on It is bracketed by a dark IVg or VVg immediately before and after. This is the canonical setup for drift-corrected ΔI extraction (see `src/derived/extractors/photoresponse.py` if implemented; the dark-IVg flanking values let you subtract baseline drift and CNP shift).

7. **The campaign builds in scope.** Sept 25 = spectral. Oct 21 = power. Oct 23 → 28 = stability + Vg dependence at 455 nm. Oct 30 = light-on Vt and CNP-region It. The progression shows the experimenter narrowing in on **455 nm + Vg ≈ 0 V or near-CNP** as the regime of greatest interest.

8. **Limited Vt-under-light coverage.** Despite being the only systematic threshold-vs-light dataset, all 31 Vt-light runs were squeezed into one 6-hour evening (Oct 30, 16:53 – 22:53). Reproducibility of light-induced threshold shift over days is not in the dataset.

---

## 5. Photoresponse Metrics (full population)

After `biotite derive-all-metrics` + `biotite enrich-history 81`, every It light-on row carries a `delta_current` (raw I_on − I_off) and `delta_i_corrected` value (drift-corrected: stretched-exponential fit on t ∈ [20, 60] s subtracted; ΔI = I_corr(120 s) − I_corr(60 s)). Numbers below are quoted from those columns directly, not from the manual spot-check.

The corresponding plots are saved under `figs/It/photoresponse/`:

| Phase | Figure |
|---|---|
| 1 wavelength sweep (chip 81 vs chip 72) | `figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength.png` |
| 2 power sweep | `figs/It/photoresponse/Alisson81_corrected_deltai_vs_power_455nm_Vgneg0p3V.png` |
| 3b gate sweep | `figs/It/photoresponse/Alisson81_corrected_deltai_vs_Vg_455nm_6uW.png` |

(The Phase 1 plot was generated by `scripts/compare_photoresponse_72_81.py` for the cross-chip comparison; it covers exactly the chip-81 wavelength-sweep seqs 4, 6, 8, 10, 12, 14, 16, 18, 33, 35.)

### 5.1 ΔI(λ) at Vg = −1.0 V, P = 6 µW (Phase 1)

| seq | λ (nm) | hν (eV) | ΔI raw (nA) | ΔI corrected (nA) |
|---:|---:|---:|---:|---:|
| 35 | 365 | 3.40 | +57 | +54 |
| **33** | **385** | **3.22** | **+1397** | **+1378** |
| 18 | 405 | 3.06 | +643 | +644 |
| 16 | 455 | 2.72 | +281 | +294 |
| 14 | 505 | 2.45 | −45 | −37 |
| 12 | 565 | 2.19 | −2 | +8 |
| 10 | 590 | 2.10 | −1 | +3 |
| 8 | 625 | 1.98 | −10 | −5 |
| 6 | 680 | 1.82 | −17 | −8 |
| 4 | 850 | 1.46 | −20 | −7 |

**Reading:** the corrected and raw values agree to a few percent, which validates the drift model on these 120-s-period traces. The peak photoresponse sits at **385 nm (+1.38 µA = +8 %)**, *not* at 405 nm — my initial spot-check missed seq 33 and so understated the true peak by ~2×. Above 505 nm the response is at the noise floor (|ΔI| ≤ 50 nA on a ~16 µA baseline, ≈ 0.3 %). The qualitative picture: **strong UV-A response (385 / 405 nm), moderate blue (455 nm), nothing at green/red/IR.**

### 5.2 ΔI(Vg) at 405 nm, P = 6 µW (embedded Phase 1 sub-sweep, seq 18–23)

| seq | Vg (V) | ΔI raw (nA) | ΔI corrected (nA) |
|---:|---:|---:|---:|
| 21 | −3.0 | +333 | +334 |
| 20 | −1.5 | +1530 | +1670 |
| 18 | −1.0 | +643 | +644 |
| **19** | **+1.0** | **+3859** | **+3915** |
| **22** | **+1.0 (repeat)** | **+4039** | **+4090** |
| 23 | +2.0 | +295 | +306 |

**Reading:** at λ = 405 nm the photoresponse has a **clear peak near Vg ≈ +1.0 V (≈ +4.0 µA)**, with the two replicates agreeing within 4 % — this is the strongest, best-replicated photoresponse anywhere in the dataset. The non-monotonic |ΔI(Vg)| with deep dips at the extreme gates (±2 / 3 V) is consistent with photoresponse magnitude tracking |gₘ| (the transconductance), which itself peaks around the CNP and falls off in the saturation regions.

### 5.3 ΔI(P) at 455 nm, Vg = −0.3 V (Phase 2)

See `figs/It/photoresponse/Alisson81_corrected_deltai_vs_power_455nm_Vgneg0p3V.png`.

| seq | P (µW) | ΔI raw (nA) | ΔI corrected (nA) | |ΔI| / P (nA / µW) |
|---:|---:|---:|---:|---:|
| 40 | 5.97 | −679 | −685 | 114.7 |
| 41 | 11.98 | −565 | −570 | 47.6 |
| 42 | 18.02 | −425 | −431 | 23.9 |
| 43 | 24.01 | −350 | −358 | 14.9 |

**Reading:** the photoresponse is **negative at this gate** and **strongly sublinear in P** — the responsivity |ΔI| / P collapses almost 8× from 6 µW to 24 µW. This is well outside what could be explained by baseline drift alone (which was ~10 % between seq 40 and 43). The most likely explanations are (a) photothermal heating dominating at higher intensities and partially cancelling the photoelectric response, or (b) a saturation of the optically-induced charge density. Either way, **6 µW is on the linear side of saturation; 24 µW is not.**

### 5.4 ΔI(Vg) at 455 nm, P = 6 µW, period = 120 s (Phase 3b/3c)

> ⚠ **Replicates are not exchangeable.** Per-chip-operator note: repeated It at fixed (λ, P, Vg) shows monotonic |ΔI| decay with iteration (see § 5.4b and the iteration-decay figure). The mean values below average a decaying time series and therefore *underestimate* the first-iteration response and overestimate the steady-state response — they should be read as a cluster-mean reference, not a steady-state ΔI(Vg) curve.

74 light-on It traces span Vg ∈ [−1.7, +1.65 V]. See `figs/It/photoresponse/Alisson81_corrected_deltai_vs_Vg_455nm_6uW.png`. Per-Vg means (replicates averaged):

| Vg (V) | n | mean ΔI corrected (µA) | s.d. (µA) |
|---:|---:|---:|---:|
| −1.70 | 8 | +0.254 | 0.274 |
| −1.50 | 8 | +0.198 | 0.192 |
| −1.15 | 13 | +0.188 | 0.167 |
| −1.00 | 2 | +0.372 | 0.110 |
| −0.70 | 6 | +0.094 | 0.067 |
| −0.50 | 3 | +0.072 | 0.059 |
| **−0.30** | **1** | **−0.685** | **—** |
| **+0.00** | **26** | **−0.038** | **0.067** |
| +0.10 | 1 | +0.011 | — |
| +0.67 | 1 | +2.04 | — |
| +1.20 | 2 | +1.72 | 1.68 |
| +1.30 | 1 | +3.25 | — |
| +1.50 | 1 | +3.25 | — |
| +1.65 | 1 | +3.21 | — |

**Reading:** the full population confirms the picture from the spot-check and sharpens it:

- **Zero-crossing at Vg ≈ 0 V** (mean ΔI = −0.038 µA over n = 26 — within noise of zero). This is the photoresponse equivalent of a CNP and matches the dark-IVg CNP statistics in § 5.5.
- **Vg < 0 V regime: small positive response** (+0.07 to +0.37 µA). The −0.3 V point sticks out as the only negative ΔI on this side, but it is also the only point in the dataset *not* taken on Oct 28/30 — it comes from the Phase 2 power sweep (Oct 21), so the apparent sign flip is plausibly a different-day baseline effect rather than a real Vg dependence.
- **Vg > 0 V regime: large positive response, saturating at ~+3.25 µA above Vg = +1.3 V.** The single +1.3 / +1.5 / +1.65 V points coincide to within 1 %, suggesting saturation kicks in between +0.67 V (+2.04 µA) and +1.30 V.
- **Asymmetric "photoresponse" at face value:** |ΔI(+1.3 V)| / |ΔI(−1.7 V)| ≈ 13 — but the +1.3 / +1.5 / +1.65 V points are each n = 1 *first-shot* measurements taken right after a sequence of negative-gate priming runs, while the negative-Vg points are means of decayed clusters. The factor of 13 therefore mixes the iteration-decay effect into the apparent gate dependence and **cannot be read as a true steady-state asymmetry.** The Phase 1b 405 nm Vg sub-sweep (§ 5.2) has the same caveat: the Vg = +1 V points (seq 19, 22) immediately followed Vg = −1.0 V (seq 18) and Vg = −3.0 V (seq 21) primings, respectively.

### 5.4b Iteration decay at fixed (Vg, λ, P)

The single clearest pattern in the entire campaign — see `figs/It/photoresponse/Alisson81_iteration_decay_It_and_Vt.png`. Within a tight-time cluster at fixed (λ = 455 nm, P = 6 µW, Vg, period = 120 s), |ΔI_corrected| decays monotonically with iteration:

| cluster | n | first-iter ΔI (µA) | last-iter ΔI (µA) | ratio |
|---|---:|---:|---:|---:|
| Vg = −1.7 V (Oct 28, 17:00 → 17:24) | 8 | +0.823 | +0.024 | 35× |
| Vg = −1.5 V (Oct 28, 19:04 → 19:26) | 8 | +0.586 | +0.030 | 20× |
| Vg = −1.15 V AM (Oct 28, 06:49 → 07:08) | 5 | +0.463 | +0.108 | 4× |
| Vg = −1.15 V PM (Oct 28, after Vg = +1.65 V prime) | 6 | +0.465 | +0.063 | 7× |
| Vg = 0 V (Oct 30, 01:45 → 02:29) | 8 | −0.151 | +0.009 | 17× |

The two Vg = −1.15 V curves overlap almost perfectly: after the AM cluster decayed to ~0.06 µA, the chip sat for 8 hours and sat at 15:40–15:50 with essentially zero photoresponse (seq 112, 114) — until a single positive-gate measurement at seq 115 (Vg = +1.65 V) re-armed the trap state, after which seq 117 onwards reproduces the AM-cluster decay quantitatively. **A sign-flipped priming bias resets the photoresponse.**

The Vt-under-light cluster at Vg = 0 V (n = 22, Oct 30 PM) shows the same iteration decay in `delta_voltage`: 0.19 → 0.08 → 0.05 → −0.005 mV in the first four iterations, then noise around zero. So the § 5.6 "null result" was actually a decayed result — the *first* Vt-light measurement at any new condition does carry signal; subsequent ones don't until the chip is re-primed.

**Practical implication:** any ΔI(Vg), ΔI(λ), or ΔI(P) extraction from this dataset must either (a) restrict to the first measurement at each new condition, or (b) explicitly model the iteration index as a covariate. Per-Vg means as in § 5.4 are biased low for the negative-Vg points (where many decayed iterations are averaged) and biased to the first-shot for the positive-Vg points (where typically n = 1).

### 5.5 CNP from dark IVgs

64 dark IVg sweeps, all in `cnp_voltage`:

| stat | value (V) |
|---|---:|
| mean | +0.033 |
| s.d. | 0.277 |
| min | −0.450 |
| max | +0.725 |

The CNP wanders by ~1 V across the campaign — typical of a chip with mobile-charge or trapped-charge memory effects between sweeps. The mean (+0.03 V) is essentially zero, consistent with the photoresponse zero-crossing in § 5.4.

### 5.6 Light-induced threshold shift (Vt under light)

31 Vt-under-light measurements at λ = 455 nm, P = 6 µW. The `delta_voltage` metric (light − dark threshold shift) has mean = **−0.45 mV** across the full population. The first-iteration value of the Vg = 0 V cluster (seq 243) is **+0.19 mV**, decaying to noise within 3–4 iterations (§ 5.4b). So the proper read is **a small but measurable first-shot ΔVt of ~0.2 mV at Vg = 0 V**, not a true null — the population mean is dragged toward zero by the same iteration-decay that affects ΔI. A clean ΔVt(Vg) study would need one fresh measurement per gate plus a re-prime in between.

### 5.7 Caveat: the stability series is dominated by drift

The 13 traces in Phase 3a (Vg = −0.7 V, 480 s period) have raw `delta_current` in [−0.81, −0.30 µA] but `delta_i_corrected` essentially in noise (|ΔI_corr| < 15 nA in every case). The stretched-exponential fit window (t ∈ [20, 60] s) is too short relative to the 480 s laser period for these traces — the fit is absorbing the photoresponse itself into the "drift" model. **Do not interpret the corrected ΔI for stability-series traces.** The raw `delta_current` shows a clear monotonic trend (more negative over 5 days, drifting from −0.31 µA on Oct 23 to −0.81 µA on Oct 28 at the higher 12 µW power), but disentangling that from the calibration-induced power doubling at seq 75 needs a custom analysis with a fit window matched to the longer cycle.

---

## 6. Existing Artifacts

Pre-existing (under `figs/Alisson81/It/Light_It/`, generated by `biotite plot-its`):

1. `Alisson81_It_seq_4_6_8_plus7_7e5ae1_alisson81_same_pwr_wl_sweep.png` — overlay of Sept 25 wavelength sweep It traces.
2. `Alisson81_It_sequential_seq_4_6_8_plus7_7e5ae1_alisson81_same_pwr_wl_sweep_seq.png` — sequential/temporal layout of the same data.
3. `alisson81_ITS_photoresponse_vs_wavelength_seq_4_6_8_plus7_7e5ae1_alisson81_same_pwr_wl_sweep_photoresponse.png` — first-pass |ΔI| vs wavelength.

Generated for this report (under `figs/It/photoresponse/`):

4. `Alisson81_corrected_deltai_vs_power_455nm_Vgneg0p3V.png` — Phase 2 power sweep, signed ΔI_corrected vs P (4 points, 6–24 µW).
5. `Alisson81_corrected_deltai_vs_Vg_455nm_6uW.png` — Phase 3b/3c gate sweep, ΔI_corrected vs Vg (74 traces, 14 distinct gates) with replicate scatter and per-Vg mean ± s.d. **Read with the § 5.4b iteration-decay caveat.**
6. `Alisson81_iteration_decay_It_and_Vt.png` — top: ΔI_corrected vs iteration index for five (Vg, time) clusters at fixed λ = 455 nm, P = 6 µW; bottom: ΔV_t vs iteration for the Oct 30 Vg = 0 V Vt cluster. Demonstrates the history-dependence of the photoresponse.

Cross-chip comparison covering Phase 1 (also generated by `scripts/compare_photoresponse_72_81.py`):

6. `figs/compare/alisson72_vs_81_ITS_photoresponse_vs_wavelength.png` (and `_semilogy.png`) — Alisson81 (biotite) vs Alisson72 (hBN) wavelength sweeps.

**Metrics now populated:** `data/03_derived/_metrics/metrics.parquet` holds 1,341 rows (384 for chip 81): `delta_current` (105), `delta_i_corrected` (158), `cnp_voltage` (90), `delta_voltage` (31).

**Not yet plotted:** Phase 1 405 nm Vg sub-sweep (§ 5.2 — n = 6 points, easy to add), Phase 3a stability with a corrected fit window matched to the 480 s laser period (§ 5.7 caveat), Vt-under-light ΔVt vs Vg (§ 5.6 — null result, low priority).

---

## 7. Suggested Follow-ups

1. ~~**Run the metric extractor**~~ — **done** (2026-05-04). `metrics.parquet` now holds 384 rows for chip 81; § 5 quotes them.

2. ~~**Plot the missing phases**~~ — partially done:
   - ✅ ΔI vs power at 455 nm, Vg = −0.3 V — `scripts/plot_corrected_deltai_vs_power_alisson81.py` → `figs/It/photoresponse/Alisson81_corrected_deltai_vs_power_455nm_Vgneg0p3V.png`.
   - ✅ ΔI vs Vg at 455 nm, P = 6 µW — `scripts/plot_corrected_deltai_vs_vg_alisson81.py` → `figs/It/photoresponse/Alisson81_corrected_deltai_vs_Vg_455nm_6uW.png`.
   - ⏳ Vt vs Vg under light — null result (§ 5.6), low-priority.
   - ⏳ ΔI(Vg) at 405 nm — n = 6 points already in `delta_i_corrected` (§ 5.2); a one-line script away.
   - ⏳ Phase 3a stability with a 480-s-matched fit window (§ 5.7 caveat).

3. **Add Alisson81 metadata to `config/chip_params.yaml`** — material, encapsulation type, fabrication date, channel geometry. Currently absent, which limits the report's contextual interpretation.

4. **Replicate the wavelength sweep at the optimal gate.** § 5.1 + § 5.2 together identify the chip's strongest photoresponse at **λ = 405 nm, Vg ≈ +1 V (≈ +4 µA)** rather than the Sept 25 working point of Vg = −1 V. A second spectral sweep at Vg = +1 V — and a finer wavelength grid around 385–405 nm where the chip is clearly absorbing — would anchor the publishable ΔI(λ) curve.

5. **Investigate Vg ≈ +1 V saturation in detail.** § 5.4 shows the ΔI(Vg) curve at 455 nm saturating at ~+3.25 µA above Vg = +1.3 V (n = 1 each at +1.30 / +1.50 / +1.65 V). Replicate at Vg ∈ {1.0, 1.1, 1.2, 1.3, 1.4 V} with several runs each to characterise the saturation onset and confirm reproducibility.

6. **Re-examine the Phase 2 power sweep with a fixed baseline.** § 5.3's strong sublinearity is hard to disentangle from the ~10 % I₀ drift between seq 40 and seq 43. A repeat at Vg = −0.3 V or another comparable gate, with dark-IVgs immediately bracketing each power point, would test whether the saturation is real or a drift artefact.

7. **Don't trust the corrected ΔI for the 480 s stability series.** § 5.7 — the raw `delta_current` is the right column to use there, or rerun the corrector with `FIT_T_END = 240 s` for those rows.

8. **Characterize the trap-state recovery time.** The history-dependence in § 5.4b is the most important physics in the dataset and is currently unmodelled. Concrete next experiments:
   - At fixed Vg = +1 V, measure ΔI(t_wait) where t_wait is the dwell at a chosen priming bias (e.g. Vg = −1 V) before the It run — gives the trap (de)charging time constant.
   - Replace the current "do many It at the same gate" protocol with "one It → re-prime at opposite gate → one It → ..." to keep every measurement first-shot.
   - Add a derived metric `iteration_index_within_cluster` to the manifest so analyses can filter to first-shot only without manual seq-list bookkeeping.

9. **Add an `iteration_index` column to enriched history.** The user's observation that replicates decay is a per-chip property worth encoding once, in the staging/enrichment pipeline, rather than re-discovering per-script. A simple definition: for each (chip, proc, vg_fixed_v, wavelength_nm, irradiated_power_w, has_light) group, the iteration index resets when the time gap to the previous measurement in the group exceeds a threshold (say 30 minutes) or when an opposite-sign Vg measurement intervenes.

---

## Appendix — Verification Queries

```python
import polars as pl
df = pl.read_parquet('data/03_derived/chip_histories_enriched/Alisson81_history.parquet')
assert len(df) == 284
assert df.filter(pl.col('has_light')).height == 137
assert df.filter(pl.col('has_light') & (pl.col('proc') == 'It')).height == 105
assert df.filter(pl.col('has_light') & (pl.col('proc') == 'Vt')).height == 31
assert df.filter(pl.col('has_light') & (pl.col('proc') == 'VVg')).height == 1
wl_light = df.filter(pl.col('has_light'))['wavelength_nm'].drop_nulls().unique().sort().to_list()
assert wl_light == [365.0, 385.0, 405.0, 455.0, 505.0, 565.0, 590.0, 625.0, 680.0, 850.0]
```
