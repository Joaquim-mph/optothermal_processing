"""Per-direction field-effect mobility extractor for IVg sweeps.

Computes peak-transconductance mobility on the requested branch (holes
or electrons) and direction (forward or backward full-range leg) of a
looped sweep, plus a backward-compatible "mean" instance that averages
the forward and backward results.

    mu_FE = (L/W) * |gm|_peak / (C_ox * |Vds|)

C_ox is derived from the chip's top-hBN + bottom-dielectric stack and
ε_r values read from `config/encap_characteristics.yaml`. Six instances
of this extractor (one per branch × direction) are registered by the
pipeline, yielding six metric rows per IVg:

    mobility_fe_holes_forward, mobility_fe_holes_backward, mobility_fe_holes
    mobility_fe_electrons_forward, mobility_fe_electrons_backward,
    mobility_fe_electrons

The bare-branch names (`mobility_fe_holes`, `mobility_fe_electrons`)
correspond to `direction="average"` and preserve the column names that
downstream scripts already read.

For sweeps without a full-range forward+backward loop, all six
instances return `None` and log `SWEEP_NOT_LOOPED` — matching the
CNP-extractor contract. See `docs/algs/MOBILITY_ESTIMATOR_GUIDE.md`
for the underlying derivation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import polars as pl

from src.core.quality import has_dead_flag
from src.derived.algorithms.cnp_parabola import split_full_range_legs
from src.derived.algorithms.mobility import (
    EncapConfig,
    chip_geometry,
    cox_per_area,
    load_encap_config,
    mobility_bounds,
    mobility_cm2,
    peak_gm_on_leg,
    saturation_fraction,
)
from src.derived.extractors.base import (
    MetricExtractor,
    build_flags,
    compute_confidence,
)
from src.models.derived_metrics import DerivedMetric

logger = logging.getLogger(__name__)


_VALID_BRANCHES = ("holes", "electrons")
_VALID_DIRECTIONS = ("forward", "backward", "average")


class MobilityExtractor(MetricExtractor):
    """Peak-gm field-effect mobility on one (branch, direction) of an IVg sweep.

    Parameters
    ----------
    branch
        "holes" / "electrons" — which side of the per-leg coarse CNP to
        report.
    direction
        "forward"  → V_start → V_end full-range leg
        "backward" → V_end → V_start full-range leg
        "average"  → mean of the two; metric name drops the direction
                     suffix (`mobility_fe_holes` / `mobility_fe_electrons`)
                     to preserve back-compat with downstream scripts.
    full_range_frac
        Minimum fraction of total Vg range a monotonic leg must cover to
        count as a full-range traversal (default 95%).
    saturation_warn_threshold, saturation_heavy_threshold
        Fractions of source-meter-compliance points above which the
        result is flagged `NOT_SATURATED` (warn) / `NOT_HEAVILY_SATURATED`
        (heavy). For the `average` row the worst direction's fraction is
        used.
    """

    def __init__(
        self,
        branch: Literal["holes", "electrons"],
        direction: Literal["forward", "backward", "average"] = "average",
        encap_yaml_path: Path = Path("config/encap_characteristics.yaml"),
        saturation_warn_threshold: float = 0.10,
        saturation_heavy_threshold: float = 0.50,
        full_range_frac: float = 0.95,
    ):
        if branch not in _VALID_BRANCHES:
            raise ValueError(f"branch must be one of {_VALID_BRANCHES}, got {branch!r}")
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of {_VALID_DIRECTIONS}, got {direction!r}"
            )
        self.branch = branch
        self.direction = direction
        self.encap_yaml_path = encap_yaml_path
        self.saturation_warn_threshold = saturation_warn_threshold
        self.saturation_heavy_threshold = saturation_heavy_threshold
        self.full_range_frac = full_range_frac
        self._encap: EncapConfig = load_encap_config(encap_yaml_path)

    # ── Required base-class properties ─────────────────────────────────

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg"]

    @property
    def metric_name(self) -> str:
        if self.direction == "average":
            return f"mobility_fe_{self.branch}"
        return f"mobility_fe_{self.branch}_{self.direction}"

    @property
    def metric_category(self) -> str:
        return "electrical"

    # ── Extraction ─────────────────────────────────────────────────────

    def extract(
        self, measurement: pl.DataFrame, metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        run_id = metadata.get("run_id")
        chip_number = metadata.get("chip_number")
        if chip_number is None:
            return None

        if has_dead_flag(metadata.get("quality_flags")):
            logger.debug(
                f"{self.metric_name} skipped: DEAD_SAMPLE "
                f"({metadata.get('quality_flags')})",
                extra={"run_id": run_id, "reason": "DEAD_SAMPLE"},
            )
            return None

        geom = chip_geometry(self._encap, int(chip_number))
        if geom is None:
            logger.debug(
                f"{self.metric_name} skipped: MISSING_GEOMETRY for chip {chip_number}",
                extra={"run_id": run_id, "reason": "MISSING_GEOMETRY"},
            )
            return None

        vds = metadata.get("vds_v")
        if vds is None or not np.isfinite(vds) or abs(vds) < 1e-12:
            logger.debug(
                f"{self.metric_name} skipped: MISSING_METADATA (vds_v)",
                extra={"run_id": run_id, "reason": "MISSING_METADATA"},
            )
            return None

        if "Vg (V)" not in measurement.columns or "I (A)" not in measurement.columns:
            logger.debug(
                f"{self.metric_name} skipped: MISSING_COLUMN",
                extra={"run_id": run_id, "reason": "MISSING_COLUMN"},
            )
            return None

        vg = measurement["Vg (V)"].to_numpy()
        i = measurement["I (A)"].to_numpy()

        legs = split_full_range_legs(vg, i, full_range_frac=self.full_range_frac)
        if not legs:
            logger.warning(
                f"{self.metric_name} skipped: SWEEP_NOT_LOOPED "
                f"(no full-range leg found)",
                extra={"run_id": run_id, "reason": "SWEEP_NOT_LOOPED"},
            )
            return None

        # Compute per-direction gm + mobility once; each instance reads only
        # its slice of the result.
        per_dir: Dict[str, Dict[str, Any]] = {}
        cox_central = cox_per_area(
            geom["top_hBN_nm"], geom["eps_top"],
            geom["bottom_dielectric_nm"], geom["eps_bot"],
        )
        for vg_leg, i_leg, leg_dir in legs:
            gm_h, gm_e, vg_h, vg_e, vg_seg, i_seg, _gm_seg, cnp = peak_gm_on_leg(
                vg_leg, i_leg
            )
            gm_signed = gm_h if self.branch == "holes" else gm_e
            vg_at_peak = vg_h if self.branch == "holes" else vg_e
            if vg_seg.size and np.isfinite(cnp):
                if self.branch == "holes":
                    n_branch = int(np.sum(vg_seg < cnp))
                else:
                    n_branch = int(np.sum(vg_seg > cnp))
            else:
                n_branch = 0
            mu_central = mobility_cm2(gm_signed, cox_central, float(vds), geom["LW"])
            mu_min, mu_max = mobility_bounds(
                gm_signed,
                geom["top_hBN_nm"], geom["bottom_dielectric_nm"],
                geom["eps_top_range"], geom["eps_bot_range"], geom["LW_range"],
                float(vds),
            )
            sat = saturation_fraction(i_leg)
            per_dir[leg_dir] = {
                "gm_signed": gm_signed,
                "vg_at_peak": vg_at_peak,
                "n_branch": n_branch,
                "mu_central": mu_central,
                "mu_min": mu_min,
                "mu_max": mu_max,
                "sat": sat,
                "cnp": cnp,
            }

        fwd = per_dir.get("forward")
        back = per_dir.get("backward")
        n_complete = sum(
            1 for d in (fwd, back) if d is not None and np.isfinite(d["gm_signed"])
        )

        # Direction selection.
        if self.direction == "forward":
            chosen = fwd if (fwd and np.isfinite(fwd["gm_signed"])) else None
        elif self.direction == "backward":
            chosen = back if (back and np.isfinite(back["gm_signed"])) else None
        else:  # average
            if n_complete < 2:
                logger.debug(
                    f"{self.metric_name} skipped: SWEEP_INCOMPLETE "
                    f"(n_complete_legs={n_complete}, mean requires both)",
                    extra={"run_id": run_id, "reason": "SWEEP_INCOMPLETE"},
                )
                chosen = None
            else:
                chosen = {
                    "mu_central": 0.5 * (fwd["mu_central"] + back["mu_central"]),
                    "mu_min": 0.5 * (fwd["mu_min"] + back["mu_min"]),
                    "mu_max": 0.5 * (fwd["mu_max"] + back["mu_max"]),
                    "sat": max(fwd["sat"], back["sat"]),
                    "n_branch": min(fwd["n_branch"], back["n_branch"]),
                    "gm_signed": float("nan"),
                    "vg_at_peak": float("nan"),
                    "cnp": float("nan"),
                }

        if chosen is None or not np.isfinite(chosen["mu_central"]):
            return None

        mu_central = float(chosen["mu_central"])
        mu_min = float(chosen["mu_min"])
        mu_max = float(chosen["mu_max"])
        sat = float(chosen["sat"])
        n_branch = int(chosen["n_branch"])

        cox_lo = cox_per_area(
            geom["top_hBN_nm"], geom["eps_top_range"][0],
            geom["bottom_dielectric_nm"], geom["eps_bot_range"][0],
        )
        cox_hi = cox_per_area(
            geom["top_hBN_nm"], geom["eps_top_range"][1],
            geom["bottom_dielectric_nm"], geom["eps_bot_range"][1],
        )

        checks = {
            "NOT_SATURATED": sat < self.saturation_warn_threshold,
            "NOT_HEAVILY_SATURATED": sat < self.saturation_heavy_threshold,
            "MU_IN_RANGE": 10.0 <= mu_central <= 1.0e5,
            "BRANCH_HAS_POINTS": n_branch >= 5,
            "BOTH_DIRECTIONS_PRESENT": n_complete == 2,
        }
        penalties = {
            "NOT_SATURATED": 0.6,
            "NOT_HEAVILY_SATURATED": 0.2,
            "MU_IN_RANGE": 0.5,
            "BRANCH_HAS_POINTS": 0.3,
            "BOTH_DIRECTIONS_PRESENT": 0.7,
        }
        confidence = compute_confidence(checks, penalties)
        flags = build_flags(checks)

        details: Dict[str, Any] = {
            "branch": self.branch,
            "direction": self.direction,
            "mu_central": mu_central,
            "mu_min": mu_min,
            "mu_max": mu_max,
            "mu_fwd": float(fwd["mu_central"]) if fwd else None,
            "mu_back": float(back["mu_central"]) if back else None,
            "gm_fwd_signed_S": float(fwd["gm_signed"]) if fwd else None,
            "gm_back_signed_S": float(back["gm_signed"]) if back else None,
            "vg_at_peak_fwd_V": float(fwd["vg_at_peak"]) if fwd else None,
            "vg_at_peak_back_V": float(back["vg_at_peak"]) if back else None,
            "cnp_v_coarse_fwd": float(fwd["cnp"]) if fwd else None,
            "cnp_v_coarse_back": float(back["cnp"]) if back else None,
            "saturation_fraction_fwd": float(fwd["sat"]) if fwd else None,
            "saturation_fraction_back": float(back["sat"]) if back else None,
            "n_complete_legs": n_complete,
            "cox_central_F_per_m2": float(cox_central),
            "cox_min_F_per_m2": float(cox_lo),
            "cox_max_F_per_m2": float(cox_hi),
            "vds_v": float(vds),
            "has_light": bool(metadata.get("has_light", False)),
            "geometry": {
                "top_hBN_nm": geom["top_hBN_nm"],
                "bottom_dielectric_nm": geom["bottom_dielectric_nm"],
                "bottom_material": geom["bottom_material"],
                "aspect_ratio_LW": geom["LW"],
                "epsilon_top_central": geom["eps_top"],
                "epsilon_bot_central": geom["eps_bot"],
            },
        }

        return DerivedMetric(
            run_id=run_id,
            chip_number=int(chip_number),
            chip_group=metadata["chip_group"],
            procedure="IVg",
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=mu_central,
            value_json=json.dumps(details),
            unit="cm^2/V/s",
            extraction_method="peak_gm_per_direction",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=flags,
        )

    def validate(self, result: DerivedMetric) -> bool:
        if result.value_float is None or not np.isfinite(result.value_float):
            return False
        if result.confidence <= 0.0:
            return False
        return True

    def __repr__(self) -> str:
        return (
            f"MobilityExtractor(branch={self.branch!r}, "
            f"direction={self.direction!r}, "
            f"sat_warn={self.saturation_warn_threshold}, "
            f"sat_heavy={self.saturation_heavy_threshold})"
        )
