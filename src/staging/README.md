Stage Raw Measurements — README
===============================

Overview
--------
This script builds a *staged* dataset from raw measurement CSV files, extracting header metadata, normalizing columns into SI units, and writing partitioned Parquet files suitable for downstream analytics.

Technologies
------------
- concurrent.futures (ProcessPoolExecutor/ThreadPoolExecutor)
- Polars
- YAML configuration

Command‑line interface
----------------------
Supported arguments:
  - * **--raw-root** — - Root folder with CSVs (01_raw)
  - * **--stage-root** — - Output root (02_stage/raw_measurements)
  - * **--procedures-yaml** — - YAML schema of procedures and types
  - * **--rejects-dir** — - Folder for reject records (default: {stage_root}/../_rejects)
  - * **--events-dir** — - Per-run event JSONs (default: {stage_root}/_manifest/events)
  - * **--manifest** — - Merged manifest parquet (default: {stage_root}/_manifest/manifest.parquet)
  - * **--local-tz** — - Timezone for date partitioning
  - * **--workers** — - Process workers
  - * **--polars-threads** — - POLARS_MAX_THREADS per worker
  - * **--force** — - Overwrite staged Parquet if exists
  - * **--only-yaml-data** — - Drop non-YAML data columns

Key functions
-------------
- `warn`
- `sha1_short`
- `to_bool`
- `parse_number_unit`
- `parse_datetime_any`
- `local_date_for_partition`
- `ensure_dir`
- `extract_date_from_path`
- `load_procedures_yaml`
- `get_procs_cached`
- `parse_header`
- `cast_block`
- `_norm`
- `build_yaml_rename_map`: Return mapping {src_col -> target_yaml_col}. If multiple df cols match a target, pick first stable order.
- `cast_df_data_types`: Cast columns present in df to the types declared in YAML Data.
- `read_numeric_table`
- `resolve_start_dt_and_date`
- `atomic_write_parquet`
- `ingest_file_task`
- `discover_csvs`
- `merge_events_to_manifest`
- `main`

Inputs / Outputs
----------------
- Reads raw CSV measurement files from a folder tree.
- Optionally reads existing Parquet for incremental runs.
- Writes partitioned Parquet files to the stage directory.
- Uses a YAML spec to interpret procedures/columns/units.

Usage
-----
Basic staging run:

```bash
python stage_raw_measurements.py \
  --raw-root data/01_raw \
  --stage-root data/02_stage/raw_measurements \
  --procedures-yaml config/procedures.yml
```

Tip: add `--workers 6` to enable parallel ingestion and `--polars-threads 2` to control Polars compute threads.

Troubleshooting
---------------
- Ensure the YAML file defines each `# Procedure:` found in your raw files.
- If timestamps lack timezone info, provide `--local-tz America/Santiago` to interpret them consistently.
- When columns are missing or named differently, update the canonical mapping in the script/YAML.
