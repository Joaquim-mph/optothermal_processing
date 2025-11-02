# Implementation Prompt: Phase 2 - Caching Layer & Command Context Object

## Context: What We've Already Built

✅ **Configuration Management Layer (Phase 1 - COMPLETE)**
- Centralized configuration system with 25+ fields
- Multiple configuration sources (CLI, files, env vars)
- Global options (`--verbose`, `--config`, `--dry-run`)
- Config commands (`config-init`, `config-show`, etc.)
- All 18 command functions updated to use `get_config()`

## Objective: Next Critical Upgrades

Implement the **two highest-priority architectural improvements** to enhance performance and maintainability:

1. **Caching Layer** - Speed up repeated operations by caching loaded data
2. **Command Context Object** - Unify scattered resource management into a single context

These upgrades will provide immediate user benefits (faster commands) and cleaner architecture (easier maintenance).

---

# Part 1: Caching Layer

## Problem Statement

Users frequently run multiple commands on the same data:

```bash
# Load history from disk
python process_and_analyze.py plot-its 67 --seq 52,57

# Load same history again (wasteful!)
python process_and_analyze.py plot-its 67 --seq 58,59

# Load same history yet again (even more wasteful!)
python process_and_analyze.py plot-ivg 67 --auto
```

**Current issues:**
- Every command re-loads the same Parquet files from disk
- No memory of what's been loaded before
- Slow for interactive workflows
- Wasteful I/O operations

**Solution:** Cache loaded histories and expensive operations in memory with automatic invalidation.

## Files to Create

### 1. `src/cli/cache.py`

Create a comprehensive caching system:

**Requirements:**
- Thread-safe caching (use `threading.Lock`)
- TTL-based expiration (from config: `cache_ttl`)
- LRU eviction when cache is full
- File modification time tracking for invalidation
- Statistics tracking (hits, misses, evictions)
- Size limits (max cached items)

**Core Classes:**

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Dict
import polars as pl
from datetime import datetime, timedelta
import threading
import hashlib

