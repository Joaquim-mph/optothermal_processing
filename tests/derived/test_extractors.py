
import json
import sys
import pytest
import numpy as np
import polars as pl
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Mock numba BEFORE importing modules
numba_mock = MagicMock()
numba_mock.jit = lambda *args, **kwargs: (lambda f: f)
numba_mock.prange = range
sys.modules["numba"] = numba_mock

from src.derived.extractors.cnp_extractor import CNPExtractor
from src.derived.extractors.mobility_extractor import MobilityExtractor
from src.derived.extractors.photoresponse_extractor import PhotoresponseExtractor
from src.derived.extractors.its_relaxation_extractor import ITSRelaxationExtractor
from src.derived.extractors.consecutive_sweep_difference import ConsecutiveSweepDifferenceExtractor

class TestCNPExtractor:
    @staticmethod
    def _looped_quadratic_ivg(v_cnp_fwd: float, v_cnp_back: float,
                              n_per_leg: int = 200, vds: float = 0.1):
        """Build a 0 → −10 → +10 → −10 → 0 sweep with quadratic I(Vg) on
        each full-range leg whose vertex sits at the requested CNP."""
        a = 1e-8  # curvature (positive: parabola opens up; min at vertex)
        i_floor = 1e-9

        # 0 → −10 (partial)
        vg_a = np.linspace(0.0, -10.0, n_per_leg // 4, endpoint=False)
        # −10 → +10 (forward, FULL)
        vg_b = np.linspace(-10.0, 10.0, n_per_leg, endpoint=False)
        # +10 → −10 (backward, FULL)
        vg_c = np.linspace(10.0, -10.0, n_per_leg, endpoint=False)
        # −10 → 0 (partial)
        vg_d = np.linspace(-10.0, 0.0, n_per_leg // 4)

        i_a = a * (vg_a - v_cnp_fwd) ** 2 + i_floor
        i_b = a * (vg_b - v_cnp_fwd) ** 2 + i_floor
        i_c = a * (vg_c - v_cnp_back) ** 2 + i_floor
        i_d = a * (vg_d - v_cnp_back) ** 2 + i_floor

        vg = np.concatenate([vg_a, vg_b, vg_c, vg_d])
        i = np.concatenate([i_a, i_b, i_c, i_d])
        return vg, i, vds

    @staticmethod
    def _meta(**overrides):
        m = {
            "run_id": "run_1234567890123456",
            "chip_number": 1,
            "chip_group": "group_0",
            "proc": "IVg",
            "vds_v": 0.1,
            "extraction_version": "test",
        }
        m.update(overrides)
        return m

    def test_looped_sweep_per_direction(self):
        """Looped IVg with different CNP on fwd vs back yields 3 rows."""
        v_fwd, v_back = 1.2, 1.5
        vg, i, vds = self._looped_quadratic_ivg(v_fwd, v_back)
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})

        fwd = CNPExtractor(direction="forward").extract(df, self._meta())
        back = CNPExtractor(direction="backward").extract(df, self._meta())
        avg = CNPExtractor(direction="average").extract(df, self._meta())

        assert fwd is not None
        assert back is not None
        assert avg is not None
        assert fwd.metric_name == "cnp_forward"
        assert back.metric_name == "cnp_backward"
        assert avg.metric_name == "cnp_voltage"  # back-compat name

        assert np.isclose(fwd.value_float, v_fwd, atol=1e-2)
        assert np.isclose(back.value_float, v_back, atol=1e-2)
        assert np.isclose(avg.value_float, 0.5 * (v_fwd + v_back), atol=1e-2)

        details = json.loads(avg.value_json)
        assert details["n_complete_legs"] == 2
        assert np.isclose(details["hysteresis_v"], v_back - v_fwd, atol=1e-2)
        assert "parabola_fwd" in details and "parabola_back" in details

    def test_one_way_sweep_emits_only_forward(self):
        """One-way 0→+10 sweep: forward + average populated, backward None."""
        vg = np.linspace(0.0, 10.0, 500)
        v_cnp = 3.7
        i = 1e-8 * (vg - v_cnp) ** 2 + 1e-9
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})

        fwd = CNPExtractor(direction="forward").extract(df, self._meta())
        back = CNPExtractor(direction="backward").extract(df, self._meta())
        avg = CNPExtractor(direction="average").extract(df, self._meta())

        assert back is None
        assert fwd is not None
        assert avg is not None
        assert np.isclose(fwd.value_float, v_cnp, atol=1e-2)
        assert np.isclose(avg.value_float, v_cnp, atol=1e-2)
        assert avg.flags is not None and "SWEEP_COMPLETE" in avg.flags

    def test_flat_signal_returns_none(self):
        """Constant I with no real minimum: nothing emitted."""
        vg = np.linspace(-10.0, 10.0, 200)
        i = np.full_like(vg, 1e-6)
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})

        for direction in ("forward", "backward", "average"):
            metric = CNPExtractor(direction=direction).extract(df, self._meta())
            assert metric is None

    def test_missing_column(self):
        """Test handling of missing columns."""
        extractor = CNPExtractor()
        df = pl.DataFrame({"Wrong": [1, 2, 3]})
        metadata = {"proc": "IVg", "run_id": "run_1234567890123456"}

        metric = extractor.extract(df, metadata)
        assert metric is None

