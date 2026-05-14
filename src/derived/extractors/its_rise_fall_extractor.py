"""
ITS Rise/Fall Time Extractor.

Computes rise time (t_rise) and fall time (t_fall) of light It measurements
using a model-free 10%-90% rule applied to the OFF -> ON -> OFF cycle.

The 10/90 levels are referenced to the span between the dark baseline and the
in-phase extremum (the standard 10-90 step-response convention), so a large
dark current and a negative photoresponse are both handled without special
casing. When the photocurrent sustains a sign reversal within a phase, the
phase is split at its first peak and a response time is computed for each of
the two sections.

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
        baseline_frac: float = 0.2,
        min_recovery_frac: float = 0.1,
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
        self.baseline_frac = baseline_frac
        self.min_recovery_frac = min_recovery_frac
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

    def _phase_baseline(self, i: np.ndarray, start: int, end: int) -> float:
        """Mean of the last `baseline_frac` of i[start:end] (tail mean)."""
        seg = i[start:end]
        tail = max(1, int(round(len(seg) * self.baseline_frac)))
        return float(np.mean(seg[-tail:]))

    def _extremum_idx(
        self, i: np.ndarray, start: int, end: int, baseline: float
    ) -> int:
        """Absolute index of the largest |i - baseline| within [start, end)."""
        seg = i[start:end]
        return start + int(np.argmax(np.abs(seg - baseline)))

    def _crossing_index(
        self, values: np.ndarray, level: float, going_up: bool
    ) -> Optional[int]:
        """First index where `values` reaches `level` (>= if going_up else <=)."""
        if going_up:
            hits = np.where(values >= level)[0]
        else:
            hits = np.where(values <= level)[0]
        return int(hits[0]) if len(hits) > 0 else None

    def _response_time(
        self,
        t: np.ndarray,
        i: np.ndarray,
        search_start: int,
        search_end: int,
        ref_start: float,
        ref_end: float,
    ) -> Optional[Dict[str, Any]]:
        """
        10-90 response time over the search window [search_start, search_end).

        The 10% and 90% levels are taken from the span ref_start -> ref_end.
        Returns a details dict, or None if either crossing is missing.
        """
        seg_i = i[search_start:search_end]
        if len(seg_i) < 2:
            return None
        span = ref_end - ref_start
        level_10 = ref_start + self.low_frac * span
        level_90 = ref_start + self.high_frac * span
        going_up = ref_end >= ref_start
        idx_10 = self._crossing_index(seg_i, level_10, going_up)
        idx_90 = self._crossing_index(seg_i, level_90, going_up)
        if idx_10 is None or idx_90 is None:
            return None
        abs_10 = search_start + idx_10
        abs_90 = search_start + idx_90
        response_time = abs(float(t[abs_90]) - float(t[abs_10]))
        return {
            "response_time": response_time,
            "ref_start": float(ref_start),
            "ref_end": float(ref_end),
            "level_10": float(level_10),
            "level_90": float(level_90),
            "idx_10": int(abs_10),
            "idx_90": int(abs_90),
            "t_10": float(t[abs_10]),
            "t_90": float(t[abs_90]),
            "section_start_idx": int(search_start),
            "section_end_idx": int(search_end),
        }

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

    def extract(
        self, measurement: pl.DataFrame, metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        run_id = metadata.get("run_id")
        required = {"t (s)", "I (A)", "VL (V)"}
        if not required.issubset(measurement.columns):
            logger.debug(
                f"Extractor {self.metric_name} skipped: MISSING_COLUMN",
                extra={"run_id": run_id, "reason": "MISSING_COLUMN"},
            )
            return None

        t = measurement["t (s)"].to_numpy()
        i = measurement["I (A)"].to_numpy()
        vl = measurement["VL (V)"].to_numpy()

        seg = self._find_led_segment(vl)
        if seg is None:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (no LED-ON segment)",
                extra={"run_id": run_id, "reason": "PRECONDITION_FAILED"},
            )
            return None
        light_start, light_end = seg

        if light_start == 0:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (no pre-dark phase)",
                extra={"run_id": run_id, "reason": "PRECONDITION_FAILED"},
            )
            return None

        pre_baseline = self._phase_baseline(i, 0, light_start)
        illum_extremum_idx = self._extremum_idx(i, light_start, light_end, pre_baseline)
        illum_extremum = float(i[illum_extremum_idx])
        rise_span = abs(illum_extremum - pre_baseline)
        if rise_span == 0.0:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (flat illuminated phase)",
                extra={"run_id": run_id, "reason": "PRECONDITION_FAILED"},
            )
            return None

        flags: List[str] = []
        confidence = 1.0
        post_baseline: Optional[float] = None

        if self.mode == "rise":
            phase_start, phase_end = light_start, light_end
            ref_start, ref_end = pre_baseline, illum_extremum
        else:
            if light_end >= len(t):
                logger.debug(
                    f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (no post-dark phase)",
                    extra={"run_id": run_id, "reason": "PRECONDITION_FAILED"},
                )
                return None
            phase_start, phase_end = light_end, len(t)
            post_baseline = self._phase_baseline(i, light_end, len(t))
            recovery_span = abs(post_baseline - illum_extremum)
            if recovery_span < self.min_recovery_frac * rise_span:
                logger.debug(
                    f"Extractor {self.metric_name} skipped: NEGLIGIBLE_RECOVERY",
                    extra={"run_id": run_id, "reason": "NEGLIGIBLE_RECOVERY"},
                )
                return None
            ref_start, ref_end = illum_extremum, post_baseline

        if phase_end - phase_start < self.min_points_per_phase:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (phase too short)",
                extra={"run_id": run_id, "reason": "PRECONDITION_FAILED"},
            )
            return None

        phase_i = i[phase_start:phase_end]
        peak = self._find_first_peak(phase_i)

        sections: List[Dict[str, Any]] = []

        if peak is None:
            # Single section
            sec = self._response_time(
                t, i, phase_start, phase_end, ref_start, ref_end
            )
            if sec is None:
                return None
            if self.mode == "rise" and sec["idx_10"] == phase_start:
                flags.append("RISE_ONSET_CLAMPED")
                confidence *= 0.7
            if self.mode == "fall" and sec["idx_90"] == phase_start:
                flags.append("FALL_ONSET_CLAMPED")
                confidence *= 0.7
            sections.append(sec)
            boundary_idx = None
        else:
            # Two sections (sustained reversal detected)
            peak_rel, s0 = peak
            boundary_idx = phase_start + peak_rel
            boundary_level = float(i[boundary_idx])
            flags.append("SIGN_SWITCH")

            sec0 = self._response_time(
                t, i, phase_start, boundary_idx + 1, ref_start, boundary_level
            )
            if sec0 is None:
                return None
            if self.mode == "rise" and sec0["idx_10"] == phase_start:
                flags.append("RISE_ONSET_CLAMPED")
                confidence *= 0.7
            if self.mode == "fall" and sec0["idx_90"] == phase_start:
                flags.append("FALL_ONSET_CLAMPED")
                confidence *= 0.7
            sections.append(sec0)

            sec1_i = i[boundary_idx:phase_end]
            if len(sec1_i) >= 2:
                if s0 > 0:
                    sec1_ext_rel = int(np.argmin(sec1_i))
                else:
                    sec1_ext_rel = int(np.argmax(sec1_i))
                sec1_ext_idx = boundary_idx + sec1_ext_rel
                sec1 = self._response_time(
                    t, i, boundary_idx, phase_end,
                    boundary_level, float(i[sec1_ext_idx]),
                )
            else:
                sec1 = None
            if sec1 is None:
                flags.append("SECTION1_INCOMPLETE")
            else:
                sections.append(sec1)

        details: Dict[str, Any] = {
            "mode": self.mode,
            "n_sections": len(sections),
            "sign_switch": peak is not None,
            "pre_baseline": pre_baseline,
            "illum_extremum": illum_extremum,
            "illum_extremum_idx": int(illum_extremum_idx),
            "rise_span": rise_span,
            "low_frac": self.low_frac,
            "high_frac": self.high_frac,
            "baseline_frac": self.baseline_frac,
            "min_recovery_frac": self.min_recovery_frac,
            "smooth_window": self.smooth_window,
            "min_reversal_run": self.min_reversal_run,
            "phase_start_t": float(t[phase_start]),
            "phase_end_t": float(t[phase_end - 1]),
            "sections": [
                {"section": k, **sec} for k, sec in enumerate(sections)
            ],
        }
        if post_baseline is not None:
            details["post_baseline"] = post_baseline
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
