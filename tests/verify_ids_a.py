
import yaml
import pytest
import polars as pl
import numpy as np
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Mock numba before importing modules that use it
import sys
from unittest.mock import MagicMock
numba_mock = MagicMock()
numba_mock.jit = lambda *args, **kwargs: (lambda f: f)  # Mock jit as identity decorator
sys.modules["numba"] = numba_mock

from src.derived.extractors.cnp_extractor import CNPExtractor
from src.derived.extractors.consecutive_sweep_difference import ConsecutiveSweepDifferenceExtractor

def test_procedures_yaml_schema():
    """Verify procedures.yml uses ids_a instead of ids_v."""
    config_path = project_root / "config/procedures.yml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Check VVg
    vvg = config["procedures"]["VVg"]["ManifestColumns"]
    assert "ids_a" in vvg, "VVg missing ids_a in ManifestColumns"
    assert "ids_v" not in vvg, "VVg still contains ids_v in ManifestColumns"
    
    # Check Vt
    vt = config["procedures"]["Vt"]["ManifestColumns"]
    assert "ids_a" in vt, "Vt missing ids_a in ManifestColumns"
    assert "ids_v" not in vt, "Vt still contains ids_v in ManifestColumns"
    
    print("✓ procedures.yml schema validated")

def test_cnp_extractor_ids_a():
    """Verify CNPExtractor works with ids_a."""
    extractor = CNPExtractor()
    
    # Mock data for VVg (Vds vs Vg)
    vg = np.linspace(-10, 10, 100)
    ids_val = 1e-6
    # Create a resistance peak at Vg=0
    r = 1000 + 500 * np.exp(-vg**2 / 4)
    vds = r * ids_val
    
    df = pl.DataFrame({
        "Vg (V)": vg,
        "Vds (V)": vds
    })
    
    metadata = {
        "proc": "VVg",
        "ids_a": ids_val,
        "run_id": "test_run_12345678",
        "chip_number": 1,
        "chip_group": "Test"
    }
    
    result = extractor.extract(df, metadata)
    assert result is not None, "CNP extraction failed"
    assert abs(result.value_float) < 0.5, f"CNP should be near 0, got {result.value_float}"
    
    print("✓ CNPExtractor accepts ids_a")

def test_sweep_difference_extractor_ids_a():
    """Verify ConsecutiveSweepDifferenceExtractor works with ids_a."""
    extractor = ConsecutiveSweepDifferenceExtractor()
    
    ids_val = 1e-6
    vg = np.linspace(-10, 10, 100)
    
    # Sweep 1: VVg
    r1 = 1000 * np.ones_like(vg)
    vds1 = r1 * ids_val
    df1 = pl.DataFrame({"Vg (V)": vg, "Vds (V)": vds1})
    meta1 = {"proc": "VVg", "ids_a": ids_val, "run_id": "test_run_12345678", "chip_number": 1, "chip_group": "T", "seq_num": 1}
    
    # Sweep 2: VVg (higher Resistance)
    r2 = 1100 * np.ones_like(vg)
    vds2 = r2 * ids_val
    df2 = pl.DataFrame({"Vg (V)": vg, "Vds (V)": vds2})
    meta2 = {"proc": "VVg", "ids_a": ids_val, "run_id": "test_run_87654321", "chip_number": 1, "chip_group": "T", "seq_num": 2}
    
    results = extractor.extract_pairwise(df1, meta1, df2, meta2)
    assert results is not None
    assert len(results) > 0
    
    metric = results[0]
    assert "delta_voltage" in metric.metric_name
    
    print("✓ ConsecutiveSweepDifferenceExtractor accepts ids_a")

if __name__ == "__main__":
    try:
        test_procedures_yaml_schema()
        test_cnp_extractor_ids_a()
        test_sweep_difference_extractor_ids_a()
        print("\nAll verification tests passed successfully!")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
