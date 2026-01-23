"""Tests for consecutive sweep difference extractor."""

import pytest
import polars as pl
import numpy as np
import json
from pathlib import Path

from src.derived.extractors.consecutive_sweep_difference import ConsecutiveSweepDifferenceExtractor


def test_consecutive_ivg_difference_basic():
    """Test basic IVg consecutive difference extraction."""

    # Create synthetic IVg sweeps
    vg = np.linspace(-5, 5, 100)

    # Sweep 1: Parabolic I-V curve (CNP at 0V)
    i_1 = 1e-6 * (vg**2 + 1)
    meas_1 = pl.DataFrame({
        "Vg (V)": vg,
        "I (A)": i_1
    })
    metadata_1 = {
        "run_id": "test_ivg_001",
        "chip_number": 67,
        "chip_group": "Test",
        "proc": "IVg",
        "seq_num": 1,
        "vds_v": 0.1,
        "extraction_version": "test"
    }

    # Sweep 2: CNP shifted to -0.5V (simulating illumination effect)
    i_2 = 1e-6 * ((vg + 0.5)**2 + 1)
    meas_2 = pl.DataFrame({
        "Vg (V)": vg,
        "I (A)": i_2
    })
    metadata_2 = {
        "run_id": "test_ivg_002",
        "chip_number": 67,
        "chip_group": "Test",
        "proc": "IVg",
        "seq_num": 2,
        "vds_v": 0.1,
        "extraction_version": "test"
    }

    # Extract difference
    extractor = ConsecutiveSweepDifferenceExtractor()
    results = extractor.extract_pairwise(meas_1, metadata_1, meas_2, metadata_2)

    # Assertions
    assert results is not None, "Extractor should return results"
    assert len(results) == 1, "Should return exactly one metric"

    metric = results[0]
    assert metric.metric_name == "consecutive_sweep_difference"
    assert metric.run_id == "test_ivg_002"  # Linked to second measurement
    assert metric.chip_number == 67
    assert metric.procedure == "IVg"
    assert metric.seq_num == 2
    assert metric.confidence > 0.0, "Confidence should be positive"

    # Check stored details
    details = json.loads(metric.value_json)
    assert details["seq_1"] == 1
    assert details["seq_2"] == 2
    assert details["run_id_1"] == "test_ivg_001"
    assert details["run_id_2"] == "test_ivg_002"
    assert details["procedure"] == "IVg"
    assert details["vg_overlap"] > 9.0, "Should have good Vg overlap"
    assert "delta_i_array" in details, "Should store full ΔI array"
    assert "vg_array" in details, "Should store Vg array"
    assert len(details["vg_array"]) == 200, "Should have 200 interpolation points"


def test_consecutive_vvg_difference_basic():
    """Test basic VVg consecutive difference extraction."""

    # Create synthetic VVg sweeps
    vg = np.linspace(-5, 5, 100)

    # Sweep 1
    vds_1 = 1e-3 * (vg**2 + 1)
    meas_1 = pl.DataFrame({
        "Vg (V)": vg,
        "Vds (V)": vds_1
    })
    metadata_1 = {
        "run_id": "test_vvg_001",
        "chip_number": 67,
        "chip_group": "Test",
        "proc": "VVg",
        "seq_num": 5,
        "ids_v": 1e-6,
        "extraction_version": "test"
    }

    # Sweep 2: Shifted curve
    vds_2 = 1e-3 * ((vg + 0.3)**2 + 1.1)
    meas_2 = pl.DataFrame({
        "Vg (V)": vg,
        "Vds (V)": vds_2
    })
    metadata_2 = {
        "run_id": "test_vvg_002",
        "chip_number": 67,
        "chip_group": "Test",
        "proc": "VVg",
        "seq_num": 6,
        "ids_v": 1e-6,
        "extraction_version": "test"
    }

    # Extract difference
    extractor = ConsecutiveSweepDifferenceExtractor()
    results = extractor.extract_pairwise(meas_1, metadata_1, meas_2, metadata_2)

    # Assertions
    assert results is not None
    assert len(results) == 1

    metric = results[0]
    assert metric.procedure == "VVg"
    assert metric.unit == "V"  # VVg measures voltage

    # Check details
    details = json.loads(metric.value_json)
    assert "delta_vds_array" in details, "Should store full ΔVds array"
    assert details["procedure"] == "VVg"


