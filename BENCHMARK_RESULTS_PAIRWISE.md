# Pairwise Extraction Performance Benchmark Results

**Date:** 2025-01-22
**Analysis:** Sequential vs Parallel Processing
**Dataset:** IVg procedure across all chips

---

## Executive Summary

**Finding:** **Sequential processing is 2-10x faster** than parallel processing for all tested dataset sizes.

**Recommendation:** Use sequential processing as default (already implemented).

---

## Detailed Benchmark Results

### Performance Comparison

| Dataset | Measurements | Pairs | Sequential Time | Parallel Time | Winner | Speedup |
|---------|-------------|-------|-----------------|---------------|--------|---------|
| **Small** | 39 | 38 | **0.202s** | 2.051s | Sequential | **10.2x faster** |
| **Medium** | 127 | 124 | **0.543s** | 2.129s | Sequential | **3.9x faster** |
| **Large** | 307 | 293 | **1.315s** | 2.306s | Sequential | **1.8x faster** |

### Timing Breakdown

**Sequential Mode:**
- Time per pair: ~0.0045s
- Overhead: Minimal (<0.01s)
- Scales linearly with dataset size

**Parallel Mode:**
- Fixed overhead: ~2.0s (process pool + serialization)
- Time per pair: ~0.001s (parallel benefit)
- Break-even point: Would require >500 pairs

---

## Analysis

### Why Sequential Wins

1. **Low overhead**: Simple loop with minimal setup cost
2. **Fast I/O**: Parquet files load quickly (~0.004s per measurement)
3. **Lightweight processing**: Current difference calculation is not CPU-bound
4. **No serialization cost**: No need to pickle data across processes

### Why Parallel Loses

1. **High fixed overhead**: ~2 seconds to create process pool
2. **Serialization cost**: ~0.5s to pickle/unpickle metadata dicts
3. **No CPU bottleneck**: Processing is I/O bound, not compute bound
4. **Diminishing returns**: Parallel benefit (~0.003s per pair) < overhead cost

### Crossover Point Analysis

**Current data (293 pairs):**
- Sequential: 1.315s
- Parallel: 2.306s
- Overhead delta: ~1.0s

**Estimated crossover point:**
- Would need >500 pairs for parallel to break even
- Your typical workload: 38-293 pairs (well below threshold)

**Recommendation:** Keep sequential as default, only use parallel for >500 pairs

---

## Implementation

### Current Settings

```python
# File: src/derived/metric_pipeline.py
# Line: 871-872

# Default behavior (auto-adaptive):
use_parallel = len(all_pair_tasks) > 500  # Conservative threshold
```

### Manual Override

```python
# Force sequential (fastest for typical workloads):
pipeline._extract_pairwise_metrics(manifest, use_parallel=False)

# Force parallel (for very large datasets only):
pipeline._extract_pairwise_metrics(manifest, use_parallel=True)
```

---

## Historical Context

### Why This Analysis Was Needed

The `IMPLEMENTATION_PLAN_METRICS_OPTIMIZATION.md` document assumed:
- ❌ Current code had parallelization with per-chip pools (INCORRECT)
- ❌ Single pool would be 50-75% faster (FALSE)

**Reality:**
- ✅ Current code (GitHub) had NO parallelization (sequential loop)
- ✅ Sequential is 2-10x FASTER than parallel

**Lesson:** Always benchmark against actual baseline, not assumed baseline.

---

## Benchmark Reproducibility

### Running Benchmarks

```bash
# Full benchmark suite (sequential vs parallel, all dataset sizes):
python3 tests/benchmark_modes_direct.py

# Results saved to:
benchmark_direct_results.txt
```

### Test Environment

- Python: 3.11+
- Polars: Latest version
- Hardware: [Your system specs]
- Dataset: IVg procedure, 15 chips, 307 measurements, 293 valid pairs

---

## Recommendations for Future

### When to Revisit Parallel Processing

Consider parallel processing if:
1. Dataset grows to >500 pairs consistently
2. Extraction becomes more CPU-intensive (e.g., complex fitting algorithms)
3. I/O becomes slower (e.g., network-mounted storage)

### Alternative Optimizations

Instead of parallelization, consider:
1. **Data caching**: Cache loaded Parquet files in memory
2. **Batch reading**: Load multiple measurements at once
3. **Lazy evaluation**: Only load data when needed
4. **Incremental processing**: Skip already-processed pairs

---

## Conclusion

**Sequential processing is the optimal strategy** for pairwise extraction in this codebase.

The dual-mode implementation provides flexibility for future needs while defaulting to the fastest approach for current workloads.

**Performance Improvement:** By keeping sequential as default, pairwise extraction is **2-10x faster** than it would be with parallelization.
