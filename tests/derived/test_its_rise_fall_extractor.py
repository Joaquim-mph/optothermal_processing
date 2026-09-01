import json
import sys
import numpy as np
import polars as pl
import pytest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src.derived.algorithms.stretched_exponential import stretched_exponential
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
        assert rise.extraction_method == "ten_ninety_rise"
        assert fall.extraction_method == "ten_ninety_fall"
        assert rise.corrected is False

    def test_corrected_properties(self):
        rise = ITSRiseFallExtractor(mode="rise", corrected=True)
        fall = ITSRiseFallExtractor(mode="fall", corrected=True)
        assert rise.metric_name == "t_rise_corrected"
        assert fall.metric_name == "t_fall_corrected"
        assert rise.applicable_procedures == ["It"]
        assert rise.metric_category == "photoresponse"
        assert rise.extraction_method == (
            "ten_ninety_rise_drift_corrected:stretched_exponential"
        )
        assert ITSRiseFallExtractor(
            mode="fall", corrected=True, drift_model="linear"
        ).extraction_method == "ten_ninety_fall_drift_corrected:linear"

    def test_invalid_drift_model_raises(self):
        with pytest.raises(ValueError, match="unknown drift_model"):
            ITSRiseFallExtractor(mode="rise", drift_model="quadratic")

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


class TestPhaseBaseline:
    def test_tail_mean_full_array(self):
        ext = ITSRiseFallExtractor(mode="rise")  # baseline_frac = 0.2
        i = np.arange(100, dtype=float)
        # last 20% = i[80:100], mean of 80..99
        assert ext._phase_baseline(i, 0, 100) == pytest.approx(89.5)

    def test_tail_mean_flat_tail(self):
        ext = ITSRiseFallExtractor(mode="rise")
        i = np.concatenate([np.linspace(0.0, 10.0, 80), np.full(20, 7.0)])
        assert ext._phase_baseline(i, 0, 100) == pytest.approx(7.0)

    def test_tail_mean_windowed(self):
        ext = ITSRiseFallExtractor(mode="rise")
        i = np.concatenate([np.zeros(5), np.arange(10, dtype=float)])
        # window [5,15) -> seg = 0..9, tail 20% = 2 samples -> mean(8, 9)
        assert ext._phase_baseline(i, 5, 15) == pytest.approx(8.5)


class TestExtremumIdx:
    def test_extremum_negative_deviation(self):
        ext = ITSRiseFallExtractor(mode="rise")
        i = np.array([0.0, 1.0, 2.0, -5.0, 1.0])
        assert ext._extremum_idx(i, 0, 5, 0.0) == 3

    def test_extremum_positive_baseline(self):
        ext = ITSRiseFallExtractor(mode="rise")
        i = np.array([10.0, 11.0, 9.0, 10.0, 13.0])
        assert ext._extremum_idx(i, 0, 5, 10.0) == 4

    def test_extremum_windowed(self):
        ext = ITSRiseFallExtractor(mode="rise")
        i = np.array([0.0, 0.0, 5.0, 1.0, 9.0, 2.0, 0.0])
        # window [2,6) -> seg = [5,1,9,2], max |dev from 0| at rel idx 2
        assert ext._extremum_idx(i, 2, 6, 0.0) == 4


class TestCrossingIndex:
    def test_crossing_going_up(self):
        ext = ITSRiseFallExtractor(mode="rise")
        values = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])
        assert ext._crossing_index(values, 5.0, going_up=True) == 3

    def test_crossing_going_down(self):
        ext = ITSRiseFallExtractor(mode="fall")
        values = np.array([10.0, 8.0, 6.0, 4.0, 2.0, 0.0])
        assert ext._crossing_index(values, 5.0, going_up=False) == 3

    def test_crossing_not_found(self):
        ext = ITSRiseFallExtractor(mode="rise")
        values = np.array([0.0, 1.0, 2.0])
        assert ext._crossing_index(values, 99.0, going_up=True) is None


