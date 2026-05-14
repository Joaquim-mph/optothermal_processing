import json
import sys
import numpy as np
import polars as pl
import pytest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

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
