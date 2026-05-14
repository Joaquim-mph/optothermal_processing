# ITS Rise/Fall Time Extractor — Design

**Date:** 2026-05-14
**Status:** Approved (design) — revised 2026-05-14 to baseline-span referencing

## Goal

Add a metric extractor that computes the **rise time** (`t_rise`) and **fall time**
(`t_fall`) of light `It` measurements using a model-free 10%–90% rule, applied to the
OFF → ON → OFF (pre-dark → light → post-dark) cycle that every light `It` trace contains.

This is distinct from the existing `ITSRelaxationExtractor` and
`ITSThreePhaseFitExtractor`, which fit stretched exponentials. The new extractor is
purely geometric: no fitting, just threshold crossings.

## Revision note — why baseline-span referencing

The original design referenced the 10/90 levels to `0 → I_max` (percentages of the
illuminated-phase maximum, implicit zero baseline). Testing against real Alisson74
365 nm `It` data showed this is degenerate: the dark current is large (~30–50 µA) and
the photoresponse is a small modulation on top, often **negative** (current drops
under illumination). With a zero reference, `10% of I_max` sits far below the entire
signal range and `90%` is grazed at the first sample — every rise collapsed to 0 s and
every fall returned `None`. A sign flip alone does not fix this; the non-zero baseline
breaks the rule for either sign.

The fix: reference the 10/90 levels to the **span between the dark baseline and the
in-phase extremum**, where the extremum is chosen as the point of largest deviation
from the baseline. This is the standard 10–90 step-response convention and handles
positive and negative photoresponse with no special-casing.

## Phase detection

The illuminated phase is the single LED-ON segment, detected via `VL (V) > 0.1`.
Confirmed from staged data: every light `It` file has exactly one LED-ON segment
(~33% on-fraction), structured as pre-dark → light → post-dark. Dark `It` files have
no LED-ON segment.

- **Rise** operates on the **illuminated phase** `[light_start, light_end)`.
- **Fall** operates on the **relaxation phase** (post-dark) `[light_end, end)`.

## Reference levels

**Baseline (tail mean).** A phase's baseline is the mean of its last `baseline_frac`
(default 0.2) of samples — robust to noise and, under drift, representative of the
level right at the phase transition.

- `pre_baseline` = tail mean of the pre-dark phase `[0, light_start)`.
- `post_baseline` = tail mean of the post-dark phase `[light_end, end)`.

**Illuminated extremum.** `illum_extremum` = the sample in the illuminated phase with
the largest **absolute deviation from `pre_baseline`** (the min for a negative
photoresponse, the max for a positive one). `illum_extremum_idx` is its absolute index.

**Photoresponse magnitude.** `rise_span = |illum_extremum − pre_baseline|`. If
`rise_span == 0` (perfectly flat illuminated phase), the extractor returns `None` for
both modes — there is no transition to measure.

## The 10–90 rule — single section (common case)

A transition is defined by two **reference levels**, `ref_start` and `ref_end`. The
10% and 90% levels are:
```
level_10 = ref_start + low_frac  * (ref_end − ref_start)
level_90 = ref_start + high_frac * (ref_end − ref_start)
```
The response time is the absolute time between the first sample crossing `level_10`
and the first sample crossing `level_90`, searched within the working phase:
```
response_time = abs( t[first sample crossing level_90] − t[first sample crossing level_10] )
```
"Crossing level `L`" means the first sample on the far side of `L` from `ref_start`
(`I >= L` if `ref_end >= ref_start`, else `I <= L`). First-crossing samples, no
interpolation. The `abs` makes it direction-agnostic and always `>= 0` (the
`ref_end`-side sample satisfies both thresholds, so the two crossing indices are
ordered). The "first reaching" rule (rather than first/last point of the filtered
10–90 set) handles noisy traces that re-enter the 10–90 window after the transition.

**Rise**, searched within the illuminated phase:
- `ref_start = pre_baseline`, `ref_end = illum_extremum`.

**Fall**, searched within the relaxation phase:
- `ref_start = illum_extremum`, `ref_end = post_baseline`.
- The fall is the mirror of the rise: it measures relaxation from the peak
  photo-response back to the recovered dark level. `rise.ref_end == fall.ref_start`.
