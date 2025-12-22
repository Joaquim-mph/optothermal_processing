"""
Benchmark sequential vs parallel pairwise extraction performance.

This script tests both processing modes on different dataset sizes to
determine the optimal crossover point where parallel becomes faster.
"""

import time
import polars as pl
from pathlib import Path
from typing import List, Dict, Any
import statistics
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.derived.metric_pipeline import MetricPipeline


def benchmark_mode(
    pipeline: MetricPipeline,
    manifest: pl.DataFrame,
    use_parallel: bool,
    n_runs: int = 3
) -> Dict[str, Any]:
    """
    Benchmark a single processing mode.

    Parameters
    ----------
    pipeline : MetricPipeline
        Pipeline instance
    manifest : pl.DataFrame
        Filtered manifest for this test
    use_parallel : bool
        Processing mode to test
    n_runs : int
        Number of benchmark runs for averaging

    Returns
    -------
    Dict[str, Any]
        Benchmark results including timings and metrics count
    """
    times = []
    metrics_counts = []

    mode = "parallel" if use_parallel else "sequential"
    print(f"\n{'='*60}")
    print(f"Testing {mode.upper()} mode ({n_runs} runs)")
    print(f"{'='*60}")

    for run in range(n_runs):
        print(f"\nRun {run + 1}/{n_runs}...")

        start = time.perf_counter()
        metrics = pipeline._extract_pairwise_metrics(manifest, use_parallel=use_parallel)
        elapsed = time.perf_counter() - start

        times.append(elapsed)
        metrics_counts.append(len(metrics))

        print(f"  Time: {elapsed:.3f}s")
        print(f"  Metrics: {len(metrics)}")

    return {
        "mode": mode,
        "times": times,
        "mean_time": statistics.mean(times),
        "stdev_time": statistics.stdev(times) if len(times) > 1 else 0,
        "min_time": min(times),
        "max_time": max(times),
        "metrics_count": metrics_counts[0],  # Should be same across runs
        "pairs_per_sec": metrics_counts[0] / statistics.mean(times) if statistics.mean(times) > 0 else 0
    }


def load_manifest_for_chips(
    pipeline: MetricPipeline,
    chip_numbers: List[int],
    procedures: List[str] = ["IVg"]
) -> pl.DataFrame:
    """Load and filter manifest for specific chips."""
    manifest_path = pipeline.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
    manifest = pl.read_parquet(manifest_path)

    # Filter by procedures
    manifest = manifest.filter(pl.col("proc").is_in(procedures))

    # Filter by chips
    manifest = manifest.filter(pl.col("chip_number").is_in(chip_numbers))

    return manifest


def count_expected_pairs(manifest: pl.DataFrame, pipeline: MetricPipeline) -> int:
    """Count how many pairs will be formed from manifest."""
    pair_count = 0

    grouped = manifest.group_by(["chip_number", "proc"])
    for (chip_num, proc), group_df in grouped:
        if proc not in pipeline.pairwise_extractor_map:
            continue

        sorted_group = group_df.sort("start_time_utc")
        rows = sorted_group.to_dicts()

        extractors = pipeline.pairwise_extractor_map[proc]

        for i in range(len(rows) - 1):
            metadata_1 = rows[i]
            metadata_2 = rows[i + 1]

            should_pair = all(
                ext.should_pair(metadata_1, metadata_2)
                for ext in extractors
            )

            if should_pair:
                pair_count += 1

    return pair_count


def print_results_table(results: List[Dict[str, Any]]):
    """Print formatted results table."""
    print("\n" + "="*80)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*80)

    print(f"\n{'Dataset':<15} {'Pairs':<8} {'Mode':<12} {'Mean Time':<12} {'Std Dev':<10} {'Pairs/sec':<10} {'Winner'}")
    print("-"*80)

    # Group by dataset size
    datasets = {}
    for r in results:
        key = r['dataset_name']
        if key not in datasets:
            datasets[key] = {'pairs': r['pair_count'], 'results': []}
        datasets[key]['results'].append(r)

    for dataset_name, data in sorted(datasets.items()):
        pairs = data['pairs']
        results_list = data['results']

        # Find fastest mode
        fastest = min(results_list, key=lambda x: x['mean_time'])

        for r in results_list:
            is_winner = r['mode'] == fastest['mode']
            winner_mark = "  ✓" if is_winner else ""

            print(f"{dataset_name:<15} {pairs:<8} {r['mode']:<12} "
                  f"{r['mean_time']:>8.3f}s   {r['stdev_time']:>6.3f}s   "
                  f"{r['pairs_per_sec']:>8.1f}   {winner_mark}")


