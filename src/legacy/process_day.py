# file: src/process_day.py
#!/usr/bin/env python3
"""
process_day.py

Generates the SAME figures as the original process_day but organized into
per-chip/day subfolders, AND adds chip-level ITS overlays that IGNORE VG,
grouped by wavelength buckets:
  - uv_blue (λ ≤ 455 nm)
  - green (505–565 nm)
  - red_orange (λ ≥ 590 nm)
  - all_wavelengths (all available λ)
Overlays go to: figs/ChipXX_YYYY_MM_DD/ITS/overlays/
"""

from __future__ import annotations

from pathlib import Path
import re
import logging
from typing import Iterable, List, Optional
import polars as pl
from src.core.timeline import print_day_timeline
from src.plotting.styles import set_plot_style
import scienceplots
set_plot_style('prism_rain')

# Your plotting utilities
from src.plotting.plots import (
    load_and_prepare_metadata,
    plot_ivg_sequence,
    plot_its_by_vg,
    plot_its_by_vg_delta,
    plot_its_wavelength_overlay_delta_for_chip,
    ivg_sequence_gif,
)

try:
    from src.plotting.plots import print_day_timeline  # optional
except Exception:
    print_day_timeline = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
log = logging.getLogger("process_day")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

METADATA_CSV: str = "Alisson_15_sept_metadata.csv"
BASE_DIR: Path = Path("raw_data")
CHIPS_TO_PROCESS: Optional[List[float]] = None
GENERATE_GIFS: bool = True
GENERATE_WAVELENGTH_OVERLAYS: bool = True  # includes grouped overlays below




# ─────────────────────────────────────────────────────────────────────────────
# Helpers
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
    chip_dir = Path("figs") / f"Chip{chip_num:02d}_{date_str}"
    for sub in [
        "IVg/sequence",
        "IVg/pairs",
        "IVg/triplets",
        "IVg/gif",
        "ITS/regular",
        "ITS/delta",
        "ITS/overlays",
    ]:
        (chip_dir / sub).mkdir(parents=True, exist_ok=True)
    return chip_dir

def find_consecutive_groups(numbers: Iterable[int]) -> List[List[int]]:
    uniq = sorted(set(int(n) for n in numbers))
    if not uniq:
        return []
    groups: List[List[int]] = []
    cur = [uniq[0]]
    for i in range(1, len(uniq)):
        if uniq[i] == uniq[i - 1] + 1:
            cur.append(uniq[i])
        else:
            if len(cur) > 1:
                groups.append(cur)
            cur = [uniq[i]]
    if len(cur) > 1:
        groups.append(cur)
    return groups

def _set_plots_fig_dir(tmp_dir: Path) -> None:
    # WHY: redirect plots output to our structured folders
    try:
        import src.plotting.plots as plots
        if hasattr(plots, "FIG_DIR"):
            plots.FIG_DIR = tmp_dir
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# IVg
# ─────────────────────────────────────────────────────────────────────────────

def process_chip_ivg(meta: pl.DataFrame, base_dir: Path, tag: str, output_dir: Path, generate_gifs: bool) -> None:
    import src.plotting.plots as plots

    ivg_data = meta.filter(pl.col("proc") == "IVg")
    if ivg_data.height == 0:
        log.info("No IVg data found for this chip.")
        return

    seq_dir = output_dir / "IVg" / "sequence"
    pairs_dir = output_dir / "IVg" / "pairs"
    trips_dir = output_dir / "IVg" / "triplets"
    gif_dir = output_dir / "IVg" / "gif"

    original_fig_dir = getattr(plots, "FIG_DIR", None)
    try:
        _set_plots_fig_dir(seq_dir)
        plot_ivg_sequence(ivg_data, base_dir, tag)

        file_indices = []
        if "file_idx" in ivg_data.columns:
            file_indices = sorted(set(ivg_data.get_column("file_idx").drop_nulls().to_list()))

        if len(file_indices) >= 2:
            _set_plots_fig_dir(pairs_dir)
            for i in range(len(file_indices) - 1):
                pair = (file_indices[i], file_indices[i + 1])
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(pair))
                plot_ivg_sequence(meta_subset, base_dir, f"{tag}_pair_{pair[0]}_{pair[1]}")

        if len(file_indices) >= 3:
            _set_plots_fig_dir(trips_dir)
            for i in range(len(file_indices) - 2):
                triplet = (file_indices[i], file_indices[i + 1], file_indices[i + 2])
                meta_subset = ivg_data.filter(pl.col("file_idx").is_in(triplet))
                plot_ivg_sequence(meta_subset, base_dir, f"{tag}_triplet_{triplet[0]}_{triplet[-1]}")

        if generate_gifs:
            _set_plots_fig_dir(gif_dir)
            try:
                ivg_sequence_gif(ivg_data, base_dir, tag, fps=2, cumulative=True)
            except Exception as e:
                log.warning(f"IVg GIF generation failed: {e}")
    finally:
        if original_fig_dir is not None:
            try:
                plots.FIG_DIR = original_fig_dir
            except Exception:
                pass

