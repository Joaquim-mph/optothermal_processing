# Deep Analysis: stage_raw_measurements.py

## Purpose
This script transforms raw CSV measurement files into a structured, partitioned Parquet data lake with schema validation and type casting based on YAML specifications.

---

## What It Does to Files

### Input Processing Pipeline

#### 1. **File Discovery**
```
01_raw/
├── experiment_2025-01-15.csv
├── test_20250116.csv
└── subdir/
    └── measurement.csv
```

The script:
- Recursively finds all `.csv` files in `--raw-root`
- Excludes hidden directories (`.git`, `.venv`, `__pycache__`, `.ipynb_checkpoints`)
- Skips macOS resource fork files (starting with `._`)
- Processes files in sorted order

#### 2. **Header Parsing**
Each CSV has a structured header with metadata:

```csv
# Procedure: <electrical.iv_sweep>
# Parameters:
# Laser wavelength: 450
# Laser voltage: 3.3
# Chip group name: batch_A
# Chip number: 42
# Sample: GaN_device
# Procedure version: 1.2
# Metadata:
# Start time: 2025-01-15T10:30:00Z
# Temperature: 25
# Data:
I (A),Vsd (V),Vg (V),t (s)
0.001,1.5,0,0.0
0.002,1.6,0,0.1
...
```

**Parsed sections:**
- **Procedure**: Identifies the measurement type (e.g., `iv_sweep`)
- **Parameters**: Experimental settings (laser config, chip info, etc.)
- **Metadata**: Runtime information (timestamps, conditions)
- **Data**: The actual measurement table (starts after `# Data:`)

#### 3. **YAML Schema Validation**
The script loads a YAML file defining expected structure:

```yaml
procedures:
  iv_sweep:
    Parameters:
      Laser wavelength: float
      Laser voltage: float
      Chip group name: str
      Chip number: int
      Sample: str
      Procedure version: str
    Metadata:
      Start time: datetime
      Temperature: float
    Data:
      I (A): float
      Vsd (V): float
      Vg (V): float
      t (s): float
```

**Type Casting:**
- Parameters and Metadata are cast according to YAML specs
- Invalid values fallback to original string (no crash)
- Handles units: `"100ms"` → `100.0` (extracts number)

#### 4. **Column Name Normalization**
The script intelligently maps CSV column names to YAML standard names:

**Problem:** CSVs may have inconsistent naming:
- `"I (A)"` vs `"i_a"` vs `"current"` vs `"IDS"`
- `"Vsd (V)"` vs `"vd_v"` vs `"VDS"` vs `"Vds(V)"`

**Solution:** Three-tier matching strategy:

1. **Normalized exact match:**
   - Strips whitespace, lowercases, removes punctuation
   - `"Vsd (V)"` → `"vsdv"`, matches CSV column `"VDS (V)"` → `"vsdv"`

2. **Synonym patterns:**
   ```python
   "I (A)": [r"^i$", r"^i_a$", r"^id(_a)?$", r"^ids(_a)?$", r"^current(_a)?$"]
   "Vsd (V)": [r"^vsd(_v)?$", r"^vd(_v)?$", r"^vds(_v)?$"]
   ```
   Uses regex to catch common variations

3. **Uppercase heuristic:**
   - Tries uppercase version: `"I (A)"` → `"I(A)"` → matches `"I(A)"`

**Result:** All columns renamed to YAML canonical names for consistency

#### 5. **Data Type Casting**
After renaming, columns are cast to their declared types:

```python
# YAML: "I (A)": float
df.with_columns([pl.col("I (A)").cast(pl.Float64)])

# YAML: "Chip number": int
df.with_columns([pl.col("Chip number").cast(pl.Int64)])

# YAML: "with_light": bool
# Special handling: "1"/"true"/"yes" → True
```

**Non-YAML columns:**
- If `--only-yaml-data` flag: dropped
- Otherwise: kept as-is (type inferred)

#### 6. **Metadata Enrichment**
Each row gets additional columns:

