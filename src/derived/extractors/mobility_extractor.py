"""Field-effect mobility extractor for IVg measurements.

Computes peak-transconductance mobility on the hole or electron branch:

    μ_FE = (L/W) · |gm|_peak / (C_ox · |Vds|)

with C_ox derived from the chip's top hBN + bottom dielectric stack and
ε_r values read from `config/encap_characteristics.yaml`. Two instances
of this extractor (one per branch) are registered by the pipeline so that
each measurement yields a separate `mobility_fe_holes` and
`mobility_fe_electrons` row in metrics.parquet.

See `docs/algs/MOBILITY_ESTIMATOR_GUIDE.md` for derivations and choices.
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
from src.derived.algorithms.mobility import (
    EncapConfig,
    chip_geometry,
    cox_per_area,
    load_encap_config,
    mobility_bounds,
    mobility_cm2,
    peak_gm_signed,
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


class MobilityExtractor(MetricExtractor):
    """Peak-gm field-effect mobility on one branch of an IVg sweep.

    Parameters
    ----------
    branch : "holes" | "electrons"
        Which side of the CNP to report. The extractor returns one
        DerivedMetric for the requested branch; register two instances
        in the pipeline to cover both.
    encap_yaml_path : Path
        Path to the encap-characteristics YAML. Loaded once at init.
    saturation_warn_threshold : float
        Fraction of points at the source-meter compliance above which the
        result is flagged `NOT_SATURATED` (warn) — peak gm is likely
        under-estimated.
    saturation_heavy_threshold : float
        Fraction above which the peak is almost certainly missed; flagged
        `NOT_HEAVILY_SATURATED` with a heavier confidence penalty.
    """

    def __init__(
        self,
        branch: Literal["holes", "electrons"],
        encap_yaml_path: Path = Path("config/encap_characteristics.yaml"),
        saturation_warn_threshold: float = 0.10,
        saturation_heavy_threshold: float = 0.50,
    ):
        if branch not in _VALID_BRANCHES:
            raise ValueError(f"branch must be one of {_VALID_BRANCHES}, got {branch!r}")
        self.branch = branch
        self.encap_yaml_path = encap_yaml_path
        self.saturation_warn_threshold = saturation_warn_threshold
        self.saturation_heavy_threshold = saturation_heavy_threshold
        self._encap: EncapConfig = load_encap_config(encap_yaml_path)

    # ── Required base-class properties ─────────────────────────────────

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg"]

    @property
    def metric_name(self) -> str:
        return f"mobility_fe_{self.branch}"

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

        # Dead-sample short-circuit: the staging-time quality assessor has
        # already determined the IVg has no usable transistor response.
        # Don't pollute metrics.parquet with mobility rows for these.
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

        gm_h, gm_e, vg_h, vg_e, vg_seg, i_seg, gm_seg, cnp = peak_gm_signed(vg, i)
        gm_signed = gm_h if self.branch == "holes" else gm_e
        vg_at_peak = vg_h if self.branch == "holes" else vg_e
        if not np.isfinite(gm_signed):
            logger.debug(
                f"{self.metric_name} skipped: ALGORITHM_FAILURE (no peak on {self.branch} branch)",
                extra={"run_id": run_id, "reason": "ALGORITHM_FAILURE"},
            )
            return None

        # Branch-population sanity check.
        if vg_seg.size and np.isfinite(cnp):
            if self.branch == "holes":
                n_branch = int(np.sum(vg_seg < cnp))
            else:
                n_branch = int(np.sum(vg_seg > cnp))
        else:
            n_branch = 0

        sat = saturation_fraction(i)

        cox_central = cox_per_area(
            geom["top_hBN_nm"], geom["eps_top"],
            geom["bottom_dielectric_nm"], geom["eps_bot"],
        )
        mu_central = mobility_cm2(gm_signed, cox_central, float(vds), geom["LW"])
        mu_min, mu_max = mobility_bounds(
            gm_signed,
            geom["top_hBN_nm"], geom["bottom_dielectric_nm"],
            geom["eps_top_range"], geom["eps_bot_range"], geom["LW_range"],
            float(vds),
        )
        cox_lo = cox_per_area(
            geom["top_hBN_nm"], geom["eps_top_range"][0],
            geom["bottom_dielectric_nm"], geom["eps_bot_range"][0],
        )
        cox_hi = cox_per_area(
            geom["top_hBN_nm"], geom["eps_top_range"][1],
            geom["bottom_dielectric_nm"], geom["eps_bot_range"][1],
        )

        # Quality checks (True = passed).
        checks = {
            "NOT_SATURATED": sat < self.saturation_warn_threshold,
            "NOT_HEAVILY_SATURATED": sat < self.saturation_heavy_threshold,
            "MU_IN_RANGE": (
                np.isfinite(mu_central) and 10.0 <= mu_central <= 1.0e5
            ),
            "BRANCH_HAS_POINTS": n_branch >= 5,
        }
        penalties = {
            "NOT_SATURATED": 0.6,
            "NOT_HEAVILY_SATURATED": 0.2,
            "MU_IN_RANGE": 0.5,
            "BRANCH_HAS_POINTS": 0.3,
        }
        confidence = compute_confidence(checks, penalties)
        flags = build_flags(checks)

        details = {
            "branch": self.branch,
            "mu_central": float(mu_central),
            "mu_min": float(mu_min),
            "mu_max": float(mu_max),
            "gm_peak_signed_S": float(gm_signed),
            "vg_at_peak_V": float(vg_at_peak),
            "cnp_v_coarse": float(cnp),
            "cox_central_F_per_m2": float(cox_central),
            "cox_min_F_per_m2": float(cox_lo),
            "cox_max_F_per_m2": float(cox_hi),
            "vds_v": float(vds),
            "has_light": bool(metadata.get("has_light", False)),
            "saturation_fraction": float(sat),
            "n_points_branch": int(n_branch),
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
            value_float=float(mu_central),
            value_json=json.dumps(details),
            unit="cm^2/V/s",
            extraction_method="peak_gm_savgol",
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
            f"sat_warn={self.saturation_warn_threshold}, "
            f"sat_heavy={self.saturation_heavy_threshold})"
        )