# ─────────────────────────────────────────────────────────────────────────────
# ITS (regular/delta) + explicit overlays (VG-windowed as requested)
# ─────────────────────────────────────────────────────────────────────────────

def process_chip_its(
    meta: pl.DataFrame, base_dir: Path, tag: str, output_dir: Path, chip_num: int, generate_wavelength_overlays: bool
) -> None:
    import src.plotting.plots as plots
    its_data = meta.filter(pl.col("proc") == "ITS")
    if its_data.height == 0:
        log.info("No ITS data found for this chip.")
        return

    reg_dir = output_dir / "ITS" / "regular"
    delta_dir = output_dir / "ITS" / "delta"
    overlay_dir = output_dir / "ITS" / "overlays"

    original_fig_dir = getattr(plots, "FIG_DIR", None)
    try:
        # Regular & delta (kept)
        _set_plots_fig_dir(reg_dir)
        vgs = its_data["VG_meta"].drop_nulls().unique().to_list() if "VG_meta" in its_data.columns else []
        wls_present = (
            sorted(float(w) for w in its_data["Laser wavelength"].drop_nulls().unique().to_list())
            if "Laser wavelength" in its_data.columns else []
        )
        for vg in (sorted(vgs) if vgs else [None]):
            for wl in (wls_present if wls_present else [None]):
                try:
                    plot_its_by_vg(meta, base_dir, tag, vgs=[vg] if vg is not None else None, wavelengths=[wl] if wl is not None else None)
                except Exception as e:
                    log.warning(f"ITS regular plot failed (VG={vg}, WL={wl}): {e}")

        _set_plots_fig_dir(delta_dir)
        for vg in (sorted(vgs) if vgs else [None]):
            for wl in (wls_present if wls_present else [None]):
                try:
                    plot_its_by_vg_delta(meta, base_dir, tag, vgs=[vg] if vg is not None else None, wavelengths=[wl] if wl is not None else None, baseline_t=60.0, clip_t_min=20.0)
                except Exception as e:
                    log.warning(f"ITS delta plot failed (VG={vg}, WL={wl}): {e}")

        # ── Explicit overlays with UNIQUE filenames (prevents overwrite) ──
        if generate_wavelength_overlays:
            _set_plots_fig_dir(overlay_dir)
            vg_center, vg_window = -5.0, 1.5
            baseline_t, clip_t_min = 60.0, 40.0

            # a) ALL wavelengths
            try:
                log.info(f"[overlays] chip {chip_num:02d} — all wavelengths {wls_present}")
                plot_its_wavelength_overlay_delta_for_chip(
                    meta, BASE_DIR, tag,
                    chip=int(chip_num),
                    vg_center=vg_center, vg_window=vg_window,  # respect VG window
                    wavelengths=None,                           # ALL present
                    baseline_t=baseline_t, clip_t_min=clip_t_min,
                    # ↓↓↓ give each overlay a unique name/title
                    title_suffix=" (all wavelengths)", filename_suffix="_all",
                )
            except Exception as e:
                log.warning(f"Overlay (all wavelengths) failed: {e}")

            # b) UV/blue group
            uv_blue_wish = [365.0, 385.0, 405.0, 455.0]
            uv_blue = [w for w in uv_blue_wish if w in wls_present]
            if len(uv_blue) >= 2:
                try:
                    log.info(f"[overlays] chip {chip_num:02d} — uv/blue {uv_blue}")
                    plot_its_wavelength_overlay_delta_for_chip(
                        meta, BASE_DIR, tag,
                        chip=int(chip_num),
                        vg_center=vg_center, vg_window=vg_window,
                        wavelengths=uv_blue,
                        baseline_t=baseline_t, clip_t_min=clip_t_min,
                        title_suffix=" (uv-blue)", filename_suffix="_uvblue",
                    )
                except Exception as e:
                    log.warning(f"Overlay (uv_blue) failed: {e}")
            else:
                log.info(f"[overlays] uv/blue insufficient for chip {chip_num:02d}: {uv_blue}")

            # c) Longer wavelengths group
            longer_wish = [505.0, 565.0, 590.0, 625.0, 680.0, 850.0]
            longer = [w for w in longer_wish if w in wls_present]
            if len(longer) >= 2:
                try:
                    log.info(f"[overlays] chip {chip_num:02d} — longer {longer}")
                    plot_its_wavelength_overlay_delta_for_chip(
                        meta, BASE_DIR, tag,
                        chip=int(chip_num),
                        vg_center=vg_center, vg_window=vg_window,
                        wavelengths=longer,
                        baseline_t=baseline_t, clip_t_min=clip_t_min,
                        title_suffix=" (longer)", filename_suffix="_long",
                    )
                except Exception as e:
                    log.warning(f"Overlay (longer) failed: {e}")
            else:
                log.info(f"[overlays] longer insufficient for chip {chip_num:02d}: {longer}")

    finally:
        if original_fig_dir is not None:
            try:
                plots.FIG_DIR = original_fig_dir
            except Exception:
                pass

