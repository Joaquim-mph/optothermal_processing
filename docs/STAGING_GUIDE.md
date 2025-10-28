# Staging Pipeline Guide

This document explains the staging phase implemented in `src/core/stage_raw_measurements.py` and its helpers. The staging pipeline converts raw laboratory CSVs into a validated, partitioned Parquet lake with an authoritative manifest. It is the backbone for chip histories, plotting commands, and the TUI.

---

## High-Level Flow

```
raw CSV files
   │
   ├─ discover_csvs()                 # enumerate inputs under --raw-root
   ├─ parse_header() / cast_block()   # header & metadata parsing (stage_utils.py)
   ├─ ingest_file_task()              # worker: schema validation + enrichment
   ├─ atomic_write_parquet()          # write proc/date/run_id partition
   └─ merge_events_to_manifest()      # consolidate per-run JSON events
        ↓
data/02_stage/raw_measurements/
    ├─ proc=IVg/date=YYYY-MM-DD/run_id=<hash>/part-000.parquet
    └─ _manifest/manifest.parquet + event-<run_id>.json
```

Each CSV is processed in isolation and yields:

1. A Parquet dataset (Hive-style partitions) containing the measurement table plus normalized metadata columns.
2. An event JSON record summarizing the ingestion. These records are merged into `manifest.parquet`, the single source of truth for all staged experiments.

---

## CLI Entry Points and Parameters

Staging is exposed through the Typer command `stage-all`:

```bash
python process_and_analyze.py stage-all \
  --raw-root data/01_raw \
  --stage-root data/02_stage/raw_measurements \
  --procedures-yaml config/procedures.yml \
  --workers 8 \
  --force          # optional, overwrite existing Parquet runs
```

Key options:

| Flag | Default | Description |
| ---- | ------- | ----------- |
| `--raw-root/-r` | `data/01_raw` | Root directory searched recursively for `.csv` files. |
| `--stage-root/-s` | `data/02_stage/raw_measurements` | Destination for partitioned Parquet output and manifest. |
| `--procedures-yaml/-p` | `config/procedures.yml` | Schema registry used for casting parameters, metadata, and data columns. |
| `--workers/-w` | `8` | Process pool size. Workers run `ingest_file_task` in parallel. |
| `--force/-f` | `False` | Rebuild Parquet even if the run already exists (determined by `run_id`). |
| `--only-yaml-data` | `False` | Drop columns not declared under the procedure’s `Data` schema. |

Runtime configuration also sets:

* `local_tz` (`America/Santiago`): used to derive `date_local` partitions.
* `polars_threads` (default `2`): passed via `POLARS_MAX_THREADS`.
* `events_dir`, `rejects_dir`, `manifest`: resolved relative to `stage_root`.

---

## Worker Responsibilities (`ingest_file_task`)

Each CSV is processed by `ingest_file_task` in `stage_raw_measurements.py`. Major steps:

1. **Header parsing:** `parse_header` (from `stage_utils.py`) separates “Procedure”, “Parameters”, “Metadata”, and the row offset for the data table.
2. **Schema lookup:** `get_procs_cached(procedures_yaml)` loads the YAML spec once per worker. It returns a `ProcSpec` containing expected fields for parameters, metadata, and data.
3. **Type casting:** `cast_block` converts header values according to the YAML spec (floats, ints, bools, datetime). Units like `"120s"` are normalized.
4. **Date resolution:** `resolve_start_dt_and_date` chooses a canonical start timestamp and calendar partition date, preferring metadata values but falling back to filenames or mtime.
5. **Data table loading:** `read_numeric_table` (Polars) reads the CSV section after `# Data:`. Empty tables raise a reject.
6. **Column normalization:** `build_yaml_rename_map` matches observed column headers to canonical names using normalization and regex synonyms (e.g., `"VDS"` → `"Vsd (V)"`). Columns are then cast to schema-defined types. Optional columns not in YAML are either kept (default) or dropped (`--only-yaml-data`).
7. **Derived metadata:** We derive quantities unavailable in the header:
   * `run_id`: a deterministic SHA-1 hash computed from `source_path|start_timestamp` (first 16 chars). Ensures idempotence.
   * `with_light`: true if both wavelength and laser voltage are present and the voltage is non-zero.
   * `laser_period_s`: parsed from “Laser ON+OFF period” entries.
   * `vds_v`, `vg_fixed_v`, `vg_start_v`, `vg_end_v`, `vg_step_v`: extracted from parameter keys to capture fixed biases and sweep definitions.
