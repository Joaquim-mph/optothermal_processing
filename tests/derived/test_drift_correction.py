"""Tests for the shared drift-baseline helper and its use by delta_i_corrected."""

import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.derived.algorithms.drift_correction import (
    MIN_FIT_POINTS,
    drift_flags,
    fit_drift_baseline,
)
from src.derived.algorithms.linear_fit import fit_linear, linear_model
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor


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


def _drifting_trace(n=200, dt=1.0, baseline=30e-6, amplitude=5e-6, tau=40.0, beta=0.6):
    """Pure stretched-exponential drift, no illumination response."""
    t = np.arange(n, dtype=float) * dt
    i = stretched_exponential(t, baseline, amplitude, tau, beta)
    return t, i


class TestFitDriftBaseline:
    def test_recovers_stretched_exponential(self):
        t, i = _drifting_trace()
        out = fit_drift_baseline(t, i)
        assert out["converged"]
        assert out["r_squared"] > 0.99
        assert out["fit_full"].shape == t.shape
        # Inside the fit window the model reproduces the data closely ...
        win = (t >= 20.0) & (t <= 60.0)
        assert np.allclose(out["fit_full"][win], i[win], rtol=1e-3)
        # ... and it is evaluated over the whole axis. Extrapolating a 40 s
        # window out to 200 s is approximate (tau/beta trade off), but the
        # stretched exponential saturates, so it stays bounded.
        assert np.allclose(out["fit_full"], i, rtol=5e-2)

    def test_linear_model(self):
        t = np.arange(200, dtype=float)
        i = 1e-6 * t + 3e-5
        out = fit_drift_baseline(t, i, model="linear")
        assert out["model"] == "linear"
        assert out["fit_params"]["slope"] == pytest.approx(1e-6, rel=1e-6)
        assert np.allclose(out["fit_full"], i)

    def test_unknown_model_raises(self):
        t, i = _drifting_trace()
        with pytest.raises(ValueError, match="unknown model"):
            fit_drift_baseline(t, i, model="quadratic")

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="same shape"):
            fit_drift_baseline(np.arange(10.0), np.arange(9.0))

    def test_insufficient_points_raises(self):
        t = np.arange(200, dtype=float)
        i = np.ones_like(t) * 1e-6
        with pytest.raises(ValueError, match="insufficient fit points"):
            fit_drift_baseline(t, i, fit_t_start=20.0, fit_t_end=25.0)

    def test_window_reports_point_count(self):
        t, i = _drifting_trace()
        out = fit_drift_baseline(t, i, fit_t_start=20.0, fit_t_end=60.0)
        # 20..60 s inclusive at dt=1 is 41 samples; sample 0 is not in the window
        assert out["n_fit_points"] == 41
        assert out["fit_window_s"] == [20.0, 60.0]

    def test_first_sample_excluded(self):
        t, i = _drifting_trace()
        out = fit_drift_baseline(t, i, fit_t_start=0.0, fit_t_end=60.0)
        assert out["n_fit_points"] == 60  # 61 samples in window, minus sample 0

    def test_first_sample_kept_when_disabled(self):
        t, i = _drifting_trace()
        out = fit_drift_baseline(t, i, fit_t_start=0.0, fit_t_end=60.0,
                                 drop_first_sample=False)
        assert out["n_fit_points"] == 61

    def test_non_finite_excluded_from_fit(self):
        t, i = _drifting_trace()
        i = i.copy()
        i[30] = np.nan
        out = fit_drift_baseline(t, i)
        assert out["n_fit_points"] == 40
        assert np.all(np.isfinite(out["fit_full"]))

    def test_min_fit_points_constant(self):
        assert MIN_FIT_POINTS == 10


class TestDriftFlags:
    def test_clean_fit_has_no_flags(self):
        assert drift_flags(0.99, True) == []

    def test_flags_reported(self):
        assert drift_flags(0.5, False) == ["FIT_DID_NOT_CONVERGE", "LOW_R_SQUARED"]


class TestCorrectedDeltaINoRegression:
    """The refactor onto fit_drift_baseline must not move delta_i_corrected."""

    @staticmethod
    def _trace():
        t = np.arange(200, dtype=float)
        i = stretched_exponential(t, 30e-6, 5e-6, 40.0, 0.6)
        # photoresponse: step down during 60..120 s
        i = i - 2e-6 * ((t >= 60) & (t <= 120))
        return t, i

    @staticmethod
    def _legacy_delta(t, i, model, fit_t_start, fit_t_end, eval_t_pre, eval_t_post,
                      delta_mode):
        """The pre-refactor computation, inlined."""
        mask = (t >= fit_t_start) & (t <= fit_t_end)
        mask[0] = False
        if model == "stretched_exponential":
            fit = fit_stretched_exponential(t[mask], i[mask])
            fit_full = stretched_exponential(
                t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
            )
        else:
            fit = fit_linear(t[mask], i[mask])
            fit_full = linear_model(t, fit["slope"], fit["intercept"])
        i_corrected = i - fit_full
        idx_pre = int(np.argmin(np.abs(t - eval_t_pre)))
        win = (t >= eval_t_pre) & (t <= eval_t_post)
        dev = i_corrected - i_corrected[idx_pre]
        if delta_mode == "max_deviation" and win.sum() > 0:
            win_idx = np.flatnonzero(win)
            idx_peak = int(win_idx[int(np.argmax(np.abs(dev[win_idx])))])
        else:
            idx_peak = int(np.argmin(np.abs(t - eval_t_post)))
        return float(dev[idx_peak]), float(fit["r_squared"])

    @pytest.mark.parametrize("model", ["stretched_exponential", "linear"])
    @pytest.mark.parametrize("delta_mode", ["max_deviation", "endpoint"])
    def test_matches_legacy_computation(self, model, delta_mode):
        t, i = self._trace()
        df = pl.DataFrame({"t (s)": t, "I (A)": i})
        ext = CorrectedDeltaIExtractor(model=model, delta_mode=delta_mode)
        metric = ext.extract(df, _meta())
        expected, expected_r2 = self._legacy_delta(
            t, i, model, ext.fit_t_start, ext.fit_t_end,
            ext.eval_t_pre, ext.eval_t_post, delta_mode,
        )
        assert metric is not None
        assert metric.value_float == pytest.approx(expected, rel=1e-12, abs=1e-18)
        assert metric.confidence == pytest.approx(expected_r2, rel=1e-12)

    def test_insufficient_fit_points_still_flagged(self):
        t = np.arange(15, dtype=float)  # nothing in the 20-60 s window
        df = pl.DataFrame({"t (s)": t, "I (A)": np.ones_like(t) * 1e-6})
        metric = CorrectedDeltaIExtractor().extract(df, _meta())
        assert metric is not None
        assert metric.flags == "INSUFFICIENT_FIT_POINTS"
        assert np.isnan(metric.value_float)

    def test_missing_column_returns_none(self):
        df = pl.DataFrame({"t (s)": np.arange(100.0)})
        assert CorrectedDeltaIExtractor().extract(df, _meta()) is None
