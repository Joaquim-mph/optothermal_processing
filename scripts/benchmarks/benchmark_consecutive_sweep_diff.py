#!/usr/bin/env python3
"""Benchmark script for consecutive sweep difference extractors.

Compares performance of:
1. Scipy-based cubic interpolation (original)
2. Scipy-based linear interpolation
3. Numba-accelerated linear interpolation (new)

Usage:
------
python3 scripts/benchmark_consecutive_sweep_diff.py

Requirements:
-------------
- numba installed: pip install numba
- Staged measurements available in data/02_stage/
"""

from __future__ import annotations
import time
import numpy as np
import polars as pl
from pathlib import Path
from typing import Optional
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.derived.extractors.consecutive_sweep_difference import (
    ConsecutiveSweepDifferenceExtractor,
    NUMBA_AVAILABLE
)
from src.core.utils import read_measurement_parquet


def generate_synthetic_sweeps(n_points: int = 100) -> tuple:
    """Generate synthetic IVg sweeps for benchmarking."""
    # Sweep 1: Dark measurement
    vg_1 = np.linspace(-5, 5, n_points)
    # Simulated graphene FET transfer curve
    i_1 = 1e-6 * (vg_1 + 0.5)**2 + np.random.randn(n_points) * 1e-8

    # Sweep 2: After illumination (CNP shifted)
    vg_2 = np.linspace(-4.8, 5.2, n_points)
    i_2 = 1e-6 * (vg_2 + 0.3)**2 + np.random.randn(n_points) * 1e-8  # CNP shifted by -0.2V

    # Create Polars DataFrames
    df_1 = pl.DataFrame({"Vg (V)": vg_1, "I (A)": i_1})
    df_2 = pl.DataFrame({"Vg (V)": vg_2, "I (A)": i_2})

    # Metadata (run_id must be >= 16 chars for Pydantic validation)
    meta_1 = {
        "run_id": "benchmark_test_seq1_00000001",
        "chip_number": 99,
        "chip_group": "Benchmark",
        "proc": "IVg",
        "seq_num": 1,
        "vds_v": 0.1,
        "extraction_version": "test_v1.0.0"
    }

    meta_2 = {
        "run_id": "benchmark_test_seq2_00000002",
        "chip_number": 99,
        "chip_group": "Benchmark",
        "proc": "IVg",
        "seq_num": 2,
        "vds_v": 0.1,
        "extraction_version": "test_v1.0.0"
    }

    return df_1, meta_1, df_2, meta_2


