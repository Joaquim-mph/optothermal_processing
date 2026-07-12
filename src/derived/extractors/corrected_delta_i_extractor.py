"""Corrected delta-I extractor for It/ITt: subtracts a drift fit, then deltas."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import polars as pl

from src.derived.algorithms.linear_fit import fit_linear, linear_model
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.models.derived_metrics import DerivedMetric, MetricCategory

from .base import MetricExtractor

logger = logging.getLogger(__name__)


class CorrectedDeltaIExtractor(MetricExtractor):
    """Fit drift on the pre-illumination window, subtract, and delta-I the residual."""

    def __init__(
        self,
        model: str = "stretched_exponential",
        fit_t_start: float = 20.0,
        fit_t_end: float = 60.0,
        eval_t_pre: float = 60.0,
        eval_t_post: float = 120.0,
        delta_mode: str = "max_deviation",
    ):
        if model not in ("stretched_exponential", "linear"):
            raise ValueError(f"unknown model: {model!r}")
        if delta_mode not in ("max_deviation", "endpoint"):
            raise ValueError(f"unknown delta_mode: {delta_mode!r}")
        self.model = model
        self.fit_t_start = fit_t_start
        self.fit_t_end = fit_t_end
        self.eval_t_pre = eval_t_pre
        self.eval_t_post = eval_t_post
        # "max_deviation": largest absolute excursion from the eval_t_pre onset
        # over the illuminated window [eval_t_pre, eval_t_post] -- the true peak
        # photoresponse. "endpoint": legacy I_corr(eval_t_post) - I_corr(eval_t_pre).
        self.delta_mode = delta_mode

    @property
    def applicable_procedures(self) -> List[str]:
        return ["It", "ITt"]

    @property
    def metric_name(self) -> str:
        return "delta_i_corrected"

    @property
    def metric_category(self) -> MetricCategory:
        return "photoresponse"

    def extract(
        self,
        measurement: pl.DataFrame,
        metadata: Dict[str, Any],
    ) -> Optional[DerivedMetric]:
        for col in ("t (s)", "I (A)"):
            if col not in measurement.columns:
                logger.debug(
                    f"Extractor {self.metric_name} skipped: MISSING_COLUMN ({col})",
                    extra={"run_id": metadata.get("run_id"), "reason": "MISSING_COLUMN"},
                )
                return None

        t = measurement["t (s)"].to_numpy().astype(np.float64)
        i = measurement["I (A)"].to_numpy().astype(np.float64)

        finite = np.isfinite(t) & np.isfinite(i)
        t = t[finite]
        i = i[finite]

        mask = (t >= self.fit_t_start) & (t <= self.fit_t_end)
        if mask.size:
            mask[0] = False  # always exclude first sample (acquisition artifact)
        if mask.sum() < 10:
            return self._failure(metadata, flags="INSUFFICIENT_FIT_POINTS")

        try:
            if self.model == "stretched_exponential":
                fit = fit_stretched_exponential(t[mask], i[mask])
                fit_full = stretched_exponential(
                    t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
                )
                fit_params = {
                    "baseline": fit["baseline"],
                    "amplitude": fit["amplitude"],
                    "tau": fit["tau"],
                    "beta": fit["beta"],
                }
                converged = bool(fit["converged"])
                r_squared = float(fit["r_squared"])
            else:
                fit = fit_linear(t[mask], i[mask])
                fit_full = linear_model(t, fit["slope"], fit["intercept"])
                fit_params = {"slope": fit["slope"], "intercept": fit["intercept"]}
                converged = True
                r_squared = float(fit["r_squared"])
        except (ValueError, RuntimeError) as exc:
            logger.debug(f"{self.metric_name} fit failed: {exc}",
                         extra={"run_id": metadata.get("run_id")})
            return self._failure(metadata, flags="FIT_FAILED")

        i_corrected = i - fit_full

        idx_pre = int(np.argmin(np.abs(t - self.eval_t_pre)))
        win = (t >= self.eval_t_pre) & (t <= self.eval_t_post)
        dev = i_corrected - i_corrected[idx_pre]  # deviation from onset

        flags: List[str] = []
        if abs(t[idx_pre] - self.eval_t_pre) > 1.0 or win.sum() == 0:
            flags.append("EVAL_TIME_OUT_OF_RANGE")

        if self.delta_mode == "max_deviation" and win.sum() > 0:
            win_idx = np.flatnonzero(win)
            idx_peak = int(win_idx[int(np.argmax(np.abs(dev[win_idx])))])
        else:
            # endpoint (or degenerate window): nearest sample to eval_t_post
            idx_peak = int(np.argmin(np.abs(t - self.eval_t_post)))

        delta = float(dev[idx_peak])  # signed peak excursion

        if not converged:
            flags.append("FIT_DID_NOT_CONVERGE")
        if r_squared < 0.8:
            flags.append("LOW_R_SQUARED")

        confidence = 0.0 if not converged else max(0.0, min(1.0, r_squared))

        value_json = json.dumps({
            "model": self.model,
            "delta_mode": self.delta_mode,
            "fit_params": fit_params,
            "r_squared": r_squared,
            "converged": converged,
            "fit_window_s": [self.fit_t_start, self.fit_t_end],
            "eval_times_s": [self.eval_t_pre, self.eval_t_post],
            "peak_time_s": float(t[idx_peak]),
            "i_at_pre": float(i[idx_pre]),
            "i_at_peak": float(i[idx_peak]),
            "fit_at_pre": float(fit_full[idx_pre]),
            "fit_at_peak": float(fit_full[idx_peak]),
        })

        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=metadata.get("procedure", metadata.get("proc")),
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=delta,
            value_json=value_json,
            unit="A",
            extraction_method=f"drift_subtraction:{self.model}:{self.delta_mode}",
            extraction_version=metadata.get("extraction_version", "2.0.0"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=",".join(flags) if flags else None,
        )

    def _failure(self, metadata: Dict[str, Any], flags: str) -> DerivedMetric:
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=metadata.get("procedure", metadata.get("proc")),
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=float("nan"),
            unit="A",
            extraction_method=f"drift_subtraction:{self.model}:{self.delta_mode}",
            extraction_version=metadata.get("extraction_version", "2.0.0"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=0.0,
            flags=flags,
        )

    def validate(self, result: DerivedMetric) -> bool:
        return result.value_float is not None and np.isfinite(result.value_float)
