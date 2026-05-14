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