def benchmark_synthetic_data(n_pairs: int = 100, n_points: int = 100):
    """Benchmark using synthetic data."""
    print(f"Benchmarking with synthetic data: {n_pairs} pairs, {n_points} points/sweep")
    print("=" * 80)

    # Generate test data
    df_1, meta_1, df_2, meta_2 = generate_synthetic_sweeps(n_points)

    results = {}

    # 1. Scipy cubic (original method)
    print("\n1. Testing scipy cubic interpolation...")
    extractor_cubic = ConsecutiveSweepDifferenceExtractor(
        vg_interpolation_points=200,
        interpolation_method='cubic',
        store_resistance=True
    )

    start = time.perf_counter()
    for _ in range(n_pairs):
        metrics = extractor_cubic.extract_pairwise(df_1, meta_1, df_2, meta_2)
    cubic_time = time.perf_counter() - start
    results['scipy_cubic'] = cubic_time
    print(f"   Time: {cubic_time:.4f}s ({cubic_time/n_pairs*1000:.2f}ms per pair)")

    # 2. Scipy linear
    print("\n2. Testing scipy linear interpolation...")
    extractor_scipy_linear = ConsecutiveSweepDifferenceExtractor(
        vg_interpolation_points=200,
        interpolation_method='linear',
        store_resistance=True
    )

    # Force scipy by temporarily disabling Numba
    import src.derived.extractors.consecutive_sweep_difference as csd_module
    original_numba_flag = csd_module.NUMBA_AVAILABLE
    csd_module.NUMBA_AVAILABLE = False

    start = time.perf_counter()
    for _ in range(n_pairs):
        metrics = extractor_scipy_linear.extract_pairwise(df_1, meta_1, df_2, meta_2)
    scipy_linear_time = time.perf_counter() - start
    results['scipy_linear'] = scipy_linear_time
    print(f"   Time: {scipy_linear_time:.4f}s ({scipy_linear_time/n_pairs*1000:.2f}ms per pair)")

    # Restore Numba flag
    csd_module.NUMBA_AVAILABLE = original_numba_flag

    # 3. Numba linear (new accelerated method)
    if NUMBA_AVAILABLE:
        print("\n3. Testing Numba-accelerated linear interpolation...")
        extractor_numba = ConsecutiveSweepDifferenceExtractor(
            vg_interpolation_points=200,
            interpolation_method='linear',
            store_resistance=True
        )

        # Warm up JIT compilation
        _ = extractor_numba.extract_pairwise(df_1, meta_1, df_2, meta_2)

        start = time.perf_counter()
        for _ in range(n_pairs):
            metrics = extractor_numba.extract_pairwise(df_1, meta_1, df_2, meta_2)
        numba_time = time.perf_counter() - start
        results['numba_linear'] = numba_time
        print(f"   Time: {numba_time:.4f}s ({numba_time/n_pairs*1000:.2f}ms per pair)")
    else:
        print("\n3. Numba not available - skipping accelerated test")
        print("   Install with: pip install numba")
        numba_time = None

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\nScipy cubic:       {cubic_time:.4f}s  (baseline)")
    print(f"Scipy linear:      {scipy_linear_time:.4f}s  ({cubic_time/scipy_linear_time:.2f}x faster)")

    if numba_time:
        print(f"Numba linear:      {numba_time:.4f}s  ({cubic_time/numba_time:.2f}x faster)")
        print(f"\n✓ Numba acceleration: {scipy_linear_time/numba_time:.2f}x speedup over scipy linear")
        print(f"✓ Numba vs cubic:     {cubic_time/numba_time:.2f}x speedup over scipy cubic")

    return results


def benchmark_real_data(chip_number: int = 67, n_pairs: int = 10):
    """Benchmark using real staged measurements.

    Parameters
    ----------
    chip_number : int
        Chip number to test with
    n_pairs : int
        Number of consecutive pairs to benchmark

    Note: This requires chip histories, not just the manifest.
    """
    print(f"Benchmarking with real data: Chip {chip_number}, {n_pairs} pairs")
    print("=" * 80)

    # Load chip history (has parquet_path and seq_num)
    history_path = Path(f"data/02_stage/chip_histories/Alisson{chip_number}.parquet")
    if not history_path.exists():
        # Try alternate path
        history_path = Path(f"data/02_stage/chip_histories/Encap{chip_number}.parquet")

    if not history_path.exists():
        print(f"ERROR: Chip history not found for chip {chip_number}")
        print("Run: python3 process_and_analyze.py build-all-histories")
        return None

    manifest = pl.read_parquet(history_path)

    # Filter to IVg measurements for this chip
    chip_manifest = manifest.filter(
        (pl.col("chip_number") == chip_number) &
        (pl.col("proc") == "IVg")
    ).sort("start_time_utc")

    if chip_manifest.height < 2:
        print(f"ERROR: Need at least 2 IVg measurements for chip {chip_number}")
        return None

    # Load first n_pairs consecutive pairs
    pairs = []
    for i in range(min(n_pairs, chip_manifest.height - 1)):
        row_1 = chip_manifest.row(i, named=True)
        row_2 = chip_manifest.row(i + 1, named=True)

        # Add seq_num if not present (for older manifests)
        if "seq_num" not in row_1:
            row_1["seq_num"] = i + 1
        if "seq_num" not in row_2:
            row_2["seq_num"] = i + 2

        # Load measurements
        df_1 = read_measurement_parquet(Path(row_1["parquet_path"]))
        df_2 = read_measurement_parquet(Path(row_2["parquet_path"]))

        pairs.append((df_1, row_1, df_2, row_2))

    print(f"Loaded {len(pairs)} consecutive IVg pairs")

    results = {}

    # Test with cubic
    print("\n1. Testing scipy cubic interpolation...")
    extractor_cubic = ConsecutiveSweepDifferenceExtractor(
        interpolation_method='cubic'
    )

    start = time.perf_counter()
    for df_1, meta_1, df_2, meta_2 in pairs:
        metrics = extractor_cubic.extract_pairwise(df_1, meta_1, df_2, meta_2)
    cubic_time = time.perf_counter() - start
    results['scipy_cubic'] = cubic_time
    print(f"   Time: {cubic_time:.4f}s ({cubic_time/len(pairs)*1000:.2f}ms per pair)")

    # Test with Numba
    if NUMBA_AVAILABLE:
        print("\n2. Testing Numba-accelerated linear interpolation...")
        extractor_numba = ConsecutiveSweepDifferenceExtractor(
            interpolation_method='linear'
        )

        # Warm up
        _ = extractor_numba.extract_pairwise(pairs[0][0], pairs[0][1], pairs[0][2], pairs[0][3])

        start = time.perf_counter()
        for df_1, meta_1, df_2, meta_2 in pairs:
            metrics = extractor_numba.extract_pairwise(df_1, meta_1, df_2, meta_2)
        numba_time = time.perf_counter() - start
        results['numba_linear'] = numba_time
        print(f"   Time: {numba_time:.4f}s ({numba_time/len(pairs)*1000:.2f}ms per pair)")

        print("\n" + "=" * 80)
        print(f"✓ Speedup: {cubic_time/numba_time:.2f}x faster with Numba acceleration")
    else:
        print("\n2. Numba not available - install with: pip install numba")

    return results