def print_crossover_analysis(results: List[Dict[str, Any]]):
    """Analyze and print crossover point."""
    print("\n" + "="*80)
    print("CROSSOVER ANALYSIS")
    print("="*80)

    # Group by dataset
    datasets = {}
    for r in results:
        key = r['dataset_name']
        if key not in datasets:
            datasets[key] = {'pairs': r['pair_count'], 'results': {}}
        datasets[key]['results'][r['mode']] = r

    print(f"\n{'Dataset':<15} {'Pairs':<8} {'Speedup':<12} {'Recommendation'}")
    print("-"*60)

    for dataset_name, data in sorted(datasets.items()):
        pairs = data['pairs']
        seq_time = data['results'].get('sequential', {}).get('mean_time', float('inf'))
        par_time = data['results'].get('parallel', {}).get('mean_time', float('inf'))

        if seq_time > 0 and par_time > 0:
            speedup = seq_time / par_time
            speedup_str = f"{speedup:.2f}x"

            if speedup > 1.1:
                recommendation = "Use PARALLEL"
            elif speedup < 0.9:
                recommendation = "Use SEQUENTIAL"
            else:
                recommendation = "SIMILAR (use sequential)"

            print(f"{dataset_name:<15} {pairs:<8} {speedup_str:<12} {recommendation}")


def main():
    """Run comprehensive benchmarks."""
    print("="*80)
    print("PAIRWISE EXTRACTION PERFORMANCE BENCHMARK")
    print("Sequential vs Parallel Processing")
    print("="*80)

    # Initialize pipeline
    base_dir = Path.cwd()
    pipeline = MetricPipeline(base_dir=base_dir)

    # Define test scenarios
    scenarios = [
        {
            "name": "Small (1 chip)",
            "chips": [67],
            "procedures": ["IVg"],
            "n_runs": 5  # More runs for small datasets
        },
        {
            "name": "Medium (3 chips)",
            "chips": [67, 81, 75],
            "procedures": ["IVg"],
            "n_runs": 3
        },
        {
            "name": "Large (10 chips)",
            "chips": [67, 81, 75, 71, 70, 69, 68, 66, 65, 64],
            "procedures": ["IVg"],
            "n_runs": 3
        },
        {
            "name": "All chips",
            "chips": None,  # All chips
            "procedures": ["IVg"],
            "n_runs": 3
        }
    ]

    all_results = []

    for scenario in scenarios:
        print(f"\n\n{'#'*80}")
        print(f"# SCENARIO: {scenario['name']}")
        print(f"{'#'*80}")

        # Load manifest
        manifest_path = pipeline.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
        manifest = pl.read_parquet(manifest_path)

        # Filter by procedures
        manifest = manifest.filter(pl.col("proc").is_in(scenario["procedures"]))

        # Filter by chips if specified
        if scenario["chips"]:
            manifest = manifest.filter(pl.col("chip_number").is_in(scenario["chips"]))

        # Count expected pairs
        pair_count = count_expected_pairs(manifest, pipeline)
        print(f"\nDataset: {scenario['name']}")
        print(f"Measurements: {manifest.height}")
        print(f"Expected pairs: {pair_count}")

        if pair_count == 0:
            print("⚠️  No pairs to process, skipping...")
            continue

        # Test sequential mode
        seq_results = benchmark_mode(
            pipeline, manifest, use_parallel=False, n_runs=scenario["n_runs"]
        )
        seq_results['dataset_name'] = scenario['name']
        seq_results['pair_count'] = pair_count
        all_results.append(seq_results)

        # Test parallel mode
        par_results = benchmark_mode(
            pipeline, manifest, use_parallel=True, n_runs=scenario["n_runs"]
        )
        par_results['dataset_name'] = scenario['name']
        par_results['pair_count'] = pair_count
        all_results.append(par_results)

        # Show quick comparison
        speedup = seq_results['mean_time'] / par_results['mean_time']
        print(f"\n{'─'*60}")
        print(f"Quick Summary for {scenario['name']}:")
        print(f"  Sequential: {seq_results['mean_time']:.3f}s")
        print(f"  Parallel:   {par_results['mean_time']:.3f}s")
        print(f"  Speedup:    {speedup:.2f}x {'(parallel faster)' if speedup > 1 else '(sequential faster)'}")
        print(f"{'─'*60}")

    # Print comprehensive results
    print_results_table(all_results)
    print_crossover_analysis(all_results)

    # Final recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
Based on the benchmark results above:

1. DEFAULT MODE: Use the mode that performed best for your typical dataset size

2. AUTO-ADAPTIVE: Implement auto-selection based on pair count:
   - If pairs < THRESHOLD: use sequential
   - If pairs >= THRESHOLD: use parallel

3. The current implementation has auto-adaptive logic with threshold = 100 pairs.
   Update this threshold based on your crossover point.

To change the default behavior, modify line 866-867 in src/derived/metric_pipeline.py:
    use_parallel = len(all_pair_tasks) > THRESHOLD  # Adjust THRESHOLD based on results
""")


if __name__ == "__main__":
    main()