- **Negligible-recovery guard:** `recovery_span = |post_baseline − illum_extremum|`.
  If `recovery_span < min_recovery_frac * rise_span` (default `min_recovery_frac` =
  0.1), the trace barely relaxed — there is no meaningful fall time, and the extractor
  returns `None`.

## The 10–90 rule — two sections (sign-switch case)

In some experiments the photocurrent **switches sign during a single illumination (or
relaxation) period**. This is captured with two response times. When a sustained
derivative reversal is detected, the phase is divided into two sections at its
**first peak**:

- **Section 0:** phase start → first peak. `ref_start` = the phase's external entry
  reference (`pre_baseline` for rise, `illum_extremum` for fall); `ref_end` = the
  current value at the first peak.
- **Section 1:** first peak → phase end. `ref_start` = the current value at the first
  peak; `ref_end` = section 1's own extremum (the directional extremum within
  section 1 — the min if the phase initially rose, the max if it initially fell).

Each section's response time uses the same `level_10`/`level_90` formula above with
its own `ref_start`/`ref_end`.

### First-peak detection — smoothed-derivative reversal

1. Smooth the phase's `I` with a moving average of width `smooth_window`.
2. Compute the discrete derivative of the smoothed signal.
3. Determine the initial direction `s0` (sign of the smoothed signal's net change over
   the first few samples).
4. Find the first index where the derivative sign flips to `-s0` **and stays `-s0`
   for at least `min_reversal_run` consecutive samples** — a sustained reversal, not a
   noise wiggle.
5. If found: the **first peak** is the extremum of the smoothed signal between the
   phase start and that reversal. Split there. If not found: no sign switch, single
   section.

## Architecture

One parameterized extractor class, registered twice — matching the existing
`CNPExtractor(direction=...)` / `MobilityExtractor(branch=..., direction=...)` pattern.
`MetricExtractor.extract()` returns a single `Optional[DerivedMetric]`. `mode="rise"`
analyses the illuminated phase; `mode="fall"` analyses the relaxation phase. Sign-switch
detection is independent per phase, so a measurement may have a split rise but an
unsplit fall, or vice versa.

### File: `src/derived/extractors/its_rise_fall_extractor.py`

Class `ITSRiseFallExtractor(MetricExtractor)`.

**Constructor:**
- `mode: str` — `"rise"` or `"fall"` (raises `ValueError` otherwise)
- `vl_threshold: float = 0.1` — LED-ON detection threshold
- `low_frac: float = 0.1` — lower threshold fraction of the span
- `high_frac: float = 0.9` — upper threshold fraction of the span
- `baseline_frac: float = 0.2` — tail fraction of a phase used for its baseline
- `min_recovery_frac: float = 0.1` — fall returns `None` if the post-dark recovery
  span is below this fraction of the rise span
- `smooth_window: int = 5` — moving-average width for first-peak detection
- `min_reversal_run: int = 15` — consecutive reversed-derivative samples that
  qualify as a sustained sign switch
- `min_points_per_phase: int = 10` — sanity floor on phase length

**Properties:**
- `applicable_procedures` → `["It"]`
- `metric_name` → `"t_rise"` if `mode == "rise"` else `"t_fall"`
- `metric_category` → `"photoresponse"`

**Private helpers:**
- `_find_led_segment(vl)` → `(start, end)` of the longest LED-ON run, or `None`.
- `_phase_baseline(i, start, end)` → tail mean of `i[start:end]` over the last
  `baseline_frac`.
- `_extremum_idx(i, start, end, baseline)` → absolute index of max `|i − baseline|`
  in `[start, end)`.
- `_crossing_index(values, level, going_up)` → first index reaching `level`, or `None`.
- `_response_time(t, i, search_start, search_end, ref_start, ref_end)` → details dict,
  or `None` if either crossing is missing.
- `_find_first_peak(signal)` → `(peak_index, s0)` or `None`.

**`extract(measurement, metadata)` logic:**
1. Require columns `t (s)`, `I (A)`, `VL (V)`; return `None` if any missing.
2. Find the LED-ON segment. No segment → dark measurement → `None`.
3. `light_start == 0` (no pre-dark phase) → `None`. Compute `pre_baseline`.
4. Compute `illum_extremum` / `illum_extremum_idx` and `rise_span`. `rise_span == 0`
   → `None`.