```python
extra_cols = {
    "run_id": "a1b2c3d4e5f6g7h8",           # SHA-1 hash of path + timestamp
    "proc": "iv_sweep",                      # Procedure name
    "start_dt": datetime(2025, 1, 15, ...),  # Measurement start time
    "source_file": "/path/to/file.csv",      # Original file path
    "with_light": True,                      # Derived flag
    "wavelength_nm": 450.0,                  # From parameters
    "laser_voltage_V": 3.3,                  # From parameters
    "chip_group": "batch_A",                 # From parameters
    "chip_number": 42,                       # From parameters
    "sample": "GaN_device",                  # From parameters
    "procedure_version": "1.2",              # From parameters
}
```

**`with_light` derivation:**
```python
with_light = (wavelength is not None) and 
             (laser_voltage is not None) and 
             (laser_voltage != 0.0)
```

#### 7. **Date Partitioning Logic**
The script determines the partition date using a fallback hierarchy:

1. **From metadata** (`Start time` field):
   ```
   Start time: 2025-01-15T10:30:00Z
   → date_part = "2025-01-15"
   ```

2. **From file path** (if no metadata):
   ```
   /data/2025-01-15/exp.csv  → "2025-01-15"
   /data/20250115_test.csv   → "2025-01-15"
   ```

3. **From file modification time** (last resort):
   ```
   mtime = 1705318200  → "2025-01-15"
   ```

**Timezone handling:**
- All timestamps converted to UTC internally
- Partition date uses local timezone (default: `America/Santiago`)
- Example: UTC `2025-01-15 03:00:00` → Santiago `2025-01-14` → date partition = `2025-01-14`

#### 8. **Atomic Write with Deduplication**
```python
# Generate unique run_id
run_id = sha1_short(f"{file_path}|{start_timestamp}")

# Construct output path
out_file = stage_root / f"proc={proc}" / f"date={date_part}" / f"run_id={run_id}" / "part-000.parquet"

# Atomic write (prevents partial files)
temp_file = tempfile.NamedTemporaryFile(dir=out_file.parent)
df.write_parquet(temp_file)
temp_file.replace(out_file)  # Atomic rename
```

**Idempotency:**
- Same source file + timestamp → same `run_id`
- If output exists and not `--force`: skip processing
- Prevents duplicate processing in subsequent runs

---

## Output Structure

### Directory Layout
```
02_stage/raw_measurements/
│
├── proc=iv_sweep/
│   ├── date=2025-01-14/
│   │   ├── run_id=a1b2c3d4e5f6g7h8/
│   │   │   └── part-000.parquet
│   │   └── run_id=f8e7d6c5b4a39281/
│   │       └── part-000.parquet
│   └── date=2025-01-15/
│       └── run_id=1234567890abcdef/
│           └── part-000.parquet
│
├── proc=temperature_sweep/
│   └── date=2025-01-15/
│       └── run_id=9876543210fedcba/
│           └── part-000.parquet
│
└── _manifest/
    ├── events/
    │   ├── event-a1b2c3d4e5f6g7h8.json
    │   ├── event-f8e7d6c5b4a39281.json
    │   └── event-1234567890abcdef.json
    └── manifest.parquet
```

### Partitioning Strategy
**Hive-style partitioning** for efficient querying:

```
proc={procedure_name}/date={YYYY-MM-DD}/run_id={hash}/part-000.parquet
```

**Benefits:**
- **Procedure filtering:** Query only specific measurement types
- **Date filtering:** Time-range queries without scanning all data
- **Run identification:** Each measurement run is isolated
- **Query optimization:** Tools like DuckDB, Polars, Spark leverage partitions

**Example query:**
```python
# Read only iv_sweep measurements from January 2025
pl.scan_parquet("02_stage/raw_measurements/proc=iv_sweep/date=2025-01-*/")
```

### Parquet File Schema

Each `part-000.parquet` contains:

#### Data Columns (from CSV)
```
┌──────────┬──────────┬──────────┬──────────┐
│ I (A)    │ Vsd (V)  │ Vg (V)   │ t (s)    │
│ float64  │ float64  │ float64  │ float64  │
├──────────┼──────────┼──────────┼──────────┤
│ 0.001    │ 1.5      │ 0.0      │ 0.0      │
│ 0.002    │ 1.6      │ 0.0      │ 0.1      │
│ ...      │ ...      │ ...      │ ...      │
└──────────┴──────────┴──────────┴──────────┘
```

