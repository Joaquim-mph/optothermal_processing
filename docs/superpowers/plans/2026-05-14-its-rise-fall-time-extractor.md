# ITS Rise/Fall Time Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a metric extractor that computes 10%–90% rise and fall times of light `It` measurements, including a two-section split when the photocurrent switches sign within the illumination or relaxation period.

**Architecture:** One parameterized `ITSRiseFallExtractor(MetricExtractor)` class registered twice (`mode="rise"`, `mode="fall"`), matching the existing `CNPExtractor(direction=...)` pattern. Phase detection uses the LED-ON segment from `VL`. Sign-switch splitting uses smoothed-derivative reversal detection. Each section's response time is the absolute time between first 10% and first 90% crossings of that section's reference extremum.

**Tech Stack:** Python 3.11+, Polars, NumPy, Pydantic v2 (`DerivedMetric`), pytest.

**Spec:** `docs/superpowers/specs/2026-05-14-its-rise-fall-time-extractor-design.md`

---

## File Structure

- **Create** `src/derived/extractors/its_rise_fall_extractor.py` — the `ITSRiseFallExtractor` class and its private helpers (`_find_led_segment`, `_crossing_index`, `_section_time`, `_single_fall`, `_find_first_peak`, `extract`, `validate`).
- **Create** `tests/derived/test_its_rise_fall_extractor.py` — unit tests for each helper plus end-to-end `extract()` tests on synthetic traces.
- **Modify** `src/derived/extractors/__init__.py` — import and export the new class.
- **Modify** `src/derived/metric_pipeline.py` — register both modes in `_default_extractors()`.

Helper methods are kept small and individually unit-tested (Tasks 1–5); `extract()` assembles them once (Task 6).

---

### Task 1: Class skeleton and LED-segment detection

**Files:**
- Create: `src/derived/extractors/its_rise_fall_extractor.py`
- Test: `tests/derived/test_its_rise_fall_extractor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/derived/test_its_rise_fall_extractor.py`:

```python
import json
import sys
import numpy as np
import polars as pl
import pytest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.derived.extractors.its_rise_fall_extractor import ITSRiseFallExtractor


def _meta(**overrides):
    m = {
        "run_id": "run_1234567890123456",
        "chip_number": 1,
        "chip_group": "group_0",
        "proc": "It",
        "extraction_version": "test",
    }
    m.update(overrides)
    return m


class TestSkeleton:
    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            ITSRiseFallExtractor(mode="sideways")

    def test_properties(self):
        rise = ITSRiseFallExtractor(mode="rise")
        fall = ITSRiseFallExtractor(mode="fall")
        assert rise.applicable_procedures == ["It"]
        assert rise.metric_name == "t_rise"
        assert fall.metric_name == "t_fall"
        assert rise.metric_category == "photoresponse"

    def test_find_led_segment_basic(self):
        ext = ITSRiseFallExtractor(mode="rise")
        vl = np.array([0.0] * 10 + [5.0] * 20 + [0.0] * 10)
        assert ext._find_led_segment(vl) == (10, 30)

    def test_find_led_segment_none_when_dark(self):
        ext = ITSRiseFallExtractor(mode="rise")
        vl = np.zeros(40)
        assert ext._find_led_segment(vl) is None

    def test_find_led_segment_longest_run(self):
        ext = ITSRiseFallExtractor(mode="rise")
        vl = np.array([0.0] * 5 + [5.0] * 3 + [0.0] * 5 + [5.0] * 10 + [0.0] * 5)
        assert ext._find_led_segment(vl) == (13, 23)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.derived.extractors.its_rise_fall_extractor'`

- [ ] **Step 3: Write minimal implementation**

Create `src/derived/extractors/its_rise_fall_extractor.py`:

