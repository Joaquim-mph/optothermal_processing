# Data Caching Guide

## Overview

The data caching layer (`src/core/data_cache.py`) provides in-memory caching of parquet files to reduce redundant disk I/O during batch plotting operations. This is particularly effective when multiple plots share common measurement data.

## Quick Start

```bash
# Caching is automatically enabled with batch plotter
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml

# The cache is integrated automatically - no flags needed!
```

## Performance Impact

### Test Results (30 plots, Alisson67)

| Metric | Value |
|--------|-------|
| Total parquet reads | 101 |
| Cache hits | 49 |
| Cache misses | 52 |
| **Hit rate** | **48.5%** |
| Estimated time saved | ~5 seconds |

**Key Insight**: Nearly half of all parquet reads are avoided through caching! This is because plots often share common measurement files (overlapping seq numbers).

### When Caching Helps Most

1. **Large batch sizes** (>20 plots): More opportunities for cache hits
2. **Overlapping data**: Plots that share seq numbers benefit greatly
3. **Sequential plots**: These reuse the same files multiple times
4. **Memory-constrained systems**: Where OS file cache is limited

### When Caching Helps Less

1. **Small batches** (<5 plots): Less data reuse
2. **Unique data per plot**: No overlapping seq numbers
3. **Systems with large RAM**: OS file cache already handles it
4. **Single plot generation**: No benefit from caching

## Features

### File Modification Tracking

The cache automatically invalidates entries if source files are modified:

```python
# File modified after caching
df1 = pl.read_parquet("data.parquet")  # Cache MISS (first read)
df2 = pl.read_parquet("data.parquet")  # Cache HIT (cached)

# ... file is modified externally ...

df3 = pl.read_parquet("data.parquet")  # Cache MISS (invalidated)
```

This prevents stale data from being used in plots.

### LRU Eviction

The cache uses Least Recently Used (LRU) eviction when full:

```python
# Cache limit: 100 items
# When 101st item is cached, oldest unused item is evicted
```

**Configuration**:
```python
from src.core.data_cache import DataCache

# Custom cache size
cache = DataCache(maxsize=200)  # Increase for larger batches
```

### Cache Statistics

Detailed statistics are reported after batch execution:

```
============================================================
Data Cache Statistics
============================================================
Cache size:      52/100 items
Total requests:  101
Cache hits:      49
Cache misses:    52
Hit rate:        48.5%
============================================================

Estimated time saved: ~4.9s from cached reads
```

**Interpretation**:
- **Cache size**: Number of unique files currently cached
- **Total requests**: All parquet read operations
- **Cache hits**: Reads served from cache (no disk I/O)
- **Cache misses**: Reads that required disk I/O
- **Hit rate**: Percentage of requests served from cache
- **Time saved**: Conservative estimate (assumes 100ms per hit)

## Advanced Usage

### Programmatic Access

```python
from src.core.data_cache import enable_parquet_caching, cache_stats, print_cache_stats

# Enable caching
enable_parquet_caching()

# Run your plotting code
# ...

# Check statistics
stats = cache_stats()
print(f"Hit rate: {stats['hit_rate_pct']}")

# Or print formatted output
print_cache_stats()
```

### Manual Caching

```python
from src.core.data_cache import cached_read_parquet
from pathlib import Path

# Use cached reads directly
df = cached_read_parquet(Path("data/file.parquet"))
```

### Cache Management

```python
from src.core.data_cache import clear_cache

# Clear cache to free memory
clear_cache()
```

### Custom Cache Decorator

For caching arbitrary functions:

```python
from src.core.data_cache import with_cache

@with_cache(cache_key_fn=lambda x, y: f"{x}_{y}")
def expensive_computation(x: int, y: int) -> int:
    # ... expensive calculation ...
    return x ** y

result1 = expensive_computation(2, 10)  # MISS (computed)
result2 = expensive_computation(2, 10)  # HIT (cached)
```

## Integration with Batch Plotter

The batch plotter automatically integrates with the data cache (no flags needed):

```bash
# Caching is automatic
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml

# Combine with parallel mode
python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --parallel 4
```

### How It Works

1. **Initialization**: Monkey-patches `pl.read_parquet` to use cache
2. **First read**: File loaded from disk, cached with modification time
3. **Subsequent reads**: Served from cache (if file unmodified)
4. **Statistics**: Displayed at end of batch execution

## Implementation Details

### Cache Key Generation

```python
# Absolute path used as cache key
path = Path("data/measurements/file.parquet").resolve()
cache_key = f"parquet:{path}"
```

This ensures consistent caching regardless of relative/absolute path usage.

