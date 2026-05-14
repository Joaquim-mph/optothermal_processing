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


class TestCrossingIndex:
    def test_crossing_going_up(self):
        ext = ITSRiseFallExtractor(mode="rise")
        values = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])
        # first index with value >= 5.0
        assert ext._crossing_index(values, 5.0, going_up=True) == 3

    def test_crossing_going_down(self):
        ext = ITSRiseFallExtractor(mode="fall")
        values = np.array([10.0, 8.0, 6.0, 4.0, 2.0, 0.0])
        # first index with value <= 5.0
        assert ext._crossing_index(values, 5.0, going_up=False) == 3

    def test_crossing_not_found(self):
        ext = ITSRiseFallExtractor(mode="rise")
        values = np.array([0.0, 1.0, 2.0])
        assert ext._crossing_index(values, 99.0, going_up=True) is None


class TestSectionTime:
    def test_section_rising_toward_positive_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # values 0..100 over 101 samples, t == index
        t = np.arange(101, dtype=float)
        i = np.linspace(0.0, 100.0, 101)
        # extremum at index 100 (value 100); levels 10 and 90
        sec = ext._section_time(t, i, start=0, end=101, extremum_idx=100)
        assert sec is not None
        assert sec["idx_10"] == 10   # first value >= 10
        assert sec["idx_90"] == 90   # first value >= 90
        assert sec["response_time"] == pytest.approx(80.0)
        assert sec["extremum"] == pytest.approx(100.0)

    def test_section_moving_toward_negative_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # section starts at +100, ends at -50 (sign switch); t == index
        t = np.arange(151, dtype=float)
        i = np.linspace(100.0, -50.0, 151)
        # extremum at index 150 (value -50); levels -5 and -45
        sec = ext._section_time(t, i, start=0, end=151, extremum_idx=150)
        assert sec is not None
        # going down: first value <= -5, first value <= -45
        assert sec["idx_10"] < sec["idx_90"]
        assert sec["response_time"] >= 0.0

    def test_section_returns_none_when_level_unreached(self):
        ext = ITSRiseFallExtractor(mode="rise")
        t = np.arange(50, dtype=float)
        i = np.linspace(0.0, 100.0, 50)
        # extremum index points at value 100, but section only covers 0..20
        sec = ext._section_time(t, i, start=0, end=20, extremum_idx=49)
        # within [0,20) max value ~38.8, never reaches 90 -> None
        assert sec is None


class TestSingleFall:
    def test_single_fall_basic(self):
        ext = ITSRiseFallExtractor(mode="fall")
        # relaxation: value decays 100 -> 0 over 101 samples, t == index
        t = np.arange(101, dtype=float)
        i = np.linspace(100.0, 0.0, 101)
        sec = ext._single_fall(t, i, start=0, end=101, i_max=100.0, i_max_idx=0)
        assert sec is not None
        # first value <= 90 at index 10, first value <= 10 at index 90
        assert sec["idx_90"] == 10
        assert sec["idx_10"] == 90
        assert sec["response_time"] == pytest.approx(80.0)

    def test_single_fall_incomplete_decay_returns_none(self):
        ext = ITSRiseFallExtractor(mode="fall")
        t = np.arange(101, dtype=float)
        # decays only to 20, never reaches 10% of i_max (10.0)
        i = np.linspace(100.0, 20.0, 101)
        sec = ext._single_fall(t, i, start=0, end=101, i_max=100.0, i_max_idx=0)
        assert sec is None