```python
"""
ITS Rise/Fall Time Extractor.

Computes rise time (t_rise) and fall time (t_fall) of light It measurements
using a model-free 10%-90% rule applied to the OFF -> ON -> OFF cycle.

When the photocurrent switches sign within the illumination or relaxation
period, the period is split at its first peak and a response time is
computed for each of the two sections.

See docs/superpowers/specs/2026-05-14-its-rise-fall-time-extractor-design.md
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import polars as pl

from src.models.derived_metrics import DerivedMetric, MetricCategory
from .base import MetricExtractor

logger = logging.getLogger(__name__)


class ITSRiseFallExtractor(MetricExtractor):
    """Extract 10%-90% rise/fall times from light It measurements."""

    def __init__(
        self,
        mode: str,
        vl_threshold: float = 0.1,
        low_frac: float = 0.1,
        high_frac: float = 0.9,
        smooth_window: int = 5,
        min_reversal_run: int = 15,
        min_points_per_phase: int = 10,
    ):
        if mode not in ("rise", "fall"):
            raise ValueError(f"mode must be 'rise' or 'fall', got: {mode}")
        self.mode = mode
        self.vl_threshold = vl_threshold
        self.low_frac = low_frac
        self.high_frac = high_frac
        self.smooth_window = smooth_window
        self.min_reversal_run = min_reversal_run
        self.min_points_per_phase = min_points_per_phase

    @property
    def applicable_procedures(self) -> List[str]:
        return ["It"]

    @property
    def metric_name(self) -> str:
        return "t_rise" if self.mode == "rise" else "t_fall"

    @property
    def metric_category(self) -> MetricCategory:
        return "photoresponse"

    def _find_led_segment(self, vl: np.ndarray) -> Optional[Tuple[int, int]]:
        """Return (start, end) of the longest contiguous LED-ON run, or None."""
        led_on = vl > self.vl_threshold
        if not np.any(led_on):
            return None
        transitions = np.diff(led_on.astype(int))
        on_edges = np.where(transitions == 1)[0] + 1
        off_edges = np.where(transitions == -1)[0] + 1
        if led_on[0]:
            on_edges = np.concatenate([[0], on_edges])
        if led_on[-1]:
            off_edges = np.concatenate([off_edges, [len(led_on)]])
        if len(on_edges) == 0 or len(off_edges) == 0:
            return None
        lengths = off_edges - on_edges
        idx = int(np.argmax(lengths))
        return int(on_edges[idx]), int(off_edges[idx])

    def extract(
        self, measurement: pl.DataFrame, metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        return None

    def validate(self, result: DerivedMetric) -> bool:
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/derived/extractors/its_rise_fall_extractor.py tests/derived/test_its_rise_fall_extractor.py
git commit -m "feat: ITSRiseFallExtractor skeleton with LED-segment detection"
```

---

### Task 2: First-crossing index helper

**Files:**
- Modify: `src/derived/extractors/its_rise_fall_extractor.py`
- Test: `tests/derived/test_its_rise_fall_extractor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/derived/test_its_rise_fall_extractor.py`:

```python
class TestCrossingIndex:
    def test_crossing_going_up(self):
        ext = ITSRiseFallExtractor(mode="rise")
        values = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])
        # first index with value >= 5.0
        assert ext._crossing_index(values, 5.0, going_up=True) == 3

    def test_crossing_going_down(self):
        ext = ITSRiseFallExtractor(mode="fall")
        values = np.array([10.0, 8.0, 6.0, 4.0, 2.0, 0.0])
        # first index with value <= 5.0
        assert ext._crossing_index(values, 5.0, going_up=False) == 3

    def test_crossing_not_found(self):
        ext = ITSRiseFallExtractor(mode="rise")
        values = np.array([0.0, 1.0, 2.0])
        assert ext._crossing_index(values, 99.0, going_up=True) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestCrossingIndex -v`
Expected: FAIL with `AttributeError: 'ITSRiseFallExtractor' object has no attribute '_crossing_index'`

- [ ] **Step 3: Write minimal implementation**

In `its_rise_fall_extractor.py`, add this method after `_find_led_segment`:

```python
    def _crossing_index(
        self, values: np.ndarray, level: float, going_up: bool
    ) -> Optional[int]:
        """First index where `values` reaches `level` (>= if going_up else <=)."""
        if going_up:
            hits = np.where(values >= level)[0]
        else:
            hits = np.where(values <= level)[0]
        return int(hits[0]) if len(hits) > 0 else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestCrossingIndex -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/derived/extractors/its_rise_fall_extractor.py tests/derived/test_its_rise_fall_extractor.py
git commit -m "feat: add first-crossing index helper to ITSRiseFallExtractor"
```

---

### Task 3: Per-section response-time helper

