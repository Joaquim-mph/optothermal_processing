# file: src/build_metadata_tree.py
#!/usr/bin/env python3
"""
Mirror-parse raw CSV headers into per-folder metadata.csv files.

Usage:
  python src/build_metadata_tree.py --raw raw_data --out metadata
"""

from __future__ import annotations

from pathlib import Path
import argparse
import re
import sys
from typing import Dict, List
import datetime as dt
import polars as pl

# ── Parsing helpers (why: robust numeric extraction from header values) ──
NUMERIC_FULL = re.compile(
    r"""^
       [-+]?               # sign
       \d*\.?\d+           # number
       (?:[eE][-+]?\d+)?   # sci
       (?:\s*[A-Za-z%μμΩ°]+)?  # unit
       $""",
    re.VERBOSE,
)
NUMERIC_PART = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

def _detect_has_light(params: Dict[str, object], csv_path: Path) -> bool | None:
    """
    Detect if experiment has light illumination.

    Detection strategy (in order of reliability):
    1. Laser voltage (LED voltage): V_LED < 0.1V = dark, V_LED >= 0.1V = light
    2. VL column in measurement data (fallback if voltage not in metadata)
    3. Unknown if both methods fail (requires manual review)

    Parameters
    ----------
    params : dict
        Parameters dictionary from CSV header
    csv_path : Path
        Path to CSV file (for reading VL data if needed)

    Returns
    -------
    bool or None
        True if light detected, False if dark, None if unknown
    """
    import numpy as np

    # Method 1: Laser voltage / LED voltage (PRIMARY - most reliable)
    # This is the DEFINITIVE indicator per user requirement
    laser_voltage = params.get("Laser voltage")
    if isinstance(laser_voltage, (int, float)):
        if laser_voltage < 0.1:
            return False  # DARK: V_LED < 0.1V
        else:
            return True   # LIGHT: V_LED >= 0.1V

    # Method 2: Check VL column in measurement data (FALLBACK)
    # Only use if laser voltage not in metadata
    try:
        # Import here to avoid circular dependency
        from src.core.utils import _read_measurement

        df = _read_measurement(csv_path)
        if "VL" in df.columns and len(df) > 0:
            vl_values = df["VL"].to_numpy()
            # Remove NaN values
            vl_clean = vl_values[~np.isnan(vl_values)]

            if len(vl_clean) > 0:
                # Apply same 0.1V threshold as metadata
                if np.any(vl_clean >= 0.1):
                    return True   # LIGHT: measured VL >= 0.1V
                else:
                    return False  # DARK: all measured VL < 0.1V
    except Exception as e:
        # If data read fails, continue to unknown
        pass

    # UNKNOWN: No reliable indicator found
    # This should trigger a warning (red !) in the UI
    return None

