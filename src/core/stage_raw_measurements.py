from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List
from .stage_utils import *
import polars as pl
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.models.parameters import StagingParameters
from pydantic import ValidationError

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore


# ----------------------------- Config -----------------------------

DEFAULT_LOCAL_TZ = "America/Santiago"
DEFAULT_WORKERS = 6
DEFAULT_POLARS_THREADS = 1

PROC_LINE_RE   = re.compile(r"^#\s*Procedure\s*:\s*<([^>]+)>\s*$", re.I)
PARAMS_LINE_RE = re.compile(r"^#\s*Parameters\s*:\s*$", re.I)
META_LINE_RE   = re.compile(r"^#\s*Metadata\s*:\s*$", re.I)
DATA_LINE_RE   = re.compile(r"^#\s*Data\s*:\s*$", re.I)
KV_PAT         = re.compile(r"^#\s*([^:]+):\s*(.*)\s*$")

# ----------------------------- YAML ------------------------------

@dataclass
class ProcSpec:
    """
    Schema specification for a measurement procedure.
    
    Defines expected types for Parameters, Metadata, and Data columns
    as declared in the procedures YAML file.
    
    Attributes:
        params: Type mappings for parameter fields (e.g., {"Laser wavelength": "float"})
        meta: Type mappings for metadata fields (e.g., {"Start time": "datetime"})
        data: Type mappings for data columns (e.g., {"I (A)": "float", "Vsd (V)": "float"})
    """
    params: Dict[str, str]
    meta: Dict[str, str]
    data: Dict[str, str]

_PROC_CACHE: Dict[str, ProcSpec] | None = None
_PROC_YAML_PATH: Path | None = None


def load_procedures_yaml(path: Path) -> Dict[str, ProcSpec]:
    """
    Load procedure specifications from YAML schema file.
    
    Parses a YAML file containing procedure definitions with their expected
    Parameters, Metadata, and Data column types. Used for validation and
    type casting during CSV ingestion.
    
    Args:
        path: Path to procedures YAML file
        
    Returns:
        Dictionary mapping procedure names to their ProcSpec specifications
        
    Example YAML structure:
        procedures:
          iv_sweep:
            Parameters:
              Laser wavelength: float
              Chip number: int
            Metadata:
              Start time: datetime
            Data:
              I (A): float
              Vsd (V): float
              
    Example:
        >>> specs = load_procedures_yaml(Path("procedures.yaml"))
        >>> specs["iv_sweep"].data
        {"I (A)": "float", "Vsd (V)": "float"}
    """
    with path.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    procs = {}
    root = y.get("procedures", {}) or {}
    for name, blocks in root.items():
        procs[name] = ProcSpec(
            params=(blocks.get("Parameters") or {}) ,
            meta=(blocks.get("Metadata") or {}) ,
            data=(blocks.get("Data") or {}) ,
        )
    return procs


def get_procs_cached(path: Path) -> Dict[str, ProcSpec]:
    """
    Get procedure specifications with caching.
    
    Loads procedures YAML file and caches the result. Subsequent calls
    with the same path return cached data. Cache is invalidated if path changes.
    
    Args:
        path: Path to procedures YAML file
        
    Returns:
        Dictionary mapping procedure names to their ProcSpec specifications
        
    Note:
        Cache is global and persists across function calls within the same process.
        Each worker process in parallel execution maintains its own cache.
    """
    global _PROC_CACHE, _PROC_YAML_PATH
    if _PROC_CACHE is None or _PROC_YAML_PATH != path:
        _PROC_CACHE = load_procedures_yaml(path)
        _PROC_YAML_PATH = path
    return _PROC_CACHE


# ----------------------------- Header parse -------------------------------

@dataclass
class HeaderBlocks:
    """
    Parsed sections from a CSV file header.
    
    Represents the structured header of a measurement CSV file, which contains
    metadata comments before the actual data table begins.
    
    Attributes:
        proc: Procedure name (extracted from "# Procedure: <name>" line)
        parameters: Experimental parameters as key-value pairs
        metadata: Runtime metadata as key-value pairs
        data_header_line: Line number where "# Data:" marker appears (data starts next line)
    """
    proc: Optional[str]
    parameters: Dict[str, str]
    metadata: Dict[str, str]
    data_header_line: Optional[int]


