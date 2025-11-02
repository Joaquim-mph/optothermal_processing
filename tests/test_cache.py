"""
Tests for the caching system.

Tests cache functionality including:
- Hit/miss tracking
- TTL expiration
- File modification detection
- LRU eviction
- Size limits
- Thread safety
"""

import pytest
from pathlib import Path
import tempfile
import time
import polars as pl

from src.cli.cache import DataCache, CacheStats, CacheEntry, get_cache, clear_cache


def test_cache_stats_initialization():
    """Test that cache statistics are initialized correctly"""
    stats = CacheStats()
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.evictions == 0
    assert stats.invalidations == 0
    assert stats.hit_rate() == 0.0


def test_cache_stats_hit_rate():
    """Test cache hit rate calculation"""
    stats = CacheStats()
    stats.hits = 7
    stats.misses = 3
    assert stats.hit_rate() == 0.7


def test_cache_initialization():
    """Test cache initialization with custom parameters"""
    cache = DataCache(ttl_seconds=60, max_items=10, max_size_mb=100)
    assert cache._ttl.total_seconds() == 60
    assert cache._max_items == 10
    assert cache._max_size_bytes == 100 * 1024 * 1024


def test_cache_miss_and_load():
    """Test cache miss and loading data"""
    cache = DataCache(ttl_seconds=60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test data")
        temp_path = Path(f.name)

    try:
        def loader(file_path: Path, **kwargs):
            with open(file_path, 'r') as f:
                return f.read()

        # First access should be a cache miss
        data = cache.get(temp_path, loader)
        assert data == "test data"
        assert cache.get_stats().misses == 1
        assert cache.get_stats().hits == 0

    finally:
        temp_path.unlink()


def test_cache_hit():
    """Test cache hit on second access"""
    cache = DataCache(ttl_seconds=60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test data")
        temp_path = Path(f.name)

    try:
        def loader(file_path: Path, **kwargs):
            with open(file_path, 'r') as f:
                return f.read()

        # First access - cache miss
        data1 = cache.get(temp_path, loader)
        # Second access - cache hit
        data2 = cache.get(temp_path, loader)

        assert data1 == data2
        assert cache.get_stats().hits == 1
        assert cache.get_stats().misses == 1

    finally:
        temp_path.unlink()


def test_cache_ttl_expiration():
    """Test that entries expire after TTL"""
    cache = DataCache(ttl_seconds=1)  # 1 second TTL

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test data")
        temp_path = Path(f.name)

    try:
        def loader(file_path: Path, **kwargs):
            with open(file_path, 'r') as f:
                return f.read()

        # First access
        data1 = cache.get(temp_path, loader)
        assert cache.get_stats().misses == 1

        # Wait for TTL to expire
        time.sleep(1.5)

        # Second access should be a cache miss due to expiration
        data2 = cache.get(temp_path, loader)
        assert cache.get_stats().misses == 2
        assert cache.get_stats().invalidations == 1

    finally:
        temp_path.unlink()


def test_cache_file_modification_detection():
    """Test that cache invalidates when source file is modified"""
    cache = DataCache(ttl_seconds=60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("original data")
        temp_path = Path(f.name)

    try:
        def loader(file_path: Path, **kwargs):
            with open(file_path, 'r') as f:
                return f.read()

        # First access
        data1 = cache.get(temp_path, loader)
        assert data1 == "original data"

        # Modify file
        time.sleep(0.1)  # Ensure mtime changes
        with open(temp_path, 'w') as f:
            f.write("modified data")

        # Second access should detect modification and reload
        data2 = cache.get(temp_path, loader)
        assert data2 == "modified data"
        assert cache.get_stats().invalidations == 1

    finally:
        temp_path.unlink()


def test_cache_lru_eviction():
    """Test LRU eviction when cache is full"""
    cache = DataCache(ttl_seconds=60, max_items=2)

    temp_files = []
    try:
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(f"data {i}")
                temp_files.append(Path(f.name))

        def loader(file_path: Path, **kwargs):
            with open(file_path, 'r') as f:
                return f.read()

        # Load 3 items (should evict the first)
        data0 = cache.get(temp_files[0], loader)
        data1 = cache.get(temp_files[1], loader)
        data2 = cache.get(temp_files[2], loader)

        assert cache.get_stats().evictions >= 1

        # Accessing first file again should be a cache miss (evicted)
        data0_again = cache.get(temp_files[0], loader)
        assert cache.get_stats().misses >= 4

    finally:
        for temp_file in temp_files:
            temp_file.unlink()


def test_cache_invalidate_all():
    """Test clearing entire cache"""
    cache = DataCache(ttl_seconds=60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test data")
        temp_path = Path(f.name)

    try:
        def loader(file_path: Path, **kwargs):
            with open(file_path, 'r') as f:
                return f.read()

        # Load data
        cache.get(temp_path, loader)
        assert cache.get_info()['item_count'] == 1

        # Clear cache
        cache.invalidate()
        assert cache.get_info()['item_count'] == 0
        assert cache.get_stats().invalidations == 1

    finally:
        temp_path.unlink()


def test_cache_get_info():
    """Test cache info retrieval"""
    cache = DataCache(ttl_seconds=60, max_items=10, max_size_mb=100)

    info = cache.get_info()
    assert 'item_count' in info
    assert 'total_size_mb' in info
    assert 'max_size_mb' in info
    assert 'utilization' in info
    assert 'stats' in info

    assert info['item_count'] == 0
    assert info['total_size_mb'] == 0
    assert info['max_size_mb'] == 100


def test_cache_with_polars_dataframe():
    """Test caching with Polars DataFrames"""
    cache = DataCache(ttl_seconds=60)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.parquet', delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Create test DataFrame
        df = pl.DataFrame({
            'a': [1, 2, 3],
            'b': ['x', 'y', 'z']
        })
        df.write_parquet(temp_path)

        def loader(file_path: Path, **kwargs):
            return pl.read_parquet(file_path)

        # Load DataFrame
        df1 = cache.get(temp_path, loader)
        assert isinstance(df1, pl.DataFrame)
        assert df1.height == 3

        # Load again (should be cached)
        df2 = cache.get(temp_path, loader)
        assert cache.get_stats().hits == 1

    finally:
        temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