class TestResponseTime:
    def test_response_positive_span(self):
        ext = ITSRiseFallExtractor(mode="rise")
        t = np.arange(101, dtype=float)
        i = np.linspace(0.0, 100.0, 101)
        sec = ext._response_time(t, i, 0, 101, ref_start=0.0, ref_end=100.0)
        assert sec is not None
        assert sec["idx_10"] == 10
        assert sec["idx_90"] == 90
        assert sec["response_time"] == pytest.approx(80.0)
        assert sec["ref_start"] == pytest.approx(0.0)
        assert sec["ref_end"] == pytest.approx(100.0)

    def test_response_negative_span(self):
        ext = ITSRiseFallExtractor(mode="fall")
        t = np.arange(101, dtype=float)
        i = np.linspace(100.0, 0.0, 101)
        sec = ext._response_time(t, i, 0, 101, ref_start=100.0, ref_end=0.0)
        assert sec is not None
        # going down: level_10 = 90 reached before level_90 = 10
        assert sec["idx_10"] < sec["idx_90"]
        assert sec["response_time"] == pytest.approx(80.0)

    def test_response_offset_baseline(self):
        ext = ITSRiseFallExtractor(mode="rise")
        t = np.arange(101, dtype=float)
        i = np.linspace(50.0, 80.0, 101)
        sec = ext._response_time(t, i, 0, 101, ref_start=50.0, ref_end=80.0)
        assert sec is not None
        assert sec["level_10"] == pytest.approx(53.0)
        assert sec["level_90"] == pytest.approx(77.0)
        assert sec["response_time"] == pytest.approx(80.0)

    def test_response_unreached_returns_none(self):
        ext = ITSRiseFallExtractor(mode="rise")
        t = np.arange(50, dtype=float)
        i = np.linspace(0.0, 100.0, 50)
        # within [0,20) the trace never reaches level_90 = 90
        assert ext._response_time(t, i, 0, 20, ref_start=0.0, ref_end=100.0) is None