8. **Data enrichment:** The Polars DataFrame gains constant columns for each run (run id, procedure, chip identifiers, derived metadata). Example:

   ```python
   extra_cols = {
       "run_id": rid,
       "proc": proc,
       "start_dt": start_dt,
       "source_file": str(src),
       "with_light": with_light,
       "wavelength_nm": wl_f,
       "laser_voltage_V": lv_f,
       "laser_period_s": laser_period_s,
       "vds_v": vds_v,
       "vg_fixed_v": vg_fixed_v,
       "vg_start_v": vg_start_v,
       "vg_end_v": vg_end_v,
       "vg_step_v": vg_step_v,
       "chip_group": params.get("Chip group name"),
       "chip_number": params.get("Chip number"),
       "sample": params.get("Sample"),
       "procedure_version": params.get("Procedure version"),
   }
   df = df.with_columns([pl.lit(v).alias(k) for k, v in extra_cols.items()])
   ```

9. **Partition path:** Each run is written to `stage_root/proc=<proc>/date=<date_local>/run_id=<rid>/part-000.parquet`. The partition mirrors common Hive/Delta patterns.

10. **Atomic write:** `atomic_write_parquet` writes via a temp file in the target directory and renames it, so readers never see a partial file (important when running many workers).

11. **Event JSON:** Regardless of an actual write (skipped vs. rebuilt), the worker returns an event dict with status (`ok`, `skipped`, or `reject`). Events include all metadata keys and are serialized to `_manifest/events/event-<run_id>.json`. Rejects are captured separately in `_rejects/` with error details.

---

## Manifest Construction (`merge_events_to_manifest`)

After all workers complete, `merge_events_to_manifest(events_dir, manifest_path)` ingests every JSON event and creates/updates `manifest.parquet`. Important behavior:

* **Schema unification:** Events written before the latest metadata additions do not contain `laser_period_s`, `vds_v`, etc. Before constructing the DataFrame, the merger collects the union of keys across all events and fills missing fields with `null`, avoiding the “schema lengths differ” Polars error.
* **Deduplication:** When a manifest already exists, the new DataFrame is concatenated (`vertical_relaxed`) and deduplicated on `(run_id, ts, status, path)` keeping the latest occurrence.
* **Output:** The manifest lives at `<stage_root>/_manifest/manifest.parquet`. Event files are left intact to aid debugging.

Manifest rows map almost one-to-one with staged Parquet runs. They feed history building (`src/core/history_builder.py`) and the CLI/TUI selectors.

### Manifest Columns

The manifest aggregates raw metadata, derived quantities, and staging bookkeeping. Key columns (common subset from `ManifestRow` in `src/models/manifest.py`):

| Column | Type | Description |
| ------ | ---- | ----------- |
| `ts` | str (ISO datetime) | When the staging event occurred. |
| `status` | str | `ok`, `skipped`, or `reject`. |
| `run_id` | str | Deterministic 16-char identifier for this measurement. |
| `proc` | str | Procedure label (`IVg`, `It`, `IV`, `LaserCalibration`, etc.). |
| `rows` | int | Row count of the staged data table. |
| `path` | str | Absolute/relative Parquet location within the stage root. |
| `source_file` | str | Original CSV path relative to raw root. |
| `date_origin` | str | `meta`, `path`, or `mtime` (indicates how `date_local` was derived). |
| `chip_group` | str | Chip family (e.g., `Alisson`). |
| `chip_number` | int | Numeric device identifier. |
| `start_time_utc` | datetime (tz-aware) | Experiment start time. |
| `date_local` | str (YYYY-MM-DD) | Local calendar day partition. |
| `has_light` | bool | Whether laser illumination is detected. |
| `wavelength_nm` | float | Laser wavelength. |
| `laser_voltage_V` | float | Laser/LED drive voltage. |
| `laser_period_s` | float | Laser ON+OFF period (It/ITt procedures). |
| `vds_v` | float | Fixed drain-source bias (relevant to It/IV runs and snapshot of IVg conditions). |
| `vg_fixed_v` | float | Fixed gate voltage used in It/IV. |
| `vg_start_v`, `vg_end_v`, `vg_step_v` | float | Sweep bounds and resolution for IVg/IVgT procedures. |

