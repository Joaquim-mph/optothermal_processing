# ITS Rise/Fall Time Extractor — Design

**Date:** 2026-05-14
**Status:** Approved (design)

## Goal

Add a metric extractor that computes the **rise time** (`t_rise`) and **fall time**
(`t_fall`) of light `It` measurements using a model-free 10%–90% rule, applied to the
OFF → ON → OFF (pre-dark → light → post-dark) cycle that every light `It` trace contains.

This is distinct from the existing `ITSRelaxationExtractor` and
`ITSThreePhaseFitExtractor`, which fit stretched exponentials. The new extractor is
purely geometric: no fitting, just threshold crossings.

## Phase detection

The illuminated phase is the single LED-ON segment, detected via `VL (V) > 0.1`.
Confirmed from staged data: every light `It` file has exactly one LED-ON segment
(~33% on-fraction), structured as pre-dark → light → post-dark. Dark `It` files have
no LED-ON segment.

- **Rise** operates on the **illuminated phase** `[light_start, light_end)`.
- **Fall** operates on the **relaxation phase** (post-dark) `[light_end, end)`.

## The 10–90 rule — single section (common case)

`I_max` = maximum `I (A)` over the illuminated phase. The reference span is `0 → I_max`
(percentages of `I_max` itself, **not** of the span above a dark baseline). No
first-point skipping. First-crossing samples, no interpolation between samples.

**Rise**, within the illuminated phase:
```
t_rise = t(first sample with I >= 0.9 * I_max) - t(first sample with I >= 0.1 * I_max)
```
Guaranteed `>= 0`: the `I_max` sample itself satisfies both thresholds, so the
first-`>=10%` index is `<=` the first-`>=90%` index. The "first reaching" rule (rather
than first/last point of the filtered 10–90 set) handles noisy traces that re-enter
the 10–90 window after peaking.

**Fall**, within the relaxation phase, reference still `I_max`:
```
t_fall = t(first sample with I <= 0.1 * I_max) - t(first sample with I <= 0.9 * I_max)
```
Guaranteed `>= 0` by the same argument. If the current never decays to `0.1 * I_max`
(incomplete recovery / persistent photoconductivity), `t_fall` is undefined and the
extractor returns `None` (debug log, reason `INCOMPLETE_DECAY`).

## The 10–90 rule — two sections (sign-switch case)

In some experiments the photocurrent **switches sign during a single illumination (or
relaxation) period**. This is captured with two response times. When a sign switch is
detected, the phase is divided into two sections at its **first peak**:

- **Section 0:** phase start → first peak
- **Section 1:** first peak → phase end

The 10–90 rule is then applied **independently to each section**, using **that
section's own bounding extremum** as the 100% reference and `0` as the 0% reference
(same rule as the single-section case, just scoped to the section). Section 1 works
because it crosses zero on its way to a peak of the opposite sign, so it genuinely
reaches 10% and 90% of that section's peak.

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

### Unified per-section response time

Each section has a **reference extremum** `E` (the bounding peak that defines it; for
the single-section rise `E = I_max`). The section's response time is:
```
response_time = abs( t[first sample crossing 0.9 * E] - t[first sample crossing 0.1 * E] )
```
"Crossing level `L`" means the first sample on the far side of `L` from the section's
starting value (`I >= L` if the section moves up toward `E`, `I <= L` if it moves
down). The `abs` makes it direction-agnostic and always `>= 0`. This unified form
covers single-section rise and all split sections (rise and fall).

**The single-section fall is the one documented exception:** its reference (`I_max`)
is the value the current starts at and decays *away* from, not a peak it moves toward,
so it uses the explicit `t_fall = t_10 - t_90` form from the section above. Split-fall
sections are *not* exceptions — each moves toward its own relaxation peak and uses the
unified rule.

## Architecture

One parameterized extractor class, registered twice — matching the existing
`CNPExtractor(direction=...)` / `MobilityExtractor(branch=..., direction=...)` pattern.
`MetricExtractor.extract()` returns a single `Optional[DerivedMetric]`. `mode="rise"`
analyses the illuminated phase; `mode="fall"` analyses the relaxation phase. Sign-switch
detection is independent per phase, so a measurement may have a split rise but an
unsplit fall, or vice versa.

### New file: `src/derived/extractors/its_rise_fall_extractor.py`

Class `ITSRiseFallExtractor(MetricExtractor)`.

**Constructor:**
- `mode: str` — `"rise"` or `"fall"` (raises `ValueError` otherwise)
- `vl_threshold: float = 0.1` — LED-ON detection threshold
- `low_frac: float = 0.1` — lower threshold fraction
- `high_frac: float = 0.9` — upper threshold fraction
- `smooth_window: int = 5` — moving-average width for first-peak detection
- `min_reversal_run: int = 15` — consecutive reversed-derivative samples that
  qualify as a sustained sign switch