@dataclass
class CacheEntry:
    """Single cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    file_mtime: Optional[float]  # File modification time for invalidation
    access_count: int
    size_bytes: int  # Approximate memory size

class CacheStats:
    """Cache statistics for monitoring"""
    def __init__(self):
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0
        self.invalidations: int = 0
    
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def __str__(self) -> str:
        return f"Hits: {self.hits}, Misses: {self.misses}, Hit Rate: {self.hit_rate():.1%}"

class DataCache:
    """Thread-safe cache for loaded data with TTL and invalidation"""
    
    def __init__(
        self,
        ttl_seconds: int = 300,
        max_items: int = 50,
        max_size_mb: int = 500
    ):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cached items
            max_items: Maximum number of items to cache
            max_size_mb: Maximum cache size in megabytes
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_items = max_items
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._stats = CacheStats()
    
    def _generate_key(self, file_path: Path, **kwargs) -> str:
        """Generate unique cache key from file path and parameters"""
        # Include file path and any filtering parameters
        key_parts = [str(file_path.resolve())]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry has expired"""
        age = datetime.now() - entry.created_at
        return age > self._ttl
    
    def _is_file_modified(self, entry: CacheEntry, file_path: Path) -> bool:
        """Check if source file has been modified since caching"""
        if entry.file_mtime is None:
            return False
        if not file_path.exists():
            return True
        return file_path.stat().st_mtime > entry.file_mtime
    
    def _evict_lru(self):
        """Evict least recently used item"""
        if not self._cache:
            return
        
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed
        )
        del self._cache[lru_key]
        self._stats.evictions += 1
    
    def _enforce_size_limit(self):
        """Evict items if cache exceeds size limit"""
        current_size = sum(entry.size_bytes for entry in self._cache.values())
        while current_size > self._max_size_bytes and self._cache:
            self._evict_lru()
            current_size = sum(entry.size_bytes for entry in self._cache.values())
    
    def get(
        self,
        file_path: Path,
        loader_fn: callable,
        **kwargs
    ) -> Any:
        """
        Get data from cache or load using loader function.
        
        Args:
            file_path: Path to data file
            loader_fn: Function to load data if not cached
            **kwargs: Additional parameters for cache key generation
        
        Returns:
            Cached or loaded data
        """
        key = self._generate_key(file_path, **kwargs)
        
        with self._lock:
            # Check if in cache
            if key in self._cache:
                entry = self._cache[key]
                
                # Check expiration
                if self._is_expired(entry):
                    del self._cache[key]
                    self._stats.invalidations += 1
                # Check file modification
                elif self._is_file_modified(entry, file_path):
                    del self._cache[key]
                    self._stats.invalidations += 1
                else:
                    # Cache hit!
                    entry.last_accessed = datetime.now()
                    entry.access_count += 1
                    self._stats.hits += 1
                    return entry.value
            
            # Cache miss - need to load
            self._stats.misses += 1
        
        # Load data (outside lock to avoid blocking)
        data = loader_fn(file_path, **kwargs)
        
        # Estimate size (rough approximation)
        if isinstance(data, pl.DataFrame):
            size_bytes = data.estimated_size()
        else:
            size_bytes = 1024  # Default estimate
        
        # Store in cache
        with self._lock:
            # Enforce item limit
            if len(self._cache) >= self._max_items:
                self._evict_lru()
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=data,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                file_mtime=file_path.stat().st_mtime if file_path.exists() else None,
                access_count=1,
                size_bytes=size_bytes
            )
            self._cache[key] = entry
            
            # Enforce size limit
            self._enforce_size_limit()
        
        return data
    
    def invalidate(self, file_path: Optional[Path] = None):
        """
        Invalidate cache entries.
        
        Args:
            file_path: If provided, only invalidate entries for this file.
                      If None, clear entire cache.
        """
        with self._lock:
            if file_path is None:
                # Clear entire cache
                self._stats.invalidations += len(self._cache)
                self._cache.clear()
            else:
                # Invalidate entries matching file path
                keys_to_remove = [
                    key for key, entry in self._cache.items()
                    if file_path.resolve() in str(key)
                ]
                for key in keys_to_remove:
                    del self._cache[key]
                    self._stats.invalidations += 1
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        return self._stats
    
    def get_info(self) -> dict:
        """Get detailed cache information"""
        with self._lock:
            total_size = sum(entry.size_bytes for entry in self._cache.values())
            return {
                "item_count": len(self._cache),
                "total_size_mb": total_size / (1024 * 1024),
                "max_size_mb": self._max_size_bytes / (1024 * 1024),
                "utilization": total_size / self._max_size_bytes if self._max_size_bytes > 0 else 0,
                "stats": str(self._stats)
            }
    
    def cleanup_expired(self):
        """Remove expired entries from cache"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]
            for key in expired_keys:
                del self._cache[key]
                self._stats.invalidations += 1

# Global cache instance
_cache: Optional[DataCache] = None

def get_cache() -> DataCache:
    """Get or create global cache instance"""
    global _cache
    if _cache is None:
        from src.cli.main import get_config
        config = get_config()
        _cache = DataCache(
            ttl_seconds=config.cache_ttl,
            max_items=50,
            max_size_mb=500
        )
    return _cache

def clear_cache():
    """Clear global cache"""
    global _cache
    if _cache is not None:
        _cache.invalidate()
```

**Helper Functions:**

```python
def load_history_cached(
    history_file: Path,
    filters: Optional[dict] = None
) -> pl.DataFrame:
    """
    Load chip history with caching.
    
    Args:
        history_file: Path to history Parquet file
        filters: Optional filters to apply
    
    Returns:
        Loaded and filtered history DataFrame
    """
    cache = get_cache()
    
    def loader(file_path: Path, **kwargs) -> pl.DataFrame:
        # Load from disk
        history = pl.read_parquet(file_path)
        
        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if key in history.columns:
                    history = history.filter(pl.col(key) == value)
        
        return history
    
    return cache.get(
        history_file,
        loader,
        filters=filters or {}
    )

def load_parquet_cached(file_path: Path) -> pl.DataFrame:
    """Load Parquet file with caching"""
    cache = get_cache()
    return cache.get(
        file_path,
        lambda p, **kw: pl.read_parquet(p)
    )
```

### 2. `src/cli/commands/cache.py`

Create cache management commands:

**Commands to Implement:**

```python
from src.cli.cache import get_cache, clear_cache
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import typer

console = Console()

def cache_stats_command():
    """Display cache statistics and performance metrics"""
    cache = get_cache()
    stats = cache.get_stats()
    info = cache.get_info()
    
    # Create stats table
    table = Table(title="Cache Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Cache Hits", str(stats.hits))
    table.add_row("Cache Misses", str(stats.misses))
    table.add_row("Hit Rate", f"{stats.hit_rate():.1%}")
    table.add_row("Evictions", str(stats.evictions))
    table.add_row("Invalidations", str(stats.invalidations))
    table.add_row("", "")  # Separator
    table.add_row("Cached Items", str(info['item_count']))
    table.add_row("Cache Size", f"{info['total_size_mb']:.1f} MB")
    table.add_row("Max Size", f"{info['max_size_mb']:.1f} MB")
    table.add_row("Utilization", f"{info['utilization']:.1%}")
    
    console.print(table)
    
    # Performance tip
    if stats.hit_rate() < 0.5 and stats.hits + stats.misses > 10:
        console.print(
            "\n[yellow]💡 Tip:[/yellow] Low hit rate. Consider increasing "
            "cache_ttl in config for better performance."
        )

def cache_clear_command(
    confirm: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt"
    )
):
    """Clear all cached data"""
    if not confirm:
        from rich.prompt import Confirm
        if not Confirm.ask("Clear all cached data?"):
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)
    
    cache = get_cache()
    stats_before = cache.get_stats()
    
    clear_cache()
    
    console.print(
        f"[green]✓[/green] Cache cleared "
        f"({stats_before.hits + stats_before.misses} operations cached)"
    )

def cache_info_command():
    """Show detailed cache information"""
    cache = get_cache()
    info = cache.get_info()
    
    lines = [
        f"[cyan]Status:[/cyan] {'Enabled' if True else 'Disabled'}",
        f"[cyan]Items Cached:[/cyan] {info['item_count']}",
        f"[cyan]Memory Used:[/cyan] {info['total_size_mb']:.1f} MB / {info['max_size_mb']:.1f} MB",
        f"[cyan]Utilization:[/cyan] {info['utilization']:.1%}",
        "",
        info['stats']
    ]
    
    panel = Panel(
        "\n".join(lines),
        title="Cache Information",
        border_style="cyan"
    )
    console.print(panel)

def cache_warmup_command(
    chips: str = typer.Argument(..., help="Chip numbers (comma-separated)"),
    chip_group: str = typer.Option("Alisson", "--chip-group", "-g", help="Chip group prefix"),
):
    """Pre-load chip histories into cache"""
    from src.cli.main import get_config
    from src.cli.cache import load_history_cached
    from pathlib import Path
    
    config = get_config()
    cache = get_cache()
    
    # Parse chip numbers
    chip_numbers = [int(c.strip()) for c in chips.split(",")]
    
    console.print(f"[cyan]Warming up cache for {len(chip_numbers)} chips...[/cyan]")
    
    success_count = 0
    for chip in chip_numbers:
        history_file = config.history_dir / f"{chip_group}{chip}_history.parquet"
        
        if not history_file.exists():
            console.print(f"  [yellow]⚠[/yellow] Chip {chip}: history not found")
            continue
        
        try:
            load_history_cached(history_file)
            console.print(f"  [green]✓[/green] Chip {chip}: loaded")
            success_count += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] Chip {chip}: {e}")
    
    console.print(
        f"\n[green]✓[/green] Cache warmed up: "
        f"{success_count}/{len(chip_numbers)} chips loaded"
    )
    
    # Show stats
    cache_stats_command()
```

**Register commands in main.py:**
```python
from src.cli.commands.cache import (
    cache_stats_command,
    cache_clear_command,
    cache_info_command,
    cache_warmup_command
)

app.command(name="cache-stats")(cache_stats_command)
app.command(name="cache-clear")(cache_clear_command)
app.command(name="cache-info")(cache_info_command)
app.command(name="cache-warmup")(cache_warmup_command)
```

### 3. Update Commands to Use Cache

**Files to modify:**
- `src/cli/commands/plot_its.py`
- `src/cli/commands/plot_ivg.py`
- `src/cli/commands/plot_transconductance.py`
- `src/cli/helpers.py`

**Pattern:**

**Before:**
```python
def plot_its_command(...):
    history = pl.read_parquet(history_file)
```

**After:**
```python
from src.cli.cache import load_history_cached

def plot_its_command(...):
    config = get_config()
    
    # Use cached loading
    history = load_history_cached(
        history_file,
        filters={"vg": vg_filter} if vg_filter else None
    )
    
    if config.verbose:
        cache = get_cache()
        stats = cache.get_stats()
        console.print(f"[dim]Cache: {stats}[/dim]")
```

**Update `src/cli/helpers.py`:**

```python
def auto_select_experiments(...):
    """Auto-select experiments using cached history loading"""
    from src.cli.cache import load_history_cached
    
    config = get_config()
    history_file = config.history_dir / f"{chip_group}{chip}_history.parquet"
    
    # Use cache
    history = load_history_cached(history_file)
    
    # ... rest of logic
```

### 4. Update Config to Support Caching

**Add to `src/cli/config.py`:**

```python
class CLIConfig(BaseModel):
    # ... existing fields ...
    
    # Caching settings
    cache_enabled: bool = Field(
        default=True,
        description="Enable caching for loaded data"
    )
    cache_ttl: int = Field(
        default=300,
        ge=0,
        description="Cache time-to-live in seconds"
    )
    cache_max_items: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of items in cache"
    )
    cache_max_size_mb: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="Maximum cache size in megabytes"
    )
```

---

# Part 2: Command Context Object

## Problem Statement

Currently, commands have scattered resource management:

```python
def plot_its_command(...):
    console = Console()  # Created in every command
    config = get_config()  # Called in every command
    # No cache reference
    # No shared state
```

**Issues:**
- Duplicated initialization code
- Hard to test (need to mock multiple imports)
- No centralized state management
- Verbose command implementations

**Solution:** Single context object containing all shared resources.

## Files to Create/Modify

### 1. `src/cli/context.py`

Create command context class:

```python
from dataclasses import dataclass
from rich.console import Console
from src.cli.config import CLIConfig
from src.cli.cache import DataCache, get_cache
from typing import Optional

@dataclass
class CommandContext:
    """Shared context for all CLI commands"""
    
    console: Console
    config: CLIConfig
    cache: DataCache
    
    # Convenience properties from config
    @property
    def verbose(self) -> bool:
        return self.config.verbose
    
    @property
    def dry_run(self) -> bool:
        return self.config.dry_run
    
    @property
    def output_dir(self):
        return self.config.output_dir
    
    @property
    def history_dir(self):
        return self.config.history_dir
    
    @property
    def stage_dir(self):
        return self.config.stage_dir
    
    # Convenience methods
    def print(self, *args, **kwargs):
        """Print to console"""
        self.console.print(*args, **kwargs)
    
    def print_verbose(self, *args, **kwargs):
        """Print only if verbose mode enabled"""
        if self.verbose:
            self.console.print(*args, **kwargs)
    
    def print_error(self, message: str):
        """Print error message"""
        self.console.print(f"[red]Error:[/red] {message}")
    
    def print_success(self, message: str):
        """Print success message"""
        self.console.print(f"[green]✓[/green] {message}")
    
    def print_warning(self, message: str):
        """Print warning message"""
        self.console.print(f"[yellow]⚠[/yellow] {message}")
    
    def confirm_action(self, prompt: str) -> bool:
        """Prompt user for confirmation (returns True in dry-run)"""
        if self.dry_run:
            self.print(f"[dim][DRY RUN] Would ask: {prompt}[/dim]")
            return True
        
        from rich.prompt import Confirm
        return Confirm.ask(prompt)

# Global context
_context: Optional[CommandContext] = None

def get_context() -> CommandContext:
    """Get or create global command context"""
    global _context
    if _context is None:
        from src.cli.main import get_config
        _context = CommandContext(
            console=Console(),
            config=get_config(),
            cache=get_cache()
        )
    return _context

def set_context(ctx: CommandContext):
    """Set global context (for testing)"""
    global _context
    _context = ctx

def create_context(
    config: Optional[CLIConfig] = None,
    console: Optional[Console] = None,
    cache: Optional[DataCache] = None
) -> CommandContext:
    """Create a new context (useful for testing)"""
    from src.cli.main import get_config
    
    return CommandContext(
        console=console or Console(),
        config=config or get_config(),
        cache=cache or get_cache()
    )
```

### 2. Update Commands to Use Context

**Pattern for updating commands:**

**Before:**
```python
from rich.console import Console
from src.cli.main import get_config

console = Console()

def plot_its_command(...):
    config = get_config()
    
    console.print("[cyan]Loading history...[/cyan]")
    history_file = config.history_dir / f"{chip_group}{chip}_history.parquet"
    
    if config.verbose:
        console.print(f"[dim]Using: {history_file}[/dim]")
```

**After:**
```python
from src.cli.context import get_context

def plot_its_command(...):
    ctx = get_context()
    
    ctx.print("[cyan]Loading history...[/cyan]")
    history_file = ctx.history_dir / f"{chip_group}{chip}_history.parquet"
    
    ctx.print_verbose(f"Using: {history_file}")
```

**Specific updates needed in each command file:**

1. Remove `console = Console()` at module level
2. Remove `config = get_config()` calls
3. Add `ctx = get_context()` at start of command
4. Replace `console.print()` with `ctx.print()`
5. Replace `if config.verbose:` with `ctx.print_verbose()`
6. Replace path constructions with `ctx.history_dir`, etc.

**Example full conversion:**

```python
# src/cli/commands/plot_its.py - BEFORE
from rich.console import Console
from src.cli.main import get_config
import typer

console = Console()

def plot_its_command(
    chip: int = typer.Argument(...),
    seq: Optional[str] = typer.Option(None, "--seq"),
):
    config = get_config()
    
    console.print("[cyan]Plotting ITS data...[/cyan]")
    history_file = config.history_dir / f"chip{chip}_history.parquet"
    
    if not history_file.exists():
        console.print(f"[red]Error:[/red] History not found: {history_file}")
        raise typer.Exit(1)
    
    if config.verbose:
        console.print(f"[dim]Loading from {history_file}[/dim]")
    
    history = pl.read_parquet(history_file)
    
    console.print(f"[green]✓[/green] Plot saved")

# AFTER
from src.cli.context import get_context
from src.cli.cache import load_history_cached
import typer

def plot_its_command(
    chip: int = typer.Argument(...),
    seq: Optional[str] = typer.Option(None, "--seq"),
):
    ctx = get_context()
    
    ctx.print("[cyan]Plotting ITS data...[/cyan]")
    history_file = ctx.history_dir / f"chip{chip}_history.parquet"
    
    if not history_file.exists():
        ctx.print_error(f"History not found: {history_file}")
        raise typer.Exit(1)
    
    ctx.print_verbose(f"Loading from {history_file}")
    
    # Use cached loading
    history = load_history_cached(history_file)
    
    ctx.print_success("Plot saved")
```

### 3. Update Helpers to Accept Context

**Update `src/cli/helpers.py`:**

**Before:**
```python
def display_experiment_list(experiments: pl.DataFrame, title: str):
    console = Console()
    # ... rest
```

**After:**
```python
from src.cli.context import CommandContext

def display_experiment_list(
    ctx: CommandContext,
    experiments: pl.DataFrame,
    title: str
):
    # Use ctx.console instead of creating new one
    # ... rest
```

Or keep backward compatible:

```python
def display_experiment_list(
    experiments: pl.DataFrame,
    title: str,
    ctx: Optional[CommandContext] = None
):
    from src.cli.context import get_context
    if ctx is None:
        ctx = get_context()
    
    # Use ctx.console
    # ... rest
```

### 4. Update Tests to Use Context

**Create `tests/test_context.py`:**

```python
import pytest
from src.cli.context import CommandContext, create_context
from src.cli.config import CLIConfig
from rich.console import Console
from pathlib import Path
import tempfile

@pytest.fixture
def test_context():
    """Create test context with temporary directories"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        config = CLIConfig(
            output_dir=tmp_path / "output",
            history_dir=tmp_path / "history",
            stage_dir=tmp_path / "stage",
            verbose=True,
            dry_run=True
        )
        
        ctx = create_context(
            config=config,
            console=Console(quiet=True)  # Suppress output in tests
        )
        
        yield ctx

