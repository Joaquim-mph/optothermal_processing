
import sys
import logging
import pytest
import polars as pl
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Mock numba BEFORE importing any modules
numba_mock = MagicMock()
numba_mock.jit = lambda *args, **kwargs: (lambda f: f)
sys.modules["numba"] = numba_mock

from src.derived.extractors.cnp_extractor import CNPExtractor
from src.derived.extractors.its_relaxation_extractor import ITSRelaxationExtractor
from src.derived.extractors.photoresponse_extractor import PhotoresponseExtractor
from src.derived.extractors.consecutive_sweep_difference import ConsecutiveSweepDifferenceExtractor

# Configure logging to capture output
logging.basicConfig(level=logging.DEBUG)

def verify_log_capture(caplog, expected_reason, expected_level=logging.DEBUG):
    """Helper to verify that a specific reason was logged."""
    for record in caplog.records:
        if record.levelno == expected_level and expected_reason in record.message:
            return True
    return False

def test_cnp_extractor_logging(caplog):
    """Verify CNPExtractor logs correct errors."""
    caplog.set_level(logging.DEBUG)
    extractor = CNPExtractor()
    metadata = {"run_id": "test_run_12345678", "chip_number": 1, "proc": "IVg"}
    
    # 1. Missing Column
    df_missing = pl.DataFrame({"wrong_column": [1, 2, 3]})
    extractor.extract(df_missing, metadata)
    assert verify_log_capture(caplog, "MISSING_COLUMN (Vg (V))")
    caplog.clear()

    # 2. Missing Metadata (IVg needs vds_v)
    df_ivg = pl.DataFrame({"Vg (V)": [1, 2, 3], "I (A)": [1, 2, 3]})
    extractor.extract(df_ivg, metadata)
    assert verify_log_capture(caplog, "MISSING_METADATA (vds_v)")
    caplog.clear()

    print("✓ CNPExtractor logging verified")

def test_its_relaxation_logging(caplog):
    """Verify ITSRelaxationExtractor logs correct errors."""
    caplog.set_level(logging.DEBUG)
    extractor = ITSRelaxationExtractor()
    metadata = {"run_id": "test_run_12345678", "chip_number": 1, "proc": "It"}

    # 1. Missing Columns
    df_missing = pl.DataFrame({"t (s)": [1, 2, 3]})
    extractor.extract(df_missing, metadata)
    # The message will contain the set of missing columns, so we check for partial match
    assert verify_log_capture(caplog, "MISSING_COLUMN")
    caplog.clear()

    # 2. Precondition Failed (No LED ON segment)
    df_dark = pl.DataFrame({
        "t (s)": np.linspace(0, 100, 100),
        "I (A)": np.random.rand(100),
        "VL (V)": np.zeros(100) # All dark
    })
    extractor.extract(df_dark, metadata)
    assert verify_log_capture(caplog, "PRECONDITION_FAILED (No LED ON segment)")
    caplog.clear()

    print("✓ ITSRelaxationExtractor logging verified")

def test_photoresponse_logging(caplog):
    """Verify PhotoresponseExtractor logs correct errors."""
    caplog.set_level(logging.DEBUG)
    extractor = PhotoresponseExtractor()
    metadata = {"run_id": "test_run_12345678", "chip_number": 1, "proc": "It"}

    # 1. Missing VL Column
    df_missing = pl.DataFrame({"t (s)": [1, 2, 3]})
    extractor.extract(df_missing, metadata)
    assert verify_log_capture(caplog, "MISSING_COLUMN (VL (V))")
    caplog.clear()

    print("✓ PhotoresponseExtractor logging verified")

def test_sweep_difference_logging(caplog):
    """Verify ConsecutiveSweepDifferenceExtractor logs correct errors."""
    caplog.set_level(logging.DEBUG)
    extractor = ConsecutiveSweepDifferenceExtractor()
    
    # 1. Procedure Mismatch
    df1 = pl.DataFrame({"Vg (V)": [1, 2], "I (A)": [1, 2]})
    meta1 = {"run_id": "run1", "proc": "IVg", "ids_a": 1e-6}
    df2 = pl.DataFrame({"Vg (V)": [1, 2], "Vds (V)": [1, 2]})
    meta2 = {"run_id": "run2", "proc": "VVg"} # Mismatch

    extractor.extract_pairwise(df1, meta1, df2, meta2)
    assert verify_log_capture(caplog, "Procedure mismatch")
    caplog.clear()

    print("✓ ConsecutiveSweepDifferenceExtractor logging verified")

if __name__ == "__main__":
    # Manually run tests since we are using pytest fixtures (caplog)
    # We'll use pytest.main to run this file
    sys.exit(pytest.main(["-v", __file__]))