def parse_header(path: Path) -> HeaderBlocks:
    """
    Parse structured header from measurement CSV file.
    
    Extracts procedure name, parameters, and metadata from comment lines
    at the beginning of a CSV file. The header follows this structure:
    
    # Procedure: <name>
    # Parameters:
    # key1: value1
    # key2: value2
    # Metadata:
    # key3: value3
    # Data:
    [CSV table starts here]
    
    Args:
        path: Path to CSV file with structured header
        
    Returns:
        HeaderBlocks containing parsed procedure, parameters, metadata,
        and the line number where data begins
        
    Example:
        >>> hb = parse_header(Path("experiment.csv"))
        >>> hb.proc
        'iv_sweep'
        >>> hb.parameters["Laser wavelength"]
        '450'
        >>> hb.metadata["Start time"]
        '2025-01-15T10:30:00Z'
        
    Note:
        - If "Start time" appears in parameters but not metadata, it's copied to metadata
        - Handles malformed headers gracefully (missing sections return empty dicts)
        - Uses 'errors="ignore"' when reading to handle encoding issues
    """
    proc = None
    params: Dict[str, str] = {}
    meta: Dict[str, str] = {}
    data_header_line: Optional[int] = None
    mode: Optional[str] = None

    with path.open("r", errors="ignore", encoding="utf-8") as f:
        for i, raw in enumerate(f):
            s = raw.rstrip("\n").strip()

            if DATA_LINE_RE.match(s):
                data_header_line = i + 1
                break

            m = PROC_LINE_RE.match(s)
            if m:
                proc = m.group(1).split(".")[-1].strip()
                continue
            if PARAMS_LINE_RE.match(s):
                mode = "params"; continue
            if META_LINE_RE.match(s):
                mode = "meta"; continue

            if s.startswith("#"):
                m = KV_PAT.match(s)
                if m:
                    key = m.group(1).strip()
                    val = m.group(2).strip()
                    if mode == "params":
                        params[key] = val
                    elif mode == "meta":
                        meta[key] = val

    if "Start time" in params and "Start time" not in meta:
        meta["Start time"] = params["Start time"]

    return HeaderBlocks(proc=proc, parameters=params, metadata=meta, data_header_line=data_header_line)


# --------------------------- Casting / Normalizing --------------------------

def cast_block(block: Dict[str, str], spec: Dict[str, str]) -> Dict[str, Any]:
    """
    Cast header block values to their declared types.
    
    Applies type casting to parameter or metadata values according to the
    YAML specification. Handles special cases like numeric values with units
    and datetime parsing.
    
    Args:
        block: Dictionary of key-value pairs from CSV header (all strings)
        spec: Type specification mapping from YAML (e.g., {"Laser wavelength": "float"})
        
    Returns:
        Dictionary with values cast to appropriate Python types
        
    Supported types:
        - "int": Integer (extracts number from strings like "100ms")
        - "float": Float (extracts number from strings with units)
        - "float_no_unit": Float (no unit parsing, strict conversion)
        - "bool": Boolean (recognizes "1", "true", "yes", "on", "y")
        - "datetime": datetime object (handles ISO format and Unix timestamps)
        - "str" or other: Kept as string
        
    Example:
        >>> block = {"Laser wavelength": "450nm", "Chip number": "42"}
        >>> spec = {"Laser wavelength": "float", "Chip number": "int"}
        >>> cast_block(block, spec)
        {"Laser wavelength": 450.0, "Chip number": 42}
        
    Note:
        If casting fails, the original string value is kept to prevent
        crashes during staging. This ensures robustness against malformed data.
    """
    out: Dict[str, Any] = {}
    for k, v in block.items():
        t = (spec.get(k) or "str").strip().lower()
        try:
            if t == "int":
                num, _ = parse_number_unit(v)
                out[k] = int(num) if num is not None else int(float(str(v)))
            elif t == "float":
                num, _ = parse_number_unit(v)
                out[k] = float(num) if num is not None else float(str(v))
            elif t == "float_no_unit":
                out[k] = float(str(v))
            elif t == "bool":
                out[k] = to_bool(v)
            elif t == "datetime":
                dtv = v if isinstance(v, dt.datetime) else parse_datetime_any(v)
                if dtv is not None:
                    out[k] = dtv
            else:
                out[k] = v
        except Exception:
            out[k] = v  # why: do not crash staging on bad header value
    return out


# -------- Column matching to YAML "Data" names (tolerant, but target = YAML) --------

def _norm(s: str) -> str:
    """
    Normalize string for robust column name matching.
    
    Removes whitespace, punctuation, and case differences to enable
    fuzzy matching between CSV column names and YAML canonical names.
    
    Args:
        s: String to normalize (typically a column name)
        
    Returns:
        Normalized string (lowercase, no spaces/punctuation)
        
    Example:
        >>> _norm("Vsd (V)")
        'vsdv'
        >>> _norm("VDS [V]")
        'vdsv'
        >>> _norm("V_DS_V")
        'vdsv'
        >>> _norm("Plate T (°C)")
        'platetdegc'
        
    Note:
        Handles Unicode degree symbols (°, ℃) by converting to "deg"/"degc"
    """
    # why: robust compare across "Vsd (V)" vs "vd_v" vs "VDS"
    s = s.strip()
    s = s.lower()
    s = re.sub(r"\s+", "", s)
    s = s.replace("_", "")
    s = s.replace("-", "")
    s = s.replace("Â°", "deg")
    s = s.replace("â„ƒ", "degc")
    s = s.replace("(", "").replace(")", "")
    s = s.replace("[", "").replace("]", "")
    return s