class TestFindFirstPeak:
    def test_monotonic_signal_no_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        signal = np.linspace(0.0, 100.0, 300)
        assert ext._find_first_peak(signal) is None

    def test_sign_switch_signal_splits_near_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        up = np.linspace(0.0, 100.0, 150)
        down = np.linspace(100.0, -80.0, 150)
        signal = np.concatenate([up, down])
        result = ext._find_first_peak(signal)
        assert result is not None
        peak_idx, s0 = result
        assert s0 == 1
        assert 140 <= peak_idx <= 158

    def test_brief_dip_not_sustained_no_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        signal = np.linspace(0.0, 300.0, 300).copy()
        signal[150:155] = signal[150]  # 5-sample flat, shorter than min_reversal_run
        assert ext._find_first_peak(signal) is None

    def test_descending_then_rising_negative_s0(self):
        ext = ITSRiseFallExtractor(mode="fall")
        down = np.linspace(100.0, -40.0, 150)
        up = np.linspace(-40.0, 0.0, 150)
        signal = np.concatenate([down, up])
        result = ext._find_first_peak(signal)
        assert result is not None
        peak_idx, s0 = result
        assert s0 == -1
        assert 140 <= peak_idx <= 158


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

    def test_no_pre_dark_returns_none(self):
        # LED on from the very first sample -> no pre-dark phase for the baseline
        ext = ITSRiseFallExtractor(mode="rise")
        light = np.linspace(20.0, 120.0, 300)
        post = np.full(100, 20.0)
        df = _make_trace(np.array([]), light, post)
        assert ext.extract(df, _meta()) is None

    def test_no_post_dark_fall_returns_none(self):
        ext = ITSRiseFallExtractor(mode="fall")
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300)
        df = _make_trace(pre, light, np.array([]))
        assert ext.extract(df, _meta()) is None

    def test_monotonic_positive_rise(self):
        # non-zero dark baseline (20), photoresponse rises to 120
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300)
        post = np.concatenate([np.linspace(120.0, 20.0, 200), np.full(100, 20.0)])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert m.metric_name == "t_rise"
        assert m.unit == "s"
        details = json.loads(m.value_json)
        assert details["n_sections"] == 1
        assert details["sign_switch"] is False
        assert details["pre_baseline"] == pytest.approx(20.0)
        assert details["illum_extremum"] == pytest.approx(120.0)
        # first >=30 at illum idx 30, first >=110 at idx 270 -> 240 samples
        assert m.value_float == pytest.approx(240.0, abs=2.0)

    def test_monotonic_positive_fall(self):
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300)
        post = np.concatenate([np.linspace(120.0, 20.0, 200), np.full(100, 20.0)])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert m is not None
        assert m.metric_name == "t_fall"
        details = json.loads(m.value_json)
        assert details["n_sections"] == 1
        assert details["post_baseline"] == pytest.approx(20.0)
        # decay 120->20: first <=110 at post idx 20, first <=30 at idx 180
        assert m.value_float == pytest.approx(160.0, abs=2.0)

    def test_negative_photoresponse(self):
        # current DROPS under light (baseline 50 -> 25) and recovers afterwards.
        # The baseline-span rule must handle this with no special-casing.
        pre = np.full(100, 50.0)
        light = np.linspace(50.0, 25.0, 300)
        post = np.concatenate([np.linspace(25.0, 50.0, 200), np.full(100, 50.0)])
        df = _make_trace(pre, light, post)

        rise = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert rise is not None
        rd = json.loads(rise.value_json)
        assert rd["n_sections"] == 1
        assert rd["illum_extremum"] == pytest.approx(25.0)
        assert rise.value_float == pytest.approx(240.0, abs=2.0)

        fall = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert fall is not None
        fd = json.loads(fall.value_json)
        assert fd["n_sections"] == 1
        assert fall.value_float == pytest.approx(160.0, abs=2.0)

    def test_flat_illuminated_phase_returns_none(self):
        pre = np.full(100, 30.0)
        light = np.full(300, 30.0)
        post = np.full(300, 30.0)
        df = _make_trace(pre, light, post)
        assert ITSRiseFallExtractor(mode="rise").extract(df, _meta()) is None
        assert ITSRiseFallExtractor(mode="fall").extract(df, _meta()) is None

    def test_negligible_recovery_fall_returns_none(self):
        # post-dark barely relaxes (stays near the illuminated extremum)
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300)
        post = np.full(300, 119.0)
        df = _make_trace(pre, light, post)
        assert ITSRiseFallExtractor(mode="fall").extract(df, _meta()) is None
        # rise still works
        assert ITSRiseFallExtractor(mode="rise").extract(df, _meta()) is not None

    def test_brief_dip_stays_single_section(self):
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300).copy()
        light[150:155] = light[150]  # 5-sample flat, not a sustained reversal
        post = np.concatenate([np.linspace(120.0, 20.0, 200), np.full(100, 20.0)])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert json.loads(m.value_json)["n_sections"] == 1

    def test_sign_switch_rise_two_sections(self):
        pre = np.full(100, 20.0)
        up = np.linspace(20.0, 120.0, 150)
        down = np.linspace(120.0, -40.0, 150)
        light = np.concatenate([up, down])
        post = np.concatenate([np.linspace(-40.0, 20.0, 200), np.full(100, 20.0)])
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
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300)
        down = np.linspace(120.0, 30.0, 150)
        recover = np.linspace(30.0, 80.0, 150)
        post = np.concatenate([down, recover])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert m is not None
        details = json.loads(m.value_json)
        assert details["n_sections"] == 2
        assert "SIGN_SWITCH" in (m.flags or "")
        for sec in details["sections"]:
            assert sec["response_time"] >= 0.0

    def test_rise_onset_clamped_flag(self):
        # first illuminated sample (35) is already past level_10 (30)
        pre = np.full(100, 20.0)
        light = np.linspace(35.0, 120.0, 300)
        post = np.concatenate([np.linspace(120.0, 20.0, 200), np.full(100, 20.0)])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert "RISE_ONSET_CLAMPED" in (m.flags or "")
        assert m.confidence == pytest.approx(0.7)

    def test_fall_onset_clamped_flag(self):
        # first post-dark sample (28) is already past level_90 (30)
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300)
        post = np.concatenate([np.linspace(28.0, 20.0, 200), np.full(100, 20.0)])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert m is not None
        assert "FALL_ONSET_CLAMPED" in (m.flags or "")
        assert m.confidence == pytest.approx(0.7)

    def test_validate_accepts_good_result(self):
        pre = np.full(100, 20.0)
        light = np.linspace(20.0, 120.0, 300)
        post = np.concatenate([np.linspace(120.0, 20.0, 200), np.full(100, 20.0)])
        df = _make_trace(pre, light, post)
        ext = ITSRiseFallExtractor(mode="rise")
        m = ext.extract(df, _meta())
        assert m is not None
        assert ext.validate(m) is True


class TestRegistration:
    def test_exported_from_extractors_package(self):
        from src.derived.extractors import ITSRiseFallExtractor as Exported
        assert Exported is ITSRiseFallExtractor

    def test_registered_in_default_extractors(self):
        from src.derived.metric_pipeline import MetricPipeline
        pipeline = MetricPipeline(base_dir=Path("."))
        names = {e.metric_name for e in pipeline.extractors}
        assert "t_rise" in names
        assert "t_fall" in names
        it_extractors = pipeline.extractor_map.get("It", [])
        it_names = {e.metric_name for e in it_extractors}
        assert {"t_rise", "t_fall"} <= it_names

    def test_corrected_registered_in_default_extractors(self):
        from src.derived.metric_pipeline import MetricPipeline
        pipeline = MetricPipeline(base_dir=Path("."))
        it_names = {e.metric_name for e in pipeline.extractor_map.get("It", [])}
        assert {"t_rise_corrected", "t_fall_corrected"} <= it_names