def test_context_properties(test_context):
    """Test context convenience properties"""
    assert test_context.verbose == True
    assert test_context.dry_run == True
    assert test_context.output_dir.name == "output"

def test_context_print_methods(test_context):
    """Test context print methods"""
    # These should not raise
    test_context.print("Test message")
    test_context.print_verbose("Verbose message")
    test_context.print_error("Error message")
    test_context.print_success("Success message")
    test_context.print_warning("Warning message")

def test_context_confirm_action(test_context):
    """Test confirm_action in dry-run mode"""
    # In dry-run, should return True without prompting
    assert test_context.confirm_action("Delete files?") == True
```

**Update existing command tests:**

```python
# tests/test_plot_commands.py
def test_plot_its_command():
    """Test plot-its with test context"""
    from src.cli.context import set_context, create_context
    from src.cli.commands.plot_its import plot_its_command
    
    # Create test context
    test_ctx = create_context(
        config=CLIConfig(
            output_dir=Path("/tmp/test"),
            verbose=True,
            dry_run=True
        )
    )
    
    # Set as global context for test
    set_context(test_ctx)
    
    # Test command
    plot_its_command(chip=67, seq="52,57")
    
    # Verify behavior
    # ...
```

---

## Integration Requirements

### Update All Command Files

The following files need to be updated to use context:

**Priority 1 (Plotting commands - use cache):**
- ✅ `src/cli/commands/plot_its.py`
- ✅ `src/cli/commands/plot_ivg.py`
- ✅ `src/cli/commands/plot_transconductance.py`

**Priority 2 (Other commands):**
- ✅ `src/cli/commands/history.py`
- ✅ `src/cli/commands/stage.py`
- ✅ `src/cli/commands/data_pipeline.py`

**Priority 3 (Helpers):**
- ✅ `src/cli/helpers.py`
- ✅ `src/cli/history_utils.py`

### Checklist for Each File

When updating a command file, ensure:

- [ ] Remove module-level `console = Console()`
- [ ] Replace `get_config()` calls with `ctx = get_context()`
- [ ] Use `ctx.print()` instead of `console.print()`
- [ ] Use `ctx.print_verbose()` for verbose messages
- [ ] Use `ctx.print_error()` / `ctx.print_success()` / `ctx.print_warning()`
- [ ] Use `ctx.history_dir`, `ctx.output_dir`, etc. for paths
- [ ] Use `load_history_cached()` instead of `pl.read_parquet()` for histories
- [ ] Use `load_parquet_cached()` instead of `pl.read_parquet()` for data files
- [ ] Add cache stats to verbose output
- [ ] Test the command still works

---

## Documentation Updates

### Update `CLI_MODULE_ARCHITECTURE.md`

Add new sections:

**Section: "Caching System"**
```markdown
## Caching System