# Synonym seeds per YAML key (targets); each value is a list of regexes or literal alt names.
YAML_DATA_SYNONYMS: Dict[str, List[str]] = {
    "I (A)":         [r"^i$", r"^i_a$", r"^id(_a)?$", r"^ids(_a)?$", r"^current(_a)?$"],
    "Vsd (V)":       [r"^vsd(_v)?$", r"^vd(_v)?$", r"^vds(_v)?$", r"^vdv$", r"^vds$"],
    "Vg (V)":        [r"^vg(_v)?$", r"^v_g(_v)?$", r"^gate_v(_v)?$"],
    "VL (V)":        [r"^vl(_v)?$", r"^vlv$"],
    "t (s)":         [r"^t(_s)?$", r"^time(_s)?$"],
    "Plate T (degC)":[r"^platet(degc)?$", r"^platetemp(degc)?$", r"^plate_c$"],
    "Ambient T (degC)":[r"^ambientt(degc)?$", r"^ambienttemp(degc)?$", r"^ambient_c$"],
    "Clock (ms)":    [r"^clock(_ms)?$"],
    "Vg (V)":        [r"^vg(_v)?$"],
}


def build_yaml_rename_map(df_cols: List[str], yaml_data: Dict[str, str]) -> Dict[str, str]:
    """
    Build mapping from CSV column names to YAML canonical names.
    
    Uses three-tier matching strategy to handle naming variations:
    1. Exact normalized match (after removing punctuation/case)
    2. Synonym pattern matching (regex-based common variations)
    3. Uppercase heuristic (tries uppercased version)
    
    Args:
        df_cols: List of column names from CSV DataFrame
        yaml_data: Target column names from YAML Data specification
        
    Returns:
        Dictionary mapping {csv_column_name -> yaml_canonical_name}
        Only includes columns that successfully matched.
        
    Example:
        >>> df_cols = ["i_a", "VDS", "vg_v", "time"]
        >>> yaml_data = {"I (A)": "float", "Vsd (V)": "float", "Vg (V)": "float", "t (s)": "float"}
        >>> build_yaml_rename_map(df_cols, yaml_data)
        {'i_a': 'I (A)', 'VDS': 'Vsd (V)', 'vg_v': 'Vg (V)', 'time': 't (s)'}
        
    Note:
        - If multiple CSV columns match the same target, only the first (in order) is used
        - Case-insensitive matching
        - Handles common variations like "I" vs "Id" vs "IDS" vs "current"
    """
    rename: Dict[str, str] = {}
    by_norm = {_norm(c): c for c in df_cols}

    for target in yaml_data.keys():
        target_norm = _norm(target)
        # 1) exact normalized match
        if target_norm in by_norm:
            rename[by_norm[target_norm]] = target
            continue
        # 2) synonym match
        for pat in YAML_DATA_SYNONYMS.get(target, []):
            # normalize pattern "like" DF names as well
            # compare normalized df col against regex sans punctuation
            rx = re.compile(pat, re.I)
            # try direct df columns
            hit = None
            for c in df_cols:
                if rx.fullmatch(c) or rx.fullmatch(_norm(c)):
                    hit = c; break
            if hit:
                rename[hit] = target
                break
        # 3) uppercase version heuristic (e.g., "VSD (V)")
        if target not in rename:
            upper_guess = target.upper().replace(" ", "")
            for c in df_cols:
                if _norm(c) == _norm(upper_guess):
                    rename[c] = target
                    break
    return rename


def cast_df_data_types(df: pl.DataFrame, yaml_data: Dict[str, str]) -> pl.DataFrame:
    """
    Cast DataFrame columns to types declared in YAML Data specification.
    
    Applies type casting to data columns that exist in both the DataFrame
    and the YAML schema. Handles type conversion failures gracefully.
    
    Args:
        df: Polars DataFrame with data columns (potentially after renaming)
        yaml_data: Type specification from YAML (e.g., {"I (A)": "float"})
        
    Returns:
        DataFrame with columns cast to declared types
        
    Supported types:
        - "float" / "float_no_unit": Cast to Float64
        - "int": Cast to Int64
        - "bool": Convert string/numeric to boolean
        - "datetime": Convert to string (full parsing deferred)
        - other: Convert to string (Utf8)
        
    Example:
        >>> df = pl.DataFrame({"I (A)": ["0.001", "0.002"], "Vsd (V)": ["1.5", "1.6"]})
        >>> yaml_data = {"I (A)": "float", "Vsd (V)": "float"}
        >>> df = cast_df_data_types(df, yaml_data)
        >>> df.schema
        {'I (A)': Float64, 'Vsd (V)': Float64}
        
    Note:
        - Uses strict=False to handle invalid values gracefully (null instead of error)
        - Only casts columns present in both df and yaml_data
        - Boolean casting recognizes: "1", "true", "yes", "on", "y" (case-insensitive)
    """
    casts = []
    for col, typ in yaml_data.items():
        if col not in df.columns:
            continue
        t = typ.strip().lower()
        if t in {"float", "float_no_unit"}:
            casts.append(pl.col(col).cast(pl.Float64, strict=False).alias(col))
        elif t == "int":
            casts.append(pl.col(col).cast(pl.Int64, strict=False).alias(col))
        elif t == "bool":
            casts.append(pl.when(pl.col(col).is_in([True, False]))
                          .then(pl.col(col))
                          .otherwise(pl.col(col).cast(pl.Utf8, strict=False).str.to_lowercase().is_in(["1","true","yes","on","y"]))
                          .alias(col))
        elif t == "datetime":
            # store as Utf8; many data tables won't have datetimes; skip heavy parsing here
            casts.append(pl.col(col).cast(pl.Utf8, strict=False).alias(col))
        else:
            casts.append(pl.col(col).cast(pl.Utf8, strict=False).alias(col))
    if casts:
        df = df.with_columns(casts)
    return df