- `min_points_per_phase: int = 10` — sanity floor on phase length

**Properties:**
- `applicable_procedures` → `["It"]`
- `metric_name` → `"t_rise"` if `mode == "rise"` else `"t_fall"`
- `metric_category` → `"photoresponse"`

**`extract(measurement, metadata)` logic:**
1. Require columns `t (s)`, `I (A)`, `VL (V)`; return `None` if any missing.
2. `led_on = VL > vl_threshold`. Find the LED-ON segment (longest contiguous run,
   expected to be exactly one). No ON segment → dark measurement → return `None`.
3. Select the working phase: illuminated phase for `rise`, relaxation phase for `fall`.
   Require `>= min_points_per_phase` samples; else `None`.
4. `I_max` = max `I` over the illuminated phase (needed for the single-section fall
   reference and for clamp flags).
5. Run smoothed-derivative reversal detection on the working phase.
6. If a sustained reversal is found → two sections; else → one section.
7. For each section, compute its reference extremum `E` and its `response_time` via
   the unified per-section rule. Single-section fall uses the explicit `I_max`-based
   form instead.
8. If any required crossing is missing for section 0 → return `None` (`INCOMPLETE_DECAY`
   for fall). If section 1 is detected but its crossings are incomplete, drop section 1
   and set flag `SECTION1_INCOMPLETE`.
9. Build and return a `DerivedMetric`.

**`DerivedMetric` fields:**
- `value_float` — section-0 response time, in seconds
- `unit` — `"s"`
- `extraction_method` — `"ten_ninety_rise"` / `"ten_ninety_fall"`
- `value_json` — `{mode, n_sections, sign_switch, I_max, smooth_window,
  min_reversal_run, low_frac, high_frac, phase_start_t, phase_end_t,
  boundary_idx (if split), sections: [ {section, response_time, extremum,
  extremum_idx, extremum_t, level_10, level_90, idx_10, idx_90, t_10, t_90,
  section_start_idx, section_end_idx} , ... ]}`
- `confidence`, `flags` — see below

**Confidence / flags:**
- `SIGN_SWITCH` — two sections were detected (`n_sections == 2`).
- `RISE_ONSET_CLAMPED` (confidence ×0.7) — rise, section 0: the current is already
  `>= 10% * E` at the first sample, so the rise window is truncated.
- `FALL_ONSET_CLAMPED` (confidence ×0.7) — single-section fall: current already
  `<= 90% * I_max` at the first relaxation sample.
- `SECTION1_INCOMPLETE` — a sign switch was detected but section 1's 10/90 crossings
  could not both be found; only section 0 is reported.
- `NEGATIVE_I_MAX` (confidence ×0.5) — `I_max <= 0`; the "maximum bias current" sign
  assumption is broken.
- Otherwise confidence `1.0`.

**`validate(result)`:** `value_float` is not `None`, finite, and `>= 0`; every section's
`response_time` in `value_json` is finite and `>= 0`.

### Registration

- `src/derived/metric_pipeline.py` — add to `_default_extractors()`:
  ```python
  ITSRiseFallExtractor(mode="rise"),
  ITSRiseFallExtractor(mode="fall"),
  ```
  plus the import.
- `src/derived/extractors/__init__.py` — import and add to `__all__`.

## Testing

New file `tests/test_its_rise_fall_extractor.py`:
- Synthetic OFF → ON → OFF trace, monotonic, with an analytically known rise and fall;
  assert `t_rise` and `t_fall` match within one sample interval, `n_sections == 1`.
- Dark `It` measurement (no LED-ON segment) → `extract()` returns `None`.
- Incomplete decay (relaxation current never reaches `0.1 * I_max`, no sign switch) →
  fall mode returns `None`; rise mode still succeeds.
- Non-monotonic trace that re-enters the 10–90 window after peaking but does *not*
  sustain a reversal → still one section, first-crossing rule gives the correct time.
- Sign-switch illumination (positive peak then negative peak) → rise mode reports two
  sections, `SIGN_SWITCH` flag set, both section times match analytics.
- Sign-switch relaxation → fall mode reports two sections referenced to each
  relaxation peak.
- Missing-column DataFrame → `None`.
- `RISE_ONSET_CLAMPED` flag set when dark current already exceeds `10% * I_max`.

## Out of scope

- Stretched-exponential or any model fitting (covered by existing extractors).
- Multi-cycle `It` traces (data confirmed single-cycle: one OFF → ON → OFF per file).
- Linear interpolation between samples (definition is explicitly "first data point
  reaching" a threshold).
- The naive "first vs last point of the filtered 10–90 set" variant — only the refined
  first-crossing rule is implemented.
- More than two sections per phase (the sign-switch model is explicitly two sections).
