#!/usr/bin/env python3
"""
process_day.py

Automated processing script for a full day's experimental data.
Generates chip-specific plots organized in folders: figs/ChipXX_YYYY_MM_DD/
"""

# ─────────────────────────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────────────────────────

# --- Standard Library ---
from pathlib import Path
import re
import logging

# --- Third-Party ---
import numpy as np
import polars as pl

# --- Local Modules ---
from src.plotting.plots import (
    load_and_prepare_metadata, plot_ivg_sequence, plot_its_by_vg,
    plot_its_by_vg_delta, plot_its_wavelength_overlay_delta_for_chip,
    ivg_sequence_gif
)
from src.core.timeline import print_day_timeline
from src.plotting.styles import set_plot_style
import scienceplots
set_plot_style('prism_rain')


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

METADATA_CSV = "Alisson_15_sept_metadata.csv"
BASE_DIR = Path("raw_data/")
CHIPS_TO_PROCESS = [68.0]  # Set to None to process all available chips
GENERATE_GIFS = True

# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────

def extract_date_from_filename(filename: str) -> str:
    match = re.search(r'(\d+)_([a-zA-Z]+)', filename)
    if match:
        day, month = match.groups()
        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'sept': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month_num = month_map.get(month.lower())
        if month_num:
            return f"2024_{month_num}_{day.zfill(2)}"
    return "unknown_date"

def setup_chip_output_dir(chip_num: int, metadata_csv: str) -> Path:
    date_str = extract_date_from_filename(metadata_csv)
    chip_dir = Path("figs") / f"Chip{int(chip_num):02d}_{date_str}"
    chip_dir.mkdir(parents=True, exist_ok=True)
    return chip_dir

def find_consecutive_groups(numbers: list) -> list:
    if not numbers:
        return []
    numbers = sorted(set(numbers))
    groups, current_group = [], [numbers[0]]
    for i in range(1, len(numbers)):
        if numbers[i] == numbers[i-1] + 1:
            current_group.append(numbers[i])
        else:
            if len(current_group) > 1:
                groups.append(current_group)
            current_group = [numbers[i]]
    if len(current_group) > 1:
        groups.append(current_group)
    return groups

# ─────────────────────────────────────────────────────────────────────────────
# Plotting Logic
# ─────────────────────────────────────────────────────────────────────────────

def process_chip_ivg(meta: pl.DataFrame, base_dir: Path, tag: str, output_dir: Path, chip_num: int):
    import src.plotting.plots as plots
    log.info(f"\n--- Processing IVg for Chip {int(chip_num)} ---")
    original_fig_dir = plots.FIG_DIR

    # Create subdirectories
    ivg_dir = output_dir / "IVg"
    full_seq_dir = ivg_dir / "full_sequence"
    pair_dir = ivg_dir / "pairs"
    consec_dir = ivg_dir / "consecutive"
    triplet_dir = ivg_dir / "triplets"
    gif_dir = ivg_dir / "gifs"
    for d in [full_seq_dir, pair_dir, consec_dir, triplet_dir, gif_dir]:
        d.mkdir(parents=True, exist_ok=True)

    plots.FIG_DIR = full_seq_dir

    try:
        plot_ivg_sequence(meta, base_dir, tag)
        ivg_data = meta.filter(pl.col("proc") == "IVg").sort("file_idx")
        if ivg_data.height > 1:
            file_indices = ivg_data.get_column("file_idx").to_list()
            for group in find_consecutive_groups(file_indices):
                if len(group) >= 2:
                    log.info(f"  Plotting IVg consecutive group: {group}")
                    meta_subset = ivg_data.filter(pl.col("file_idx").is_in(group))
                    plots.FIG_DIR = consec_dir
                    plot_ivg_sequence(meta_subset, base_dir, f"{tag}_consec_{group[0]}to{group[-1]}")
            for i in range(len(file_indices) - 1):
                pair = (file_indices[i], file_indices[i+1])
                log.info(f"  Plotting IVg pair: {pair}")
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(pair))
                plots.FIG_DIR = pair_dir
                plot_ivg_sequence(meta_subset, base_dir, f"{tag}_pair_{pair[0]}_{pair[1]}")
            for i in range(len(file_indices) - 2):
                triplet = (file_indices[i], file_indices[i+1], file_indices[i+2])
                log.info(f"  Plotting IVg triplet: {triplet}")
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(triplet))
                plots.FIG_DIR = triplet_dir
                plot_ivg_sequence(meta_subset, base_dir, f"{tag}_triplet_{triplet[0]}_{triplet[-1]}")
        try:
            log.info("  Generating IVg sequence GIF...")
            plots.FIG_DIR = gif_dir
            ivg_sequence_gif(meta, base_dir, tag, fps=2, cumulative=True)
        except Exception as e:
            log.warning(f"  Warning: GIF generation failed: {e}")
    finally:
        plots.FIG_DIR = original_fig_dir