The CLI includes an intelligent caching layer that speeds up repeated operations.

### How It Works

- **Automatic caching**: History files and data are cached on first load
- **TTL-based expiration**: Cache entries expire after configured time (default: 5 minutes)
- **File modification tracking**: Cache invalidates if source file changes
- **LRU eviction**: Least recently used items evicted when cache is full
- **Thread-safe**: Safe for concurrent operations

### Cache Commands

- `cache-stats` - View hit rate and performance metrics
- `cache-clear` - Clear all cached data
- `cache-info` - Detailed cache information
- `cache-warmup <chips>` - Pre-load chip histories

### Configuration

```python
cache_enabled: bool = True           # Enable/disable caching
cache_ttl: int = 300                # Time-to-live in seconds
cache_max_items: int = 50           # Max cached items
cache_max_size_mb: int = 500        # Max cache size
```

### Performance Impact

Example workflow:
```bash
# First command: Load from disk (slow)
python process_and_analyze.py plot-its 67 --seq 52,57
# → 2.5 seconds

# Second command: Load from cache (fast)
python process_and_analyze.py plot-its 67 --seq 58,59
# → 0.3 seconds (8x faster!)
```
```

**Section: "Command Context Object"**
```markdown
## Command Context Object

All commands receive a `CommandContext` object providing unified access to shared resources.