Downstream processes may enrich the manifest further (e.g., by adding computed statistics), but the staging step is responsible for the structural consistency.

---

## Reject Handling

* Rejects are written to `_rejects/<filename>-<hash>.reject.json`.
* JSON payload includes `"source_file"`, `"error"`, and `"ts"`.
* Common triggers:
  * Empty data section (`df.height == 0`).
  * Missing “# Procedure” header.
  * Schema casting errors (e.g., illegal numeric conversions) when `only_yaml_data=True`.
* The CLI reports the reject count when staging completes.

---

## Utilities in `stage_utils.py`

`stage_utils.py` centralizes parsing and casting logic. Notable functions:

* `discover_csvs(raw_root)`: recursively finds CSVs, skipping hidden/system folders. Used in orchestration.
* `parse_header(path)`: returns a `HeaderBlocks` dataclass containing parsed procedure, parameter dict, metadata dict, and the zero-based line index where the data table starts.
* `cast_block(block, schema)`: casts parameter/metadata dictionaries to Python types using definitions from YAML.
* `resolve_start_dt_and_date(path, metadata, local_tz)`: prioritizes metadata start time, but gracefully falls back to path patterns or file modification times. Returns `(start_dt, date_local, origin_label)`.
* `build_yaml_rename_map(columns, schema.data)`: attempts to map observed column names to canonical ones through normalization and regex heuristics.
* `read_numeric_table(path, header_line)`: loads the CSV portion after the header using Polars’ fast CSV reader.
* `sha1_short`, `ensure_dir`, `atomic_write_parquet`: small helpers for hashing, filesystem creation, and safe writes.

Understanding these helpers is essential when extending staging behavior (e.g., adding new parameter keys or supporting additional instruments).

---

## Adding New Procedures

1. Update `config/procedures.yml` with the new procedure name and its `Parameters`, `Metadata`, and `Data` sections.
2. Ensure the raw CSV headers include `# Procedure: <name>` matching the YAML entry.
3. If the data columns use novel naming, extend `COLUMN_SYNONYMS` or regex patterns in `stage_utils.py` so the renamer can map them.
4. If derived quantities are needed, extend `ingest_file_task` to compute them (following the pattern used for `laser_period_s` or `vds_v`).
5. Optionally add validation logic (e.g., expected ranges) either during casting or as part of a post-processing validation step.

---

## Operational Tips

* **Idempotence:** Because `run_id` encodes both source path and start time, rerunning without `--force` skips work for runs already staged. Use `--force` when you need to regenerate Parquet (e.g., after schema updates).
* **Manifest refresh:** Removing `_manifest/` before a run forces a clean rebuild of event logs and the manifest. This is useful when the schema of event JSON records changes.
* **Performance tuning:** 
  * Increase `--workers` for more CPU-bound parallelism.
  * Adjust `polars_threads` (via CLI option or env var) to control intra-task threading.
  * Keep the YAML schema minimal and precise; complex regex mappings can slow the renamer for large datasets.
* **Diagnostics:** 
  * Inspect `_manifest/events/event-<run_id>.json` to debug individual runs.
  * Use `process_and_analyze.py inspect-manifest` to explore the manifest interactively.
  * `tui_plot_generation.log` records CLI activity during plotting but can also expose staging paths used later.

---

## Summary

The staging phase guarantees that heterogeneous CSV dumps turn into strongly typed, partitioned Parquet datasets with rich metadata. The manifest sits at the core of every downstream consumer: chip history builders, CLI plotting commands, and the TUI wizard. When modifying staging, verify that:

* The YAML schema represents all expected headers.
* The derived metadata stays in sync with downstream expectations.
* New event fields are backward-compatible (the merger now normalizes schemas to guard against older JSON records).

With these components, the project maintains a reproducible and queryable data lake for semiconductor experiment analysis.