def process_single_chip(metadata_csv: str, chip_num: float, base_dir: Path = Path("."), generate_gifs: bool = True, generate_wavelength_overlays: bool = True) -> None:
    chip_i = int(chip_num)
    log.info(f"\n{'='*64}\nPROCESSING CHIP {chip_i:02d}\n{'='*64}")
    out_dir = setup_chip_output_dir(chip_i, metadata_csv)
    meta = load_and_prepare_metadata(metadata_csv, chip_num)
    if meta.height == 0:
        log.info(f"No data found for chip {chip_num}, skipping."); return
    tag = Path(metadata_csv).stem
    #a=print_day_timeline(metadata_csv, base_dir, save_csv=False)
    procs = set(meta.get_column("proc").to_list())
    if "IVg" in procs:
        process_chip_its(meta, base_dir, tag, out_dir, chip_num=chip_i, generate_wavelength_overlays=generate_wavelength_overlays)  # ensure ITS runs first if order matters
        process_chip_ivg(meta, base_dir, tag, out_dir, generate_gifs=generate_gifs)
    else:
        process_chip_its(meta, base_dir, tag, out_dir, chip_num=chip_i, generate_wavelength_overlays=generate_wavelength_overlays)

def _infer_chips_from_metadata(metadata_csv: str) -> List[float]:
    try:
        df = pl.read_csv(metadata_csv, infer_schema_length=1000)
    except Exception as e:
        raise RuntimeError(f"Failed to read metadata CSV '{metadata_csv}': {e}")
    candidates = ["Chip number", "chip", "Chip", "CHIP", "Chip_number", "chip_number"]
    chip_col = next((c for c in candidates if c in df.columns), None)
    if chip_col is None:
        raise RuntimeError(f"Could not find a chip column in {metadata_csv}. Tried: {', '.join(candidates)}. Columns: {list(df.columns)}")
    chips_series = df.get_column(chip_col).drop_nulls()
    try:
        chips = sorted({float(x) for x in chips_series.to_list()})
    except Exception:
        chips = sorted({float(str(x).strip()) for x in chips_series.to_list() if str(x).strip()})
    return chips

def process_day_experiments(metadata_csv: str, base_dir: Path = Path("."), chips_to_process: Optional[List[float]] = None, generate_gifs: bool = True, generate_wavelength_overlays: bool = True) -> None:
    chips = chips_to_process or _infer_chips_from_metadata(metadata_csv)
    if not chips:
        log.warning("No chips found to process."); return
    log.info(f"Chips to process: {chips}")
    for chip in chips:
        try:
            process_single_chip(metadata_csv, chip, base_dir=base_dir, generate_gifs=generate_gifs, generate_wavelength_overlays=generate_wavelength_overlays)
        except Exception as e:
            log.error(f"Chip {chip}: processing failed: {e}")

if __name__ == "__main__":
    process_day_experiments(METADATA_CSV, BASE_DIR, chips_to_process=CHIPS_TO_PROCESS, generate_gifs=GENERATE_GIFS, generate_wavelength_overlays=GENERATE_WAVELENGTH_OVERLAYS)