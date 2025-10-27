#!/usr/bin/env python3
"""
process_day.py — refactored

Automated processing script for a full day's experimental data.
Generates all requested plots based on the timeline and available measurements.

Key improvements:
- No global chdir; safe per-call output dirs via a pushd() context manager.
- Read metadata once; slice per chip in-memory (optionally parallel across chips).
- Robust date extraction from filename or metadata (falls back to "today").
- Chip ids normalized to int to avoid float troubles in joins/labels.
- Safer numeric extraction for VG_meta and Laser wavelength.
- Faster consecutive-group finder using NumPy.
- Logging instead of prints; --dry-run and --workers CLI flags.

Folder layout (unchanged):
figs/
└── ChipXX_YYYY_MM_DD/
    ├── ivg/
    │   ├── sequence/
    │   ├── groups/
    │   └── gifs/
    └── its/
        ├── by_vg_wl/
        ├── delta/
        └── overlays/
            ├── all/
            ├── uv_blue/
            └── green_red/
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import polars as pl

from src.plotting.plots import (
    load_and_prepare_metadata,  # expects (metadata_csv, chip_num) in your codebase
    plot_ivg_sequence,
    plot_its_by_vg,
    plot_its_by_vg_delta,
    plot_its_wavelength_overlay_delta_for_chip,
    ivg_sequence_gif,
)
from src.core.timeline import print_day_timeline
from src.plotting.styles import set_plot_style
import scienceplots  # noqa: F401  (style chosen by set_plot_style)
set_plot_style("prism_rain")


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

@contextmanager
def pushd(path: Path):
    """Temporary working directory switch that is exception-safe."""
    old = os.getcwd()
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old)


def create_organized_folder_structure(base_figs_dir: Path, chip_num: int, date_str: str) -> dict:
    chip_folder = base_figs_dir / f"Chip{chip_num:02d}_{date_str}"
    folders = {
        "chip_root": chip_folder,
        "ivg_root": chip_folder / "ivg",
        "ivg_sequence": chip_folder / "ivg" / "sequence",
        "ivg_groups": chip_folder / "ivg" / "groups",
        "ivg_gifs": chip_folder / "ivg" / "gifs",
        "its_root": chip_folder / "its",
        "its_by_vg_wl": chip_folder / "its" / "by_vg_wl",
        "its_delta": chip_folder / "its" / "delta",
        "its_overlays": chip_folder / "its" / "overlays",
        "its_overlays_all": chip_folder / "its" / "overlays" / "all",
        "its_overlays_uv_blue": chip_folder / "its" / "overlays" / "uv_blue",
        "its_overlays_green_red": chip_folder / "its" / "overlays" / "green_red",
    }
    for p in folders.values():
        p.mkdir(parents=True, exist_ok=True)
    return folders


def extract_date_from_metadata(metadata_csv: str, fallback_tz: str = "America/Santiago") -> str:
    """
    Prefer YYYY_MM_DD or DD_MM_YYYY in filename; else try first timestamp column in file; else today.
    """
    fn = Path(metadata_csv).stem

    # Filename patterns
    m = re.search(r"(?P<y>\d{4})[_-](?P<m>\d{1,2})[_-](?P<d>\d{1,2})", fn)
    if not m:
        m = re.search(r"(?P<d>\d{1,2})[_-](?P<m>\d{1,2})[_-](?P<y>\d{4})", fn)
    if m:
        y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
        return f"{y:04d}_{mo:02d}_{d:02d}"

    # Try reading one timestamp-ish column
    try:
        df_head = pl.read_csv(metadata_csv, n_rows=200)
        for col in ("Start time", "start_time", "start_dt", "time", "timestamp"):
            if col in df_head.columns:
                ts = (
                    df_head.select(
                        pl.col(col).str.strptime(pl.Datetime, strict=False, time_unit=None)
                    )
                    .drop_nulls()
                    .to_series()
                )
                if ts.len() > 0:
                    dt0 = ts[0].to_python()
                    return f"{dt0.year:04d}_{dt0.month:02d}_{dt0.day:02d}"
    except Exception:
        pass

    # Fallback to today
    t = datetime.now()
    return f"{t.year:04d}_{t.month:02d}_{t.day:02d}"


def norm_chip(value) -> int:
    """Normalize chip id to int (handles '75', 75.0, '75.0')."""
    try:
        return int(float(value))
    except Exception:
        return int(value)  # let it raise if impossible


def unique_numeric(df: pl.DataFrame, col: str) -> List[float]:
    """Return sorted, unique numeric values from df[col], robust to strings/mixed types."""
    if col not in df.columns:
        return []
    s = (
        df.select(pl.col(col).cast(pl.Float64, strict=False))
        .drop_nulls()
        .unique()
        .sort()
        .to_series()
    )
    return [float(x) for x in s.to_list()]


def find_consecutive_groups(nums: Iterable[int]) -> List[List[int]]:
    """Return lists of consecutive integers of length ≥ 2, using NumPy for speed."""
    a = np.unique(np.asarray(list(nums), dtype=int))
    if a.size == 0:
        return []
    splits = np.where(np.diff(a) != 1)[0] + 1
    groups = np.split(a, splits)
    return [g.tolist() for g in groups if g.size > 1]


# -------------------------------------------------------------------
# Core work
# -------------------------------------------------------------------

def process_chip(
    tag: str,
    full_meta: pl.DataFrame,
    chip_num: int,
    base_dir: Path,
    date_str: str,
    base_figs_dir: Path,
    generate_gifs: bool,
    generate_wavelength_overlays: bool,
    dry_run: bool = False,
) -> Path:
    """
    Process a single chip (safe to run in a separate process).
    Returns the chip's root output folder.
    """
    log = logging.getLogger(f"chip.{chip_num:02d}")
    folders = create_organized_folder_structure(base_figs_dir, chip_num, date_str)

    # Get chip-specific meta using your established helper
    # (kept as-is to avoid changing your internal plotting API)
    meta = load_and_prepare_metadata  # alias for readability

    # If your `load_and_prepare_metadata` only accepts (csv_path, chip_num),
    # use it directly; otherwise you can slice full_meta here.
    chip_meta = meta(str(tag), chip_num) if Path(tag).suffix else meta(tag, chip_num)

    if chip_meta.height == 0:
        log.warning("No data found; skipping.")
        return folders["chip_root"]

    procs = set(chip_meta.get_column("proc").to_list())
    log.info("Procedures: %s", sorted(procs))

    # -------------------- IVg --------------------
    if "IVg" in procs:
        log.info("IVg: sequence plot")
        seq_fname = f"{Path(tag).stem}_chip{chip_num:02d}_ivg_sequence"
        if dry_run:
            log.info("[dry-run] would plot_ivg_sequence → %s", folders["ivg_sequence"] / (seq_fname + ".png"))
        else:
            with pushd(folders["ivg_sequence"]):
                plot_ivg_sequence(chip_meta, base_dir, seq_fname)

        # Consecutive groups
        ivg_data = chip_meta.filter(pl.col("proc") == "IVg").sort("file_idx")
        if ivg_data.height > 1:
            indices = ivg_data.get_column("file_idx").to_list()
            for grp in find_consecutive_groups(indices):
                grp_fname = f"{Path(tag).stem}_chip{chip_num:02d}_group_{grp[0]:03d}_{grp[-1]:03d}"
                log.info("IVg: group %s", grp)
                if dry_run:
                    log.info("[dry-run] would plot group → %s", folders["ivg_groups"] / (grp_fname + ".png"))
                else:
                    subset = chip_meta.filter((pl.col("proc") == "IVg") & pl.col("file_idx").is_in(grp))
                    with pushd(folders["ivg_groups"]):
                        plot_ivg_sequence(subset, base_dir, grp_fname)

        # GIF
        if generate_gifs:
            gif_tag = f"{Path(tag).stem}_chip{chip_num:02d}_sequence"
            log.info("IVg: GIF")
            if dry_run:
                log.info("[dry-run] would gif → %s", folders["ivg_gifs"] / (gif_tag + ".gif"))
            else:
                with pushd(folders["ivg_gifs"]):
                    ivg_sequence_gif(chip_meta, base_dir, gif_tag, fps=2, cumulative=True)

    # -------------------- ITS --------------------
    if "ITS" in procs:
        its = chip_meta.filter(pl.col("proc") == "ITS")

        vgs = unique_numeric(its, "VG_meta")
        wls = unique_numeric(its, "Laser wavelength")

        log.info("ITS: VGs=%s | λ=%s", vgs, wls)

        # ITS per (VG, λ)
        for vg in vgs:
            for wl in wls:
                tag_base = f"{Path(tag).stem}_chip{chip_num:02d}_its_Vg{vg:+.1f}V_wl{wl:.0f}nm"
                if dry_run:
                    logging.info("[dry-run] would ITS → %s", folders["its_by_vg_wl"] / (tag_base + ".png"))
                else:
                    with pushd(folders["its_by_vg_wl"]):
                        plot_its_by_vg(chip_meta, base_dir, tag_base, vgs=[vg], wavelengths=[wl])

        # ITS Δ (baseline subtracted)
        for vg in vgs:
            for wl in wls:
                tag_base = f"{Path(tag).stem}_chip{chip_num:02d}_its_delta_Vg{vg:+.1f}V_wl{wl:.0f}nm"
                if dry_run:
                    logging.info("[dry-run] would ITSΔ → %s", folders["its_delta"] / (tag_base + ".png"))
                else:
                    with pushd(folders["its_delta"]):
                        plot_its_by_vg_delta(
                            chip_meta,
                            base_dir,
                            tag_base,
                            vgs=[vg],
                            wavelengths=[wl],
                            baseline_t=60.0,
                            clip_t_min=20.0,
                        )

        # Overlays
        if generate_wavelength_overlays and vgs:
            uv_blue = [wl for wl in wls if wl <= 455.0]
            green_red = [wl for wl in wls if wl > 455.0]

            for vg in vgs:
                # All λ
                t_all = f"{Path(tag).stem}_chip{chip_num:02d}_overlay_all_Vg{vg:+.1f}V"
                if dry_run:
                    logging.info("[dry-run] would overlay(all) → %s", folders["its_overlays_all"] / (t_all + ".png"))
                else:
                    with pushd(folders["its_overlays_all"]):
                        plot_its_wavelength_overlay_delta_for_chip(
                            chip_meta, base_dir, t_all,
                            chip=chip_num,
                            vg_center=vg, vg_window=1.5,
                            wavelengths=None,
                            baseline_t=60.0, clip_t_min=40.0,
                        )

                # UV/Blue
                if uv_blue:
                    t_uv = f"{Path(tag).stem}_chip{chip_num:02d}_overlay_UV_blue_Vg{vg:+.1f}V"
                    if dry_run:
                        logging.info("[dry-run] would overlay(uv_blue) → %s", folders["its_overlays_uv_blue"] / (t_uv + ".png"))
                    else:
                        with pushd(folders["its_overlays_uv_blue"]):
                            plot_its_wavelength_overlay_delta_for_chip(
                                chip_meta, base_dir, t_uv,
                                chip=chip_num,
                                vg_center=vg, vg_window=1.5,
                                wavelengths=uv_blue,
                                baseline_t=60.0, clip_t_min=40.0,
                            )

                # Green/Red
                if green_red:
                    t_gr = f"{Path(tag).stem}_chip{chip_num:02d}_overlay_green_red_Vg{vg:+.1f}V"
                    if dry_run:
                        logging.info("[dry-run] would overlay(green_red) → %s", folders["its_overlays_green_red"] / (t_gr + ".png"))
                    else:
                        with pushd(folders["its_overlays_green_red"]):
                            plot_its_wavelength_overlay_delta_for_chip(
                                chip_meta, base_dir, t_gr,
                                chip=chip_num,
                                vg_center=vg, vg_window=1.5,
                                wavelengths=green_red,
                                baseline_t=60.0, clip_t_min=40.0,
                            )

    log.info("Done. Output → %s", folders["chip_root"])
    return folders["chip_root"]


def process_day_experiments(
    metadata_csv: str,
    base_dir: Path,
    chips_to_process: Optional[List[int]] = None,
    generate_gifs: bool = True,
    generate_wavelength_overlays: bool = True,
    base_figs_dir: Path = Path("figs"),
    dry_run: bool = False,
    workers: int = 1,
) -> None:
    log = logging.getLogger("day")

    # Tag and date
    tag = Path(metadata_csv).as_posix()
    date_str = extract_date_from_metadata(metadata_csv)
    log.info("Date: %s", date_str)
    log.info("Base dir: %s  |  Output: %s", base_dir, base_figs_dir)

    # Timeline (best-effort)
    try:
        timeline = print_day_timeline(metadata_csv, base_dir)
        if isinstance(timeline, pl.DataFrame):
            log.info("Timeline rows: %d", timeline.height)
    except Exception as e:
        log.warning("Timeline skipped (%s)", e)

    # Load once
    full_meta = pl.read_csv(metadata_csv, infer_schema_length=2000)

    # Normalize chip column → int
    if "Chip number" in full_meta.columns:
        chips = (
            full_meta.get_column("Chip number")
            .drop_nulls()
            .map_elements(norm_chip)
            .unique()
            .sort()
            .to_list()
        )
    else:
        chips = []
    if chips_to_process is None or len(chips_to_process) == 0:
        chips_to_process = chips
    else:
        chips_to_process = [norm_chip(x) for x in chips_to_process if norm_chip(x) in set(chips)]

    log.info("Available chips: %s", chips)
    log.info("Processing chips: %s", chips_to_process)

    # Serial or parallel over chips
    if workers and workers > 1 and len(chips_to_process) > 1 and not dry_run:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = []
            for c in chips_to_process:
                futs.append(
                    ex.submit(
                        process_chip,
                        tag,
                        full_meta,
                        c,
                        base_dir,
                        date_str,
                        base_figs_dir,
                        generate_gifs,
                        generate_wavelength_overlays,
                        dry_run,
                    )
                )
            for f in as_completed(futs):
                try:
                    chip_root = f.result()
                    log.info("Finished %s", chip_root)
                except Exception as e:
                    log.exception("Chip failed: %s", e)
    else:
        for c in chips_to_process:
            process_chip(
                tag,
                full_meta,
                c,
                base_dir,
                date_str,
                base_figs_dir,
                generate_gifs,
                generate_wavelength_overlays,
                dry_run,
            )

    # Pretty tree print (best-effort)
    log.info("Output rooted at %s", base_figs_dir.resolve())
    for c in chips_to_process:
        chip_folder = base_figs_dir / f"Chip{c:02d}_{date_str}"
        if chip_folder.exists():
            log.info("Tree: %s", chip_folder)
            for sub in sorted(chip_folder.rglob("*")):
                if sub.is_dir():
                    rel = sub.relative_to(chip_folder)
                    indent = "  " * len(rel.parts)
                    log.info("%s└── %s/", indent, sub.name)


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Process all plots for a day's experiments into an organized folder tree.")
    ap.add_argument("--metadata-csv", type=Path, required=True, help="Path to the day's metadata CSV")
    ap.add_argument("--base-dir", type=Path, default=Path("raw_data"), help="Folder containing raw CSV files referenced by metadata")
    ap.add_argument("--chips", type=str, default="", help="Comma-separated chip numbers to process (default: all found)")
    ap.add_argument("--figs-dir", type=Path, default=Path("figs"), help="Base directory for figure output")
    ap.add_argument("--no-gifs", action="store_true", help="Disable IVg GIF rendering")
    ap.add_argument("--no-overlays", action="store_true", help="Disable ITS wavelength overlays")
    ap.add_argument("--dry-run", action="store_true", help="List actions without rendering")
    ap.add_argument("--workers", type=int, default=1, help="Parallel processes across chips (>=2 enables parallelism)")

    ap.add_argument("--log", type=str, default="INFO", help="Logging level: DEBUG/INFO/WARNING/ERROR")

    args = ap.parse_args()
    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO), format="%(levelname)s | %(name)s | %(message)s")

    chips_list: Optional[List[int]] = None
    if args.chips.strip():
        chips_list = [norm_chip(x) for x in args.chips.split(",") if x.strip()]

    process_day_experiments(
        metadata_csv=str(args.metadata_csv),
        base_dir=args.base_dir,
        chips_to_process=chips_list,
        generate_gifs=not args.no_gifs,
        generate_wavelength_overlays=not args.no_overlays,
        base_figs_dir=args.figs_dir,
        dry_run=args.dry_run,
        workers=max(1, int(args.workers)),
    )


if __name__ == "__main__":
    main()
