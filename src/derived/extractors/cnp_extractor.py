"""Per-direction Charge Neutrality Point (CNP) extractor.

For looped IVg/VVg sweeps of the shape

    0 → V_start → V_end → V_start → 0

this extractor isolates the two full-range traversals (forward
V_start→V_end and backward V_end→V_start) and fits a quadratic to a
small window around the leg's extremum in the swept signal (|I| min for
IVg, |Vds| max for VVg). No resistance is computed.

Three instances are registered in the pipeline, one per direction:

    CNPExtractor(direction="forward")   → metric_name "cnp_forward"
    CNPExtractor(direction="backward")  → metric_name "cnp_backward"
    CNPExtractor(direction="average")   → metric_name "cnp_voltage"  (preserved name)

Each instance independently runs the full per-direction analysis and
emits only its own row; the per-call cost is microseconds. Hysteresis
(V_back − V_fwd) is stored in `value_json` of every row.

Sweeps without any full-range leg produce no row from any instance and
log a `SWEEP_NOT_LOOPED` warning. Sweeps with only one full-range leg
populate the matching direction and the average (with `SWEEP_INCOMPLETE`
flag), and skip the missing direction.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import polars as pl

from src.derived.algorithms.cnp_parabola import (
    fit_parabola_vertex,
    split_full_range_legs,
)
from src.derived.extractors.base import (
    MetricExtractor,
    build_flags,
    compute_confidence,
)
from src.models.derived_metrics import DerivedMetric

logger = logging.getLogger(__name__)


_VALID_DIRECTIONS = ("forward", "backward", "average")
_METRIC_NAMES = {
    "forward": "cnp_forward",
    "backward": "cnp_backward",
    "average": "cnp_voltage",
}


class CNPExtractor(MetricExtractor):
    """Charge-neutrality point on one direction of an IVg/VVg sweep.

    Parameters
    ----------
    direction
        "forward"  → reports the V_start→V_end traversal
        "backward" → reports the V_end→V_start traversal
        "average"  → reports the mean of the two (back-compat with the
                     legacy ``cnp_voltage`` metric)
    window_frac
        Parabolic-fit window width as a fraction of the leg length
        (default 1%).
    full_range_frac
        Minimum fraction of total Vg range a monotonic leg must cover to
        count as a full-range traversal (default 95%).
    hysteresis_warn_v
        Threshold above which `|V_back − V_fwd|` trips the
        ``HIGH_HYSTERESIS`` flag.
    """

    def __init__(
        self,
        direction: Literal["forward", "backward", "average"] = "average",
        window_frac: float = 0.01,
        full_range_frac: float = 0.95,
        hysteresis_warn_v: float = 1.0,
    ):
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {_VALID_DIRECTIONS}, got {direction!r}"
            )
        self.direction = direction
        self.window_frac = window_frac
        self.full_range_frac = full_range_frac
        self.hysteresis_warn_v = hysteresis_warn_v

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg", "VVg"]

    @property
    def metric_name(self) -> str:
        return _METRIC_NAMES[self.direction]

    @property
    def metric_category(self) -> str:
        return "electrical"

    def extract(
        self,
        measurement: pl.DataFrame,
        metadata: Dict[str, Any],
    ) -> Optional[DerivedMetric]:
        run_id = metadata.get("run_id")
        procedure = metadata.get("proc", metadata.get("procedure"))

        if "Vg (V)" not in measurement.columns:
            logger.debug(
                f"{self.metric_name} skipped: MISSING_COLUMN (Vg (V))",
                extra={"run_id": run_id, "reason": "MISSING_COLUMN"},
            )
            return None

        vg = measurement["Vg (V)"].to_numpy()

        if procedure == "IVg":
            if "I (A)" not in measurement.columns:
                logger.debug(
                    f"{self.metric_name} skipped: MISSING_COLUMN (I (A))",
                    extra={"run_id": run_id, "reason": "MISSING_COLUMN"},
                )
                return None
            signal = measurement["I (A)"].to_numpy()
            extremum = "min"
            unit_signal = "A"
        elif procedure == "VVg":
            vds_col = None
            for col in ("Vds (V)", "VDS (V)", "V (V)"):
                if col in measurement.columns:
                    vds_col = col
                    break
            if vds_col is None:
                logger.debug(
                    f"{self.metric_name} skipped: MISSING_COLUMN (Vds/VDS/V)",
                    extra={"run_id": run_id, "reason": "MISSING_COLUMN"},
                )
                return None
            signal = measurement[vds_col].to_numpy()
            extremum = "max"
            unit_signal = "V"
        else:
            return None

        finite = np.isfinite(vg) & np.isfinite(signal)
        if not np.any(finite):
            logger.debug(
                f"{self.metric_name} skipped: DATA_QUALITY (no finite samples)",
                extra={"run_id": run_id, "reason": "DATA_QUALITY"},
            )
            return None
        vg = vg[finite]
        signal = signal[finite]

        legs = split_full_range_legs(
            vg, signal, full_range_frac=self.full_range_frac
        )

        fwd_fit = None
        back_fit = None
        for vg_leg, sig_leg, leg_dir in legs:
            fit = fit_parabola_vertex(
                vg_leg, sig_leg,
                window_frac=self.window_frac,
                extremum=extremum,
            )
            if fit is None:
                continue
            # If multiple legs of same direction qualify, keep the first.
            if leg_dir == "forward" and fwd_fit is None:
                fwd_fit = fit
            elif leg_dir == "backward" and back_fit is None:
                back_fit = fit

        n_complete = int(fwd_fit is not None) + int(back_fit is not None)

        if n_complete == 0:
            logger.warning(
                f"{self.metric_name} skipped: SWEEP_NOT_LOOPED "
                f"(no full-range leg with a fittable extremum)",
                extra={"run_id": run_id, "reason": "SWEEP_NOT_LOOPED"},
            )
            return None

        v_fwd = fwd_fit["v_cnp"] if fwd_fit else None
        v_back = back_fit["v_cnp"] if back_fit else None
        i_fwd = fwd_fit["i_cnp"] if fwd_fit else None
        i_back = back_fit["i_cnp"] if back_fit else None
        hysteresis = (
            float(v_back - v_fwd)
            if (v_fwd is not None and v_back is not None)
            else None
        )

        if self.direction == "forward":
            value_float = v_fwd
            self_fit = fwd_fit
        elif self.direction == "backward":
            value_float = v_back
            self_fit = back_fit
        else:  # average
            if v_fwd is not None and v_back is not None:
                value_float = 0.5 * (v_fwd + v_back)
            else:
                value_float = v_fwd if v_fwd is not None else v_back
            self_fit = fwd_fit if fwd_fit is not None else back_fit

        if value_float is None:
            # This direction's leg was missing — emit nothing.
            return None

        checks = {
            "BOTH_DIRECTIONS_PRESENT": n_complete == 2,
            "LOW_HYSTERESIS": (
                hysteresis is None or abs(hysteresis) <= self.hysteresis_warn_v
            ),
            "FIT_CONVERGED": self_fit is not None,
        }
        # Modulation: only meaningful if we have a finite leg slope; check
        # the fitted leg's signal range relative to its extremum.
        if self_fit is not None and len(legs) > 0:
            leg_for_check = next(
                (
                    leg for leg in legs
                    if (
                        (self.direction == "forward" and leg[2] == "forward")
                        or (self.direction == "backward" and leg[2] == "backward")
                        or (self.direction == "average")
                    )
                ),
                legs[0],
            )
            sig_leg = leg_for_check[1]
            s_min = float(np.min(np.abs(sig_leg)))
            s_max = float(np.max(np.abs(sig_leg)))
            checks["MODULATION_OK"] = (
                s_max > 0.0 and (s_max - s_min) / s_max > 0.5
            )
        else:
            checks["MODULATION_OK"] = False

        penalties = {
            "BOTH_DIRECTIONS_PRESENT": 0.7,
            "LOW_HYSTERESIS": 0.6,
            "FIT_CONVERGED": 0.0,
            "MODULATION_OK": 0.4,
        }
        confidence = compute_confidence(checks, penalties)

        flag_checks = dict(checks)
        if self.direction == "average" and n_complete == 1:
            flag_checks["SWEEP_COMPLETE"] = False
        flags = build_flags(flag_checks)

        details: Dict[str, Any] = {
            "direction": self.direction,
            "v_fwd": v_fwd,
            "v_back": v_back,
            "i_fwd": i_fwd,
            "i_back": i_back,
            "hysteresis_v": hysteresis,
            "n_complete_legs": n_complete,
            "vg_total_range_v": float(np.max(vg) - np.min(vg)),
            "signal_unit": unit_signal,
        }
        if fwd_fit is not None:
            details["parabola_fwd"] = {
                "a": fwd_fit["a"], "b": fwd_fit["b"], "c": fwd_fit["c"],
                "window_n": fwd_fit["window_n"],
            }
        if back_fit is not None:
            details["parabola_back"] = {
                "a": back_fit["a"], "b": back_fit["b"], "c": back_fit["c"],
                "window_n": back_fit["window_n"],
            }
        if procedure == "IVg":
            details["vds_v"] = metadata.get("vds_v")
        else:
            details["ids_a"] = metadata.get("ids_a")

        return DerivedMetric(
            run_id=run_id,
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=procedure,
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=float(value_float),
            value_json=json.dumps(details),
            unit="V",
            extraction_method="parabolic_fit_per_direction",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=flags,
        )

    def validate(self, result: DerivedMetric) -> bool:
        if result.value_float is None or not np.isfinite(result.value_float):
            return False
        if not (-15.0 <= result.value_float <= 15.0):
            return False
        if result.confidence <= 0.0:
            return False
        return True

    def __repr__(self) -> str:
        return (
            f"CNPExtractor(direction={self.direction!r}, "
            f"window_frac={self.window_frac}, "
            f"full_range_frac={self.full_range_frac})"
        )
