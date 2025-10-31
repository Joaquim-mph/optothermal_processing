"""
Charge Neutrality Point (CNP) extractor for IVg/VVg measurements.

Handles complex sweep patterns (0→-Vgmax→0→+Vgmax→0→-Vgmax→0) and detects:
- Single CNP (most common case)
- Multiple CNPs due to hysteresis (CNP shifts between forward/backward sweeps)
- Multiple distinct CNPs (e.g., from bilayer graphene or other materials)

The algorithm:
1. Segments the sweep by direction changes
2. Finds resistance peaks in each segment
3. Clusters CNPs by voltage proximity
4. Reports all distinct clusters or averages if they're close
"""

from __future__ import annotations

import numpy as np
import polars as pl
from typing import Optional, List, Dict, Any
from scipy.signal import find_peaks
from scipy.cluster.hierarchy import fclusterdata
from datetime import datetime, timezone
import json

from src.derived.extractors.base import MetricExtractor, compute_confidence, build_flags
from src.models.derived_metrics import DerivedMetric


class CNPExtractor(MetricExtractor):
    """
    Extract charge neutrality point from IVg/VVg measurements.

    The CNP is the gate voltage where resistance is maximum (most resistive point).
    For samples with hysteresis, the CNP may shift between sweep directions.
    This extractor detects and clusters all CNP occurrences.

    Parameters
    ----------
    cluster_threshold_v : float
        Voltage threshold for clustering CNPs (default: 0.5V).
        CNPs within this threshold are considered the same point.
    prominence_factor : float
        Minimum peak prominence as fraction of resistance range (default: 0.1).
        Higher values = stricter peak detection.
    min_segment_points : int
        Minimum points in a segment to analyze (default: 10).
    """

    def __init__(
        self,
        cluster_threshold_v: float = 0.5,
        prominence_factor: float = 0.1,
        min_segment_points: int = 10
    ):
        self.cluster_threshold_v = cluster_threshold_v
        self.prominence_factor = prominence_factor
        self.min_segment_points = min_segment_points

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg", "VVg"]

    @property
    def metric_name(self) -> str:
        return "cnp_voltage"

    @property
    def metric_category(self) -> str:
        return "electrical"

    def extract(
        self,
        measurement: pl.DataFrame,
        metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        """
        Extract CNP from IVg/VVg measurement.

        Returns DerivedMetric with:
        - value_float: Average CNP voltage
        - value_json: JSON with all detected CNPs and clustering info
        - flags: Warnings about data quality or multiple CNPs
        """

        procedure = metadata.get("proc", metadata.get("procedure"))

        # Validate columns and extract data based on procedure type
        if "Vg (V)" not in measurement.columns:
            return None

        vg = measurement["Vg (V)"].to_numpy()

        # IVg: Fixed Vds, measured Ids → R = Vds / Ids
        if procedure == "IVg":
            # Check for current column
            if "I (A)" not in measurement.columns:
                return None

            i = measurement["I (A)"].to_numpy()

            # Get fixed Vds from metadata
            vds = metadata.get("vds_v")
            if vds is None or abs(vds) < 1e-9:
                return None

            # Calculate resistance
            with np.errstate(divide='ignore', invalid='ignore'):
                resistance = np.abs(vds / i)

        # VVg: Fixed Ids, measured Vds → R = Vds / Ids
        elif procedure == "VVg":
            # Check for voltage column (note: might be "VDS (V)" with capitals)
            vds_col = None
            for col in ["Vds (V)", "VDS (V)", "V (V)"]:
                if col in measurement.columns:
                    vds_col = col
                    break

            if vds_col is None:
                return None

            vds = measurement[vds_col].to_numpy()

            # Get fixed Ids from metadata
            ids = metadata.get("ids_v")
            if ids is None or abs(ids) < 1e-12:
                return None

            # Calculate resistance
            with np.errstate(divide='ignore', invalid='ignore'):
                resistance = np.abs(vds / ids)

        else:
            return None

        # Remove infinities/NaNs
        valid_mask = np.isfinite(resistance)
        if not np.any(valid_mask):
            return None

        vg = vg[valid_mask]
        resistance = resistance[valid_mask]

        # Segment the sweep by direction changes
        segments = self._segment_sweep(vg)

        # Find CNPs in each segment
        all_cnps = []
        for seg_idx, seg in enumerate(segments):
            if len(seg) < self.min_segment_points:
                continue

            cnp_candidates = self._find_segment_cnps(
                vg[seg],
                resistance[seg],
                segment_idx=seg_idx
            )
            all_cnps.extend(cnp_candidates)

        if not all_cnps:
            return None

        # Cluster CNPs by voltage proximity
        cnp_voltages = np.array([c['vg'] for c in all_cnps])
        clusters = self._cluster_cnps(cnp_voltages)

        # Analyze clustering results
        result = self._analyze_clusters(cnp_voltages, resistance, clusters, all_cnps)

        # Build DerivedMetric
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=procedure,
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=result["cnp_avg"],
            value_json=json.dumps(result["details"]),
            unit="V",
            extraction_method="peak_resistance_clustered",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=result["confidence"],
            flags=result["flags"]
        )

    def _segment_sweep(self, vg: np.ndarray) -> List[np.ndarray]:
        """
        Segment sweep by direction changes.

        Returns list of index arrays, one per segment.
        """
        if len(vg) < 2:
            return [np.arange(len(vg))]

        # Calculate voltage differences
        diff = np.diff(vg)

        # Detect direction (sign of diff)
        # Add small epsilon to avoid issues with exact zeros
        direction = np.sign(diff + 1e-12)

        # Find where direction changes
        direction_changes = np.where(np.diff(direction) != 0)[0] + 1

        # Split into segments
        segments = np.split(np.arange(len(vg)), direction_changes)

        return segments

    def _find_segment_cnps(
        self,
        vg_seg: np.ndarray,
        r_seg: np.ndarray,
        segment_idx: int
    ) -> List[Dict[str, Any]]:
        """
        Find CNP candidates in a single sweep segment.

        Returns list of dicts with 'vg', 'r', 'segment', 'direction'.
        """
        cnps = []

        # Find resistance peaks using scipy
        prominence_threshold = np.ptp(r_seg) * self.prominence_factor
        peaks, properties = find_peaks(r_seg, prominence=prominence_threshold)

        if len(peaks) == 0:
            return cnps

        # Determine sweep direction
        direction = "forward" if vg_seg[-1] > vg_seg[0] else "backward"

        # Take the top peak (highest resistance)
        peak_resistances = r_seg[peaks]
        top_peak_idx = np.argmax(peak_resistances)
        top_peak = peaks[top_peak_idx]

        cnps.append({
            'vg': vg_seg[top_peak],
            'r': r_seg[top_peak],
            'segment': segment_idx,
            'direction': direction,
            'n_peaks': len(peaks)
        })

        return cnps

    def _cluster_cnps(self, cnp_voltages: np.ndarray) -> np.ndarray:
        """
        Cluster CNPs by voltage proximity.

        Returns cluster labels (1, 2, 3, ...) for each CNP.
        """
        if len(cnp_voltages) == 1:
            return np.array([1])

        # Use hierarchical clustering with voltage threshold
        clusters = fclusterdata(
            cnp_voltages.reshape(-1, 1),
            t=self.cluster_threshold_v,
            criterion='distance',
            method='single'
        )

        return clusters

    def _analyze_clusters(
        self,
        cnp_voltages: np.ndarray,
        resistance: np.ndarray,
        clusters: np.ndarray,
        all_cnps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze clustering results and compute metrics.

        Returns dict with:
        - cnp_avg: Average CNP voltage
        - confidence: Quality score
        - flags: Warning string or None
        - details: JSON-serializable dict with all info
        """
        n_clusters = len(np.unique(clusters))

        # Compute per-cluster statistics
        cluster_info = []
        for cluster_id in np.unique(clusters):
            cluster_mask = clusters == cluster_id
            cluster_voltages = cnp_voltages[cluster_mask]
            cluster_cnps = [cnp for i, cnp in enumerate(all_cnps) if cluster_mask[i]]

            cluster_info.append({
                'cluster_id': int(cluster_id),
                'n_points': int(np.sum(cluster_mask)),
                'vg_mean': float(np.mean(cluster_voltages)),
                'vg_std': float(np.std(cluster_voltages)),
                'vg_min': float(np.min(cluster_voltages)),
                'vg_max': float(np.max(cluster_voltages)),
                'directions': [cnp['direction'] for cnp in cluster_cnps],
                'resistances': [float(cnp['r']) for cnp in cluster_cnps]
            })

        # Overall CNP: average of all cluster means
        cnp_avg = np.mean([c['vg_mean'] for c in cluster_info])

        # Quality checks
        checks = {
            'SINGLE_CLUSTER': n_clusters == 1,
            'MULTIPLE_CLUSTERS': n_clusters > 1,
            'HIGH_HYSTERESIS': False,  # Set below
            'AT_EDGE': False,  # Set below
            'LOW_RESISTANCE': False,  # Set below
        }

        # Check for high hysteresis (>1V between clusters)
        if n_clusters > 1:
            cluster_means = [c['vg_mean'] for c in cluster_info]
            hysteresis = max(cluster_means) - min(cluster_means)
            if hysteresis > 1.0:
                checks['HIGH_HYSTERESIS'] = True

        # Check if CNP is at edge of sweep
        vg_range = [np.min(cnp_voltages), np.max(cnp_voltages)]
        # Assume sweep is roughly symmetric around 0 (common case)
        vg_sweep_max = np.max(np.abs(cnp_voltages)) + 1.0  # Add 1V margin
        if np.min(np.abs(cnp_voltages)) > vg_sweep_max * 0.9:
            checks['AT_EDGE'] = True

        # Check if resistance is suspiciously low (might not be real CNP)
        r_max = np.max([cnp['r'] for cnp in all_cnps])
        r_min = np.min(resistance)
        if r_max / r_min < 2.0:  # Less than 2x modulation
            checks['LOW_RESISTANCE'] = True

        # Compute confidence
        penalties = {
            'MULTIPLE_CLUSTERS': 0.8,  # Minor penalty - hysteresis is real
            'HIGH_HYSTERESIS': 0.6,    # Larger shift might indicate issues
            'AT_EDGE': 0.5,             # CNP might be out of range
            'LOW_RESISTANCE': 0.4,      # Weak modulation - questionable CNP
        }

        confidence = compute_confidence(checks, penalties)

        # Build flags
        flags = build_flags({k: v for k, v in checks.items() if k != 'SINGLE_CLUSTER'})

        # Build details dict
        details = {
            'n_clusters': n_clusters,
            'clusters': cluster_info,
            'cnp_avg': float(cnp_avg),
            'cnp_spread_v': float(np.std(cnp_voltages)),
            'all_cnps': [
                {'vg': float(cnp['vg']), 'r': float(cnp['r']),
                 'segment': cnp['segment'], 'direction': cnp['direction']}
                for cnp in all_cnps
            ]
        }

        return {
            'cnp_avg': cnp_avg,
            'confidence': confidence,
            'flags': flags,
            'details': details
        }

    def validate(self, result: DerivedMetric) -> bool:
        """
        Validate CNP is in physically reasonable range.

        Typical CNPs for graphene/2D materials: -10V to +10V.
        """
        if result.value_float is None:
            return False

        # CNP should be in reasonable voltage range
        if not (-15.0 <= result.value_float <= 15.0):
            return False

        # Confidence should be > 0 (some extraction happened)
        if result.confidence <= 0.0:
            return False

        return True

    def __repr__(self) -> str:
        return (
            f"CNPExtractor(cluster_threshold={self.cluster_threshold_v}V, "
            f"prominence_factor={self.prominence_factor})"
        )