class TestMobilityExtractor:
    GEOM = {
        "bottom_material": "SiO2",
        "top_hBN_nm": 10.0,
        "bottom_dielectric_nm": 290.0,
        "eps_top": 3.9,
        "eps_bot": 3.9,
        "eps_top_range": (3.9, 3.9),
        "eps_bot_range": (3.9, 3.9),
        "LW": 2.0,
        "LW_range": (2.0, 2.0),
    }

    @staticmethod
    def _quadratic_branches(vg, gm_h_peak, gm_e_peak, v_cnp=0.0,
                            vg_h_edge=-10.0, vg_e_edge=10.0, i_min=1e-9):
        """Piecewise-quadratic I(Vg) chosen so that peak |gm| at the leg
        boundaries equals the requested values.

        I(Vg) = i_min + a_h*(Vg-CNP)^2   for Vg < CNP, with peak |gm_h| at vg_h_edge
        I(Vg) = i_min + a_e*(Vg-CNP)^2   for Vg > CNP, with peak |gm_e| at vg_e_edge

        Sav-Gol order-3 reproduces the derivative of a quadratic exactly, so
        peak |gm| picked by the algorithm equals the requested values.
        """
        a_h = gm_h_peak / (2.0 * abs(vg_h_edge - v_cnp))
        a_e = gm_e_peak / (2.0 * abs(vg_e_edge - v_cnp))
        i = np.where(
            vg < v_cnp,
            i_min + a_h * (vg - v_cnp) ** 2,
            i_min + a_e * (vg - v_cnp) ** 2,
        )
        return i

    @classmethod
    def _looped_ivg(cls, slopes_fwd, slopes_back, v_cnp=0.0, n_per_leg=400):
        """0 → −10 → +10 → −10 → 0 with different peak-|gm| per direction."""
        vg_a = np.linspace(0.0, -10.0, n_per_leg // 4, endpoint=False)
        vg_b = np.linspace(-10.0, 10.0, n_per_leg, endpoint=False)   # forward
        vg_c = np.linspace(10.0, -10.0, n_per_leg, endpoint=False)   # backward
        vg_d = np.linspace(-10.0, 0.0, n_per_leg // 4)

        i_a = cls._quadratic_branches(vg_a, *slopes_back, v_cnp=v_cnp)
        i_b = cls._quadratic_branches(vg_b, *slopes_fwd, v_cnp=v_cnp)
        i_c = cls._quadratic_branches(vg_c, *slopes_back, v_cnp=v_cnp)
        i_d = cls._quadratic_branches(vg_d, *slopes_back, v_cnp=v_cnp)

        vg = np.concatenate([vg_a, vg_b, vg_c, vg_d])
        i = np.concatenate([i_a, i_b, i_c, i_d])
        return vg, i

    @staticmethod
    def _meta(**overrides):
        m = {
            "run_id": "run_1234567890123456",
            "chip_number": 74,
            "chip_group": "Alisson",
            "proc": "IVg",
            "vds_v": 0.1,
            "extraction_version": "test",
        }
        m.update(overrides)
        return m

    @staticmethod
    def _expected_mu(gm, geom=None, vds=0.1):
        from src.derived.algorithms.mobility import cox_per_area
        geom = geom or TestMobilityExtractor.GEOM
        cox = cox_per_area(geom["top_hBN_nm"], geom["eps_top"],
                           geom["bottom_dielectric_nm"], geom["eps_bot"])
        return geom["LW"] * abs(gm) / (cox * abs(vds)) * 1e4

    @patch("src.derived.extractors.mobility_extractor.chip_geometry")
    def test_looped_sweep_all_six_directions(self, mock_geom):
        mock_geom.return_value = self.GEOM
        # (slope_h, slope_e) per direction. Different slopes so we can check
        # that fwd/back/mean are independently computed.
        slopes_fwd = (1.0e-5, 1.2e-5)
        slopes_back = (1.5e-5, 0.8e-5)
        vg, i = self._looped_ivg(slopes_fwd, slopes_back)
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})

        results = {}
        for branch in ("holes", "electrons"):
            for direction in ("forward", "backward", "average"):
                m = MobilityExtractor(
                    branch=branch, direction=direction,
                ).extract(df, self._meta())
                results[(branch, direction)] = m

        # All six rows present.
        for key, m in results.items():
            assert m is not None, f"missing metric {key}"

        # Metric names.
        assert results[("holes", "forward")].metric_name == "mobility_fe_holes_forward"
        assert results[("holes", "backward")].metric_name == "mobility_fe_holes_backward"
        assert results[("holes", "average")].metric_name == "mobility_fe_holes"
        assert results[("electrons", "forward")].metric_name == "mobility_fe_electrons_forward"
        assert results[("electrons", "backward")].metric_name == "mobility_fe_electrons_backward"
        assert results[("electrons", "average")].metric_name == "mobility_fe_electrons"

        # Hole values: |gm_h| = slope_h on the chosen leg.
        mu_h_fwd_expected = self._expected_mu(slopes_fwd[0])
        mu_h_back_expected = self._expected_mu(slopes_back[0])
        assert np.isclose(results[("holes", "forward")].value_float,
                          mu_h_fwd_expected, rtol=0.05)
        assert np.isclose(results[("holes", "backward")].value_float,
                          mu_h_back_expected, rtol=0.05)
        assert np.isclose(results[("holes", "average")].value_float,
                          0.5 * (results[("holes", "forward")].value_float
                                 + results[("holes", "backward")].value_float),
                          rtol=1e-6)

        # Electron values.
        mu_e_fwd_expected = self._expected_mu(slopes_fwd[1])
        mu_e_back_expected = self._expected_mu(slopes_back[1])
        assert np.isclose(results[("electrons", "forward")].value_float,
                          mu_e_fwd_expected, rtol=0.05)
        assert np.isclose(results[("electrons", "backward")].value_float,
                          mu_e_back_expected, rtol=0.05)

        # JSON carries both directions.
        details = json.loads(results[("holes", "average")].value_json)
        assert details["n_complete_legs"] == 2
        assert details["mu_fwd"] is not None
        assert details["mu_back"] is not None

    @patch("src.derived.extractors.mobility_extractor.chip_geometry")
    def test_one_way_sweep_returns_none_for_all(self, mock_geom):
        mock_geom.return_value = self.GEOM
        # Only a one-way forward sweep — no looped backward leg.
        vg = np.linspace(-10.0, 10.0, 400)
        i = self._quadratic_branches(vg, 1e-5, 1e-5)
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})

        # split_full_range_legs will return a single forward leg (covers
        # full range). Forward instance still emits; backward + average
        # return None.
        fwd = MobilityExtractor(branch="holes", direction="forward").extract(df, self._meta())
        back = MobilityExtractor(branch="holes", direction="backward").extract(df, self._meta())
        avg = MobilityExtractor(branch="holes", direction="average").extract(df, self._meta())

        assert fwd is not None
        assert back is None
        assert avg is None  # average requires both directions

    @patch("src.derived.extractors.mobility_extractor.chip_geometry")
    def test_no_full_range_leg_returns_none(self, mock_geom):
        mock_geom.return_value = self.GEOM
        # Tiny range — won't satisfy 95% threshold relative to itself,
        # but more importantly the sweep is too short to qualify. Force
        # a sweep that fails the full-range gate by having all legs <95%.
        # Easiest: a single short monotonic sweep over a tiny window.
        vg = np.linspace(0.0, 0.5, 50)
        i = self._quadratic_branches(vg, 1e-5, 1e-5, v_cnp=0.25)
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})

        # full_range_frac defaults to 0.95; a single forward leg covers
        # 100% of the *measurement's* total range so this actually emits.
        # To make it truly off-pattern, use a sweep with two short oscillations.
        vg2 = np.concatenate([
            np.linspace(0.0, 2.0, 50),
            np.linspace(2.0, 1.0, 30),
            np.linspace(1.0, -10.0, 200),  # only this leg spans the full range
        ])
        i2 = np.zeros_like(vg2) + 1e-9
        df2 = pl.DataFrame({"Vg (V)": vg2, "I (A)": i2})
        # Flat current → gm = 0, mu_central = NaN → returns None.
        for direction in ("forward", "backward", "average"):
            assert MobilityExtractor(
                branch="holes", direction=direction,
            ).extract(df2, self._meta()) is None

    @patch("src.derived.extractors.mobility_extractor.chip_geometry")
    def test_missing_vds_returns_none(self, mock_geom):
        mock_geom.return_value = self.GEOM
        vg = np.linspace(-10.0, 10.0, 200)
        i = self._quadratic_branches(vg, 1e-5, 1e-5)
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})
        meta = self._meta(vds_v=None)
        assert MobilityExtractor(
            branch="holes", direction="forward",
        ).extract(df, meta) is None

    @patch("src.derived.extractors.mobility_extractor.chip_geometry")
    def test_dead_sample_returns_none(self, mock_geom):
        mock_geom.return_value = self.GEOM
        vg = np.linspace(-10.0, 10.0, 200)
        i = self._quadratic_branches(vg, 1e-5, 1e-5)
        df = pl.DataFrame({"Vg (V)": vg, "I (A)": i})
        meta = self._meta(quality_flags="DEAD_SAMPLE,NOISE_HIGH")
        for direction in ("forward", "backward", "average"):
            assert MobilityExtractor(
                branch="holes", direction=direction,
            ).extract(df, meta) is None