# ══════════════════════════════════════════════════════════════════════
# Drift-corrected mode (t_rise_corrected / t_fall_corrected)
# ══════════════════════════════════════════════════════════════════════

def _response_trace(n_pre=150, n_light=200, n_decay=100, n_flat=150, amp=2e-6):
    """
    Clean OFF -> ON -> OFF response with an exactly known 10-90 geometry:
    linear ramp up over the light phase, linear ramp down over the first
    `n_decay` post-dark samples, then flat.
    """
    resp = np.concatenate([
        np.zeros(n_pre),
        np.linspace(0.0, amp, n_light),
        np.linspace(amp, 0.0, n_decay),
        np.zeros(n_flat),
    ])
    t = np.arange(len(resp), dtype=float)
    vl = np.concatenate([
        np.zeros(n_pre),
        np.full(n_light, 5.0),
        np.zeros(n_decay + n_flat),
    ])
    return t, resp, vl


def _frame(t, i, vl):
    return pl.DataFrame({"t (s)": t, "I (A)": i, "VL (V)": vl})


class TestCorrectedMode:
    def test_no_op_on_drift_free_trace(self):
        """A flat baseline leaves the 10-90 geometry untouched."""
        t, resp, vl = _response_trace()
        df = _frame(t, resp + 30e-6, vl)
        for mode in ("rise", "fall"):
            raw = ITSRiseFallExtractor(mode=mode).extract(df, _meta())
            corr = ITSRiseFallExtractor(
                mode=mode, corrected=True, drift_model="linear"
            ).extract(df, _meta())
            assert raw is not None and corr is not None
            assert corr.value_float == pytest.approx(raw.value_float, abs=1e-9)

    @pytest.mark.parametrize("mode", ["rise", "fall"])
    def test_linear_drift_recovers_drift_free_time(self, mode):
        """
        A linear drift is removed exactly, so the corrected response time
        matches the one measured on the same trace without drift. Raw does not.
        """
        t, resp, vl = _response_trace()
        clean = _frame(t, resp + 30e-6, vl)
        dirty = _frame(t, resp + 30e-6 + 2e-8 * t, vl)

        truth = ITSRiseFallExtractor(mode=mode).extract(clean, _meta())
        raw = ITSRiseFallExtractor(mode=mode).extract(dirty, _meta())
        corrected = ITSRiseFallExtractor(
            mode=mode, corrected=True, drift_model="linear"
        ).extract(dirty, _meta())

        assert truth is not None and raw is not None and corrected is not None
        assert corrected.value_float == pytest.approx(truth.value_float, abs=1e-9)
        assert raw.value_float != pytest.approx(truth.value_float, abs=1e-9)

    def test_stretched_exponential_drift_improves_rise(self):
        """
        A relaxing dark baseline drags the raw rise time well off the
        drift-free value; subtracting the fitted drift recovers most of it.
        """
        t, resp, vl = _response_trace()
        drift = stretched_exponential(t, 30e-6, 8e-6, 60.0, 0.6)
        clean = _frame(t, resp + 30e-6, vl)
        dirty = _frame(t, resp + drift, vl)

        truth = ITSRiseFallExtractor(mode="rise").extract(clean, _meta())
        raw = ITSRiseFallExtractor(mode="rise").extract(dirty, _meta())
        corrected = ITSRiseFallExtractor(mode="rise", corrected=True).extract(
            dirty, _meta()
        )
        assert truth is not None and raw is not None and corrected is not None
        raw_err = abs(raw.value_float - truth.value_float)
        corr_err = abs(corrected.value_float - truth.value_float)
        assert corr_err < 0.5 * raw_err

    def test_details_carry_the_drift_fit(self):
        t, resp, vl = _response_trace()
        dirty = _frame(t, resp + stretched_exponential(t, 30e-6, 8e-6, 60.0, 0.6), vl)
        m = ITSRiseFallExtractor(mode="rise", corrected=True).extract(dirty, _meta())
        assert m is not None
        d = json.loads(m.value_json)
        assert d["corrected"] is True
        dc = d["drift_correction"]
        assert dc["model"] == "stretched_exponential"
        assert dc["fit_window_s"] == [20.0, 60.0]
        assert dc["n_fit_points"] == 41
        assert dc["converged"] is True
        assert dc["r_squared"] > 0.9
        assert set(dc["fit_params"]) == {"baseline", "amplitude", "tau", "beta"}
        # the raw metric's payload is untouched
        assert set(d) >= {"mode", "n_sections", "sections", "pre_baseline"}

    def test_raw_details_have_no_drift_section(self):
        t, resp, vl = _response_trace()
        df = _frame(t, resp + 30e-6, vl)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        d = json.loads(m.value_json)
        assert "drift_correction" not in d
        assert "corrected" not in d

    def test_confidence_scaled_by_fit_quality(self):
        t, resp, vl = _response_trace()
        rng = np.random.default_rng(0)
        noisy = resp + 30e-6 + rng.normal(0.0, 3e-6, size=len(t))
        m = ITSRiseFallExtractor(
            mode="rise", corrected=True, drift_model="linear"
        ).extract(_frame(t, noisy, vl), _meta())
        assert m is not None
        assert 0.0 <= m.confidence < 1.0
        assert "LOW_R_SQUARED" in (m.flags or "")

    def test_fit_window_truncated_when_light_starts_early(self):
        """LED on at t = 40 s -> the 20-60 s window is clipped to the pre-dark."""
        t, resp, vl = _response_trace(n_pre=40)
        df = _frame(t, resp + 30e-6 + 2e-8 * t, vl)
        m = ITSRiseFallExtractor(
            mode="rise", corrected=True, drift_model="linear"
        ).extract(df, _meta())
        assert m is not None
        assert "FIT_WINDOW_TRUNCATED" in (m.flags or "")
        dc = json.loads(m.value_json)["drift_correction"]
        assert dc["fit_window_s"] == [20.0, 39.0]

    def test_too_short_pre_dark_returns_none(self):
        """Not enough pre-dark samples in the window for a fit."""
        t, resp, vl = _response_trace(n_pre=25)
        df = _frame(t, resp + 30e-6, vl)
        assert ITSRiseFallExtractor(mode="rise", corrected=True).extract(
            df, _meta()
        ) is None

    def test_indices_stay_comparable_with_raw(self):
        """Correction must not resample: details indices address the same samples."""
        t, resp, vl = _response_trace()
        df = _frame(t, resp + 30e-6 + 2e-8 * t, vl)
        corrected = ITSRiseFallExtractor(
            mode="rise", corrected=True, drift_model="linear"
        ).extract(df, _meta())
        assert corrected is not None
        sec = json.loads(corrected.value_json)["sections"][0]
        assert 0 <= sec["idx_10"] < len(t)
        assert 0 <= sec["idx_90"] < len(t)
        assert sec["t_10"] == pytest.approx(float(t[sec["idx_10"]]))
        assert sec["t_90"] == pytest.approx(float(t[sec["idx_90"]]))

    def test_corrected_current_matches_extract_trace(self):
        """The viz helper returns exactly the trace extract() measures on."""
        t, resp, vl = _response_trace()
        i = resp + 30e-6 + 2e-8 * t
        ext = ITSRiseFallExtractor(mode="rise", corrected=True, drift_model="linear")
        i_corr = ext.corrected_current(t, i, vl)
        assert i_corr is not None and i_corr.shape == i.shape
        # drift removed -> the pre-dark baseline sits at ~0
        assert abs(float(np.mean(i_corr[:150]))) < 1e-9
        # the 10/90 crossings from extract() land on this trace's levels
        m = ext.extract(_frame(t, i, vl), _meta())
        sec = json.loads(m.value_json)["sections"][0]
        assert i_corr[sec["idx_10"]] == pytest.approx(sec["level_10"], abs=1e-8)

    def test_corrected_current_none_in_raw_mode(self):
        t, resp, vl = _response_trace()
        ext = ITSRiseFallExtractor(mode="rise")
        assert ext.corrected_current(t, resp + 30e-6, vl) is None

    def test_corrected_current_none_without_pre_dark(self):
        t, resp, vl = _response_trace()
        ext = ITSRiseFallExtractor(mode="rise", corrected=True)
        assert ext.corrected_current(t, resp + 30e-6, np.full_like(vl, 5.0)) is None

    def test_validate_accepts_corrected_result(self):
        t, resp, vl = _response_trace()
        df = _frame(t, resp + 30e-6 + 2e-8 * t, vl)
        ext = ITSRiseFallExtractor(mode="fall", corrected=True, drift_model="linear")
        m = ext.extract(df, _meta())
        assert m is not None
        assert ext.validate(m) is True
        assert m.metric_name == "t_fall_corrected"
        assert m.unit == "s"