class TestFindFirstPeak:
    def test_monotonic_signal_no_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        signal = np.linspace(0.0, 100.0, 300)
        assert ext._find_first_peak(signal) is None

    def test_sign_switch_signal_splits_near_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # rise 0->100 over 150 samples, then fall 100->-80 over 150 samples
        up = np.linspace(0.0, 100.0, 150)
        down = np.linspace(100.0, -80.0, 150)
        signal = np.concatenate([up, down])
        result = ext._find_first_peak(signal)
        assert result is not None
        peak_idx, s0 = result
        assert s0 == 1
        # peak should be located near the turning point (index ~149)
        assert 140 <= peak_idx <= 158

    def test_brief_dip_not_sustained_no_peak(self):
        ext = ITSRiseFallExtractor(mode="rise")
        # mostly rising, with a 5-sample dip that is shorter than
        # min_reversal_run (15) -> must not trigger a split
        signal = np.linspace(0.0, 300.0, 300).copy()
        signal[150:155] = signal[150]  # flat/dip, only 5 samples
        assert ext._find_first_peak(signal) is None

    def test_descending_then_rising_negative_s0(self):
        ext = ITSRiseFallExtractor(mode="fall")
        # decay 100->-40 over 150, then recover -40->0 over 150
        down = np.linspace(100.0, -40.0, 150)
        up = np.linspace(-40.0, 0.0, 150)
        signal = np.concatenate([down, up])
        result = ext._find_first_peak(signal)
        assert result is not None
        peak_idx, s0 = result
        assert s0 == -1
        assert 140 <= peak_idx <= 158


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

    def test_monotonic_rise(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert m.metric_name == "t_rise"
        assert m.unit == "s"
        details = json.loads(m.value_json)
        assert details["n_sections"] == 1
        assert details["sign_switch"] is False
        # light index of first >=10 is 30, first >=90 is 270 -> 240 samples
        assert m.value_float == pytest.approx(240.0, abs=2.0)

    def test_monotonic_fall(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert m is not None
        assert m.metric_name == "t_fall"
        details = json.loads(m.value_json)
        assert details["n_sections"] == 1
        assert m.value_float == pytest.approx(240.0, abs=2.0)

    def test_incomplete_decay_fall_returns_none(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 20.0, 300)  # never reaches 10
        df = _make_trace(pre, light, post)
        assert ITSRiseFallExtractor(mode="fall").extract(df, _meta()) is None
        # rise still works
        assert ITSRiseFallExtractor(mode="rise").extract(df, _meta()) is not None

    def test_brief_dip_stays_single_section(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300).copy()
        light[150:155] = light[150]  # 5-sample dip, not sustained
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert json.loads(m.value_json)["n_sections"] == 1

    def test_sign_switch_rise_two_sections(self):
        pre = np.zeros(100)
        up = np.linspace(0.0, 100.0, 200)
        down = np.linspace(100.0, -80.0, 200)
        light = np.concatenate([up, down])
        post = np.linspace(-80.0, 0.0, 300)
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
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        down = np.linspace(100.0, -60.0, 200)
        recover = np.linspace(-60.0, 0.0, 200)
        post = np.concatenate([down, recover])
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="fall").extract(df, _meta())
        assert m is not None
        details = json.loads(m.value_json)
        assert details["n_sections"] == 2
        assert "SIGN_SWITCH" in (m.flags or "")

    def test_negative_i_max_flag(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, -100.0, 300)  # all-negative photocurrent
        post = np.linspace(-100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        # I_max <= 0 -> NEGATIVE_I_MAX flag set, confidence reduced
        if m is not None:
            assert "NEGATIVE_I_MAX" in (m.flags or "")
            assert m.confidence <= 0.5

    def test_rise_onset_clamped_flag(self):
        # light phase starts already at 20 (>= 10% of I_max=100)
        pre = np.zeros(100)
        light = np.linspace(20.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        m = ITSRiseFallExtractor(mode="rise").extract(df, _meta())
        assert m is not None
        assert "RISE_ONSET_CLAMPED" in (m.flags or "")
        assert m.confidence == pytest.approx(0.7)

    def test_validate_accepts_good_result(self):
        pre = np.zeros(100)
        light = np.linspace(0.0, 100.0, 300)
        post = np.linspace(100.0, 0.0, 300)
        df = _make_trace(pre, light, post)
        ext = ITSRiseFallExtractor(mode="rise")
        m = ext.extract(df, _meta())
        assert m is not None
        assert ext.validate(m) is True