class TestPhotoresponseExtractor:
    def test_basic_photoresponse(self):
        """Test basic photoresponse extraction."""
        extractor = PhotoresponseExtractor()
        
        # OFF (0), ON (1e-6), OFF (0)
        t = np.arange(30)
        vl = np.array([0]*10 + [5]*10 + [0]*10)
        current = np.array([1e-9]*10 + [1e-6]*10 + [1e-9]*10)
        
        df = pl.DataFrame({
            "t (s)": t,
            "VL (V)": vl,
            "I (A)": current
        })
        
        metadata = {
            "run_id": "run_1234567890123456",
            "chip_number": 1,
            "chip_group": "group_0",
            "proc": "It",
            "extraction_version": "test"
        }
        
        metric = extractor.extract(df, metadata)
        
        assert metric is not None
        # Photoresponse = last_on - first_on = 1e-6 - 1e-6 = 0 (same values during ON)
        # Actually the implementation computes I(last_ON) - I(first_ON)
        # Since current is constant during ON, delta should be 0
        assert metric.metric_name == "delta_current"

    def test_insufficient_samples(self):
        """Test skipping when samples are insufficient."""
        extractor = PhotoresponseExtractor(min_samples_per_state=50) # Set high req
        t = np.arange(30)
        vl = np.array([0]*10 + [5]*10 + [0]*10)
        current = np.zeros(30)
        
        df = pl.DataFrame({"t (s)": t, "VL (V)": vl, "I (A)": current})
        metadata = {"proc": "It", "run_id": "run_1234567890123456"}
        
        metric = extractor.extract(df, metadata)
        assert metric is None