**Files:**
- Modify: `src/derived/extractors/its_rise_fall_extractor.py`
- Test: `tests/derived/test_its_rise_fall_extractor.py`

The unified per-section rule: a section spanning `[start, end)` with a reference
extremum at absolute index `extremum_idx`. Levels are `low_frac * E` and
`high_frac * E` where `E = i[extremum_idx]`. Direction is "up" if `E >= section
start value", else "down". `response_time = abs(t[idx_90] - t[idx_10])`.

- [ ] **Step 1: Write the failing test**

Append to `tests/derived/test_its_rise_fall_extractor.py`:

```python
class TestSectionTime:
    def test_section_rising_toward_positive_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # values 0..100 over 101 samples, t == index
        t = np.arange(101, dtype=float)
        i = np.linspace(0.0, 100.0, 101)
        # extremum at index 100 (value 100); levels 10 and 90
        sec = ext._section_time(t, i, start=0, end=101, extremum_idx=100)
        assert sec is not None
        assert sec["idx_10"] == 10   # first value >= 10
        assert sec["idx_90"] == 90   # first value >= 90
        assert sec["response_time"] == pytest.approx(80.0)
        assert sec["extremum"] == pytest.approx(100.0)

    def test_section_moving_toward_negative_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # section starts at +100, ends at -50 (sign switch); t == index
        t = np.arange(151, dtype=float)
        i = np.linspace(100.0, -50.0, 151)
        # extremum at index 150 (value -50); levels -5 and -45
        sec = ext._section_time(t, i, start=0, end=151, extremum_idx=150)
        assert sec is not None
        # going down: first value <= -5, first value <= -45
        assert sec["idx_10"] < sec["idx_90"]
        assert sec["response_time"] >= 0.0

    def test_section_returns_none_when_level_unreached(self):
        ext = ITSRiseFallExtractor(mode="rise")
        t = np.arange(50, dtype=float)
        i = np.linspace(0.0, 100.0, 50)
        # extremum index points at value 100, but section only covers 0..20
        sec = ext._section_time(t, i, start=0, end=20, extremum_idx=49)
        # within [0,20) max value ~38.8, never reaches 90 -> None
        assert sec is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestSectionTime -v`
Expected: FAIL with `AttributeError: ... '_section_time'`

- [ ] **Step 3: Write minimal implementation**

In `its_rise_fall_extractor.py`, add after `_crossing_index`:

```python
    def _section_time(
        self,
        t: np.ndarray,
        i: np.ndarray,
        start: int,
        end: int,
        extremum_idx: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Compute the 10-90 response time for section [start, end) whose
        reference extremum is at absolute index `extremum_idx`.

        Returns a details dict, or None if either crossing is missing.
        """
        seg_i = i[start:end]
        if len(seg_i) < 2:
            return None
        E = float(i[extremum_idx])
        start_val = float(seg_i[0])
        going_up = E >= start_val
        level_10 = self.low_frac * E
        level_90 = self.high_frac * E
        idx_10 = self._crossing_index(seg_i, level_10, going_up)
        idx_90 = self._crossing_index(seg_i, level_90, going_up)
        if idx_10 is None or idx_90 is None:
            return None
        abs_10 = start + idx_10
        abs_90 = start + idx_90
        response_time = abs(float(t[abs_90]) - float(t[abs_10]))
        return {
            "response_time": response_time,
            "extremum": E,
            "extremum_idx": int(extremum_idx),
            "extremum_t": float(t[extremum_idx]),
            "level_10": level_10,
            "level_90": level_90,
            "idx_10": int(abs_10),
            "idx_90": int(abs_90),
            "t_10": float(t[abs_10]),
            "t_90": float(t[abs_90]),
            "section_start_idx": int(start),
            "section_end_idx": int(end),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestSectionTime -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/derived/extractors/its_rise_fall_extractor.py tests/derived/test_its_rise_fall_extractor.py
git commit -m "feat: add per-section 10-90 response-time helper"
```

---

### Task 4: Single-section fall helper

**Files:**
- Modify: `src/derived/extractors/its_rise_fall_extractor.py`
- Test: `tests/derived/test_its_rise_fall_extractor.py`

The single-section fall is the documented exception: its reference is `I_max`
(from the illumination phase), and the current decays *away* from it, so it
uses an explicit `<=`-crossing form rather than `_section_time`.

- [ ] **Step 1: Write the failing test**

Append to `tests/derived/test_its_rise_fall_extractor.py`:

```python
class TestSingleFall:
    def test_single_fall_basic(self):
        ext = ITSRiseFallExtractor(mode="fall")
        # relaxation: value decays 100 -> 0 over 101 samples, t == index
        t = np.arange(101, dtype=float)
        i = np.linspace(100.0, 0.0, 101)
        sec = ext._single_fall(t, i, start=0, end=101, i_max=100.0, i_max_idx=0)
        assert sec is not None
        # first value <= 90 at index 10, first value <= 10 at index 90
        assert sec["idx_90"] == 10
        assert sec["idx_10"] == 90
        assert sec["response_time"] == pytest.approx(80.0)

    def test_single_fall_incomplete_decay_returns_none(self):
        ext = ITSRiseFallExtractor(mode="fall")
        t = np.arange(101, dtype=float)
        # decays only to 20, never reaches 10% of i_max (10.0)
        i = np.linspace(100.0, 20.0, 101)
        sec = ext._single_fall(t, i, start=0, end=101, i_max=100.0, i_max_idx=0)
        assert sec is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestSingleFall -v`
Expected: FAIL with `AttributeError: ... '_single_fall'`

- [ ] **Step 3: Write minimal implementation**

In `its_rise_fall_extractor.py`, add after `_section_time`:

```python
    def _single_fall(
        self,
        t: np.ndarray,
        i: np.ndarray,
        start: int,
        end: int,
        i_max: float,
        i_max_idx: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Single-section fall: current decays away from I_max in the
        relaxation phase. Returns details dict, or None if the current
        never decays to 10% of I_max (incomplete decay).
        """
        seg_i = i[start:end]
        if len(seg_i) < 2:
            return None
        level_10 = self.low_frac * i_max
        level_90 = self.high_frac * i_max
        idx_90 = self._crossing_index(seg_i, level_90, going_up=False)
        idx_10 = self._crossing_index(seg_i, level_10, going_up=False)
        if idx_90 is None or idx_10 is None:
            return None
        abs_90 = start + idx_90
        abs_10 = start + idx_10
        response_time = abs(float(t[abs_10]) - float(t[abs_90]))
        return {
            "response_time": response_time,
            "extremum": float(i_max),
            "extremum_idx": int(i_max_idx),
            "extremum_t": float(t[i_max_idx]),
            "level_10": level_10,
            "level_90": level_90,
            "idx_10": int(abs_10),
            "idx_90": int(abs_90),
            "t_10": float(t[abs_10]),
            "t_90": float(t[abs_90]),
            "section_start_idx": int(start),
            "section_end_idx": int(end),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestSingleFall -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/derived/extractors/its_rise_fall_extractor.py tests/derived/test_its_rise_fall_extractor.py
git commit -m "feat: add single-section fall helper with incomplete-decay guard"
```

---

### Task 5: First-peak detection (smoothed-derivative reversal)

**Files:**
- Modify: `src/derived/extractors/its_rise_fall_extractor.py`
- Test: `tests/derived/test_its_rise_fall_extractor.py`

`_find_first_peak` smooths the signal with a moving average, takes the discrete
derivative, finds the first sustained reversal (`min_reversal_run` consecutive
samples of the opposite derivative sign), and returns `(peak_index, s0)` where
`peak_index` is the extremum before the reversal (relative to the input array)
and `s0` is the initial direction (+1 or -1). Returns `None` if no sustained
reversal exists.

- [ ] **Step 1: Write the failing test**

Append to `tests/derived/test_its_rise_fall_extractor.py`:

```python
class TestFindFirstPeak:
    def test_monotonic_signal_no_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        signal = np.linspace(0.0, 100.0, 300)
        assert ext._find_first_peak(signal) is None

    def test_sign_switch_signal_splits_near_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # rise 0->100 over 150 samples, then fall 100->-80 over 150 samples
        up = np.linspace(0.0, 100.0, 150)
        down = np.linspace(100.0, -80.0, 150)
        signal = np.concatenate([up, down])
        result = ext._find_first_peak(signal)
        assert result is not None
        peak_idx, s0 = result
        assert s0 == 1
        # peak should be located near the turning point (index ~149)
        assert 140 <= peak_idx <= 158

    def test_brief_dip_not_sustained_no_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # mostly rising, with a 5-sample dip that is shorter than
        # min_reversal_run (15) -> must not trigger a split
        signal = np.linspace(0.0, 300.0, 300).copy()
        signal[150:155] = signal[150]  # flat/dip, only 5 samples
        assert ext._find_first_peak(signal) is None

    def test_descending_then_rising_negative_s0(self):
        ext = ITSRiseFallExtractor(mode="fall")
        # decay 100->-40 over 150, then recover -40->0 over 150
        down = np.linspace(100.0, -40.0, 150)
        up = np.linspace(-40.0, 0.0, 150)
        signal = np.concatenate([down, up])
        result = ext._find_first_peak(signal)
        assert result is not None
        peak_idx, s0 = result
        assert s0 == -1
        assert 140 <= peak_idx <= 158
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestFindFirstPeak -v`
Expected: FAIL with `AttributeError: ... '_find_first_peak'`

- [ ] **Step 3: Write minimal implementation**

In `its_rise_fall_extractor.py`, add after `_single_fall`:

```python
    def _find_first_peak(
        self, signal: np.ndarray
    ) -> Optional[Tuple[int, int]]:
        """
        Detect a sustained derivative reversal (sign switch) in `signal`.

        Returns (peak_index, s0): `peak_index` is the extremum reached
        before the sustained reversal (index relative to `signal`), `s0`
        is the initial direction (+1 or -1). Returns None if `signal`
        does not sustain a reversal.
        """
        n = len(signal)
        w = self.smooth_window
        if n < 2 * w + self.min_reversal_run:
            return None
        kernel = np.ones(w) / w
        smooth = np.convolve(signal, kernel, mode="valid")
        d = np.diff(smooth)
        if len(d) == 0:
            return None
        s0 = int(np.sign(np.sum(d[: max(1, self.min_reversal_run)])))
        if s0 == 0:
            return None
        reversed_mask = np.sign(d) == -s0
        run = 0
        offset = (w - 1) // 2
        for k in range(len(reversed_mask)):
            if reversed_mask[k]:
                run += 1
                if run >= self.min_reversal_run:
                    reversal_start = k - run + 1
                    seg = smooth[: reversal_start + 1]
                    if s0 > 0:
                        peak_smooth_idx = int(np.argmax(seg))
                    else:
                        peak_smooth_idx = int(np.argmin(seg))
                    return peak_smooth_idx + offset, s0
            else:
                run = 0
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestFindFirstPeak -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/derived/extractors/its_rise_fall_extractor.py tests/derived/test_its_rise_fall_extractor.py
git commit -m "feat: add smoothed-derivative reversal detection for sign-switch splitting"
```

---

### Task 6: Assemble `extract()` and `validate()`

**Files:**
- Modify: `src/derived/extractors/its_rise_fall_extractor.py`
- Test: `tests/derived/test_its_rise_fall_extractor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/derived/test_its_rise_fall_extractor.py`:

```python
def _make_trace(pre_i, light_i, post_i, dt=1.0):
    """Build an It DataFrame from per-phase current arrays."""
    i = np.concatenate([pre_i, light_i, post_i])
    vl = np.concatenate([
        np.zeros(len(pre_i)),
        np.full(len(light_i), 5.0),
        np.zeros(len(post_i)),
    ])
    t = np.arange(len(i), dtype=float) * dt
    return pl.DataFrame({"t (s)": t, "I (A)": i, "VL (V)": vl})


class TestExtract:
    def test_missing_columns_returns_none(self):
        ext = ITSRiseFallExtractor(mode="rise")
        df = pl.DataFrame({"t (s)": [0.0, 1.0], "I (A)": [1.0, 2.0]})
        assert ext.extract(df, _meta()) is None

    def test_dark_measurement_returns_none(self):
        ext = ITSRiseFallExtractor(mode="rise")
        i = np.linspace(0.0, 1.0, 120)
        vl = np.zeros(120)
        t = np.arange(120, dtype=float)
        df = pl.DataFrame({"t (s)": t, "I (A)": i, "VL (V)": vl})
        assert ext.extract(df, _meta()) is None

    def test_monotonic_rise(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert m.metric_name == "t_rise"
        assert m.unit == "s"
        details = json.loads(m.value_json)
        assert details["n_sections"] == 1
        assert details["sign_switch"] is False
        # light index of first >=10 is 30, first >=90 is 270 -> 240 samples
        assert m.value_float == pytest.approx(240.0, abs=2.0)

    def test_monotonic_fall(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert m is not None
        assert m.metric_name == "t_fall"
        details = json.loads(m.value_json)
        assert details["n_sections"] == 1
        assert m.value_float == pytest.approx(240.0, abs=2.0)

    def test_incomplete_decay_fall_returns_none(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 20.0, 300)  # never reaches 10
        df = _make_trace(pre, light, post)
        assert ITSRiseFallExtractor(mode="fall").extract(df, _meta()) is None
        # rise still works
        assert ITSRiseFallExtractor(mode="rise").extract(df, _meta()) is not None

    def test_brief_dip_stays_single_section(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300).copy()
        light[150:155] = light[150]  # 5-sample dip, not sustained
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert json.loads(m.value_json)["n_sections"] == 1

    def test_sign_switch_rise_two_sections(self):
        pre = np.zeros(100)
        up = np.linspace(0.0, 100.0, 200)
        down = np.linspace(100.0, -80.0, 200)
        light = np.concatenate([up, down])
        post = np.linspace(-80.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        details = json.loads(m.value_json)
        assert details["n_sections"] == 2
        assert details["sign_switch"] is True
        assert "SIGN_SWITCH" in (m.flags or "")
        assert len(details["sections"]) == 2
        for sec in details["sections"]:
            assert sec["response_time"] >= 0.0

    def test_sign_switch_fall_two_sections(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        down = np.linspace(100.0, -60.0, 200)
        recover = np.linspace(-60.0, 0.0, 200)
        post = np.concatenate([down, recover])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert m is not None
        details = json.loads(m.value_json)
        assert details["n_sections"] == 2
        assert "SIGN_SWITCH" in (m.flags or "")

    def test_negative_i_max_flag(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, -100.0, 300)  # all-negative photocurrent
        post = np.linspace(-100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        # I_max <= 0 -> NEGATIVE_I_MAX flag set, confidence reduced
        if m is not None:
            assert "NEGATIVE_I_MAX" in (m.flags or "")
            assert m.confidence <= 0.5

    def test_rise_onset_clamped_flag(self):
        # light phase starts already at 20 (>= 10% of I_max=100)
        pre = np.zeros(100)
        light = np.linspace(20.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert "RISE_ONSET_CLAMPED" in (m.flags or "")
        assert m.confidence == pytest.approx(0.7)

    def test_validate_accepts_good_result(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        ext = ITSRiseFallExtractor(mode="rise")
        m = ext.extract(df, _meta())
        assert m is not None
        assert ext.validate(m) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestExtract -v`
Expected: FAIL — `extract()` currently returns `None` for all cases, so `test_monotonic_rise` and others fail on `assert m is not None`.

- [ ] **Step 3: Replace `extract()` and `validate()` with the full implementation**

In `its_rise_fall_extractor.py`, replace the placeholder `extract` and `validate`
methods (the two methods added in Task 1) with:

```python
    def extract(
        self, measurement: pl.DataFrame, metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        required = {"t (s)", "I (A)", "VL (V)"}
        if not required.issubset(measurement.columns):
            logger.debug(
                f"Extractor {self.metric_name} skipped: MISSING_COLUMN",
                extra={"run_id": metadata.get("run_id"), "reason": "MISSING_COLUMN"},
            )
            return None

        t = measurement["t (s)"].to_numpy()
        i = measurement["I (A)"].to_numpy()
        vl = measurement["VL (V)"].to_numpy()

        seg = self._find_led_segment(vl)
        if seg is None:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (no LED-ON segment)",
                extra={"run_id": metadata.get("run_id"), "reason": "PRECONDITION_FAILED"},
            )
            return None
        light_start, light_end = seg
        if light_end - light_start < 1:
            return None

        illum_i = i[light_start:light_end]
        i_max_rel = int(np.argmax(illum_i))
        i_max = float(illum_i[i_max_rel])
        i_max_idx = light_start + i_max_rel

        flags: List[str] = []
        confidence = 1.0
        if i_max <= 0:
            flags.append("NEGATIVE_I_MAX")
            confidence *= 0.5

        if self.mode == "rise":
            phase_start, phase_end = light_start, light_end
        else:
            phase_start, phase_end = light_end, len(t)

        if phase_end - phase_start < self.min_points_per_phase:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (phase too short)",
                extra={"run_id": metadata.get("run_id"), "reason": "PRECONDITION_FAILED"},
            )
            return None

        phase_i = i[phase_start:phase_end]
        peak = self._find_first_peak(phase_i)

        sections: List[Dict[str, Any]] = []

        if peak is None:
            # Single section
            if self.mode == "rise":
                sec = self._section_time(t, i, phase_start, phase_end, i_max_idx)
                if sec is None:
                    return None
                if sec["idx_10"] == phase_start:
                    flags.append("RISE_ONSET_CLAMPED")
                    confidence *= 0.7
                sections.append(sec)
            else:
                sec = self._single_fall(
                    t, i, phase_start, phase_end, i_max, i_max_idx
                )
                if sec is None:
                    logger.debug(
                        f"Extractor {self.metric_name} skipped: INCOMPLETE_DECAY",
                        extra={
                            "run_id": metadata.get("run_id"),
                            "reason": "INCOMPLETE_DECAY",
                        },
                    )
                    return None
                if sec["idx_90"] == phase_start:
                    flags.append("FALL_ONSET_CLAMPED")
                    confidence *= 0.7
                sections.append(sec)
            boundary_idx = None
        else:
            # Two sections (sustained reversal detected)
            peak_rel, s0 = peak
            boundary_idx = phase_start + peak_rel
            flags.append("SIGN_SWITCH")

            sec0 = self._section_time(
                t, i, phase_start, boundary_idx + 1, boundary_idx
            )
            if sec0 is None:
                return None
            if self.mode == "rise" and sec0["idx_10"] == phase_start:
                flags.append("RISE_ONSET_CLAMPED")
                confidence *= 0.7
            sections.append(sec0)

            sec1_i = i[boundary_idx:phase_end]
            if len(sec1_i) >= 2:
                if s0 > 0:
                    sec1_ext_rel = int(np.argmin(sec1_i))
                else:
                    sec1_ext_rel = int(np.argmax(sec1_i))
                sec1_ext_idx = boundary_idx + sec1_ext_rel
                sec1 = self._section_time(
                    t, i, boundary_idx, phase_end, sec1_ext_idx
                )
            else:
                sec1 = None
            if sec1 is None:
                flags.append("SECTION1_INCOMPLETE")
            else:
                sections.append(sec1)

        details = {
            "mode": self.mode,
            "n_sections": len(sections),
            "sign_switch": peak is not None,
            "i_max": i_max,
            "smooth_window": self.smooth_window,
            "min_reversal_run": self.min_reversal_run,
            "low_frac": self.low_frac,
            "high_frac": self.high_frac,
            "phase_start_t": float(t[phase_start]),
            "phase_end_t": float(t[phase_end - 1]),
            "sections": [
                {"section": k, **sec} for k, sec in enumerate(sections)
            ],
        }
        if boundary_idx is not None:
            details["boundary_idx"] = int(boundary_idx)

        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=metadata.get("proc", metadata.get("procedure")),
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=sections[0]["response_time"],
            value_json=json.dumps(details),
            unit="s",
            extraction_method=(
                "ten_ninety_rise" if self.mode == "rise" else "ten_ninety_fall"
            ),
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=max(0.0, min(1.0, confidence)),
            flags=",".join(flags) if flags else None,
        )

    def validate(self, result: DerivedMetric) -> bool:
        if result.value_float is None:
            return False
        v = result.value_float
        if not np.isfinite(v) or v < 0:
            return False
        try:
            details = json.loads(result.value_json)
            for sec in details.get("sections", []):
                rt = sec.get("response_time")
                if rt is None or not np.isfinite(rt) or rt < 0:
                    return False
        except (json.JSONDecodeError, KeyError, TypeError):
            return False
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py -v`
Expected: PASS (all tests across all classes)

- [ ] **Step 5: Commit**

```bash
git add src/derived/extractors/its_rise_fall_extractor.py tests/derived/test_its_rise_fall_extractor.py
git commit -m "feat: assemble ITSRiseFallExtractor extract() and validate()"
```

---

### Task 7: Register the extractor in the pipeline

**Files:**
- Modify: `src/derived/extractors/__init__.py`
- Modify: `src/derived/metric_pipeline.py:176-193`
- Test: `tests/derived/test_its_rise_fall_extractor.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/derived/test_its_rise_fall_extractor.py`:

```python
class TestRegistration:
    def test_exported_from_extractors_package(self):
        from src.derived.extractors import ITSRiseFallExtractor as Exported
        assert Exported is ITSRiseFallExtractor

    def test_registered_in_default_extractors(self):
        from src.derived.metric_pipeline import MetricPipeline
        pipeline = MetricPipeline()
        names = {e.metric_name for e in pipeline.extractors}
        assert "t_rise" in names
        assert "t_fall" in names
        it_extractors = pipeline.extractor_map.get("It", [])
        it_names = {e.metric_name for e in it_extractors}
        assert {"t_rise", "t_fall"} <= it_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py::TestRegistration -v`
Expected: FAIL — `ImportError: cannot import name 'ITSRiseFallExtractor' from 'src.derived.extractors'`

- [ ] **Step 3: Add the export in `src/derived/extractors/__init__.py`**

Add the import after the `mobility_extractor` import line:

```python
from .its_rise_fall_extractor import ITSRiseFallExtractor
```

Add `"ITSRiseFallExtractor"` to the `__all__` list.

- [ ] **Step 4: Register both modes in `src/derived/metric_pipeline.py`**

In the `_default_extractors` method (around line 167-193), add the import with the
other local imports inside the method:

```python
        from .extractors.its_rise_fall_extractor import ITSRiseFallExtractor
```

And add these two entries to the returned list (after the `MobilityExtractor` entries):

```python
            ITSRiseFallExtractor(mode="rise"),
            ITSRiseFallExtractor(mode="fall"),
```

- [ ] **Step 5: Run the full test file and the CLI import check**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/test_its_rise_fall_extractor.py -v`
Expected: PASS (all tests including `TestRegistration`)

Run: `source .venv/bin/activate && python3 -c "from src.cli.main import app; print('CLI imports OK')"`
Expected: `CLI imports OK`

- [ ] **Step 6: Commit**

```bash
git add src/derived/extractors/__init__.py src/derived/metric_pipeline.py tests/derived/test_its_rise_fall_extractor.py
git commit -m "feat: register ITSRiseFallExtractor (t_rise, t_fall) in metric pipeline"
```

---

### Task 8: Full test-suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the derived test suite**

Run: `source .venv/bin/activate && python3 -m pytest tests/derived/ -v`
Expected: PASS — no regressions in existing extractor/pipeline tests.

- [ ] **Step 2: Run the broader suite**

Run: `source .venv/bin/activate && python3 -m pytest tests/ -q`
Expected: PASS (or only pre-existing unrelated failures — if any failure touches
`derived/`, `metric_pipeline`, or `extractors`, investigate before finishing).

- [ ] **Step 3: Commit (only if any fixups were needed)**

```bash
git add -A
git commit -m "test: fix regressions from ITSRiseFallExtractor integration"
```

If no fixups were needed, skip this commit.

---

## Notes for the implementer

- Always `source .venv/bin/activate` before running Python — the project uses an editable install in `.venv`.
- Use Polars, never pandas. The test DataFrames are built with `pl.DataFrame`.
- Column names include units and a space: `"t (s)"`, `"I (A)"`, `"VL (V)"`.
- `DerivedMetric` is a Pydantic v2 model with `extra="forbid"` — only pass the
  fields shown in the `extract()` code; do not invent new ones.
- The `metadata` dict uses key `"proc"` (the pipeline passes `proc`); `extract()`
  falls back to `"procedure"` for safety.
- Reference implementations for style: `src/derived/extractors/its_relaxation_extractor.py`
  and `src/derived/extractors/its_three_phase_fit_extractor.py`.