def process_chip_its(meta: pl.DataFrame, base_dir: Path, tag: str, output_dir: Path, chip_num: int):
    import src.plotting.plots as plots
    log.info(f"\n--- Processing ITS for Chip {int(chip_num)} ---")
    original_fig_dir = plots.FIG_DIR

    its_dir = output_dir / "ITS"
    overlay_dir = its_dir / "overlays"
    its_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    plots.FIG_DIR = its_dir

    try:
        its_data = meta.filter(pl.col("proc") == "ITS")
        if its_data.height == 0:
            log.info("  No ITS data found")
            return

        vgs = sorted([float(x) for x in its_data.get_column("VG_meta").drop_nulls().unique().to_list()]) if "VG_meta" in its_data.columns else []
        wavelengths = sorted([float(x) for x in its_data.get_column("Laser wavelength").drop_nulls().unique().to_list()]) if "Laser wavelength" in its_data.columns else []

        log.info(f"  Found VG values: {vgs}")
        log.info(f"  Found wavelengths: {wavelengths}")

        for vg in vgs:
            vg_dir = its_dir / f"vg_{vg:.1f}V"
            vg_dir.mkdir(parents=True, exist_ok=True)
            plots.FIG_DIR = vg_dir
            for wl in wavelengths:
                log.info(f"  Plotting ITS: Vg={vg}V, λ={wl}nm (regular)")
                plot_its_by_vg(meta, base_dir, tag, vgs=[vg], wavelengths=[wl])
                log.info(f"  Plotting ITS: Vg={vg}V, λ={wl}nm (delta)")
                plot_its_by_vg_delta(meta, base_dir, tag, vgs=[vg], wavelengths=[wl], baseline_t=60.0, clip_t_min=20.0)

        log.info("  Generating wavelength overlay plots...")
        for vg in vgs:
            plots.FIG_DIR = overlay_dir
            plot_its_wavelength_overlay_delta_for_chip(meta, base_dir, f"{tag}_all_wavelengths", chip=chip_num, vg_center=vg, vg_window=1.5, wavelengths=None, baseline_t=60.0, clip_t_min=40.0)
            if len(wavelengths) > 4:
                uv_blue = [wl for wl in wavelengths if wl <= 455.0]
                if len(uv_blue) > 1:
                    plot_its_wavelength_overlay_delta_for_chip(meta, base_dir, f"{tag}_UV_blue", chip=chip_num, vg_center=vg, vg_window=1.5, wavelengths=uv_blue, baseline_t=60.0, clip_t_min=40.0)
                green_red = [wl for wl in wavelengths if wl > 455.0]
                if len(green_red) > 1:
                    plot_its_wavelength_overlay_delta_for_chip(meta, base_dir, f"{tag}_green_red", chip=chip_num, vg_center=vg, vg_window=1.5, wavelengths=green_red, baseline_t=60.0, clip_t_min=40.0)
    finally:
        plots.FIG_DIR = original_fig_dir


# ─────────────────────────────────────────────────────────────────────────────
# Chip Processing Logic
# ─────────────────────────────────────────────────────────────────────────────

def process_single_chip(metadata_csv: str, chip_num: float, base_dir: Path = Path("."), generate_gifs: bool = True):
    log.info(f"\n{'='*60}\nPROCESSING CHIP {int(chip_num)}\n{'='*60}")
    output_dir = setup_chip_output_dir(int(chip_num), metadata_csv)
    log.info(f"Output directory: {output_dir}")

    meta = load_and_prepare_metadata(metadata_csv, chip_num)
    if meta.height == 0:
        log.info(f"No data found for chip {chip_num}")
        return

    tag = Path(metadata_csv).stem
    procs = set(meta.get_column("proc").to_list())
    log.info(f"Available procedures: {procs}")
    log.info(f"Total measurements: {meta.height}")

    log.info(f"\nChip {int(chip_num)} Timeline:")
    timeline_full = print_day_timeline(metadata_csv, base_dir, save_csv=False)
    if "chip" in timeline_full.columns:
        chip_timeline = timeline_full.filter(pl.col("chip") == chip_num)
        for row in chip_timeline.iter_rows(named=True):
            log.info(f"  {row['seq']:>3d}  {row['time_hms']:>8}  {row['summary']}")

    if "IVg" in procs:
        process_chip_ivg(meta, base_dir, tag, output_dir, chip_num)

    if "ITS" in procs:
        process_chip_its(meta, base_dir, tag, output_dir, chip_num)

    log.info(f"\nCompleted processing Chip {int(chip_num)}")
    log.info(f"All plots saved to: {output_dir.absolute()}")


def process_day_experiments(metadata_csv: str, base_dir: Path = Path("."), chips_to_process: list = None, generate_gifs: bool = True):
    log.info(f"Processing day experiments from: {metadata_csv}")
    log.info(f"Base directory: {base_dir}")

    log.info(f"\n{'='*60}\nFULL DAY TIMELINE\n{'='*60}")
    timeline = print_day_timeline(metadata_csv, base_dir)

    full_meta = pl.read_csv(metadata_csv, infer_schema_length=1000)
    available_chips = sorted([float(x) for x in full_meta.get_column("Chip number").unique().to_list() if x is not None])
    if chips_to_process is None:
        chips_to_process = available_chips

    log.info(f"\nAvailable chips: {available_chips}")
    log.info(f"Processing chips: {chips_to_process}")

    for chip_num in chips_to_process:
        if chip_num not in available_chips:
            log.warning(f"\nWarning: Chip {chip_num} not found in data, skipping...")
            continue
        process_single_chip(metadata_csv, chip_num, base_dir, generate_gifs)

    log.info(f"\n{'='*60}\nALL CHIPS PROCESSING COMPLETE\n{'='*60}")
    log.info("Output structure:")
    for chip_num in chips_to_process:
        if chip_num in available_chips:
            output_dir = setup_chip_output_dir(int(chip_num), metadata_csv)
            log.info(f"  Chip {int(chip_num):02d}: {output_dir}")

# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    process_day_experiments(
        METADATA_CSV,
        BASE_DIR,
        chips_to_process=CHIPS_TO_PROCESS,
        generate_gifs=GENERATE_GIFS
    )