# ------------------------------- IO ----------------------------------

def read_numeric_table(path: Path, header_line: Optional[int]) -> pl.DataFrame:
    """
    Read CSV data table with fallback parsing strategy.
    
    Attempts to read CSV with comment-aware parsing first, then falls back
    to manual skip_rows if that fails. Designed to handle measurement CSVs
    with comment headers.
    
    Args:
        path: Path to CSV file
        header_line: Line number where data header appears (if known)
        
    Returns:
        Polars DataFrame containing the data table
        
    Example:
        >>> df = read_numeric_table(Path("measurement.csv"), header_line=10)
        >>> df.columns
        ['I (A)', 'Vsd (V)', 'Vg (V)', 't (s)']
        
    Note:
        - First tries with comment_prefix="#" to auto-skip comment lines
        - Falls back to skip_rows if that fails (handles non-standard formats)
        - Uses low_memory=True for efficiency
        - truncate_ragged_lines=True handles inconsistent row lengths
        - try_parse_dates=False keeps dates as strings (faster)
    """
    try:
        return pl.read_csv(
            path,
            comment_prefix="#",
            has_header=True,
            infer_schema_length=10000,
            try_parse_dates=False,
            low_memory=True,
            truncate_ragged_lines=True,
        )
    except Exception:
        return pl.read_csv(
            path,
            skip_rows=(header_line or 0),
            has_header=True,
            infer_schema_length=10000,
            try_parse_dates=False,
            low_memory=True,
            truncate_ragged_lines=True,
        )


def resolve_start_dt_and_date(src: Path, meta: Dict[str, Any], local_tz: str) -> Tuple[dt.datetime, str, str]:
    """
    Determine measurement start datetime and partition date with fallback logic.
    
    Uses a three-tier fallback strategy to determine when a measurement occurred:
    1. Metadata "Start time" field (most reliable)
    2. Date extracted from file path (e.g., "2025-01-15" in filename)
    3. File modification time (last resort)
    
    Args:
        src: Path to source CSV file
        meta: Metadata dictionary (may contain "Start time")
        local_tz: IANA timezone name for date partitioning (e.g., "America/Santiago")
        
    Returns:
        Tuple of (start_datetime, partition_date, origin_source):
        - start_datetime: UTC timestamp when measurement started
        - partition_date: Date string in YYYY-MM-DD format (in local timezone)
        - origin_source: One of "meta", "path", or "mtime" indicating data source
        
    Example:
        >>> meta = {"Start time": "2025-01-15T10:30:00Z"}
        >>> resolve_start_dt_and_date(Path("exp.csv"), meta, "America/Santiago")
        (datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc), '2025-01-15', 'meta')
        
        >>> # No metadata, but path contains date
        >>> resolve_start_dt_and_date(Path("data/2025-01-15/exp.csv"), {}, "America/Santiago")
        (datetime(2025, 1, 15, 4, 0, tzinfo=timezone.utc), '2025-01-15', 'path')
        
    Note:
        - All timestamps normalized to UTC internally
        - Partition date uses local timezone (important for business date grouping)
        - File mtime fallback ensures function always succeeds
    """
    st = meta.get("Start time")
    dtv = st if isinstance(st, dt.datetime) else parse_datetime_any(st)
    if isinstance(dtv, dt.datetime):
        return dtv, local_date_for_partition(dtv, local_tz), "meta"
    dpath = extract_date_from_path(src)
    if dpath:
        if ZoneInfo is not None:
            tz = ZoneInfo(local_tz)
            local_midnight = dt.datetime.combine(dt.date.fromisoformat(dpath), dt.time(), tzinfo=tz)
            utc_dt = local_midnight.astimezone(dt.timezone.utc)
        else:
            utc_dt = dt.datetime.fromisoformat(dpath + "T00:00:00").replace(tzinfo=dt.timezone.utc)
        return utc_dt, dpath, "path"
    mtime = dt.datetime.fromtimestamp(src.stat().st_mtime, tz=dt.timezone.utc)
    dpart = local_date_for_partition(mtime, local_tz)
    return mtime, dpart, "mtime"


def atomic_write_parquet(df: pl.DataFrame, out_file: Path) -> None:
    """
    Write DataFrame to Parquet with atomic file creation.
    
    Uses a temporary file + rename strategy to ensure partial files are never
    visible. This prevents corruption if the process crashes during write.
    
    Args:
        df: Polars DataFrame to write
        out_file: Destination path for Parquet file
        
    Raises:
        Exception: If write fails, temporary file is cleaned up
        
    Example:
        >>> df = pl.DataFrame({"a": [1, 2, 3]})
        >>> atomic_write_parquet(df, Path("output/data.parquet"))
        # Creates output/data.parquet atomically
        
    Note:
        - Parent directory is created if it doesn't exist
        - Temporary file created in same directory (ensures same filesystem)
        - Atomic rename ensures readers never see partial data
        - Temporary file cleaned up on failure
    """
    ensure_dir(out_file.parent)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=out_file.parent) as tmp:
        tmp_path = Path(tmp.name)
    try:
        df.write_parquet(tmp_path)
        tmp_path.replace(out_file)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        raise