### Context Properties

```python
ctx = get_context()

# Configuration
ctx.config              # Full CLIConfig object
ctx.verbose             # Shortcut for config.verbose
ctx.dry_run             # Shortcut for config.dry_run
ctx.output_dir          # Shortcut for config.output_dir
ctx.history_dir         # Shortcut for config.history_dir
ctx.stage_dir           # Shortcut for config.stage_dir

# Resources
ctx.console             # Rich console for output
ctx.cache               # Data cache instance

# Convenience methods
ctx.print()             # Print to console
ctx.print_verbose()     # Print only if verbose
ctx.print_error()       # Print error message
ctx.print_success()     # Print success message
ctx.print_warning()     # Print warning message
ctx.confirm_action()    # Prompt for confirmation
```

### Usage in Commands

```python
def my_command(...):
    ctx = get_context()
    
    ctx.print("[cyan]Processing...[/cyan]")
    history_file = ctx.history_dir / "file.parquet"
    
    ctx.print_verbose(f"Loading {history_file}")
    data = load_history_cached(history_file)
    
    ctx.print_success("Complete!")
```

### Benefits

- **Cleaner code**: Single import, single initialization
- **Easier testing**: Mock one object instead of many
- **Consistent behavior**: All commands use same resources
- **Type safety**: IDE autocomplete for all context properties
```

### Create `docs/CACHING.md`

New documentation file explaining:
- How caching works
- Performance benefits
- Configuration options
- Cache management commands
- Best practices
- Troubleshooting

---

## Testing Requirements

### Cache Testing (`tests/test_cache.py`)

**Test cases:**
- [ ] Cache hit/miss tracking
- [ ] TTL expiration
- [ ] File modification detection
- [ ] LRU eviction
- [ ] Size limit enforcement
- [ ] Thread safety
- [ ] Statistics accuracy
- [ ] Cache clear operation

### Context Testing (`tests/test_context.py`)

**Test cases:**
- [ ] Context creation
- [ ] Property access
- [ ] Print methods
- [ ] Dry-run behavior
- [ ] Context isolation in tests

### Integration Testing

**Test scenarios:**
- [ ] Load same history twice (verify cache hit)
- [ ] Modify history file (verify cache invalidation)
- [ ] Run multiple commands (verify context singleton)
- [ ] Cache warmup command
- [ ] Cache stats command
- [ ] All plot commands with caching

---

## Performance Benchmarks

After implementation, measure performance improvements:

```bash
# Benchmark script
time python process_and_analyze.py plot-its 67 --seq 52,57
# First run: ~2.5s