def test_non_consecutive_rejected():
    """Test that non-consecutive measurements are not paired."""

    extractor = ConsecutiveSweepDifferenceExtractor()

    metadata_1 = {
        "seq_num": 1,
        "proc": "IVg",
        "chip_number": 67,
        "chip_group": "Test"
    }
    metadata_2 = {
        "seq_num": 5,  # Gap!
        "proc": "IVg",
        "chip_number": 67,
        "chip_group": "Test"
    }

    # Should not pair (gap in sequence)
    assert not extractor.should_pair(metadata_1, metadata_2)


def test_mixed_procedures_rejected():
    """Test that IVg and VVg are not paired together."""

    extractor = ConsecutiveSweepDifferenceExtractor()

    metadata_1 = {
        "seq_num": 1,
        "proc": "IVg",
        "chip_number": 67,
        "chip_group": "Test"
    }
    metadata_2 = {
        "seq_num": 2,
        "proc": "VVg",  # Different procedure!
        "chip_number": 67,
        "chip_group": "Test"
    }

    # Should not pair different procedures
    assert not extractor.should_pair(metadata_1, metadata_2)


def test_different_chips_rejected():
    """Test that measurements from different chips are not paired."""

    extractor = ConsecutiveSweepDifferenceExtractor()

    metadata_1 = {
        "seq_num": 1,
        "proc": "IVg",
        "chip_number": 67,
        "chip_group": "Test"
    }
    metadata_2 = {
        "seq_num": 2,
        "proc": "IVg",
        "chip_number": 75,  # Different chip!
        "chip_group": "Test"
    }

    # Should not pair different chips
    assert not extractor.should_pair(metadata_1, metadata_2)


def test_insufficient_overlap_rejected():
    """Test that pairs with insufficient Vg overlap are rejected."""

    # Create sweeps with minimal overlap
    vg_1 = np.linspace(-5, 0, 50)  # -5V to 0V
    vg_2 = np.linspace(-0.5, 5, 50)  # -0.5V to 5V (only 0.5V overlap)

    i_1 = 1e-6 * (vg_1**2 + 1)
    i_2 = 1e-6 * (vg_2**2 + 1)

    meas_1 = pl.DataFrame({"Vg (V)": vg_1, "I (A)": i_1})
    meas_2 = pl.DataFrame({"Vg (V)": vg_2, "I (A)": i_2})

    metadata_1 = {
        "run_id": "test_001",
        "chip_number": 67,
        "chip_group": "Test",
        "proc": "IVg",
        "seq_num": 1,
        "vds_v": 0.1,
        "extraction_version": "test"
    }
    metadata_2 = {
        **metadata_1,
        "run_id": "test_002",
        "seq_num": 2
    }

    # Extract with min_vg_overlap=1.0V (default)
    extractor = ConsecutiveSweepDifferenceExtractor(min_vg_overlap=1.0)
    results = extractor.extract_pairwise(meas_1, metadata_1, meas_2, metadata_2)

    # Should be rejected due to insufficient overlap
    assert results is None, "Should reject pairs with insufficient Vg overlap"


def test_resistance_difference_computed():
    """Test that resistance difference is computed and stored."""

    vg = np.linspace(-5, 5, 100)

    # Sweep 1: Lower resistance
    i_1 = 1e-6 * (vg**2 + 2)  # Higher current
    meas_1 = pl.DataFrame({"Vg (V)": vg, "I (A)": i_1})

    # Sweep 2: Higher resistance
    i_2 = 1e-6 * (vg**2 + 1)  # Lower current
    meas_2 = pl.DataFrame({"Vg (V)": vg, "I (A)": i_2})

    metadata = {
        "run_id": "test",
        "chip_number": 67,
        "chip_group": "Test",
        "proc": "IVg",
        "vds_v": 0.1,
        "extraction_version": "test"
    }

    extractor = ConsecutiveSweepDifferenceExtractor(store_resistance=True)
    results = extractor.extract_pairwise(
        meas_1, {**metadata, "seq_num": 1, "run_id": "test_1"},
        meas_2, {**metadata, "seq_num": 2, "run_id": "test_2"}
    )

    assert results is not None
    details = json.loads(results[0].value_json)

    # Check resistance arrays are stored
    assert "delta_resistance_array" in details, "Should store ΔR array"
    assert "max_delta_resistance" in details
    assert details["max_delta_resistance"] > 0, "Should have positive resistance change"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
