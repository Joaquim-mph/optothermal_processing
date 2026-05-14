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

## Definitions

The illuminated phase is the single LED-ON segment, detected via `VL (V) > 0.1`.
Confirmed from staged data: every light `It` file has exactly one LED-ON segment
(~33% on-fraction), structured as pre-dark → light → post-dark. Dark `It` files have
no LED-ON segment.

`I_max` = maximum `I (A)` over the illuminated phase `[light_start, light_end)`.
The reference span for both thresholds is `0 → I_max` (percentages of `I_max` itself,
**not** of the span above a dark baseline). No first-point skipping.

**Rise time** — within the illuminated phase:
```
t_rise = t(first sample with I >= 0.9 * I_max) - t(first sample with I >= 0.1 * I_max)
```
First-crossing samples, no interpolation. Guaranteed `>= 0`: the `I_max` sample itself
satisfies both thresholds, so the first-`>=10%` index is `<=` the first-`>=90%` index.
This "first reaching" rule (rather than first/last point of the filtered 10–90 set)
handles noisy, non-monotonic traces that re-enter the 10–90 window after peaking.

**Fall time** — within the post-dark phase `[light_end, end)`, reference still `I_max`:
```
t_fall = t(first sample with I <= 0.1 * I_max) - t(first sample with I <= 0.9 * I_max)
```
First-crossing samples, no interpolation. Guaranteed `>= 0` by the same argument.
If the current never decays to `0.1 * I_max` (incomplete recovery / persistent
photoconductivity), `t_fall` is undefined and the extractor returns `None`.

## Architecture

One parameterized extractor class, registered twice — matching the existing
`CNPExtractor(direction=...)` / `MobilityExtractor(branch=..., direction=...)` pattern.
`MetricExtractor.extract()` returns a single `Optional[DerivedMetric]`, and both modes
share LED-phase detection and `I_max` computation, so a single class with a `mode`
parameter is the natural fit.

### New file: `src/derived/extractors/its_rise_fall_extractor.py`

Class `ITSRiseFallExtractor(MetricExtractor)`.

**Constructor:**
- `mode: str` — `"rise"` or `"fall"` (raises `ValueError` otherwise)
- `vl_threshold: float = 0.1` — LED-ON detection threshold
- `low_frac: float = 0.1` — lower threshold fraction of `I_max`
- `high_frac: float = 0.9` — upper threshold fraction of `I_max`
- `min_points_per_phase: int = 10` — sanity floor on phase length

**Properties:**
- `applicable_procedures` → `["It"]`
- `metric_name` → `"t_rise"` if `mode == "rise"` else `"t_fall"`
- `metric_category` → `"photoresponse"`

**`extract(measurement, metadata)` logic:**
1. Require columns `t (s)`, `I (A)`, `VL (V)`; return `None` if any missing.
2. Extract arrays; `led_on = VL > vl_threshold`.
3. Find the LED-ON segment (longest contiguous run, expected to be exactly one).
   No ON segment → dark measurement → return `None`.
4. Determine `light_start`, `light_end` (exclusive). Check both the illuminated phase
   and (for fall) the post-dark phase have `>= min_points_per_phase` samples; else `None`.
5. `I_max = max(I[light_start:light_end])`.
6. Rise mode: find first index in `[light_start, light_end)` with `I >= low_frac*I_max`
   (`t_10`) and first with `I >= high_frac*I_max` (`t_90`); `t_rise = t_90 - t_10`.
7. Fall mode: find first index in `[light_end, end)` with `I <= high_frac*I_max`
   (`t_90`) and first with `I <= low_frac*I_max` (`t_10`); `t_fall = t_10 - t_90`.
   If either crossing is missing → return `None` (debug log, reason `INCOMPLETE_DECAY`).
8. Build and return a `DerivedMetric`.

**`DerivedMetric` fields:**
- `value_float` — `t_rise` / `t_fall` in seconds
- `unit` — `"s"`
- `extraction_method` — `"ten_ninety_rise"` / `"ten_ninety_fall"`
- `value_json` — `{mode, I_max, level_10, level_90, t_10, t_90, idx_10, idx_90,
  light_start_t, light_end_t, n_points_phase, low_frac, high_frac}`
- `confidence`, `flags` — see below

**Confidence / flags:**
- `RISE_ONSET_CLAMPED` (confidence ×0.7) — for rise: `idx_10 == light_start`, i.e. the
  current is already `>= 10% * I_max` at the first illuminated sample, so the rise
  window is truncated by a large dark current.
- `FALL_ONSET_CLAMPED` (confidence ×0.7) — for fall: `idx_90 == light_end`, i.e. the
  current is already `<= 90% * I_max` at the first post-dark sample.
- `NEGATIVE_I_MAX` (confidence ×0.5) — `I_max <= 0`; the "maximum bias current" sign
  assumption is broken, thresholds may be meaningless.
- Otherwise confidence `1.0`.

**`validate(result)`:** `value_float` is not `None`, finite, and `>= 0`.

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
- Synthetic OFF → ON → OFF trace with an analytically known rise and fall; assert
  `t_rise` and `t_fall` match within one sample interval.
- Dark `It` measurement (no LED-ON segment) → `extract()` returns `None`.
- Incomplete decay (post-dark current never reaches `0.1 * I_max`) → fall mode
  returns `None`; rise mode still succeeds.
- Non-monotonic trace that re-enters the 10–90 window after peaking → first-crossing
  rule still yields the correct `t_rise`.
- Missing-column DataFrame → `None`.
- `RISE_ONSET_CLAMPED` flag set when dark current already exceeds `10% * I_max`.

## Out of scope

- Stretched-exponential or any model fitting (covered by existing extractors).
- Multi-cycle `It` traces (data confirmed single-cycle).
- Linear interpolation between samples (definition is explicitly "first data point
  reaching" a threshold).
- The naive "first vs last point of the filtered 10–90 set" variant — only the refined
  first-crossing rule is implemented.
