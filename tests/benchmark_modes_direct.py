"""
Direct benchmark of sequential vs parallel modes.
Tests actual pairwise extraction performance on real data.
"""

import time
import polars as pl
from pathlib import Path
import sys
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.derived.metric_pipeline import MetricPipeline


def benchmark_extraction(pipeline, manifest, mode_name, use_parallel, n_runs=3):
    """Run benchmark for a specific mode."""
    print(f"\n{'='*70}")
    print(f"Mode: {mode_name}")
    print(f"{'='*70}")

    times = []
    metrics_counts = []

    for i in range(n_runs):
        print(f"  Run {i+1}/{n_runs}...", end=" ", flush=True)

        start = time.perf_counter()
        metrics = pipeline._extract_pairwise_metrics(manifest, use_parallel=use_parallel)
        elapsed = time.perf_counter() - start

        times.append(elapsed)
        metrics_counts.append(len(metrics))

        print(f"{elapsed:.3f}s ({len(metrics)} metrics)")

    mean_time = statistics.mean(times)
    std_time = statistics.stdev(times) if len(times) > 1 else 0

    print(f"\n  Summary:")
    print(f"    Mean:   {mean_time:.3f}s ± {std_time:.3f}s")
    print(f"    Min:    {min(times):.3f}s")
    print(f"    Max:    {max(times):.3f}s")
    print(f"    Metrics: {metrics_counts[0]}")

    return {
        "mode": mode_name,
        "times": times,
        "mean": mean_time,
        "std": std_time,
        "metrics": metrics_counts[0]
    }


def main():
    print("="*70)
    print("PAIRWISE EXTRACTION: Sequential vs Parallel Benchmark")
    print("="*70)

    base_dir = Path.cwd()
    pipeline = MetricPipeline(base_dir=base_dir)

    # Load manifest
    manifest_path = pipeline.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
    manifest = pl.read_parquet(manifest_path)

    # Test scenarios
    scenarios = [
        ("1 chip (67)", [67]),
        ("3 chips (67,81,75)", [67, 81, 75]),
        ("All chips", None)
    ]

    all_results = []

    for scenario_name, chips in scenarios:
        print(f"\n\n{'#'*70}")
        print(f"# SCENARIO: {scenario_name}")
        print(f"{'#'*70}")

        # Filter manifest
        manifest_test = manifest.filter(pl.col("proc") == "IVg")
        if chips:
            manifest_test = manifest_test.filter(pl.col("chip_number").is_in(chips))

        print(f"Measurements: {manifest_test.height}")

        # Test sequential mode
        seq_result = benchmark_extraction(
            pipeline, manifest_test, "SEQUENTIAL", use_parallel=False, n_runs=3
        )
        seq_result['scenario'] = scenario_name
        seq_result['measurements'] = manifest_test.height
        all_results.append(seq_result)

        # Test parallel mode
        par_result = benchmark_extraction(
            pipeline, manifest_test, "PARALLEL", use_parallel=True, n_runs=3
        )
        par_result['scenario'] = scenario_name
        par_result['measurements'] = manifest_test.height
        all_results.append(par_result)

        # Compare
        speedup = seq_result['mean'] / par_result['mean']
        print(f"\n  {'─'*66}")
        print(f"  COMPARISON:")
        print(f"    Sequential: {seq_result['mean']:.3f}s")
        print(f"    Parallel:   {par_result['mean']:.3f}s")
        print(f"    Speedup:    {speedup:.2f}x", end="")
        if speedup > 1:
            print(f" (parallel is {speedup:.1f}x FASTER)")
        else:
            print(f" (sequential is {1/speedup:.1f}x FASTER)")
        print(f"  {'─'*66}")

    # Summary table
    print(f"\n\n{'='*70}")
    print("SUMMARY TABLE")
    print(f"{'='*70}")
    print(f"{'Scenario':<20} {'Mode':<12} {'Mean Time':<12} {'Metrics':<8}")
    print(f"{'-'*70}")

    for r in all_results:
        print(f"{r['scenario']:<20} {r['mode']:<12} {r['mean']:>8.3f}s     {r['metrics']:<8}")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")

    scenarios_dict = {}
    for r in all_results:
        if r['scenario'] not in scenarios_dict:
            scenarios_dict[r['scenario']] = {}
        scenarios_dict[r['scenario']][r['mode']] = r

    print(f"\n{'Scenario':<20} {'Measurements':<15} {'Speedup':<12} {'Winner'}")
    print(f"{'-'*70}")

    for scenario_name, modes in scenarios_dict.items():
        seq = modes.get('SEQUENTIAL', {})
        par = modes.get('PARALLEL', {})

        if seq and par:
            speedup = seq['mean'] / par['mean']
            winner = "PARALLEL" if speedup > 1.05 else ("SEQUENTIAL" if speedup < 0.95 else "TIE")

            print(f"{scenario_name:<20} {seq.get('measurements', 0):<15} {speedup:>8.2f}x     {winner}")

    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}")
    print("""
Based on results above:
- If parallel is consistently slower: Keep sequential as default
- If there's a clear crossover point: Implement adaptive threshold
- Current adaptive threshold is 100 pairs (see line 866-867 in metric_pipeline.py)
""")


if __name__ == "__main__":
    main()
