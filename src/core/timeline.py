from pathlib import Path
import re, math, datetime as dt
import polars as pl

# ---------- tiny header parsers ----------
_start_pat = re.compile(r"^\s*#\s*Start time:\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.I)
_proc_pat  = re.compile(r"^\s*#\s*Procedure:\s*<([^>]+)>\s*$", re.I)
_num_part = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _read_header_info(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            start_time = None
            procedure  = None
            for line in f:
                if line.lstrip().startswith("#Data"):
                    break
                if start_time is None:
                    m = _start_pat.match(line)
                    if m:
                        start_time = float(m.group(1))
                if procedure is None:
                    m2 = _proc_pat.match(line)
                    if m2:
                        procedure = m2.group(1)
            return {"start_time": start_time, "procedure": procedure}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def _proc_short(proc_str: str | None) -> str:
    if not proc_str:
        return "?"
    p = proc_str.split(".")
    return p[-1] if p else proc_str

def _light_indicator(has_light: bool | None) -> str:
    """
    Get emoji indicator for light status.

    Parameters
    ----------
    has_light : bool or None
        True=light, False=dark, None=unknown

    Returns
    -------
    str
        Emoji indicator: 💡 (light), 🌙 (dark), or ❗ (unknown/warning)
    """
    if has_light is True:
        return "💡"
    elif has_light is False:
        return "🌙"
    else:
        return "❗"  # Unknown - requires manual review




def _coerce_float(x):
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        m = _num_part.search(x)
        if m:
            try:
                return float(m.group())
            except ValueError:
                return None
    return None

def build_day_timeline(meta_csv: str, base_dir: Path, chip_group_name: str = "Chip") -> pl.DataFrame:
    # load the day metadata as-is (no chip filter)
    meta = pl.read_csv(meta_csv, ignore_errors=True)

    # Ensure columns we’ll reference exist
    for c in ["source_file","Chip number","VG","VDS","Laser voltage",
              "Laser wavelength","Laser ON+OFF period","Information",
              "VSD start","VSD end","VSD step","VG start","VG end","VG step",
              "start_time","Start time"]:
        if c not in meta.columns:
            meta = meta.with_columns(pl.lit(None).alias(c))

    file_idx_re = re.compile(r"_([0-9]+)\.csv$", re.I)

    rows = []
    for row in meta.iter_rows(named=True):
        src = row.get("source_file")
        if not src or (isinstance(src, float) and math.isnan(src)):
            continue
        path = base_dir / str(src)

        # --- NEW: prefer start_time from the metadata row itself ---
        start_time = _coerce_float(row.get("start_time"))
        if start_time is None:
            start_time = _coerce_float(row.get("Start time"))

        proc_full = None

        # If missing, try header scan
        if start_time is None or proc_full is None:
            head = _read_header_info(path)
            if start_time is None:
                st = head.get("start_time")
                start_time = float(st) if isinstance(st, (int, float)) else None
            proc_full = head.get("procedure") or proc_full

        # Last resort: file mtime
        if start_time is None:
            try:
                start_time = path.stat().st_mtime
            except Exception:
                start_time = None

        start_dt = dt.datetime.fromtimestamp(start_time) if start_time else None
        time_hms = start_dt.strftime("%H:%M:%S") if start_dt else "?"

        proc_short = _proc_short(proc_full)
        if proc_short == "?" and isinstance(src, str):
            if "IVg" in src: proc_short = "IVg"
            elif "It" in src: proc_short = "It"
            elif "IV" in src: proc_short = "IV"
            elif "LaserCalibration" in src: proc_short = "LaserCalibration"

        m = file_idx_re.search(str(src))
        file_idx = int(m.group(1)) if m else None

        # Get has_light from metadata (will be None if not present - old metadata)
        has_light = row.get("has_light")
        # Convert string "True"/"False" to boolean if needed (from CSV)
        if isinstance(has_light, str):
            has_light = has_light.lower() == "true" if has_light.lower() in ("true", "false") else None

        rows.append({
            "start_time": start_time,
            "start_dt": start_dt,
            "time_hms": time_hms,
            "proc": proc_short,
            "proc_full": proc_full,
            "chip": row.get("Chip number"),
            "VG": row.get("VG"),
            "VDS": row.get("VDS"),
            "VL": row.get("Laser voltage"),
            "wl": row.get("Laser wavelength"),
            "period": row.get("Laser ON+OFF period"),
            "info": row.get("Information"),
            "VSD_start": row.get("VSD start"),
            "VSD_end": row.get("VSD end"),
            "VSD_step": row.get("VSD step"),
            "VG_start": row.get("VG start"),
            "VG_end": row.get("VG end"),
            "VG_step": row.get("VG step"),
            "source_file": src,
            "file_idx": file_idx,
            "has_light": has_light,  # NEW: light status
        })

    if not rows:
        return pl.DataFrame()

    df = pl.DataFrame(rows).sort("start_time", nulls_last=True)

    # ---- build 'summary' in Python (no pl.map_rows) ----
    def _mk_summary(r: dict) -> str:
        p = r.get("proc")
        chip_num = (int(r["chip"]) if r.get("chip") is not None and str(r.get("chip")).strip() != "" else "?")
        chip = f"{chip_group_name}{chip_num}"

        # Get light indicator for ITS experiments
        light_icon = ""
        if p == "It":
            light_icon = _light_indicator(r.get("has_light")) + " "

        if p == "It":
            return (f"{light_icon}It  {chip}  "
                    f"VG={r.get('VG','?')} V  VDS={r.get('VDS','?')} V  "
                    f"VL={r.get('VL','?')} V  λ={r.get('wl','?')} nm  "
                    f"period={r.get('period','?')} s  "
                    f"#{r.get('file_idx','?')}")
        if p == "IVg":
            return (f"IVg {chip}  VDS={r.get('VDS','?')} V  "
                    f"VG:{r.get('VG_start','?')}→{r.get('VG_end','?')} (step {r.get('VG_step','?')})  "
                    f"#{r.get('file_idx','?')}")
        if p == "IV":
            return (f"IV  {chip}  VG={r.get('VG','?')} V  "
                    f"VSD:{r.get('VSD_start','?')}→{r.get('VSD_end','?')} (step {r.get('VSD_step','?')})  "
                    f"#{r.get('file_idx','?')}")
        if p == "LaserCalibration":
            return f"LaserCalibration λ={r.get('wl','?')} nm  #{r.get('file_idx','?')}"
        return f"{p} #{r.get('file_idx','?')}"

    summaries = [_mk_summary(r) for r in df.iter_rows(named=True)]
    df = df.with_columns(pl.Series("summary", summaries))
    df = df.with_columns(pl.arange(1, df.height + 1).alias("seq"))

    # Select columns to return - include has_light if present
    base_cols = ["seq","time_hms","proc","chip","summary","source_file","file_idx","start_time"]
    if "has_light" in df.columns:
        base_cols.append("has_light")

    return df.select(base_cols)



def print_day_timeline(
    meta_csv: str,
    base_dir: Path,
    *,
    save_csv: bool = True,
    chip_filter: int | None = None,
    proc_filter: str | None = None,
    show_elapsed: bool = True,
    chip_group_name: str = "Encap",
) -> pl.DataFrame:
    """
    Build and print a chronological timeline for a day's experiments.

    Parameters
    ----------
    meta_csv : str
        Path to the per-folder metadata.csv
    base_dir : Path
        Root that, combined with 'source_file', points to raw CSVs
    save_csv : bool
        If True, writes a sibling '<stem>_timeline.csv'
    chip_filter : int | None
        If set, only show this chip number
    proc_filter : str | None
        If set, only show this short procedure (e.g., "IV", "IVg", "It")
    show_elapsed : bool
        If True, prints cumulative elapsed time and gap since previous run
    chip_group_name : str
        Chip group name prefix (e.g., "Encap", "Chip"). Default: "Encap"

    Returns
    -------
    pl.DataFrame
        Columns: seq, time_hms, proc, chip, summary, source_file, file_idx, start_time
    """
    tl = build_day_timeline(meta_csv, base_dir, chip_group_name=chip_group_name)
    if tl.height == 0:
        print("[warn] no experiments found")
        return tl

    # Optional filters
    if chip_filter is not None:
        tl = tl.filter(pl.col("chip") == chip_filter)
    if proc_filter is not None:
        tl = tl.filter(pl.col("proc") == proc_filter)

    if tl.height == 0:
        print("[warn] timeline is empty after filters")
        return tl

    # Compute elapsed / gap if requested (safe on missing times)
    if show_elapsed and "start_time" in tl.columns:
        st = tl["start_time"].to_list()
        gaps = []
        elapsed = []
        t0 = None
        prev = None
        for t in st:
            if t is None:
                gaps.append(None)
                elapsed.append(None)
                continue
            if t0 is None:
                t0 = t
            gaps.append(None if prev is None or prev is None else t - prev)
            elapsed.append(t - t0 if t0 is not None else None)
            prev = t
        tl = tl.with_columns(
            pl.Series("gap_s", gaps),
            pl.Series("elapsed_s", elapsed),
        )

    # Pretty print
    print("\n=== Day timeline (chronological) ===")
    if show_elapsed and "elapsed_s" in tl.columns:
        # header with extra columns
        for r in tl.iter_rows(named=True):
            gap = r.get("gap_s")
            elp = r.get("elapsed_s")
            #gap_str = f"  +{gap:6.1f}s" if isinstance(gap, (int, float)) else "         "
            #elp_str = f"  t={elp:7.1f}s" if isinstance(elp, (int, float)) else "          "
            print(f"{r['seq']:>3d}  {r['time_hms']:>8}  {r['summary']}")
    else:
        for r in tl.iter_rows(named=True):
            print(f"{r['seq']:>3d}  {r['time_hms']:>8}  {r['summary']}")
    print("====================================\n")

    if save_csv:
        out = Path(meta_csv).with_name(Path(meta_csv).stem + "_timeline.csv")
        tl.write_csv(out)
        print(f"saved {out}")

    return tl


def build_chip_history(
    metadata_dir: Path,
    raw_data_dir: Path,
    chip_number: int,
    chip_group_name: str = "Alisson"
) -> pl.DataFrame:
    """
    Build complete experiment history for a specific chip across all days.

    Searches all metadata CSV files in metadata_dir and combines experiments
    for the specified chip into a single chronological timeline.

    Parameters
    ----------
    metadata_dir : Path
        Directory containing metadata CSV files (e.g., "metadata/")
    raw_data_dir : Path
        Root directory for raw data files (e.g., "raw_data/")
    chip_number : int
        The chip number to track (e.g., 72 for "Alisson72")
    chip_group_name : str
        Chip group name prefix. Default: "Alisson"

    Returns
    -------
    pl.DataFrame
        Combined timeline with columns: seq, date, time_hms, proc, summary,
        source_file, file_idx, start_time, day_folder
    """
    import glob

    # Find all metadata CSV files
    metadata_files = list(metadata_dir.glob("**/metadata.csv")) + \
                     list(metadata_dir.glob("**/*_metadata.csv"))

    if not metadata_files:
        print(f"[warn] no metadata files found in {metadata_dir}")
        return pl.DataFrame()

    all_timelines = []

    for meta_file in sorted(metadata_files):
        # Build timeline for this day
        try:
            day_tl = build_day_timeline(str(meta_file), raw_data_dir, chip_group_name=chip_group_name)

            if day_tl.height == 0:
                continue

            # Filter for the specific chip
            if "chip" in day_tl.columns:
                chip_tl = day_tl.filter(pl.col("chip") == chip_number)

                if chip_tl.height > 0:
                    # Add day folder info
                    day_folder = meta_file.parent.name
                    chip_tl = chip_tl.with_columns(pl.lit(day_folder).alias("day_folder"))
                    all_timelines.append(chip_tl)

        except Exception as e:
            print(f"[warn] failed to process {meta_file}: {e}")
            continue

    if not all_timelines:
        print(f"[info] no experiments found for {chip_group_name}{chip_number}")
        return pl.DataFrame()

    # Combine all timelines and sort by start_time
    combined = pl.concat(all_timelines).sort("start_time", nulls_last=True)

    # Add date column from start_time
    def _extract_date(ts):
        if ts is None:
            return "unknown"
        try:
            return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except:
            return "unknown"

    dates = [_extract_date(ts) for ts in combined["start_time"].to_list()]
    combined = combined.with_columns(pl.Series("date", dates))

    # Renumber sequence globally
    combined = combined.with_columns(pl.arange(1, combined.height + 1).alias("seq"))

    # Select columns to return - include has_light if present
    base_columns = [
        "seq", "date", "time_hms", "proc", "summary",
        "source_file", "file_idx", "start_time", "day_folder"
    ]

    # Add has_light if it exists in the dataframe
    if "has_light" in combined.columns:
        base_columns.append("has_light")

    return combined.select(base_columns)


def print_chip_history(
    metadata_dir: Path,
    raw_data_dir: Path,
    chip_number: int,
    chip_group_name: str = "Alisson",
    *,
    save_csv: bool = True,
    proc_filter: str | None = None,
) -> pl.DataFrame:
    """
    Print complete experiment history for a specific chip across all days.

    Parameters
    ----------
    metadata_dir : Path
        Directory containing metadata CSV files
    raw_data_dir : Path
        Root directory for raw data files
    chip_number : int
        The chip number to track
    chip_group_name : str
        Chip group name prefix. Default: "Alisson"
    save_csv : bool
        If True, saves timeline to '{chip_group_name}{chip_number}_history.csv'
    proc_filter : str | None
        If set, only show this procedure type (e.g., "IVg", "It", "IV")

    Returns
    -------
    pl.DataFrame
        Complete chip history timeline
    """
    history = build_chip_history(metadata_dir, raw_data_dir, chip_number, chip_group_name)

    if history.height == 0:
        print(f"[warn] no experiment history found for {chip_group_name}{chip_number}")
        return history

    # Optional procedure filter
    if proc_filter is not None:
        history = history.filter(pl.col("proc") == proc_filter)

    if history.height == 0:
        print(f"[warn] no experiments found after filtering for procedure '{proc_filter}'")
        return history

    # Print header
    chip_name = f"{chip_group_name}{chip_number}"
    print(f"\n{'='*80}")
    print(f"Complete Experiment History: {chip_name}")
    print(f"Total experiments: {history.height}")

    # Get date range
    dates = [d for d in history["date"].to_list() if d != "unknown"]
    if dates:
        print(f"Date range: {min(dates)} to {max(dates)}")

    print(f"{'='*80}\n")

    # Print timeline grouped by date
    current_date = None
    for r in history.iter_rows(named=True):
        date = r.get("date", "unknown")

        # Print date header when it changes
        if date != current_date:
            if current_date is not None:
                print()  # blank line between days
            print(f"─── {date} ({r.get('day_folder', '?')}) {'─'*50}")
            current_date = date

        print(f"{r['seq']:>4d}  {r['time_hms']:>8}  {r['summary']}")

    print(f"\n{'='*80}\n")

    # Save to CSV
    if save_csv:
        out_file = Path(f"{chip_name}_history.csv")
        history.write_csv(out_file)
        print(f"✓ Saved complete history to: {out_file}")

    return history


def generate_all_chip_histories(
    metadata_dir: Path,
    raw_data_dir: Path,
    chip_group_name: str = "Alisson",
    *,
    save_csv: bool = True,
    min_experiments: int = 1,
) -> dict[int, pl.DataFrame]:
    """
    Automatically generate experiment histories for all chips found in metadata.

    Scans all metadata files to find unique chip numbers, then generates
    a complete timeline for each chip.

    Parameters
    ----------
    metadata_dir : Path
        Directory containing metadata CSV files
    raw_data_dir : Path
        Root directory for raw data files
    chip_group_name : str
        Chip group name prefix. Default: "Alisson"
    save_csv : bool
        If True, saves each chip's history to a separate CSV file
    min_experiments : int
        Only include chips with at least this many experiments. Default: 1

    Returns
    -------
    dict[int, pl.DataFrame]
        Dictionary mapping chip_number -> history DataFrame
    """
    import glob

    print(f"\nScanning metadata directory: {metadata_dir}")

    # Find all metadata files
    metadata_files = list(metadata_dir.glob("**/metadata.csv")) + \
                     list(metadata_dir.glob("**/*_metadata.csv"))

    if not metadata_files:
        print(f"[warn] no metadata files found in {metadata_dir}")
        return {}

    print(f"Found {len(metadata_files)} metadata file(s)")

    # Discover all unique chip numbers
    all_chips = set()
    for meta_file in metadata_files:
        try:
            meta = pl.read_csv(meta_file, ignore_errors=True)
            if "Chip number" in meta.columns:
                chips = meta.get_column("Chip number").drop_nulls().unique().to_list()
                for c in chips:
                    try:
                        all_chips.add(int(float(c)))
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"[warn] failed to read {meta_file}: {e}")

    if not all_chips:
        print("[warn] no chips found in metadata files")
        return {}

    print(f"Found {len(all_chips)} unique chip(s): {sorted(all_chips)}\n")

    # Generate history for each chip
    histories = {}

    for chip_num in sorted(all_chips):
        print(f"Processing {chip_group_name}{chip_num}...")

        history = build_chip_history(
            metadata_dir,
            raw_data_dir,
            chip_num,
            chip_group_name
        )

        if history.height >= min_experiments:
            histories[chip_num] = history

            # Print summary
            dates = [d for d in history["date"].to_list() if d != "unknown"]
            date_range = f"{min(dates)} to {max(dates)}" if dates else "unknown dates"
            print(f"  → {history.height} experiments ({date_range})")

            # Save to CSV
            if save_csv:
                out_file = Path(f"{chip_group_name}{chip_num}_history.csv")
                history.write_csv(out_file)
                print(f"  → Saved to {out_file}")
        else:
            print(f"  → Skipped (only {history.height} experiment(s), minimum is {min_experiments})")

        print()

    print(f"{'='*80}")
    print(f"Generated histories for {len(histories)} chip(s)")
    print(f"{'='*80}\n")

    return histories