### File Modification Detection

```python
# Cached item stores file modification time
cached_item = CachedItem(
    value=dataframe,
    file_mtime=1699234567.123  # Unix timestamp
)

# On cache lookup
current_mtime = path.stat().st_mtime
if current_mtime > cached_item.file_mtime:
    # File modified - invalidate cache
    return None
```

### Memory Efficiency

The cache stores DataFrame references, not copies:

```python
# Same DataFrame object referenced in cache
df1 = cached_read_parquet("file.parquet")  # MISS
df2 = cached_read_parquet("file.parquet")  # HIT
assert df1 is df2  # True - same object!
```

**Important**: Don't modify cached DataFrames in-place!

## Best Practices

### DO:

✅ Enable caching for batch operations (>5 plots)
✅ Use with plots that share common data
✅ Let the cache auto-invalidate on file changes
✅ Check hit rate to assess benefit
✅ Combine with parallel execution for maximum speedup

### DON'T:

❌ Enable for single plot generation (no benefit)
❌ Modify cached DataFrames in-place (affects all references)
❌ Set maxsize too high (wastes memory)
❌ Assume caching always helps (measure performance)
❌ Cache non-file sources (URLs, buffers, etc.)

## Troubleshooting

### Low Hit Rate (<20%)

**Possible causes**:
- Plots don't share common data
- Each plot uses unique files
- Batch size too small

**Solutions**:
- Review plot configuration for data reuse opportunities
- Disable caching if hit rate remains low
- Combine related plots into single batch

### High Memory Usage

**Possible causes**:
- Cache size too large
- Large parquet files cached

**Solutions**:
```python
# Reduce cache size
from src.core.data_cache import DataCache
cache = DataCache(maxsize=50)  # Default: 100
```

### Stale Data Issues

**Should not happen** - cache auto-invalidates on file modification.

If you suspect stale data:
```python
from src.core.data_cache import clear_cache
clear_cache()
```

Or restart the Python process to clear all caches.

### Cache Not Available

```
Warning: Caching module not found, proceeding without cache
```

**Solution**: Ensure `src/core/data_cache.py` is properly installed in the project.

## Performance Tuning

### Optimal Cache Size

```python
# Rule of thumb: maxsize = (unique files in batch) × 1.5

# For 30 plots with ~50 unique files
cache = DataCache(maxsize=75)

# For 100 plots with ~150 unique files
cache = DataCache(maxsize=225)
```

### Memory vs Speed Tradeoff

| Cache Size | Memory Use | Hit Rate | Notes |
|-----------|-----------|----------|-------|
| 25 | ~50-100 MB | 30-40% | Minimal overhead |
| 100 (default) | ~200-400 MB | 45-60% | Balanced |
| 200 | ~400-800 MB | 50-70% | Maximum benefit |

**Recommendation**: Start with default (100), increase if memory permits and hit rate is high.

## Comparison with CLI Cache

The project has two caching systems:

| Feature | `data_cache.py` | `src/cli/cache.py` |
|---------|----------------|-------------------|
| **Purpose** | Batch plotting | CLI commands |
| **TTL** | None (manual clear) | 300s (configurable) |
| **Thread-safe** | No | Yes |
| **File tracking** | Yes | Yes |
| **Size limit** | Count-based (100) | Size-based (500 MB) |
| **Statistics** | Yes | Yes |
| **Use case** | Short-lived batch jobs | Long-running CLI sessions |

**When to use which**:
- `data_cache.py`: Batch plotting (this guide)
- `src/cli/cache.py`: Interactive CLI usage

## Example Configurations

### High-Memory Server (32+ GB RAM)

```python
# Aggressive caching
cache = DataCache(maxsize=500)
```

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/config.yaml --parallel 8
```

### Laptop (8-16 GB RAM)

```python
# Conservative caching (default)
cache = DataCache(maxsize=100)
```

```bash
python3 process_and_analyze.py batch-plot config/batch_plots/config.yaml --parallel 2
```

### Low-Memory VM (4 GB RAM)

```python
# Minimal caching
cache = DataCache(maxsize=25)
```

```bash
# Use small batches
python3 process_and_analyze.py batch-plot config/batch_plots/config.yaml --parallel 1
```

## See Also

- `BATCH_PLOTTING_GUIDE.md` - Batch plotter usage guide
- `BATCH_PLOTTING_GUIDE.md` - Includes performance benchmarks (previously in BATCH_PLOT_RESULTS.md)
- `src/cli/cache.py` - CLI caching system (different use case)
- `src/core/data_cache.py` - Source code with inline documentation
- `src/plotting/batch.py` - Batch plotting engine