def parse_iv_metadata(csv_path: Path) -> Dict[str, object]:
    """
    Read the '#Parameters' and '#Metadata' header blocks of a .csv and return a flat dict.
    Adds:
      - start_time: float seconds since epoch (if found)
      - time_hms: 'HH:MM:SS' derived from start_time (local naive time)
    """
    params: Dict[str, object] = {}
    meta: Dict[str, object] = {}

    def _coerce(raw_val: str) -> object:
        if NUMERIC_FULL.match(raw_val):
            m = NUMERIC_PART.search(raw_val)
            if m:
                try:
                    return float(m.group())
                except ValueError:
                    return raw_val
        if raw_val.lower() in ("true", "false"):
            return raw_val.lower() == "true"
        return raw_val

    with csv_path.open(encoding="utf-8", errors="ignore") as f:
        section: str | None = None
        for line in f:
            if line.startswith("#Parameters:"):
                section = "params"
                continue
            if line.startswith("#Metadata:"):
                section = "meta"
                continue

            # stop once we hit non-header content
            if not line.startswith("#"):
                break

            # only parse indented header lines like "#\tKey: value"
            if section in ("params", "meta") and line.startswith("#\t"):
                try:
                    key, raw_val = line[2:].split(":", 1)
                except ValueError:
                    continue  # malformed line; skip
                key = key.strip()
                raw_val = raw_val.strip()
                val = _coerce(raw_val)
                if section == "params":
                    params[key] = val
                else:
                    meta[key] = val

    # Derive optional fields (existing logic)
    lv = params.get("Laser voltage")
    if isinstance(lv, (int, float)):
        params["Laser toggle"] = (lv != 0.0)

    # NEW: Detect has_light (True=light, False=dark, None=unknown)
    params["has_light"] = _detect_has_light(params, csv_path)

    # Add file path always
    params["source_file"] = str(csv_path)

    # --- New: derive start_time (float) and time_hms ---
    start_ts: float | None = None
    # Prefer metadata block, but fall back to parameters if present there
    start_raw = meta.get("Start time", params.get("Start time"))
    if isinstance(start_raw, (int, float)):
        start_ts = float(start_raw)
    elif isinstance(start_raw, str):
        m = NUMERIC_PART.search(start_raw)
        if m:
            try:
                start_ts = float(m.group())
            except ValueError:
                pass

    if start_ts is not None:
        params["start_time"] = start_ts
        # naive local time; if you want a specific TZ, convert here
        t = dt.datetime.fromtimestamp(start_ts)
        params["time_hms"] = t.strftime("%H:%M:%S")
    else:
        # keep keys present for schema stability
        params["start_time"] = None
        params["time_hms"] = None

    return params

# ── Core build ──
def find_csvs_in_directory(dir_path: Path) -> List[Path]:
    """
    Return CSV files directly under dir_path (no recursion), excluding '._*'.
    """
    return [
        p for p in dir_path.glob("*.csv")
        if not p.name.startswith("._") and p.is_file()
    ]

def write_metadata_csv(records: List[Dict[str, object]], out_csv: Path) -> None:
    """
    Write records to out_csv using Polars. Ensures parent dirs exist.
    """
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(records)
    # WHY: polars writes faster and keeps types; csv for portability
    df.write_csv(out_csv)

def build_metadata_tree(raw_root: Path, out_root: Path) -> int:
    """
    Walk raw_root; for each directory that has CSVs directly in it,
    parse and write out_root/<relative>/metadata.csv.
    Returns count of metadata files written.
    """
    written = 0
    # Include raw_root itself
    for dir_path in [raw_root, *[p for p in raw_root.rglob("*") if p.is_dir()]]:
        csvs = find_csvs_in_directory(dir_path)
        if not csvs:
            continue

        records: List[Dict[str, object]] = []
        for p in csvs:
            try:
                rec = parse_iv_metadata(p)
                records.append(rec)
            except Exception as e:
                print(f"warning: could not parse {p}: {e}", file=sys.stderr)

        if not records:
            continue

        rel = dir_path.relative_to(raw_root)  # '' for root
        out_dir = out_root / rel
        out_csv = out_dir / "metadata.csv"
        write_metadata_csv(records, out_csv)
        written += 1
        print(f"[ok] wrote {out_csv} ({len(records)} rows)")

    return written

# ── CLI ──
def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Mirror raw_data/ tree into metadata/ with per-folder metadata.csv files.")
    ap.add_argument("--raw", type=Path, default=Path("raw_data"), help="Root of raw CSV tree (default: raw_data)")
    ap.add_argument("--out", type=Path, default=Path("metadata"), help="Root of output mirror tree (default: metadata)")
    return ap.parse_args(argv)

def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    raw_root: Path = args.raw
    out_root: Path = args.out

    if not raw_root.exists() or not raw_root.is_dir():
        print(f"error: raw root not found: {raw_root}", file=sys.stderr)
        return 2

    count = build_metadata_tree(raw_root, out_root)
    if count == 0:
        print("warning: no metadata files written (no CSVs found?)", file=sys.stderr)
        return 1

    print(f"|DONE| wrote {count} metadata.csv file(s) under {out_root}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
