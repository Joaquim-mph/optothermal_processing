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

    def _crossing_index(
        self, values: np.ndarray, level: float, going_up: bool
    ) -> Optional[int]:
        """First index where `values` reaches `level` (>= if going_up else <=)."""
        if going_up:
            hits = np.where(values >= level)[0]
        else:
            hits = np.where(values <= level)[0]
        return int(hits[0]) if len(hits) > 0 else None

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

    def extract(
        self, measurement: pl.DataFrame, metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        return None

    def validate(self, result: DerivedMetric) -> bool:
        return True
