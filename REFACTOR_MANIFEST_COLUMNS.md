# Refactor: ManifestColumns → Global Mapping

**Date:** 2026-02-13

## Problem

Each of the 14 procedures in `config/procedures.yml` had its own `ManifestColumns` section mapping CSV parameter names to manifest field names. This created massive duplication — entries like `nplc: [NPLC]`, `sample: [Sample]`, and `information: [Information]` were repeated across nearly every procedure. Of ~157 total entries, roughly 37% were identical single-alias identity mappings.

## Solution

Replaced all per-procedure `ManifestColumns` sections with a single top-level `ManifestColumnMap` defined once. The extraction code already merges `{**params, **meta}` and searches for aliases, so procedure-specific config was unnecessary — we just need to know which params a procedure has (already in its `Parameters` section) and what manifest field each param maps to (the global map).

## Files Changed

### `config/procedures.yml`

- Added top-level `ManifestColumnMap` with 33 entries covering all manifest fields and their CSV aliases
- Removed all 14 per-procedure `ManifestColumns` sections (~157 duplicated entries eliminated)
- Key design decision: `wavelength_nm: [Laser wavelength, Wavelength]` merges aliases so ItWl (which uses `Wavelength`) and all other procedures (which use `Laser wavelength`) are handled by the same global entry

### `src/core/stage_raw_measurements.py`

- **Added `ProceduresConfig` dataclass** — holds `specs: Dict[str, ProcSpec]` and `manifest_column_map: Dict[str, List[str]]`
- **Simplified `ProcSpec`** — removed `manifest_columns` field (no longer per-procedure)
- **Updated `load_procedures_yaml()`** — now returns `ProceduresConfig`, parses global `ManifestColumnMap` from YAML
- **Updated `get_procs_cached()`** — returns `ProceduresConfig` instead of `Dict[str, ProcSpec]`
- **Rewrote `extract_manifest_columns_dynamic()`** — new signature takes global map + combined sources dict; only includes fields where a matching alias exists in sources (natural per-procedure filtering without needing per-procedure config)
- **Removed legacy hardcoded fallback** — the ~25-line `_get_float()` fallback dict that was used when a procedure lacked `ManifestColumns`
- **Updated `ingest_file_task()` call site** — uses `procs_config.specs` and `procs_config.manifest_column_map`

## How It Works

The global map defines every possible manifest field and its CSV aliases:

```yaml
ManifestColumnMap:
  vds_v: [VDS, Vds, VSD, Drain voltage]
  wavelength_nm: [Laser wavelength, Wavelength]
  nplc: [NPLC]
  sample: [Sample]
  # ... 33 entries total
```

During extraction, the code iterates the global map and tries each alias against the combined `{**params, **meta}` dict. If no alias matches (because the procedure doesn't have that parameter), the field is simply omitted from the result. This provides natural per-procedure filtering without any per-procedure configuration.

## Verification

```
860 measurements staged successfully (862 CSV files, 860 ok, 2 rejects)
Manifest validation: passed (0 schema errors)
History building: all 15 chip histories built
Tests: 144/144 relevant tests pass (3 pre-existing failures unrelated to this change)
```

Manifest column completeness spot-check:

| Column | Non-null count | Expected |
|--------|---------------|----------|
| nplc | 793/860 | All chip procedures |
| sample | 793/860 | All chip procedures |
| information | 860/860 | All procedures |
| wavelength_nm | 860/860 | All procedures |
| optical_fiber | 67/860 | LaserCalibration only |
| sensor_model | 67/860 | LaserCalibration + Pt/Pwl |
| ids_a | 62/860 | VVg + Vt only |