#### Metadata Columns (added by script)
```
┌─────────────────┬───────────┬────────────────────┬─────────────────────────┐
│ run_id          │ proc      │ start_dt           │ source_file             │
│ str             │ str       │ datetime           │ str                     │
├─────────────────┼───────────┼────────────────────┼─────────────────────────┤
│ a1b2c3d4e5f6... │ iv_sweep  │ 2025-01-15 10:30   │ /raw/exp_20250115.csv   │
│ a1b2c3d4e5f6... │ iv_sweep  │ 2025-01-15 10:30   │ /raw/exp_20250115.csv   │
└─────────────────┴───────────┴────────────────────┴─────────────────────────┘

┌─────────────┬───────────────┬──────────────────┬────────────┬──────────────┐
│ with_light  │ wavelength_nm │ laser_voltage_V  │ chip_group │ chip_number  │
│ bool        │ float64       │ float64          │ str        │ int64        │
├─────────────┼───────────────┼──────────────────┼────────────┼──────────────┤
│ true        │ 450.0         │ 3.3              │ batch_A    │ 42           │
│ true        │ 450.0         │ 3.3              │ batch_A    │ 42           │
└─────────────┴───────────────┴──────────────────┴────────────┴──────────────┘

┌──────────┬────────────────────┐
│ sample   │ procedure_version  │
│ str      │ str                │
├──────────┼────────────────────┤
│ GaN_...  │ 1.2                │
│ GaN_...  │ 1.2                │
└──────────┴────────────────────┘
```

---

## Manifest System

### Event Files
Each processed file generates an event JSON:

**Success event:**
```json
{
  "ts": "2025-01-15T10:35:22Z",
  "status": "ok",
  "run_id": "a1b2c3d4e5f6g7h8",
  "proc": "iv_sweep",
  "rows": 1500,
  "path": "/stage/proc=iv_sweep/date=2025-01-15/run_id=a1b2.../part-000.parquet",
  "source_file": "/raw/experiment_20250115.csv",
  "date_origin": "meta"
}
```

**Skip event** (file already processed):
```json
{
  "ts": "2025-01-15T11:00:00Z",
  "status": "skipped",
  "run_id": "a1b2c3d4e5f6g7h8",
  "proc": "iv_sweep",
  "rows": 1500,
  "path": "/stage/proc=iv_sweep/.../part-000.parquet",
  "source_file": "/raw/experiment_20250115.csv",
  "date_origin": "meta"
}
```

**Reject record** (parsing error):
```json
{
  "source_file": "/raw/corrupted_file.csv",
  "error": "empty data table",
  "ts": "2025-01-15T10:40:00Z"
}
```

### Consolidated Manifest
After all processing, events are merged into `manifest.parquet`:

```python
pl.read_parquet("02_stage/raw_measurements/_manifest/manifest.parquet")

shape: (500, 8)
┌────────────────────┬──────────┬─────────────────┬───────────┬──────┬───────────────┬────────────────┬─────────────┐
│ ts                 │ status   │ run_id          │ proc      │ rows │ path          │ source_file    │ date_origin │
│ datetime           │ str      │ str             │ str       │ i64  │ str           │ str            │ str         │
├────────────────────┼──────────┼─────────────────┼───────────┼──────┼───────────────┼────────────────┼─────────────┤
│ 2025-01-15 10:35   │ ok       │ a1b2c3d4e5f6... │ iv_sweep  │ 1500 │ /stage/pro... │ /raw/exp_20... │ meta        │
│ 2025-01-15 10:36   │ ok       │ f8e7d6c5b4a3... │ temp_sw...│ 800  │ /stage/pro... │ /raw/temp_2... │ path        │
│ 2025-01-15 11:00   │ skipped  │ a1b2c3d4e5f6... │ iv_sweep  │ 1500 │ /stage/pro... │ /raw/exp_20... │ meta        │
└────────────────────┴──────────┴─────────────────┴───────────┴──────┴───────────────┴────────────────┴─────────────┘
```

**Deduplication:** Uses `(run_id, ts, status, path)` as unique key, keeping latest