5. Select the working phase and its `ref_start`/`ref_end`:
   - rise: phase = illuminated, `ref_start = pre_baseline`, `ref_end = illum_extremum`.
   - fall: phase = relaxation. `light_end >= len(t)` (no post-dark) → `None`. Compute
     `post_baseline`; apply the negligible-recovery guard. `ref_start = illum_extremum`,
     `ref_end = post_baseline`.
6. Phase shorter than `min_points_per_phase` → `None`.
7. Run `_find_first_peak` on the working phase. `None` → single section; otherwise
   two sections (see above).
8. Single section: `_response_time` over the whole phase with the phase
   `ref_start`/`ref_end`. `None` → return `None`.
9. Two sections: section 0 via `_response_time` (`None` → return `None`); section 1
   referenced to its own extremum (`None` → `SECTION1_INCOMPLETE` flag, section 0 only).
10. Build and return a `DerivedMetric`.

**`DerivedMetric` fields:**
- `value_float` — section-0 response time, in seconds
- `unit` — `"s"`
- `extraction_method` — `"ten_ninety_rise"` / `"ten_ninety_fall"`
- `value_json` — `{mode, n_sections, sign_switch, pre_baseline, illum_extremum,
  illum_extremum_idx, rise_span, post_baseline (fall only), low_frac, high_frac,
  baseline_frac, min_recovery_frac, smooth_window, min_reversal_run, phase_start_t,
  phase_end_t, boundary_idx (if split), sections: [ {section, response_time,
  ref_start, ref_end, level_10, level_90, idx_10, idx_90, t_10, t_90,
  section_start_idx, section_end_idx} , ... ]}`
- `confidence`, `flags` — see below

**Confidence / flags:**
- `SIGN_SWITCH` — two sections were detected (`n_sections == 2` after detection).
- `RISE_ONSET_CLAMPED` (confidence ×0.7) — rise, section 0: the current is already
  past `level_10` at the first illuminated sample, so the rise window is truncated.
- `FALL_ONSET_CLAMPED` (confidence ×0.7) — fall, section 0: the current is already
  past `level_90` at the first relaxation sample.
- `SECTION1_INCOMPLETE` — a sign switch was detected but section 1's 10/90 crossings
  could not both be found; only section 0 is reported.
- Otherwise confidence `1.0`.

**`validate(result)`:** `value_float` is not `None`, finite, and `>= 0`; every section's
`response_time` in `value_json` is finite and `>= 0`.

### Registration

- `src/derived/metric_pipeline.py` — `_default_extractors()` registers
  `ITSRiseFallExtractor(mode="rise")` and `ITSRiseFallExtractor(mode="fall")`.
- `src/derived/extractors/__init__.py` — imports and exports the class.

## Testing

`tests/derived/test_its_rise_fall_extractor.py`:
- Helper unit tests: `_find_led_segment`, `_phase_baseline`, `_extremum_idx`,
  `_crossing_index`, `_response_time`, `_find_first_peak`.
- End-to-end on synthetic OFF → ON → OFF traces with flat-tail phases (so baselines
  are exact):
  - Monotonic positive rise / fall with a non-zero dark baseline — analytically known
    times.
  - **Negative photoresponse** (current drops under light, recovers after) — confirms
    sign is handled with no special-casing.
  - Dark `It` measurement (no LED-ON segment) → `None`.
  - Flat illuminated phase (`rise_span == 0`) → `None`.
  - Negligible recovery (post-dark barely relaxes) → fall returns `None`; rise still
    succeeds.
  - Non-monotonic trace that re-enters the 10–90 window after the transition but does
    not sustain a reversal → still one section, correct time.
  - Sign-switch illumination → two-section rise, `SIGN_SWITCH` flag.
  - Sign-switch relaxation → two-section fall.
  - Missing-column DataFrame → `None`.
  - `RISE_ONSET_CLAMPED` / `FALL_ONSET_CLAMPED` flags.
- Registration: exported from the package and present in `_default_extractors()`.

## Out of scope

- Stretched-exponential or any model fitting (covered by existing extractors).
- Multi-cycle `It` traces (data confirmed single-cycle: one OFF → ON → OFF per file).
- Linear interpolation between samples (definition is explicitly "first data point
  reaching" a threshold).
- More than two sections per phase (the sign-switch model is explicitly two sections).
- Drift correction of the `It` trace before extraction — the extractor works on the
  raw staged current; baseline referencing absorbs a constant offset but not curvature.