class TestITSRelaxationExtractor:
    @patch('src.derived.extractors.its_relaxation_extractor.fit_stretched_exponential')
    def test_light_buildup_fit(self, mock_fit):
        """Test fitting of light segment."""
        # Setup mock return
        mock_fit.return_value = {
            'tau': 50.0,
            'beta': 0.8,
            'amplitude': 1e-6,
            'baseline': 0,
            'r_squared': 0.99,
            'n_iterations': 10,
            'converged': True
        }
        
        extractor = ITSRelaxationExtractor(fit_segment="light", min_points_for_fit=5)
        
        # 20 samples: 5 OFF, 15 ON
        t = np.linspace(0, 19, 20)
        vl = np.array([0]*5 + [5]*15)
        current = np.zeros(20) # content doesn't matter as we mock fit
        
        df = pl.DataFrame({
            "t (s)": t,
            "VL (V)": vl,
            "I (A)": current
        })
        
        metadata = {
            "run_id": "run_1234567890123456",
            "chip_number": 1,
            "chip_group": "group_0",
            "proc": "It"
        }
        
        metric = extractor.extract(df, metadata)
        
        assert metric is not None
        assert metric.value_float == 50.0
        assert metric.metric_name == "tau_dark" # Name is always tau_dark per class
        # Verify longest segment logic found the 15 ON points
        # Mock should be called with slice of data
        assert mock_fit.called