# ------------------------------- Worker ----------------------------------

def ingest_file_task(
    src_str: str,
    stage_root_str: str,
    procedures_yaml_str: str,
    local_tz: str,
    force: bool,
    events_dir_str: str,
    rejects_dir_str: str,
    only_yaml_data: bool,
) -> Dict[str, Any]:
    """
    Process a single CSV file into staged Parquet format.
    
    This is the main worker function executed in parallel. It handles the complete
    pipeline for one CSV file: parsing, validation, column mapping, type casting,
    metadata enrichment, and Parquet output.
    
    Args:
        src_str: Path to source CSV file (as string for serialization)
        stage_root_str: Root directory for staged Parquet output
        procedures_yaml_str: Path to procedures YAML schema file
        local_tz: IANA timezone name for date partitioning
        force: If True, overwrite existing Parquet files
        events_dir_str: Directory for per-run event JSON files
        rejects_dir_str: Directory for reject records (failed files)
        only_yaml_data: If True, drop columns not in YAML schema
        
    Returns:
        Event dictionary with processing results:
        - status: "ok", "skipped", or "reject"
        - run_id: Unique identifier for this measurement run
        - proc: Procedure name
        - rows: Number of data rows
        - path: Output Parquet file path
        - source_file: Original CSV file path
        - date_origin: Source of date ("meta", "path", or "mtime")
        - error: Error message (only if status="reject")
        
    Example output (success):
        {
            "ts": datetime(2025, 1, 15, 10, 35, 22),
            "status": "ok",
            "run_id": "a1b2c3d4e5f6g7h8",
            "proc": "iv_sweep",
            "rows": 1500,
            "path": "/stage/proc=iv_sweep/date=2025-01-15/run_id=a1b2.../part-000.parquet",
            "source_file": "/raw/experiment_20250115.csv",
            "date_origin": "meta"
        }
        
    Processing steps:
        1. Parse CSV header (procedure, parameters, metadata)
        2. Validate against YAML schema
        3. Cast parameter/metadata types
        4. Read data table
        5. Rename columns to YAML canonical names
        6. Cast data column types
        7. Derive computed flags (e.g., with_light)
        8. Add metadata columns (run_id, proc, timestamps, etc.)
        9. Write to Hive-partitioned Parquet structure
        10. Write event JSON for tracking
        
    Note:
        - Function takes string paths (not Path objects) for pickle serialization
        - Generates unique run_id from source path + timestamp
        - Skips processing if output exists and force=False
        - Writes reject record to separate directory on any error
        - Uses cached YAML schema (loaded once per worker process)
    """
    src = Path(src_str)
    stage_root = Path(stage_root_str)
    procedures_yaml = Path(procedures_yaml_str)
    events_dir = Path(events_dir_str)
    rejects_dir = Path(rejects_dir_str)

    procs = get_procs_cached(procedures_yaml)

    try:
        hb = parse_header(src)
        if not hb.proc:
            raise RuntimeError("missing '# Procedure:'")
        proc = hb.proc
        spec = procs.get(proc, ProcSpec({}, {}, {}))

        params = cast_block(hb.parameters, spec.params)
        meta = cast_block(hb.metadata, spec.meta)
        if "Start time" in params and "Start time" not in meta:
            meta["Start time"] = params["Start time"]

        start_dt, date_part, origin = resolve_start_dt_and_date(src, meta, local_tz)
        rid = sha1_short(f"{src.as_posix()}|{start_dt.timestamp()}")

        df = read_numeric_table(src, hb.data_header_line)
        if df.height == 0:
            raise RuntimeError("empty data table")

        # --- NEW: rename data columns to exact YAML "Data" names ---
        if spec.data:
            ren_map = build_yaml_rename_map(df.columns, spec.data)
            if ren_map:
                df = df.rename(ren_map)
            # Optionally drop non-YAML columns
            if only_yaml_data:
                keep = [c for c in spec.data.keys() if c in df.columns]
                df = df.select(keep)
            # Cast per YAML types (for those present)
            df = cast_df_data_types(df, spec.data)

        # Derive light flags (works even with YAML naming; keys come from Parameters)
        with_light = False
        wl_f = None
        lv_f = None
        def _get_float(keys):
            for key in keys:
                if key in params and params[key] is not None:
                    try:
                        return float(params[key])
                    except (TypeError, ValueError):
                        continue
            return None

        try:
            wl_f = float(params.get("Laser wavelength")) if params.get("Laser wavelength") is not None else None
        except Exception:
            wl_f = None
        try:
            lv_f = float(params.get("Laser voltage")) if params.get("Laser voltage") is not None else None
        except Exception:
            lv_f = None

        vds_v = _get_float(["VDS", "Vds", "VSD", "Drain voltage"])
        vg_fixed_v = _get_float(["VG", "Vg", "Gate voltage", "Fixed gate voltage"])
        vg_start_v = _get_float(["VG start", "Vg start"])
        vg_end_v = _get_float(["VG end", "Vg end"])
        vg_step_v = _get_float(["VG step", "Vg step"])
        laser_period_s = _get_float(["Laser ON+OFF period", "Laser ON+OFF period (s)", "ON+OFF period"])

        # LaserCalibration-specific parameters
        optical_fiber = params.get("Optical fiber")
        laser_voltage_start_v = _get_float(["Laser voltage start"])
        laser_voltage_end_v = _get_float(["Laser voltage end"])
        laser_voltage_step_v = _get_float(["Laser voltage step"])
        sensor_model = meta.get("Sensor model")

        # with_light logic: For LaserCalibration, check if wavelength exists and voltage sweep is defined
        if proc == "LaserCalibration":
            with_light = (wl_f is not None) and (laser_voltage_start_v is not None or laser_voltage_end_v is not None)
        else:
            with_light = (wl_f is not None) and (lv_f is not None) and (lv_f != 0.0)

        out_dir = stage_root / f"proc={proc}" / f"date={date_part}" / f"run_id={rid}"
        out_file = out_dir / "part-000.parquet"

        event_common = {
            "ts": dt.datetime.now(tz=dt.timezone.utc),
            "run_id": rid,
            "proc": proc,
            "rows": df.height,
            "path": str(out_file),
            "source_file": str(src),
            "date_origin": origin,
            "chip_number": params.get("Chip number"),
            "chip_group": params.get("Chip group name"),
            "start_time_utc": start_dt,
            "has_light": with_light,
            "wavelength_nm": wl_f,
            "laser_voltage_V": lv_f,
            "laser_period_s": laser_period_s,
            "vds_v": vds_v,
            "vg_fixed_v": vg_fixed_v,
            "vg_start_v": vg_start_v,
            "vg_end_v": vg_end_v,
            "vg_step_v": vg_step_v,
            "date_local": date_part,
            # LaserCalibration-specific parameters
            "optical_fiber": optical_fiber,
            "laser_voltage_start_v": laser_voltage_start_v,
            "laser_voltage_end_v": laser_voltage_end_v,
            "laser_voltage_step_v": laser_voltage_step_v,
            "sensor_model": sensor_model,
        }

        if out_file.exists() and not force:
            event = {"status": "skipped", **event_common}
        else:
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
                # LaserCalibration-specific parameters
                "optical_fiber": optical_fiber,
                "laser_voltage_start_v": laser_voltage_start_v,
                "laser_voltage_end_v": laser_voltage_end_v,
                "laser_voltage_step_v": laser_voltage_step_v,
                "sensor_model": sensor_model,
            }
            df = df.with_columns([pl.lit(v).alias(k) for k, v in extra_cols.items()])
            atomic_write_parquet(df, out_file)

            event = {"status": "ok", **event_common}

        ev_path = events_dir / f"event-{rid}.json"
        ensure_dir(ev_path.parent)
        with ev_path.open("w", encoding="utf-8") as f:
            json.dump(event, f, ensure_ascii=False, default=str)
        return event

    except Exception as e:
        phash = sha1_short(src.as_posix(), 12)
        rej_path = Path(rejects_dir) / f"{src.stem}-{phash}.reject.json"
        ensure_dir(rej_path.parent)
        rec = {"source_file": str(src), "error": str(e), "ts": dt.datetime.now(tz=dt.timezone.utc).isoformat()}
        with rej_path.open("w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        return {"status": "reject", "source_file": str(src), "error": str(e)}


# ------------------------------- Orchestration ----------------------------------

def discover_csvs(root: Path) -> list[Path]:
    """
    Recursively discover all CSV files under a root directory.
    
    Searches for CSV files while excluding common non-data directories
    and system files.
    
    Args:
        root: Root directory to search
        
    Returns:
        Sorted list of Path objects pointing to CSV files
        
    Excluded:
        - Hidden directories: .git, .venv, __pycache__, .ipynb_checkpoints
        - macOS resource fork files (starting with "._")
        
    Example:
        >>> csvs = discover_csvs(Path("01_raw"))
        >>> len(csvs)
        147
        >>> csvs[0]
        Path('01_raw/2025-01-15/experiment_001.csv')
        
    Note:
        Results are sorted for reproducible processing order.
    """
    EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".ipynb_checkpoints"}
    files: list[Path] = []
    for p in root.rglob("*.csv"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.name.startswith("._"):
            continue
        files.append(p)
    files.sort()
    return files


def merge_events_to_manifest(events_dir: Path, manifest_path: Path) -> None:
    """
    Consolidate individual event JSON files into a single Parquet manifest.
    
    Reads all event-*.json files from the events directory, combines them
    into a DataFrame, and merges with any existing manifest. Deduplicates
    by (run_id, ts, status, path), keeping the latest occurrence.
    
    Args:
        events_dir: Directory containing event-*.json files
        manifest_path: Path to output manifest.parquet file
        
    Example:
        >>> merge_events_to_manifest(
        ...     Path("02_stage/_manifest/events"),
        ...     Path("02_stage/_manifest/manifest.parquet")
        ... )
        # Creates/updates manifest.parquet with all processing events
        
    Manifest schema:
        - ts: Timestamp when event occurred
        - status: "ok", "skipped", or "reject"
        - run_id: Unique measurement run identifier
        - proc: Procedure name
        - rows: Number of data rows processed
        - path: Output Parquet file path
        - source_file: Original CSV file path
        - date_origin: Source of partition date ("meta", "path", or "mtime")
        
    Note:
        - Creates parent directory if needed
        - Handles missing event files gracefully
        - Uses vertical_relaxed concat to handle schema variations
        - Deduplication ensures idempotent reruns
    """
    ev_files = sorted(events_dir.glob("event-*.json"))
    if not ev_files:
        return
    rows = []
    for e in ev_files:
        try:
            rows.append(json.loads(e.read_text(encoding="utf-8")))
        except Exception:
            continue
    if not rows:
        return
    # Normalize rows to shared schema before creating DataFrame.
    # Existing event files may have been written by older staging versions
    # without the newer metadata columns (vds_v, vg_fixed_v, etc.).
    # Polars requires consistent keys across rows, so fill missing ones.
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    ordered_keys = sorted(all_keys)

    normalized_rows = []
    for row in rows:
        normalized = {k: row.get(k, None) for k in ordered_keys}
        normalized_rows.append(normalized)

    df = pl.DataFrame(normalized_rows)
    ensure_dir(manifest_path.parent)
    if manifest_path.exists():
        prev = pl.read_parquet(manifest_path)

        # Ensure both DataFrames have the same columns with matching types
        prev_cols = set(prev.columns)
        new_cols = set(df.columns)

        # Add missing columns to prev with correct types from df
        for col in new_cols - prev_cols:
            dtype = df[col].dtype
            prev = prev.with_columns(pl.lit(None, dtype=dtype).alias(col))

        # Add missing columns to df with correct types from prev
        for col in prev_cols - new_cols:
            dtype = prev[col].dtype
            df = df.with_columns(pl.lit(None, dtype=dtype).alias(col))

        # Ensure same column order
        common_cols = sorted(set(prev.columns) & set(df.columns))
        prev = prev.select(common_cols)
        df = df.select(common_cols)

        all_df = pl.concat([prev, df], how="vertical")
        # Deduplicate by run_id only (run_id is deterministic hash of path+timestamp)
        # Keep "last" to update records when re-running with --force
        all_df = all_df.unique(subset=["run_id"], keep="last")
        all_df.write_parquet(manifest_path)
    else:
        df.write_parquet(manifest_path)


def run_staging_pipeline(params: StagingParameters, progress_callback=None) -> None:
    """
    Run staging pipeline with Pydantic-validated parameters.

    Args:
        params: Validated StagingParameters instance
        progress_callback: Optional callback function(current, total, proc, status) for progress updates

    Example:
        >>> from models.parameters import StagingParameters
        >>> params = StagingParameters(
        ...     raw_root=Path("data/01_raw"),
        ...     stage_root=Path("data/02_stage/raw_measurements"),
        ...     procedures_yaml=Path("config/procedures.yml"),
        ...     workers=8,
        ...     force=True
        ... )
        >>> run_staging_pipeline(params)
    """
    # Extract validated parameters
    raw_root = params.raw_root
    stage_root = params.stage_root
    rejects_dir = params.rejects_dir
    events_dir = params.events_dir
    manifest_path = params.manifest
    local_tz = params.local_tz
    workers = params.workers
    polars_threads = params.polars_threads
    force = params.force
    only_yaml_data = params.only_yaml_data

    # Create output directories
    ensure_dir(stage_root)
    ensure_dir(rejects_dir)
    ensure_dir(events_dir)
    ensure_dir(manifest_path.parent)

    # Set Polars thread count
    os.environ["POLARS_MAX_THREADS"] = str(polars_threads)

    # Validate YAML schema (fail fast)
    _ = get_procs_cached(params.procedures_yaml)

    # Discover CSV files
    csvs = discover_csvs(raw_root)
    if not progress_callback:
        print(f"[info] discovered {len(csvs)} CSV files under {raw_root}")
    if not csvs:
        if not progress_callback:
            print("[done] nothing to do.")
        return

    # Process files in parallel
    from concurrent.futures import as_completed

    submitted = 0
    ok = skipped = reject = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        # Submit all tasks and track futures with their source files
        future_to_src = {}
        for src in csvs:
            fut = ex.submit(
                ingest_file_task,
                str(src),
                str(stage_root),
                str(params.procedures_yaml),
                local_tz,
                force,
                str(events_dir),
                str(rejects_dir),
                only_yaml_data,
            )
            future_to_src[fut] = src
            submitted += 1

        # Process futures as they complete (not in submission order)
        completed = 0
        for fut in as_completed(future_to_src):
            completed += 1
            src = future_to_src[fut]

            try:
                out = fut.result()
            except Exception as e:
                reject += 1
                if not progress_callback:
                    print(f"[{completed:04d}]  REJECT {src} :: {e}")
                if progress_callback:
                    progress_callback(completed, len(csvs), "unknown", "reject")
                continue

            st = out.get("status")
            proc = out.get("proc", "unknown")

            if st == "ok":
                ok += 1
            elif st == "skipped":
                skipped += 1
            elif st == "reject":
                reject += 1

            # Only print if no callback (verbose mode)
            if not progress_callback:
                if st in {"ok", "skipped"}:
                    print(f"[{completed:04d}] {st.upper():>7} {out['proc']:<8} rows={out['rows']:<7} → {out['path']}  ({out.get('date_origin','meta')})")
                else:
                    print(f"[{completed:04d}]  REJECT {src} :: {out.get('error')}")

            # Call progress callback if provided
            if progress_callback:
                progress_callback(completed, len(csvs), proc, st)

    # Merge events into manifest
    merge_events_to_manifest(events_dir, manifest_path)

    # Only print summary if no callback (verbose mode)
    if not progress_callback:
        print(f"[done] staging complete  |  ok={ok}  skipped={skipped}  rejects={reject}  submitted={submitted}")


def main() -> None:
    """
    Main entry point with both Pydantic and legacy argparse support.

    Supports three modes:
    1. JSON config file (--config)
    2. Pydantic parameters from code
    3. Legacy argparse (backward compatibility)

    Command-line arguments:
        --config: Path to JSON configuration file (Pydantic mode)

        OR legacy arguments:
        --raw-root: Input directory with CSV files (required)
        --stage-root: Output directory for Parquet files (required)
        --procedures-yaml: YAML schema file (required)
        --rejects-dir: Directory for reject records
        --events-dir: Directory for event JSONs
        --manifest: Manifest file path
        --local-tz: Timezone for date partitions (default: America/Santiago)
        --workers: Number of parallel workers (default: 6)
        --polars-threads: Polars threads per worker (default: 1)
        --force: Overwrite existing Parquet files
        --only-yaml-data: Drop non-YAML columns from output
    """
    ap = argparse.ArgumentParser(
        description="Stage raw CSVs → Parquet using YAML Data names (parallel & atomic).",
        epilog="""
Examples:
  # Using JSON config (recommended)
  python stage_raw_measurements.py --config config/staging_config.json

  # Using command-line arguments (legacy)
  python stage_raw_measurements.py \\
    --raw-root data/01_raw \\
    --stage-root data/02_stage/raw_measurements \\
    --procedures-yaml config/procedures.yml \\
    --workers 8 --force
        """
    )

    # Pydantic mode
    ap.add_argument("--config", type=Path, help="Path to JSON configuration file (Pydantic mode)")

    # Legacy arguments
    ap.add_argument("--raw-root", type=Path, help="Root folder with CSVs (01_raw)")
    ap.add_argument("--stage-root", type=Path, help="Output root (02_stage/raw_measurements)")
    ap.add_argument("--procedures-yaml", type=Path, help="YAML schema of procedures and types")
    ap.add_argument("--rejects-dir", type=Path, help="Folder for reject records")
    ap.add_argument("--events-dir", type=Path, help="Per-run event JSONs")
    ap.add_argument("--manifest", type=Path, help="Merged manifest parquet")
    ap.add_argument("--local-tz", type=str, default=DEFAULT_LOCAL_TZ, help="Timezone for date partitioning")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Process workers")
    ap.add_argument("--polars-threads", type=int, default=DEFAULT_POLARS_THREADS, help="POLARS_MAX_THREADS per worker")
    ap.add_argument("--force", action="store_true", help="Overwrite staged Parquet if exists")
    ap.add_argument("--only-yaml-data", action="store_true", help="Drop non-YAML data columns")

    args = ap.parse_args()

    try:
        # Mode 1: JSON config file (Pydantic)
        if args.config:
            print(f"[info] Loading configuration from {args.config}")
            params = StagingParameters.model_validate_json(args.config.read_text())
            print("[info] Configuration validated successfully")

        # Mode 2: Legacy argparse
        elif args.raw_root and args.stage_root and args.procedures_yaml:
            print("[info] Using command-line arguments (creating Pydantic parameters)")
            params = StagingParameters(
                raw_root=args.raw_root,
                stage_root=args.stage_root,
                procedures_yaml=args.procedures_yaml,
                rejects_dir=args.rejects_dir,
                events_dir=args.events_dir,
                manifest=args.manifest,
                local_tz=args.local_tz,
                workers=args.workers,
                polars_threads=args.polars_threads,
                force=args.force,
                only_yaml_data=args.only_yaml_data,
            )

        else:
            ap.print_help()
            print("\n[error] Must provide either --config or (--raw-root, --stage-root, --procedures-yaml)")
            sys.exit(1)

        # Run pipeline with validated parameters
        run_staging_pipeline(params)

    except ValidationError as e:
        print(f"\n[error] Parameter validation failed:")
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"\n[error] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