time python process_and_analyze.py plot-its 67 --seq 58,59
# Second run: ~0.3s (cache hit)

python process_and_analyze.py cache-stats
# Verify hit rate
```

Expected improvements:
- **70-90% faster** for cached history loads
- **50-70% faster** for repeated plot commands
- **Minimal memory overhead** (<500 MB for typical usage)

---

## Success Criteria

### Caching Layer Complete When:
1. ✅ `src/cli/cache.py` implemented with all features
2. ✅ Cache commands work (`cache-stats`, `cache-clear`, etc.)
3. ✅ All plotting commands use `load_history_cached()`
4. ✅ Cache hit rate >70% for repeated operations
5. ✅ Tests pass with >85% coverage
6. ✅ Documentation updated

### Context Object Complete When:
1. ✅ `src/cli/context.py` implemented
2. ✅ All 18 command functions updated to use context
3. ✅ All helpers updated to accept context
4. ✅ No more module-level `console = Console()`
5. ✅ Tests updated to use test context
6. ✅ All existing functionality preserved

### Overall Success When:
1. ✅ Commands are 70%+ faster for repeated operations
2. ✅ Code is cleaner (fewer imports, less duplication)
3. ✅ Tests are easier to write (mock context, not multiple resources)
4. ✅ No breaking changes to command signatures
5. ✅ Documentation complete with examples

---

## Implementation Order

1. **Caching Layer** (Days 1-2)
   - [ ] Create `src/cli/cache.py`
   - [ ] Add cache tests
   - [ ] Create cache commands
   - [ ] Update plotting commands to use cache
   - [ ] Verify performance improvement

2. **Command Context** (Days 3-4)
   - [ ] Create `src/cli/context.py`
   - [ ] Add context tests
   - [ ] Update one command as reference
   - [ ] Update remaining commands
   - [ ] Update helpers

3. **Documentation** (Day 5)
   - [ ] Update architecture doc
   - [ ] Create caching guide
   - [ ] Add code examples
   - [ ] Create performance benchmarks

4. **Testing & Polish** (Day 6)
   - [ ] Integration tests
   - [ ] Performance benchmarks
   - [ ] Code review
   - [ ] Final documentation pass

---

## Notes

- **Backward Compatibility**: All changes must preserve existing command signatures
- **Performance**: Caching should be transparent - users don't need to think about it
- **Testing**: Use temporary directories and test contexts to avoid side effects
- **Documentation**: Include before/after examples showing improvements

---

This completes Phase 2 of the CLI modernization. After this, the CLI will have:
- ✅ Centralized configuration (Phase 1)
- ✅ Intelligent caching (Phase 2)
- ✅ Unified context object (Phase 2)

Making it faster, cleaner, and easier to maintain!