class TestConsecutiveSweepDifferenceExtractor:
    def test_should_pair(self):
        """Test pairing logic."""
        extractor = ConsecutiveSweepDifferenceExtractor()
        
        m1 = {"chip_number": 1, "proc": "IVg", "seq_num": 1}
        m2 = {"chip_number": 1, "proc": "IVg", "seq_num": 2} # Consecutive
        m3 = {"chip_number": 1, "proc": "IVg", "seq_num": 4} # Gap
        m4 = {"chip_number": 2, "proc": "IVg", "seq_num": 2} # Different chip
        
        assert extractor.should_pair(m1, m2) is True
        assert extractor.should_pair(m1, m3) is False
        assert extractor.should_pair(m1, m4) is False

    @patch('src.derived.extractors.consecutive_sweep_difference.compute_sweep_difference')
    def test_extract_pairwise(self, mock_diff):
        """Test pairwise extraction flow."""
        # Mock return: vg_common, delta_y, min, max
        mock_diff.return_value = (np.arange(10), np.ones(10), 0, 9)
        
        extractor = ConsecutiveSweepDifferenceExtractor()
        
        df1 = pl.DataFrame({"Vg (V)": np.arange(10), "I (A)": np.zeros(10)})
        df2 = pl.DataFrame({"Vg (V)": np.arange(10), "I (A)": np.ones(10)})
        
        meta1 = {"run_id": "run_1234567890123456", "chip_number": 1, "chip_group": "group_0", "proc": "IVg", "seq_num": 1, "vds_v": 0.1}
        meta2 = {"run_id": "run_1234567890123457", "chip_number": 1, "chip_group": "group_0", "proc": "IVg", "seq_num": 2, "vds_v": 0.1}
        
        metrics = extractor.extract_pairwise(df1, meta1, df2, meta2)
        
        assert metrics is not None
        assert len(metrics) == 1
        metric = metrics[0]
        # Max delta should be 1.0 (from mocked ones)
        assert metric.value_float == 1.0
        assert metric.run_id == "run_1234567890123457"

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