def main():
    """Run all benchmarks."""
    print("\n" + "=" * 80)
    print("CONSECUTIVE SWEEP DIFFERENCE EXTRACTOR - PERFORMANCE BENCHMARK")
    print("=" * 80)

    if not NUMBA_AVAILABLE:
        print("\nWARNING: Numba not installed!")
        print("Install with: pip install numba")
        print("\nRunning scipy-only benchmarks...\n")

    # Synthetic data benchmark
    print("\n\nPART 1: SYNTHETIC DATA BENCHMARK")
    print("=" * 80)
    synthetic_results = benchmark_synthetic_data(n_pairs=100, n_points=100)

    # Real data benchmark (optional - requires chip histories)
    history_dir = Path("data/02_stage/chip_histories")
    if history_dir.exists() and list(history_dir.glob("*.parquet")):
        print("\n\nPART 2: REAL DATA BENCHMARK")
        print("=" * 80)
        try:
            real_results = benchmark_real_data(chip_number=67, n_pairs=10)
        except Exception as e:
            print(f"Real data benchmark failed: {e}")
            import traceback
            traceback.print_exc()
            real_results = None
    else:
        print("\n\nPART 2: REAL DATA BENCHMARK - SKIPPED")
        print("=" * 80)
        print("No chip histories found. Run: python3 process_and_analyze.py build-all-histories")
        real_results = None

    # Final summary
    print("\n\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    if NUMBA_AVAILABLE and 'numba_linear' in synthetic_results:
        scipy_time = synthetic_results.get('scipy_cubic', 0)
        numba_time = synthetic_results.get('numba_linear', 0)
        speedup = scipy_time / numba_time if numba_time > 0 else 0

        print(f"\n✓ Numba acceleration provides {speedup:.1f}x speedup on synthetic data")
        print(f"✓ Recommended: Use interpolation_method='linear' (default)")
        print(f"✓ For smoother curves: Use interpolation_method='cubic' (slower)")

        if real_results and 'numba_linear' in real_results:
            real_speedup = real_results['scipy_cubic'] / real_results['numba_linear']
            print(f"\n✓ Real data speedup: {real_speedup:.1f}x faster")
    else:
        print("\n⚠ Install numba for ~8x performance improvement:")
        print("  pip install numba")

    print()


if __name__ == "__main__":
    main()