---

## Parallel Processing Architecture

```
Main Process
    │
    ├─ Discover CSV files
    ├─ Validate YAML schema
    ├─ Create ProcessPoolExecutor (N workers)
    │
    ├─► Worker 1: file_1.csv → proc=X/date=Y/run_id=A/part-000.parquet
    ├─► Worker 2: file_2.csv → proc=X/date=Z/run_id=B/part-000.parquet
    ├─► Worker 3: file_3.csv → proc=Y/date=Y/run_id=C/part-000.parquet
    │   ...
    └─► Worker N: file_N.csv → proc=Z/date=W/run_id=D/part-000.parquet
    │
    └─ Merge all events → manifest.parquet
```

**Key points:**
- Each worker gets isolated Polars thread pool (`POLARS_MAX_THREADS`)
- Workers don't share state (cache is per-process)
- Output paths are isolated by `run_id` (no conflicts)
- Atomic writes prevent partial files even with crashes

---

## Error Handling

### Graceful Degradation

1. **Bad header values:** Fallback to string, don't crash
   ```python
   # YAML says "int", but value is "N/A"
   out[k] = v  # Keep as string "N/A"
   ```

2. **Missing procedure:** Uses empty spec
   ```python
   spec = procs.get(proc, ProcSpec({}, {}, {}))
   ```

3. **Invalid dates:** Try path, then mtime
   ```python
   resolve_start_dt_and_date(src, meta, local_tz)
   # meta → path → mtime (always succeeds)
   ```

4. **Parsing failures:** Write reject record, continue
   ```python
   # 02_stage/../_rejects/experiment_20250115-a1b2c3d4.reject.json
   {
     "source_file": "/raw/experiment_20250115.csv",
     "error": "empty data table",
     "ts": "2025-01-15T10:40:00Z"
   }
   ```

### Atomicity Guarantees

**No partial files:** Write to temp, then atomic rename
```python
with tempfile.NamedTemporaryFile(dir=parent) as tmp:
    df.write_parquet(tmp.name)
    tmp_path.replace(out_file)  # Atomic OS operation
```

**Idempotent reruns:** Same input → same output path
- Safe to rerun after crashes
- Use `--force` to override existing files

---

## Command-Line Usage

### Basic Usage
```bash
python stage_raw_measurements.py \
--raw-root ./01_raw \
  --stage-root ./02_stage/raw_measurements \
  --procedures-yaml ./procedures.yaml
```

### Advanced Options
```bash
python stage_raw_measurements.py \
  --raw-root ./01_raw \
  --stage-root ./02_stage/raw_measurements \
  --procedures-yaml ./procedures.yaml \
  --local-tz "America/New_York" \
  --workers 12 \
  --polars-threads 2 \
  --force \
  --only-yaml-data \
  --rejects-dir ./errors \
  --events-dir ./events \
  --manifest ./manifest.parquet
```

**Flag explanations:**
- `--local-tz`: Timezone for date partitions (affects which date a late-night measurement belongs to)
- `--workers`: Number of parallel processes (default: 6)
- `--polars-threads`: Threads per Polars worker (default: 1)
- `--force`: Overwrite existing Parquet files
- `--only-yaml-data`: Drop columns not in YAML schema (strict mode)
- `--rejects-dir`: Where to store error records (default: `{stage_root}/../_rejects`)
- `--events-dir`: Where to store per-run events (default: `{stage_root}/_manifest/events`)
- `--manifest`: Final manifest location (default: `{stage_root}/_manifest/manifest.parquet`)

---

## Summary

This script is a **robust ETL pipeline** that:

1. **Discovers** CSV files recursively
2. **Parses** structured headers with metadata
3. **Validates** against YAML schemas with intelligent column matching
4. **Normalizes** column names and casts types
5. **Enriches** data with experimental parameters
6. **Partitions** by procedure and date for query efficiency
7. **Writes** atomically to prevent corruption
8. **Tracks** processing history in a manifest
9. **Handles** errors gracefully without stopping the pipeline
10. **Parallelizes** across multiple workers for speed

**Result:** A clean, queryable data lake optimized for analytical workloads.