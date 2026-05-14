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
