# Using the datetime_local Column

The `datetime_local` column provides a combined date+time label in local timezone (America/Santiago) for easy experiment identification.

## Format

- **Column name**: `datetime_local`
- **Type**: String
- **Format**: `YYYY-MM-DD HH:MM:SS` (e.g., `"2025-10-14 15:03:53"`)
- **Timezone**: America/Santiago (UTC-3)
- **Location**: All chip history files in `data/02_stage/chip_histories/`

## Comparison with Other Time Columns

| Column | Format | Timezone | Type | Use Case |
|--------|--------|----------|------|----------|
| `datetime_local` | `2025-10-14 15:03:53` | Local (Santiago) | String | **Human-readable experiment labels** |
| `date` | `2025-10-14` | Local | String | Grouping by day |
| `time_hms` | `18:03:53` | **UTC** | String | Legacy time display |
| `start_time_utc` | Full datetime | UTC | Datetime | Precise timestamps, calculations |
| `start_time` | `1728926633.123` | UTC | Float | Unix epoch for calculations |

⚠️ **Important**: `time_hms` shows UTC time (not local), so it will be 3 hours ahead of `datetime_local`.

## Usage Examples

### 1. Python Scripts (Polars)

```python
import polars as pl

# Load chip history
history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")

# Display experiments with datetime
experiments = history.select([
    "seq",
    "datetime_local",
    "proc",
    "summary"
])

# Filter by date range
filtered = history.filter(
    (pl.col("datetime_local") >= "2025-10-14 00:00:00") &
    (pl.col("datetime_local") <= "2025-10-14 23:59:59")
)

# Group by date (extract from datetime_local)
daily_counts = history.with_columns([
    pl.col("datetime_local").str.slice(0, 10).alias("date_only")
]).group_by("date_only").count()
```

### 2. CLI Commands

```bash
# View history with datetime_local
python process_and_analyze.py show-history 67

# The CLI automatically displays datetime_local if available
```

### 3. TUI Integration

Update experiment selectors to display `datetime_local`:

```python
# In TUI experiment selection screens
for row in history.iter_rows(named=True):
    label = f"{row['seq']:3} | {row['datetime_local']} | {row['proc']:4} | {row['summary'][:50]}"
    yield Checkbox(label, value=False, id=f"exp-{row['seq']}")
```

### 4. Plotting Functions

```python
import polars as pl
from pathlib import Path

# Load history and use datetime_local for plot titles
history = pl.read_parquet(f"data/02_stage/chip_histories/Alisson{chip_number}_history.parquet")

# Filter experiments
selected = history.filter(pl.col("seq").is_in([4, 5, 6]))

# Use datetime_local in plot labels
for row in selected.iter_rows(named=True):
    label = f"{row['datetime_local']} - {row['proc']}"
    # Plot with this label...
```

### 5. Sorting and Filtering

```python
# Sort by datetime (string sorting works correctly due to ISO format)
sorted_history = history.sort("datetime_local")

# Find experiments from a specific date
oct_14_experiments = history.filter(
    pl.col("datetime_local").str.starts_with("2025-10-14")
)

# Find experiments in a time window
morning_experiments = history.filter(
    pl.col("datetime_local").str.slice(11, 2).cast(pl.Int32) < 12
)
```

### 6. Export for External Tools

```python
# Export experiment list with datetime labels
export = history.select([
    "seq",
    "datetime_local",
    "proc",
    "chip_name",
    "summary"
]).write_csv("experiments.csv")
```

## Benefits

1. **Single field** for date+time instead of two separate columns
2. **Human-readable** format (ISO 8601)
3. **Sortable** as string (lexicographic order = chronological order)
4. **Local timezone** context (matches lab clock)
5. **Consistent format** across all histories
6. **Easy filtering** using string operations
7. **Compatible with external tools** (Excel, etc.)

## Implementation Notes

- Generated in `src/core/history_builder.py` from `start_time_utc`
- Converts from UTC to America/Santiago timezone
- Added to all chip histories automatically during `build-all-histories`
- Does not replace existing columns (backward compatible)

## Migration Guide

If you have code using separate `date` and `time_hms` columns:

```python
# Old approach
display = f"{row['date']} {row['time_hms']}"  # ⚠️ time_hms is UTC!

# New approach
display = row['datetime_local']  # ✓ Correct local time
```

## Future Enhancements

Possible additions:
- `datetime_utc` (string version of start_time_utc for consistency)
- Custom timezone support (configurable via chip_params.yaml)
- Relative time labels ("2 hours ago", "yesterday")
- Time delta calculations between experiments
